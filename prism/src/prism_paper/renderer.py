"""Pure, escaped HTML rendering from one hash-bound, pre-result engine bundle.

The HTML is a four-page integration preview. Hash checks prove internal integrity,
not source truth, editorial quality, independent AI execution or model accuracy.
"""
from html import escape
from prism_engine.contracts import digest, timestamp, validate


def _text(value):
    return escape(str(value), quote=True)


def _bound(record, prediction):
    expected = {'race_id': prediction['race_id'], 'input_hash': prediction['input_hash'],
                'prediction_hash': prediction['lock_hash']}
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError('paper artifact identity mismatch')


def _excerpt(text, limit=160):
    value = str(text)
    return _text(value if len(value) <= limit else value[:limit] + '…〔抜粋〕')


def _check(bundle):
    if not isinstance(bundle, dict) or bundle.get('schema') != 'prism.engine.bundle/v1':
        raise ValueError('paper requires an engine bundle')
    if 'settlement' in bundle:
        raise ValueError('pre-race paper must not contain settlement')
    pred = bundle['prediction']
    if pred['lock_hash'] != digest({k: v for k, v in pred.items() if k != 'lock_hash'}):
        raise ValueError('paper prediction hash mismatch')
    raw = validate(bundle['raw'])
    if digest(raw) != pred['input_hash'] or raw['race']['race_id'] != pred['race_id']:
        raise ValueError('paper raw input mismatch')
    if raw['mode'] != pred['mode']:
        raise ValueError('paper mode mismatch')
    horses = {r['horse_id']: r for r in raw['runners']}
    if set(horses) != set(pred['win']) or any(str(h['frame_no']) != pred['frames'].get(i) for i, h in horses.items()):
        raise ValueError('paper horse/frame coverage mismatch')
    market = bundle.get('market_values')
    if market is not None:
        if market.get('race_id') != pred['race_id'] or market.get('prediction_hash') != pred['lock_hash']:
            raise ValueError('paper market binding mismatch')
        if market.get('mode') != pred['mode'] or market.get('execution_allowed') is not False:
            raise ValueError('paper is research-only')
        plan = market['plan']
        if plan['plan_hash'] != digest({k: v for k, v in plan.items() if k != 'plan_hash'}):
            raise ValueError('paper plan hash mismatch')
        if plan.get('race_id') != pred['race_id'] or plan.get('prediction_hash') != pred['lock_hash']:
            raise ValueError('paper plan binding mismatch')
        if plan['stake_yen'] != 100 * len(plan['tickets']) or any(t.get('stake_yen') != 100 for t in plan['tickets']):
            raise ValueError('paper fixed-100-yen plan mismatch')
    return pred, raw, horses, market


def _panel(title, body, cls=''):
    return '<section class="panel ' + cls + '"><h2>' + _text(title) + '</h2>' + body + '</section>'


def _page(number, title, panels):
    return ('<article class="sheet" data-page="' + str(number) + '"><header><p class="edition">'
            'ＰＲＩＳＭ　研究接続版　' + str(number) + '面</p><h1>' + _text(title) + '</h1></header>'
            '<div class="page-body">' + ''.join(panels) + '</div></article>')


def render_paper(bundle, discussion=None, validation=None):
    """Return deterministic, self-contained Japanese vertical print HTML.

    ``bundle['raw']`` is required so horse numbers cannot be inferred from IDs or
    confused with frame numbers. Discussion must bind to this prediction. A
    validation aggregate deliberately cannot stand in for this race's evidence.
    """
    pred, raw, horses, market = _check(bundle)
    mode = {'SYNTHETIC': '人工入力・架空レース', 'HISTORICAL_RECONSTRUCTION': '過去再構成・当時取得の証明なし',
            'PRE_AVAILABLE': '事前時刻整合・外部出典真正性未認証'}[pred['mode']]
    ordered = sorted(horses.values(), key=lambda r: r['horse_no'])
    race = raw['race']
    # The engine input schema intentionally has no horse-name field. Do not
    # fabricate a plausible name or silently read one from unbound metadata.
    card = ''.join('<div class="runner" data-horse-id="' + _text(r['horse_id']) + '"><b>枠番 '
                   + str(r['frame_no']) + '</b><b>馬番 ' + str(r['horse_no']) + '</b><span>馬名未収録</span>'
                   '<span>馬ＩＤ ' + _text(r['horse_id']) + '</span><span>負担重量 '
                   + _text(r['carried_weight']) + '</span></div>' for r in ordered)
    conditions = '<p>' + _text(race['venue']) + '　' + _text(race['surface']) + '　' + str(race['distance_m']) + 'ｍ　' + _text(race['direction']) + '</p><p>締切 ' + _text(race['cutoff']) + '</p>'
    first = _page(1, '確率から候補へ　同じ入力で結ぶ', [
        _panel('検証区分', '<p>' + _text(mode) + '</p><p>予測性能・収益性は未実証。購入の実行は行わない。</p><p>編集責任の表示：篠宮律。リオは質問役。この記事は自動生成プレビュー。</p>'),
        _panel('レース条件', conditions, 'conditions'),
        _panel('全頭出馬表', '<div class="racecard">' + card + '</div>', 'card-panel')])

    coverage = []
    for r in ordered:
        hid = r['horse_id']
        missing = pred['features']['horses'][hid].get('missing', [])
        coverage.append('<p><b>馬番 ' + str(r['horse_no']) + '</b>　能力指標 ' + format(pred['features']['horses'][hid]['base_ability'], '.2f')
                        + '　欠測 ' + (_text('・'.join(missing)) if missing else 'なし') + '</p>')
    dialogue = '<p>座談会未実施。実際の発言や独立したＡＩ検討を生成した記録ではない。</p>'
    if discussion is not None:
        _bound(discussion, pred)
        if 'mode' in discussion and discussion['mode'] != pred['mode']:
            raise ValueError('paper discussion mode mismatch')
        if discussion.get('recorded_at') is not None and timestamp(discussion['recorded_at']) > timestamp(pred['cutoff']):
            raise ValueError('paper discussion was recorded after cutoff')
        turns = discussion.get('turns', [])
        if not isinstance(turns, list):
            raise ValueError('paper discussion turns must be a list')
        if turns:
            execution = discussion.get('execution_mode', 'UNVERIFIED')
            label = {'TEMPLATE': 'テンプレート・実討論ではない', 'ROLE_SIMULATION': '役割シミュレーション・独立ＡＩ未認証',
                     'INDEPENDENT_EXECUTION': '独立実行を申告・実行真正性未認証'}.get(execution, '実行形態未認証')
            dialogue = '<p>' + _text(label) + '。発言抜粋であり学習実績には算入しない。</p>'
            dialogue += ''.join('<p><b>' + _text(t.get('agent_id', '不明')) + '</b>「' + _excerpt(t.get('text', '')) + '」</p>' for t in turns[:6])
            if len(turns) > 6:
                dialogue += '<p>残り ' + str(len(turns) - 6) + ' 発言は元記録を参照。</p>'
    second = _page(2, '根拠と対話を混同しない', [
        _panel('全頭の材料確認', ''.join(coverage)),
        _panel('座談会接続', dialogue),
        _panel('観測の限界', '<p>固定係数の実験モデル。欠測を取得済みと扱わず、ハッシュ一致を出典真正性の証明と扱わない。</p><p>調教・馬体・血統・騎手・陣営コメントを網羅した編集取材は未完。</p>')])

    probabilities = ''.join('<p>馬番 ' + str(horses[h]['horse_no']) + '　勝率 ' + format(p * 100, '.2f') + '％</p>'
                            for h, p in sorted(pred['win'].items(), key=lambda x: (-x[1], x[0])))
    tickets = '<p>市場データ接続なし。候補作成なし。</p>'
    if market is not None:
        plan = market['plan']
        rows = []
        for t in plan['tickets']:
            kind = t['bet_type']
            if kind == 'FRAME':
                legs = '枠番 ' + '・'.join(_text(x) for x in t['legs'])
            else:
                if not set(t['legs']) <= set(horses):
                    raise ValueError('paper ticket has unknown horse')
                legs = '馬番 ' + '・'.join(str(horses[x]['horse_no']) for x in t['legs'])
            rows.append('<p>' + _text(kind) + '　' + legs + '　百円　期待純収益 ' + format(t['expected_profit_yen'], '.2f') + '円</p>')
        tickets = ''.join(rows) if rows else '<p>見送り。条件を満たす候補なし。</p>'
        tickets += '<p>候補総額 ' + str(plan['stake_yen']) + '円。各点固定百円。購入指示ではない。</p>'
    third = _page(3, '結論　候補と見送りを明記', [_panel('全頭勝率', probabilities), _panel('固定百円の候補', tickets),
        _panel('判断の範囲', '<p>期待値は的中確率×下限オッズ−一。期待純収益は百円×期待値。市場比率と的中確率は別物。</p><p>この候補は紙上研究用。過去回収率や将来利益を保証しない。</p>')])

    comparison = '<p>同条件比較の接続記録なし。この一レースから性能改善は判定できない。</p>'
    if validation is not None:
        if not isinstance(validation, dict):
            raise ValueError('paper validation must be a record')
        # A corpus-wide result may not share this race's binding. It can only be
        # labelled as separate research, never displayed as race-level accuracy.
        comparison = '<p>別集計の検証記録を受領。このレースの性能証明ではない。</p><p>集計識別子 ' + _excerpt(validation.get('schema', '未指定'), 100) + '</p>'
        if validation.get('schema') == 'prism.validation.comparison/v1':
            if validation.get('report_hash') != digest({k: v for k, v in validation.items() if k != 'report_hash'}):
                raise ValueError('paper comparison report hash mismatch')
            scope = validation.get('scope')
            scope_text = '旧一月研究方式の比較。今回予想・新Ｂ全機能の性能証明ではない。' if scope == 'ARCHIVED_JANUARY_RESEARCH_COMPARISON' else '人工比較・実レース性能の証明ではない。'
            comparison += '<p>' + scope_text + '</p>'
            comparison += '<p>共通対象 ' + _text(validation.get('coverage', {}).get('paired_races', '未確認')) + ' レース。厳密な当時取得時刻の認証 ' + _text(validation.get('strict_pit_certified_races', '未確認')) + ' レース。</p>'
            for name, values in sorted(validation.get('runs', {}).items())[:4]:
                ratio = values.get('effective_return_rate')
                ratio_text = format(ratio * 100, '.2f') + '％' if type(ratio) in (int, float) else '未確認'
                comparison += '<p><b>' + _text(name) + '</b>　対数損失 ' + _text(values.get('log_loss', '未確認')) + '　有効投資回収率 ' + _text(ratio_text) + '　損益 ' + _text(values.get('profit_yen', '未確認')) + ' 円</p>'
        else:
            comparison += '<p>比較値は同一対象・時刻条件の監査後に掲載する。</p>'
    hashes = '<p>レース ' + _text(pred['race_id']) + '</p><p class="hash">入力 ' + _text(pred['input_hash']) + '</p><p class="hash">予測 ' + _text(pred['lock_hash']) + '</p>'
    fourth = _page(4, '比較　結論とは別の検証欄', [_panel('比較の範囲', comparison),
        _panel('受け渡し記録', hashes), _panel('次の受入条件', '<p>実データで同じ対象群の比較、時刻証明、独立対話の実行記録、紙面の目視校正が必要。</p><p>縦組み接続の成立は、新聞製品の全面完成を意味しない。</p>')])
    return '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>PRISM 縦組み研究接続版</title><style>' + _STYLE + '</style></head><body>' + first + second + third + fourth + '</body></html>\n'


_STYLE = '''
@page {size:A3 portrait;margin:0}
* {box-sizing:border-box}
body {margin:0;background:#ddd;color:#18212b;font-family:"Noto Serif CJK JP","Yu Mincho",serif}
.sheet {width:297mm;min-height:420mm;margin:10mm auto;padding:12mm;background:#fff;display:flex;flex-direction:row-reverse;gap:7mm;break-after:page;page-break-after:always;border-top:3mm solid #18394b}
.sheet:last-child {break-after:auto;page-break-after:auto}
header {writing-mode:vertical-rl;text-orientation:mixed;border-left:1px solid #52646d;padding-left:5mm;flex:0 0 32mm}
h1 {font-size:23pt;letter-spacing:.12em;line-height:1.7;margin:0}
.edition {font-size:10pt;letter-spacing:.1em;margin:0 0 4mm}
.page-body {display:flex;flex-direction:row-reverse;gap:5mm;flex:1;min-width:0;align-items:stretch}
.panel {writing-mode:vertical-rl;text-orientation:mixed;border-left:1px solid #c0c7ca;padding-left:4mm;flex:1;min-width:0;line-height:1.9;font-size:11pt;overflow-wrap:anywhere}
h2 {font-size:15pt;margin:0 0 0 4mm;letter-spacing:.08em;color:#18394b}
p {margin:0 0 0 3mm}
.conditions {flex:.7}.card-panel {flex:2.8}
.racecard {display:flex;flex-direction:row-reverse;gap:2mm;writing-mode:horizontal-tb;flex-wrap:wrap;align-content:flex-start;max-width:100%}
.runner {writing-mode:vertical-rl;display:flex;flex-direction:row;gap:4mm;padding:2mm;border:1px solid #b6c1c6;font-size:10pt;min-height:115mm}
.hash {font-family:monospace;font-size:8pt;overflow-wrap:anywhere;word-break:break-all}
@media print {body {background:white}.sheet {margin:0;box-shadow:none}}
'''
