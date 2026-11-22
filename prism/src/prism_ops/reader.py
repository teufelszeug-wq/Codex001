"""Read-only private operational archive. Bind loopback unless explicitly proxied."""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlsplit, urlencode


def archive(data, query=''):
    data = Path(data).resolve()
    db = sqlite3.connect('file:' + str(data / 'operations.sqlite') + '?mode=ro', uri=True)
    try:
        jobs = db.execute('SELECT race_id,status,detail,updated_at FROM jobs WHERE race_id LIKE ? ORDER BY race_id',
                          ('%' + query + '%',)).fetchall()
        artifacts = db.execute('SELECT race_id,kind,key,path FROM artifacts WHERE race_id LIKE ? '
                               'AND kind IN (\'publication\',\'bundle\',\'settlement\',\'review\') ORDER BY persisted_at,race_id,kind,key',
                               ('%' + query + '%',)).fetchall()
    finally:
        db.close()
    rows = ''.join('<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in row) + '</tr>' for row in jobs)
    links, papers, latest_settlements, authors = [], [], {}, {}
    for race, kind, key, path in artifacts:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        target = '/artifact?' + urlencode({'path': str(Path(path).relative_to(data))})
        links.append('<li>' + escape(race + ' / ' + kind + ' / ' + key) +
                     ' <a href="' + escape(target, quote=True) + '">JSON</a></li>')
        if kind == 'bundle':
            for author in payload.get('characters', []):
                authors[author['agent_id']] = ('本紙（編集部）' if author.get('role') == 'editor'
                                               else author.get('name', author['agent_id']))
        if kind == 'publication':
            paper = payload.get('paper', {})
            pdf = paper.get('pdf', {}).get('path')
            if pdf:
                relative = Path(pdf).resolve().relative_to(data)
                target = '/paper?' + urlencode({'path': str(relative)})
                papers.append('<li>' + escape(race + ' / ' + key) + ' <a href="' +
                              escape(target, quote=True) + '">PDFを開く</a>（' +
                              escape(str(paper.get('qa', {}).get('pages', '?'))) + 'ページ）</li>')
        if kind == 'settlement' and payload.get('official_settlements') == 1:
            # Keep corrected payouts and different editions distinct; never sum
            # a superseded settlement twice or count a synthetic fixture.
            latest_settlements[(race, payload['edition'])] = payload
    performance = []
    for (race, edition), settlement in sorted(latest_settlements.items()):
        for result in settlement['summary']:
            values = (race, edition, authors.get(result['forecaster_id'], result['forecaster_id']),
                      result['stake_yen'], result['payout_yen'], result['profit_yen'])
            performance.append('<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in values) + '</tr>')
    return ('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>PRISM Reader</title><style>body{font-family:sans-serif;margin:2rem}td,th{padding:.6rem;border:1px solid #aaa}'
            'table{border-collapse:collapse;width:100%}main{overflow:auto}a{color:#124d81}</style>'
            '<h1>PRISM Reader</h1><p>予想・発行・精算の保存記録。未実行は成功件数に含めません。</p>'
            '<form><label>レースID検索 <input name="q" value="' + escape(query, quote=True) + '"></label><button>検索</button></form>'
            '<main><table><tr><th>レース</th><th>状態</th><th>記録</th><th>更新時刻</th></tr>' + rows +
            '</table></main><h2>発行済み新聞</h2><ul>' + ''.join(papers) + '</ul>'
            '<h2>AI別成績（公式精算・版別）</h2><main><table><tr><th>レース</th><th>版</th><th>担当</th>'
            '<th>仮想購入円</th><th>払戻円</th><th>収支円</th></tr>' + ''.join(performance) +
            '</table></main><h2>版別アーカイブ</h2><ul>' + ''.join(links) + '</ul></html>')


def paper_asset(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if (root not in path.parents or 'papers' not in path.relative_to(root).parts or
            path.suffix.lower() not in {'.pdf', '.png'}):
        raise ValueError('invalid paper asset')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args(argv)
    root = Path(args.data).resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            params = parse_qs(url.query)
            try:
                if url.path == '/':
                    body = archive(root, params.get('q', [''])[0]).encode()
                    content_type = 'text/html; charset=utf-8'
                elif url.path == '/artifact':
                    path = (root / params.get('path', [''])[0]).resolve()
                    if root not in path.parents or path.suffix != '.json' or 'artifacts' not in path.relative_to(root).parts:
                        raise ValueError('invalid artifact')
                    body = path.read_bytes()
                    content_type = 'application/json; charset=utf-8'
                elif url.path == '/paper':
                    path = paper_asset(root, params.get('path', [''])[0])
                    body = path.read_bytes()
                    content_type = 'application/pdf' if path.suffix.lower() == '.pdf' else 'image/png'
                else:
                    self.send_error(404); return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
                self.send_header('Content-Length', str(len(body)))
                self.end_headers(); self.wfile.write(body)
            except (OSError, ValueError):
                self.send_error(404)

    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
