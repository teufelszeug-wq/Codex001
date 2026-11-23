"""Paginated vertical operational newspaper, PDF and PDF-derived PNG evidence.

The research renderer is intentionally separate. Mechanical layout checks are
EXECUTED evidence; only an explicit review of every rendered page may promote
the paper's visual QA to VERIFIED. Hashes detect changes, not external truth.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re
import struct

from prism_engine.contracts import digest, timestamp


def _now():
    return datetime.now(timezone.utc).isoformat()


def _file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _seal(manifest):
    manifest['qa']['qa_hash'] = digest({k: v for k, v in manifest['qa'].items() if k != 'qa_hash'})
    manifest['manifest_hash'] = digest({k: v for k, v in manifest.items() if k != 'manifest_hash'})
    return manifest


def _text(value):
    if value is None:
        return '未確定'
    return str(value)


def _blocks(bundle):
    """Return complete editorial blocks. No record or text is excerpted."""
    if not isinstance(bundle, dict) or not isinstance(bundle.get('race'), dict):
        raise ValueError('operational race bundle required')
    race = bundle['race']
    runners = race.get('runners')
    if not race.get('race_id') or not isinstance(runners, list) or not runners:
        raise ValueError('race identity and full field required')
    ids = [r.get('horse_id') for r in runners]
    if None in ids or len(set(ids)) != len(ids):
        raise ValueError('unambiguous horse identity required')
    all_runners = [*runners, *race.get('scratched_runners', [])]
    names = {r['horse_id']: r.get('name', r.get('horse_name', r['horse_id'])) for r in all_runners}
    by_id = {r['horse_id']: r for r in all_runners}
    authors = bundle.get('characters', {})
    if isinstance(authors, list):
        authors = {r['agent_id']: r for r in authors}

    def author_name(agent, *, forecast=False):
        record = authors.get(agent, {})
        # The editor's canonical source identity remains unchanged. Only the
        # forecast byline is the paper's editorial desk; discussions retain
        # Ritsu's actual moderator name and do not invent another character.
        if forecast and isinstance(record, dict) and record.get('role') == 'editor':
            return '本紙（編集部）'
        if agent == 'SHINOMIYA_RITSU':
            return '篠宮律'
        if agent == 'RIO':
            return 'りお'
        return record.get('name', agent) if isinstance(record, dict) else str(record)

    def horse(horse_id):
        row = by_id.get(horse_id, {})
        return '馬番' + _text(row.get('horse_no')) + '・' + str(names.get(horse_id, horse_id))

    mode = bundle.get('mode', bundle.get('execution_mode', 'UNVERIFIED'))
    day_correction = bundle.get('edition_kind') == 'DAY_CORRECTION'
    labels = {'SYNTHETIC': '人工入力・機能検証用。実レースの予想実績ではありません。',
              'single_model_simulation': '単一モデルの役割シミュレーション。独立ＡＩ予想ではありません。',
              'PRE_AVAILABLE': '発走前の発行候補。正式な前日発行は発行判定記録を参照。発行後の変更は別版に保存します。'}
    label = labels.get(mode, '各予想の実行区分は保存記録を参照。未検証事項は確定扱いしません。')
    if day_correction:
        label = ('人工入力・当日差分の機能検証用。実レースの予想実績ではありません。' if mode == 'SYNTHETIC'
                 else '当日差分版。前日版の予想・新聞は保持しています。')
    blocks = [('発行区分', label),
              ('開催・発走', str(race.get('race_name', race['race_id'])) + '　' + str(race.get('authority', '')) + '\n発走 ' + str(race.get('start_at', race.get('off_at', '未確認')))),
              ('編集部', '編集長・座談会司会　篠宮律\n新人記者　りお\n前日予想を保持し、当日は差分を記録します。')]
    if day_correction:
        changes = bundle.get('changes', {})
        field_labels = {'body_weight': '馬体重', 'body_weight_change': '馬体重増減', 'odds': 'オッズ',
                        'going': '馬場状態', 'weather': '天候', 'track_bias': 'トラックバイアス',
                        'scratches': '取消', 'rider_change': '騎手変更', 'off_at': '発走時刻'}
        details = ['変更理由　' + str(bundle.get('change_reason', '未記録'))]
        for field, value in changes.items():
            if isinstance(value, dict) and set(value) <= set(names):
                rendered = '・'.join(str(names[key]) + ' ' + _text(item) for key, item in value.items())
            elif field == 'scratches' and isinstance(value, list):
                rendered = '・'.join(str(names.get(item, item)) for item in value)
            else:
                rendered = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else _text(value)
            details.append(field_labels.get(field, field) + '　' + rendered)
        source = bundle.get('day_delta', {}).get('source', {})
        if source.get('official_url'):
            details.append('変更出典　' + source['official_url'])
        blocks.append(('当日差分', '\n'.join(details)))
        blocks.append(('保持した前日版', '版　' + str(bundle.get('base_edition', '未記録')) + '\n参照ハッシュ　' + str(bundle.get('base_bundle_hash', '未記録'))))
    card_lines = []
    for r in runners:
        detail = '枠番' + _text(r.get('frame_no')) + '　馬番' + _text(r.get('horse_no')) + '　' + str(names[r['horse_id']])
        for key, label in [('jockey_name', '騎手'), ('carried_weight', '斤量'), ('status', '出走状況')]:
            if key in r:
                detail += '\n' + label + '　' + _text(r[key])
        card_lines.append(detail)
    blocks.append(('全頭馬柱', '\n'.join(card_lines)))
    if race.get('scratched_runners'):
        blocks.append(('公式取消', '\n'.join(horse(r['horse_id']) + '　取消' for r in race['scratched_runners'])))
    core = bundle.get('core_prediction', {})
    if core.get('win'):
        lines = ['固定係数の実験エンジン。性能検証済みの確率とは区別します。']
        for horse_id, probability in sorted(core['win'].items(), key=lambda item: (-item[1], item[0])):
            lines.append(horse(horse_id) + '　勝率 ' + format(probability * 100, '.2f') + '％')
        blocks.append(('定量予測', '\n'.join(lines)))

    for stage, heading in [('preliminary', '一次予想'), ('final', '最終予想')]:
        if day_correction:
            heading = '前日一次予想' if stage == 'preliminary' else '当日差分最終予想'
        records = bundle.get(stage, {})
        if not isinstance(records, dict):
            raise ValueError(stage + ' must be an author mapping')
        for agent, record in records.items():
            title = heading + '　' + author_name(agent, forecast=True)
            details = '保存 ' + _text(record.get('saved_at')) + '\n実行区分 ' + _text(record.get('mode', record.get('execution_mode')))
            if record.get('change_reason'):
                details += '\n変更理由 ' + str(record['change_reason'])
            if record.get('summary'):
                details += '\n' + str(record['summary'])
            lines = [details, '全頭診断']
            for d in record.get('diagnoses', []):
                detail = horse(d.get('horse_id')) + '　' + str(d.get('reason', '根拠未記録'))
                if d.get('win_probability') is not None:
                    detail += '　勝率 ' + str(d['win_probability'])
                lines.append(detail)
            for p in record.get('picks', []):
                if not isinstance(p, dict):
                    raise ValueError('named structured picks required')
                lines.append('印 ' + str(p.get('mark', '印未記録')) + '　' + horse(p.get('horse_id')) + '　' + str(p.get('reason', '理由未記録')))
            tickets = record.get('tickets', [])
            for t in tickets:
                number_field = 'frame_nos' if t.get('type') in ('FRAME', 'FRAME_QUINELLA') else 'horse_nos'
                numbers = t.get(number_field, t.get('horse_nos', []))
                lines.append('買い目 ' + str(t.get('type', '券種未記録')) + '　' + '・'.join(map(str, numbers)) + '　' + str(t.get('stake_yen', '金額未記録')) + '円')
            if tickets:
                lines.append('合計 ' + str(sum(t.get('stake_yen', 0) for t in tickets)) + '円')
            if not tickets:
                lines.append('見送り ' + str(record.get('skip_reason', '買い目・見送り理由未記録')))
            blocks.append((title, '\n'.join(lines)))

        # The saved discussion belongs between INITIAL and FINAL, including all
        # turns and all topics. It is never synthesized by the renderer.
        if stage == 'preliminary':
            discussions = bundle.get('discussions', [])
            if not discussions:
                blocks.append(('座談会', '保存された座談会はありません。'))
            for topic in discussions:
                topic_title = ('前日座談会　' if day_correction else '座談会　') + str(topic.get('title', topic.get('topic_id', '議題未記録')))
                lines = ['司会 ' + author_name(topic.get('moderator_id', topic.get('facilitator', '未記録'))) + '\n開始 ' + _text(topic.get('started_at')) + '\n完了 ' + _text(topic.get('completed_at'))]
                for turn in topic.get('turns', []):
                    text = str(turn.get('text', ''))
                    if turn.get('evidence_refs'):
                        text += '\n根拠 ' + '・'.join(map(str, turn['evidence_refs']))
                    lines.append(author_name(turn.get('forecaster_id', turn.get('agent_id', '未記録'))) + '　' + text)
                blocks.append((topic_title, '\n'.join(lines)))
    if bundle.get('source_refs'):
        blocks.append(('参照資料', '\n'.join(map(str, bundle['source_refs']))))
    return blocks


def render_operational_html(bundle, *, version='pre-v1'):
    """Return escaped, complete, browser-paginated A3 portrait HTML."""
    blocks = _blocks(bundle)
    # Bounded chunks prevent a single long comment from exceeding a sheet.
    # Concatenating all chunks exactly reconstructs every original paragraph.
    chunks = []
    for title, text in blocks:
        chunks.extend({'title': title + ('（続き）' if pos else ''), 'text': text[pos:pos + 320]}
                      for pos in range(0, max(len(text), 1), 320))
    payload = json.dumps(chunks, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    title = str(bundle['race'].get('race_name', bundle['race']['race_id']))
    return '<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>M-PAPER ' + escape(title) + '</title><style>' + _STYLE + '</style></head><body data-version="' + escape(version, quote=True) + '"><script id="paper-data" type="application/json">' + payload + '</script><script>' + _PAGINATE + '</script></body></html>'


def render_operational_paper(bundle, out_dir, version='pre-v1'):
    """Create HTML, PDF and every PDF page as PNG in a new immutable directory.

    Requires Playwright, Chromium and PyMuPDF. No network is used.
    Returned QA stays EXECUTED until every PNG has been visually reviewed.
    """
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', version):
        raise ValueError('safe publication version required')
    html = render_operational_html(bundle, version=version)
    output = Path(out_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    html_path = output / 'newspaper.html'
    html_path.write_text(html, encoding='utf-8')
    raw_pdf_path = output / 'newspaper.chromium.pdf'
    pdf_path = output / 'newspaper.pdf'
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                             args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            page = browser.new_page(viewport={'width': 1200, 'height': 1700}, device_scale_factor=1)
            # set_content also works in managed browsers that intentionally
            # disable file:// navigation. The paper embeds all text and CSS.
            page.set_content(html, wait_until='load')
            page.wait_for_function('window.paperReady === true', timeout=30000)
            qa = page.evaluate('window.paperLayoutQA')
            if not qa['passed']:
                raise ValueError('newspaper layout overflow: ' + json.dumps(qa, ensure_ascii=False))
            page.emulate_media(media='print')
            page.pdf(path=str(raw_pdf_path), width='297mm', height='420mm', print_background=True,
                     prefer_css_page_size=True, margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
        finally:
            browser.close()
    import fitz
    with fitz.open(raw_pdf_path) as document:
        if len(document) < qa['pages']:
            raise ValueError('PDF page count differs from checked HTML sheets')
        # Chromium may add a terminal page containing only the white body
        # background after many explicit print breaks. Keep its original PDF
        # and remove only pages proved to contain no text, images or ink.
        trimmed = len(document) - qa['pages']
        for extra in list(document)[qa['pages']:]:
            pixel = extra.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            if extra.get_text().strip() or extra.get_images() or any(channel != 255 for channel in pixel.samples):
                raise ValueError('extra PDF page contains content; refusing to discard it')
        if trimmed:
            document.delete_pages(qa['pages'], len(document) - 1)
        document.save(pdf_path)
        qa['trimmed_blank_pdf_pages'] = trimmed
    # PyMuPDF preserves the vertical CJK font mappings in Chromium output.
    # Some Poppler builds misplace these glyphs, so screenshots alone are not
    # substituted for images rasterized from the final PDF.
    pages = []
    with fitz.open(pdf_path) as document:
        if len(document) != qa['pages']:
            raise ValueError('PDF page count differs from checked HTML sheets')
        for number, pdf_page in enumerate(document, 1):
            path = output / ('page-' + str(number).zfill(3) + '.png')
            pdf_page.get_pixmap(matrix=fitz.Matrix(96 / 72, 96 / 72), alpha=False).save(path)
            pages.append(path)
    image_records = []
    for image in pages:
        data = image.read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('PDF rasterization did not produce PNG')
        width, height = struct.unpack('>II', data[16:24])
        if width < 800 or height < 1100 or len(data) < 5000:
            raise ValueError('empty or undersized newspaper page')
        image_records.append({'path': str(image), 'sha256': _file_hash(image), 'width': width, 'height': height})
    generated_at = _now()
    manifest = _seal({'schema': 'prism.operational.paper/v1', 'race_id': bundle['race']['race_id'],
                      'version': version, 'content_hash': digest(bundle), 'generated_at': generated_at,
                      'html': {'path': str(html_path), 'sha256': _file_hash(html_path)},
                      'source_pdf': {'path': str(raw_pdf_path), 'sha256': _file_hash(raw_pdf_path)},
                      'pdf': {'path': str(pdf_path), 'sha256': _file_hash(pdf_path)}, 'images': image_records,
                      'qa': {'status': 'EXECUTED', 'checked_at': generated_at, 'pages': len(pages),
                             'writing_mode': 'vertical-rl', 'reviewer': None,
                             'mechanical_checks': qa,
                             'note': 'All rendered PNG pages require visual review before VERIFIED.'}})
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


def confirm_visual_qa(manifest, reviewer, notes, checked_at=None):
    """Seal an explicit all-page visual review without overwriting run artifacts.

    Caller must actually inspect every PNG before calling this function. The
    returned record can be saved as a new approval artifact; it is not external
    attestation. Original EXECUTED manifest is retained.
    """
    if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(notes, str) or not notes.strip():
        raise ValueError('named reviewer and all-page review notes required')
    if manifest.get('manifest_hash') != digest({k: v for k, v in manifest.items() if k != 'manifest_hash'}):
        raise ValueError('paper manifest changed after rendering')
    qa = manifest.get('qa', {})
    if qa.get('qa_hash') != digest({k: v for k, v in qa.items() if k != 'qa_hash'}):
        raise ValueError('QA record integrity failure')
    if not qa.get('mechanical_checks', {}).get('passed') or qa.get('pages') != len(manifest.get('images', [])):
        raise ValueError('mechanical QA incomplete')
    for record in [manifest['html'], manifest['pdf'], *manifest['images'], *([manifest['source_pdf']] if 'source_pdf' in manifest else [])]:
        if _file_hash(record['path']) != record['sha256']:
            raise ValueError('rendered paper artifact changed')
    checked_at = checked_at or _now()
    if timestamp(checked_at) < timestamp(manifest['generated_at']):
        raise ValueError('visual review predates rendering')
    result = deepcopy(manifest)
    result['qa'].update(status='VERIFIED', checked_at=checked_at, reviewer=reviewer.strip(), notes=notes.strip())
    return _seal(result)


_STYLE = '''
@page {size:297mm 420mm;margin:0}
* {box-sizing:border-box}
html,body {margin:0;padding:0;background:#dedbd4;color:#1b242b;font-family:"Noto Serif CJK JP","Noto Sans CJK JP",serif}
.sheet {width:297mm;height:419.5mm;margin:8mm auto;padding:10mm;background:#fffdf8;display:flex;flex-direction:row-reverse;gap:5mm;break-after:page;page-break-after:always;break-inside:avoid;overflow:visible;border-top:2mm solid #213e49}
.sheet:last-child {break-after:auto;page-break-after:auto}
.masthead {flex:0 0 22mm;writing-mode:vertical-rl;border-left:1px solid #849298;padding-left:4mm;font-size:14px;line-height:1.8}
.masthead h1 {font-size:28px;font-weight:800;letter-spacing:.16em;margin:0 0 0 5mm}
.masthead p {margin:0 0 0 3mm}
.content {display:grid;grid-template-rows:repeat(3,minmax(0,1fr));gap:5mm;flex:1;min-width:0;height:100%;overflow:visible}
.band {display:flex;flex-direction:row-reverse;gap:4mm;min-width:0;min-height:0;align-items:stretch;overflow:visible;border-bottom:1px solid #b8b9b3;padding-bottom:2mm}
.band:last-child {border-bottom:0}
.block {writing-mode:vertical-rl;text-orientation:mixed;height:100%;width:max-content;flex:0 0 auto;border-left:1px solid #b8b9b3;padding-left:3mm;font-size:18px;line-height:1.85;overflow-wrap:anywhere;word-break:normal}
.block h2 {font-size:20px;line-height:1.6;font-weight:700;color:#234853;margin:0 0 0 3mm;letter-spacing:.07em}
.block p {margin:0;white-space:pre-wrap;max-height:100%;min-height:0}
@media print {html,body {background:white}.sheet {margin:0}}
'''

_PAGINATE = r'''
(async function(){
  await document.fonts.ready;
  const chunks=JSON.parse(document.getElementById('paper-data').textContent);
  const originalText=chunks.map(chunk=>chunk.text).join('');
  let sheet,content,bands,bandIndex,count=0;
  function addSheet(){
    sheet=document.createElement('article');sheet.className='sheet';sheet.dataset.page=String(++count);
    const head=document.createElement('header');head.className='masthead';
    const title=document.createElement('h1');title.textContent='Ｍ・ＰＡＰＥＲ';head.appendChild(title);
    const detail=document.createElement('p');detail.textContent='ＰＲＩＳＭ　'+document.body.dataset.version+'　'+count+'面';head.appendChild(detail);
    sheet.appendChild(head);const body=document.createElement('main');body.className='content';sheet.appendChild(body);document.body.appendChild(sheet);
    bands=[];for(let n=0;n<3;n++){const band=document.createElement('div');band.className='band';body.appendChild(band);bands.push(band);}
    bandIndex=0;content=bands[0];
  }
  function advanceBand(){if(bandIndex<2){content=bands[++bandIndex];}else{addSheet();}}
  function makeBlock(chunk){
    const block=document.createElement('section');block.className='block';
    const heading=document.createElement('h2');heading.textContent=chunk.title;block.appendChild(heading);
    const text=document.createElement('p');text.textContent=chunk.text;block.appendChild(text);return block;
  }
  function fits(block){return block.getBoundingClientRect().left>=content.getBoundingClientRect().left-1;}
  addSheet();
  for(let index=0;index<chunks.length;index++){
    const chunk=chunks[index];
    const block=makeBlock(chunk);
    content.appendChild(block);
    if(!fits(block)){
      content.removeChild(block);
      // Fit the longest exact prefix in this band before advancing. This
      // avoids leaving half a sheet empty when a large record follows a short
      // headline, and also handles comments containing many explicit newlines.
      const letters=Array.from(chunk.text);let low=1,high=letters.length-1,best=0;
      while(low<=high){
        const midpoint=Math.floor((low+high)/2),trial=makeBlock({title:chunk.title,text:letters.slice(0,midpoint).join('')});
        content.appendChild(trial);const okay=fits(trial);content.removeChild(trial);
        if(okay){best=midpoint;low=midpoint+1;}else{high=midpoint-1;}
      }
      if(best>=Math.min(letters.length,30)||(best>0&&!content.children.length)){
        const prefix={title:chunk.title,text:letters.slice(0,best).join('')};
        content.appendChild(makeBlock(prefix));
        chunks.splice(index,1,prefix,{title:chunk.title.replace(/（続き）$/, '')+'（続き）',text:letters.slice(best).join('')});
      }else if(content.children.length){advanceBand();index--;}
      else{throw new Error('Single character or heading cannot fit the page');}
    }
  }
  const errors=[];
  for(const page of document.querySelectorAll('.sheet')){
    if(!page.querySelector('.block'))errors.push('empty:'+page.dataset.page);
    for(const area of page.querySelectorAll('.band')){
    const bounds=area.getBoundingClientRect();
    if(area.scrollWidth>area.clientWidth+1 || area.scrollHeight>area.clientHeight+1) errors.push('overflow:'+page.dataset.page);
    for(const block of area.children){
      const r=block.getBoundingClientRect();
      if(r.left<bounds.left-1||r.right>bounds.right+1||r.top<bounds.top-1||r.bottom>bounds.bottom+1)errors.push('bounds:'+page.dataset.page);
      if(getComputedStyle(block).writingMode!=='vertical-rl')errors.push('not-vertical:'+page.dataset.page);
      const p=block.querySelector('p');
      if(p.scrollWidth>p.clientWidth+1||p.scrollHeight>p.clientHeight+1)errors.push('text-overflow:'+page.dataset.page);
    }
    }
  }
  const allTextRetained=Array.from(document.querySelectorAll('.block p')).map(p=>p.textContent).join('')===originalText;
  if(!allTextRetained)errors.push('text-mismatch');
  window.paperLayoutQA={passed:errors.length===0,pages:count,bands_per_page:3,blocks:chunks.length,errors,all_text_retained:allTextRetained,font_ready:document.fonts.status==='loaded'};
  window.paperReady=true;
})();
'''
