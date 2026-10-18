"""Transparent experimental feature adapters; no learned-coefficient claim."""
from math import exp
from .contracts import timestamp

def weighted(rows,weight):
    mass=sum(weight(r) for r in rows)
    return sum(r['performance_score']*weight(r) for r in rows)/mass if mass else None

def features(raw,config):
    race=raw['race'];cutoff=timestamp(race['cutoff']);runners=sorted(raw['runners'],key=lambda r:r['horse_no'])
    surface=race['surface'];special=surface in {'BANEI','JUMP'}
    pace_labels=('VERY_SLOW','SLOW','MIDDLE','HIGH','VERY_HIGH')
    style_rows=[r['style'] for r in runners if r.get('style')]
    missing_pace=len(style_rows)!=len(runners) or special
    if missing_pace:pace=None
    else:
        pressure=min(1.,sum(s['escape']/sum(s[k] for k in ('escape','front','mid','closer')) for s in style_rows)/2)
        w=[exp(-((pressure-c)**2)/.08) for c in (.1,.28,.48,.68,.88)];total=sum(w)
        pace=dict(zip(pace_labels,(x/total for x in w)))
    by_horse={};barrier_count=race['barrier_count']
    for r in runners:
        available={};contributions={};missing=[]
        rows=[h for h in r['history'] if h['surface']==surface]
        recency=lambda h:0.5**((cutoff-timestamp(h['occurred_at'])).total_seconds()/86400/config['half_life_days'])
        pai=weighted(rows,recency)
        # Cold start is a documented explicit prior, not an observed score.
        base=config['cold_start_prior'] if pai is None else pai
        available['base_ability']='EXPLICIT_PRIOR' if pai is None else 'AVAILABLE'
        if pai is None:missing.append('base_history')
        dai=weighted(rows,lambda h:recency(h)*exp(-abs(h['distance_m']-race['distance_m'])/500))
        cai=weighted(rows,lambda h:recency(h)*(1 if h['direction']==race['direction'] else .5)*(1 if h['venue']==race['venue'] else .8))
        class_diff=weighted([dict(h,performance_score=h['class_rating']) for h in rows],recency)
        load_adjustment=.005*(650-r['carried_weight']) if surface=='BANEI' else .05*(55-r['carried_weight'])
        norm=None if dai is None else .25*(dai-base)+.25*(cai-base)+.1*(class_diff-race['class_rating'])+load_adjustment
        contributions['course_surface_class']=norm
        state=r.get('state')
        contributions['state_recency_rotation']=None if state is None else .08*(state['readiness']-50)-min(abs(state['rotation_days']-28),180)*.006
        style=r.get('style')
        if pace is None or style is None:contributions['pace']=None
        else:
            fast=pace['HIGH']+pace['VERY_HIGH']-pace['SLOW']-pace['VERY_SLOW']
            sm=sum(style[k] for k in ('escape','front','mid','closer'))
            front=(style['escape']+.65*style['front']-.55*style['closer'])/sm
            contributions['pace']=fast*(.04*(style['resistance']-50)-3*front)+.01*(style['early_speed']-50)
        bias=raw.get('bias')
        if bias is None:contributions['bias_tbi_ssi']=None
        else:
            sign=1 if bias['positive_lane']=='OUTER' else -1
            gate=2*(r['barrier_no']-1)/(barrier_count-1)-1
            lane=4*sign*bias['gate']*gate
            path=r.get('path_position')
            if path is not None:lane+=2*sign*bias['path']*path
            else:missing.append('path_position')
            if special:
                contributions['bias_tbi_ssi']=lane
            elif style:
                sm=sum(style[k] for k in ('escape','front','mid','closer'))
                front=(style['escape']+.65*style['front']-.55*style['closer'])/sm
                contributions['bias_tbi_ssi']=lane+3*bias['front']*front+1.5*bias['ssi']*(style['early_speed']-50)/50
            else:contributions['bias_tbi_ssi']=None
        for name,scale in [('workout',.06),('condition',.06),('sectional',.04)]:
            value=r.get(name)
            contributions[name]=None if value is None or special and name=='sectional' else scale*(value['score']-50)
        jockey=r.get('jockey')
        contributions['jockey']=None if jockey is None else .05*(jockey['score']-50)*jockey['sample_size']/(jockey['sample_size']+20)
        clusters={}
        for s in raw.get('specialists',[]):
            if s['horse_id']!=r['horse_id']:continue
            val=s['delta']*s['confidence'];old=clusters.get(s['evidence_id'])
            # Same evidence is one signal even when cited by several agents.
            if old is None or abs(val)>abs(old) or abs(val)==abs(old) and val<old:clusters[s['evidence_id']]=val
        contributions['specialist']=max(-10,min(10,sum(clusters.values()))) if clusters else None
        if surface=='BANEI':
            b=r.get('ban_ei');water=None if bias is None else bias.get('water_content')
            # Moisture rises => lighter, not heavier; no flat-racing sectional model.
            contributions['surface_specific']=None if b is None or water is None else .12*(b['barrier_skill']-50)+.08*(b['pulling_power']-50)*(1-water/100)
        elif surface=='JUMP':
            j=r.get('jump');contributions['surface_specific']=None if j is None else .15*(j['jump_skill']-50)
        else:contributions['surface_specific']=0.
        for name,value in contributions.items():
            available[name]='UNAVAILABLE' if value is None else 'AVAILABLE'
            if value is None:missing.append(name)
        scenarios={}
        if pace is not None and style is not None:
            for label,fast in zip(pace_labels,(-1.,-.5,0.,.5,1.)):
                scenarios[label]=fast*(.04*(style['resistance']-50)-3*front)+.01*(style['early_speed']-50)
        by_horse[r['horse_id']]={'base_ability':base,'components':contributions,'availability':available,'pace_scenarios':scenarios,
                                  'missing':missing,'horse_no':r['horse_no'],'frame_no':r['frame_no'],'barrier_no':r['barrier_no']}
    return {'horses':by_horse,'pace_distribution':pace,'surface_route':surface,
            'note':'Coefficients are experimental defaults; validate performance in Phase D.'}
