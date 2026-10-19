"""Four-page retrospective newspaper from an explicit research-only handoff.

This is separate from the pre-race engine renderer: held-out historical research
cannot be relabelled as a certified pre-race forecast or an executed discussion.
"""
import math
from prism_engine.contracts import digest
from .renderer import _text, _panel, _page, _STYLE


def _verified(dto, report):
    if dto.get('schema') != 'prism.paper.research-race/v1':
        raise ValueError('research race DTO required')
    if dto.get('dto_hash') != digest({k:v for k,v in dto.items() if k != 'dto_hash'}):
        raise ValueError('research paper DTO hash mismatch')
    if report.get('schema') != 'prism.validation.feature-experiment/v1' or report.get('report_hash') != digest({k:v for k,v in report.items() if k != 'report_hash'}):
        raise ValueError('research comparison hash mismatch')
    if dto.get('mode') != 'HISTORICAL_RECONSTRUCTION_NOT_PIT' or dto.get('strict_pit_certified') is not False:
        raise ValueError('research paper cannot claim PIT certification')
    if not report['holdout_dates'][0] <= dto['date'] <= report['holdout_dates'][1]:
        raise ValueError('paper date outside held-out cohort')
    if dto['model_hash'] not in {m['model_hash'] for m in report['models'].values()}:
        raise ValueError('paper model absent from comparison')
    runners = dto['runners']
    if not runners or len({r['horse_id'] for r in runners}) != len(runners) or len({r['horse_no'] for r in runners}) != len(runners):
        raise ValueError('research roster identity mismatch')
    for r in runners:
        if type(r['horse_no']) is not int or r['horse_no'] <= 0 or type(r['frame_no']) is not int or not 1 <= r['frame_no'] <= 8:
            raise ValueError('research horse/frame number invalid')
        if not isinstance(r['name'], str) or not r['name'].strip():
            raise ValueError('research horse name missing')
        if type(r['p_win']) not in (int,float) or not math.isfinite(r['p_win']) or not 0 < r['p_win'] < 1:
            raise ValueError('research probability invalid')
    if not math.isclose(sum(r['p_win'] for r in runners),1,abs_tol=1e-9):
        raise ValueError('research probability sum invalid')
    if dto.get('discussions'):
        raise ValueError('research DTO cannot substitute unvalidated dialogue')
    return sorted(runners,key=lambda r:r['horse_no'])


def render_research_paper(dto, report):
    """Render named runners and separately labelled same-cohort comparisons."""
    runners = _verified(dto,report)
    card = ''.join('<div class="runner" data-horse-id="'+_text(r['horse_id'])+'"><b>枠番 '+str(r['frame_no'])+'</b><b>馬番 '+str(r['horse_no'])+'</b><strong>'+_text(r['name'])+'</strong></div>' for r in runners)
    first = _page(1,'全頭を読む　一月検証レース',[
        _panel('開催', '<p>'+_text(dto['date'])+'　'+_text(dto['start'])+'　'+_text(dto['venue'])+'</p><p>'+_text(dto['title'])+'</p><p>'+_text(dto['surface'])+'　'+str(dto['distance_m'])+'ｍ　'+_text(dto['direction'])+'</p><p>過去再構成の研究版。当時取得時刻は未認証。</p>','conditions'),
        _panel('出馬表','<div class="racecard">'+card+'</div>','card-panel')])
    second = _page(2,'材料と記憶　記録に沿って話す',[
        _panel('今回使った材料','<p>十二月の履歴を初期情報とし、一月の前日までの結果から能力を再構成。騎手の過去成績と馬体重・増減を追加する実験。</p><p>係数の学習は一月十五日まで。十六日以降は係数を固定し、同日の結果を当日の他レースへ渡さない。</p>'),
        _panel('座談会','<p>このレースの座談会記録は未投入。篠宮律・りお・専門ＡＩの発言は掲載していない。</p><p>過去の本命や応援の継続は、本人の明示した選択記録をＤＢから確認できたときに反映する。</p>'),
        _panel('観測の注意','<p>馬・騎手の識別は暫定。欠測には欠測指標を残す。馬体情報の当時の公開時刻は未認証。</p><p>専門ＡＩ・Ｎ値・調教などを完成させたモデルではない。</p>')])
    ordered = sorted(runners,key=lambda r:(-r['p_win'],r['horse_no']))
    probabilities = ''.join('<p>馬番 '+str(r['horse_no'])+'　'+_text(r['name'])+'　'+format(r['p_win']*100,'.2f')+'％</p>' for r in ordered)
    top = ordered[0]
    third = _page(3,'結論　研究確率と固定百円',[
        _panel('全頭の推定勝率',probabilities),
        _panel('検証の一票','<p>馬番 '+str(top['horse_no'])+'　'+_text(top['name'])+'。このモデル内で推定勝率が最も高い馬に、単勝百円を仮置きする比較規則。</p><p>事前オッズと期待値を確認できないため、実際の購入候補・価値判断としては採用しない。</p><p>学習済みの過去検証モデルによる出力。今回のレース結果はこの欄へ掲載しない。</p>'),
        _panel('編集判断','<p>能力と追加材料の差は四面で比較する。一頭の確率や過去回収率から将来利益を保証できない。</p><p>本命の個人評価と、モデルの確率最大馬は別の記録として管理する。</p>')])
    labels={'ability_only':'能力単独','plus_jockey':'能力＋騎手','plus_body':'能力＋馬体','plus_both':'能力＋騎手＋馬体'}
    rows=[]
    for key,label in labels.items():
        v=report['runs'][key]
        rows.append('<p><b>'+label+'</b>　対数損失 '+format(v['log_loss'],'.4f')+'　Ｂｒｉｅｒ '+format(v['brier'],'.4f')+'　ＥＣＥ '+format(v['calibration']['ece'],'.4f')+'　回収率 '+format(v['effective_return_rate']*100,'.2f')+'％　損益 '+str(v['profit_yen'])+'円　最大ドローダウン '+str(v['max_drawdown_yen'])+'円</p>')
    missing=''.join('<p>'+_text(k)+'　'+format(v*100,'.2f')+'％</p>' for k,v in report['missing_rates']['plus_both'].items())
    ll_best=min(labels,key=lambda k:report['runs'][k]['log_loss'])
    brier_best=min(labels,key=lambda k:report['runs'][k]['brier'])
    roi_best=max(labels,key=lambda k:report['runs'][k]['effective_return_rate'])
    comparison_reading='<p>今回の集計では、対数損失は'+labels[ll_best]+'、Ｂｒｉｅｒは'+labels[brier_best]+'、回収率は'+labels[roi_best]+'が上位。</p>'
    if all(report['runs'][k]['profit_yen']<0 for k in labels):
        comparison_reading+='<p>いずれも単勝の累積損益は赤字。</p>'
    fourth = _page(4,'比較　同じ七〇一レースで読む',[
        _panel('同条件の成績','<p>学習 '+str(report['training_races'])+'レース、比較 '+str(report['holdout_races'])+'レース。一月十六日〜三十一日の共通対象。各レース単勝百円、返還は有効投資額から控除。</p>'+''.join(rows)),
        _panel('追加材料の欠損率',missing+comparison_reading+'<p>一つの尺度で自動採用しない。事後に定めた分割のため、二月の独立検証が必要。</p>'),
        _panel('検証記録','<p>当時取得時刻の認証 '+str(report['strict_pit_certified_races'])+'レース。二月検証・本番採用は未完。</p><p class="hash">レース '+_text(dto['race_id'])+'</p><p class="hash">予測 '+_text(dto['prediction_hash'])+'</p><p class="hash">集計 '+_text(report['report_hash'])+'</p>')])
    return '<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>PRISM 一月検証新聞</title><style>'+_STYLE+'</style></head><body>'+first+second+third+fourth+'</body></html>\n'
