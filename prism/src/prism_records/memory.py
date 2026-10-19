"""Read-only, as-of conversation context from exact entity IDs.

Recorded role opinions are not independent executions or externally verified facts.
No name-based identity lookup, prose-based selection inference, or automatic picks.
"""
from datetime import datetime, timezone, timedelta
import json
from .store import digest, text


def stamp(value):
    if not isinstance(value,str): raise ValueError('timezone-aware as_of required')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('timezone-aware as_of required')
    return dt.astimezone(timezone.utc)


def race_time(metadata):
    """Schedule inference is used only to count prior entries, never certify PRE."""
    if metadata.get('cutoff'):
        try: return stamp(metadata['cutoff']), 'RECORDED_CUTOFF_NOT_ATTESTED'
        except (ValueError,TypeError): return None,'INVALID_RACE_CUTOFF'
    values=metadata.get('reconstructed_pre',{}).get('values',{})
    date=values.get('date',metadata.get('date')); start=values.get('start',metadata.get('start'))
    if isinstance(date,str) and isinstance(start,str):
        try:
            dt=datetime.strptime(date+start.zfill(4),'%Y%m%d%H%M').replace(tzinfo=timezone(timedelta(hours=9)))
            return dt.astimezone(timezone.utc),'ARCHIVED_JAPAN_SCHEDULE_NOT_AVAILABILITY_PROOF'
        except ValueError: pass
    return None,'UNKNOWN_RACE_TIME'


def agent_horse_memory(store, agent_id, horse_id, as_of, current_race_id=None, limit=20):
    text(agent_id,'agent_id');text(horse_id,'horse_id');when=stamp(as_of)
    if type(limit) is not int or not 1<=limit<=200: raise ValueError('limit must be 1..200')
    conn=store.connection
    horse=conn.execute('SELECT * FROM horses WHERE id=?',(horse_id,)).fetchone()
    if horse is None: raise KeyError(horse_id)
    if digest({'display_name':horse['display_name'],'canonical_id':horse['canonical_id'],
               'profile':json.loads(horse['profile_json'])})!=horse['content_hash']:
        raise ValueError('horse record integrity mismatch')
    rows=conn.execute('SELECT e.*,r.metadata_json,r.content_hash AS race_content_hash FROM entries e JOIN races r ON r.id=e.race_id '
                      'WHERE e.horse_id=? ORDER BY e.race_id',(horse_id,)).fetchall()
    prior={};excluded={'current_race_entries':0,'future_entries':0,'unknown_race_time_entries':0,
                      'template_assessments':0,'future_or_unknown_discussions':0,'invalid_binding_assessments':0,
                      'post_or_unknown_observations':0,'future_observations':0,'invalid_observations':0,
                      'invalid_record_entries':0}
    for row in rows:
        if row['race_id']==current_race_id: excluded['current_race_entries']+=1;continue
        metadata=json.loads(row['metadata_json'])
        entry_body={k:row[k] for k in ('race_id','horse_no','horse_id','jockey_id','frame_no')}
        entry_body['details']=json.loads(row['details_json'])
        if digest(metadata)!=row['race_content_hash'] or digest(entry_body)!=row['content_hash']:
            excluded['invalid_record_entries']+=1;continue
        dt,provenance=race_time(metadata)
        if dt is None: excluded['unknown_race_time_entries']+=1;continue
        if dt>=when: excluded['future_entries']+=1;continue
        prior[row['race_id']]={'entry_id':row['id'],'scheduled_at':dt.isoformat(),'time_provenance':provenance,
                               'entry_content_hash':row['content_hash'],'race_content_hash':row['race_content_hash']}
    assessments=conn.execute('SELECT a.*,d.race_id AS discussion_race_id,d.occurred_at,d.mode AS discussion_mode,'
        'd.phase AS discussion_phase,d.prediction_hash AS discussion_prediction_hash,d.payload_json AS discussion_payload_json,d.content_hash AS discussion_content_hash '
        'FROM assessments a JOIN discussions d ON d.id=a.discussion_id '
        "WHERE a.horse_id=? AND a.agent_id=? AND a.subject_type='HORSE' ORDER BY d.occurred_at,a.id",
        (horse_id,agent_id)).fetchall()
    meetings={};selections=[];accepted_hashes=[]
    for a in assessments:
        race=a['discussion_race_id']
        if a['mode']=='TEMPLATE' or a['discussion_mode']=='TEMPLATE':
            excluded['template_assessments']+=1;continue
        try: at=stamp(a['occurred_at'])
        except (ValueError,TypeError): at=None
        if race not in prior or at is None or at>=when:
            excluded['future_or_unknown_discussions']+=1;continue
        claim=json.loads(a['payload_json']);discussion=json.loads(a['discussion_payload_json'])
        turn=claim.get('turn',{});records=discussion.get('records',{})
        engine_horse=turn.get('horse_id')
        if (digest(claim)!=a['content_hash'] or digest(discussion)!=a['discussion_content_hash'] or
                a['phase']!='PRE' or a['discussion_phase']!='PRE' or a['mode']!=a['discussion_mode'] or
                a['mode'] not in {'ROLE_SIMULATION','INDEPENDENT_EXECUTION'} or
                claim.get('horse_id')!=horse_id or claim.get('race_id')!=race or
                claim.get('entry_id')!=prior[race]['entry_id'] or a['entry_id']!=prior[race]['entry_id'] or
                claim.get('prediction_hash')!=a['prediction_hash'] or
                a['prediction_hash']!=a['discussion_prediction_hash'] or
                records.get('recorded_at')!=a['occurred_at'] or records.get('execution_mode')!=a['mode'] or
                records.get('prediction_hash')!=a['prediction_hash'] or records.get('race_id')!=race or
                turn.get('agent_id')!=agent_id or turn.get('turn_id')!=a['turn_id'] or
                discussion.get('horse_map',{}).get(engine_horse)!=horse_id or
                turn not in records.get('turns',[])):
            excluded['invalid_binding_assessments']+=1;continue
        history_type='ROLE_SIMULATION_ATTRIBUTED_HISTORY' if a['mode']=='ROLE_SIMULATION' else 'SUPPLIED_HISTORY_NOT_INDEPENDENTLY_VERIFIED'
        meeting=meetings.setdefault(a['discussion_id'],{'discussion_id':a['discussion_id'],'race_id':race,
            'occurred_at':a['occurred_at'],'mode':a['mode'],'history_type':history_type,
            'prediction_hash':a['prediction_hash'],'discussion_content_hash':a['discussion_content_hash'],
            'opinions':[],'independent_execution_verified':False})
        meeting['opinions'].append({'assessment_id':a['id'],'turn_id':a['turn_id'],
            'stage':turn.get('stage'),'attributed_text':turn.get('text',''),
            'content_hash':a['content_hash'],'observed_fact':False})
        accepted_hashes.append(a['content_hash'])
        selection=claim.get('selection')
        if selection is not None:
            if (turn.get('stage')!='FINAL' or not isinstance(selection,dict) or
                    selection.get('agent_id')!=agent_id or selection.get('horse_id')!=engine_horse or
                    selection.get('turn_id')!=turn.get('turn_id') or
                    selection.get('selection') not in {'TOP_PICK','CONTENDER','WATCH','AVOID'} or
                    selection not in records.get('selections',[])):
                excluded['invalid_binding_assessments']+=1;continue
            selections.append({'race_id':race,'discussion_id':a['discussion_id'],'occurred_at':a['occurred_at'],
                'agent_id':agent_id,'horse_id':horse_id,'selection':selection['selection'],
                'turn_id':turn['turn_id'],'assessment_hash':a['content_hash'],'history_type':history_type,
                'explicitly_recorded':True,'inferred_from_prose':False,'independent_execution_verified':False})
    evidence=[]
    for obs in conn.execute('SELECT * FROM observations WHERE horse_id=? ORDER BY id',(horse_id,)):
        if obs['race_id'] not in prior: continue
        if obs['phase']!='PRE' or obs['temporal_class']!='PRE_AVAILABLE' or obs['available_at'] is None:
            excluded['post_or_unknown_observations']+=1;continue
        try: at=stamp(obs['available_at'])
        except (ValueError,TypeError): excluded['invalid_observations']+=1;continue
        if at>=when: excluded['future_observations']+=1;continue
        payload=json.loads(obs['payload_json'])
        body={'horse_id':obs['horse_id'],'race_id':obs['race_id'],'payload':payload,
              'source_ref':obs['source_ref'],'available_at':obs['available_at'],'temporal_class':obs['temporal_class']}
        if digest(body)!=obs['content_hash']:
            excluded['invalid_observations']+=1;continue
        # Only a provenance pointer is emitted; raw facts and POST details are not copied into conversation.
        evidence.append({'observation_id':obs['id'],'race_id':obs['race_id'],'source_ref':obs['source_ref'],
                         'available_at':obs['available_at'],'content_hash':obs['content_hash'],
                         'source_authenticity_verified':False})
    ordered=sorted(meetings.values(),key=lambda r:(stamp(r['occurred_at']),r['discussion_id']),reverse=True)
    selections.sort(key=lambda r:(stamp(r['occurred_at']),r['discussion_id'],r['turn_id']),reverse=True)
    top=[s for s in selections if s['selection']=='TOP_PICK']
    out={'schema':'prism.records.agent-horse-memory/v1','agent_id':agent_id,'horse_id':horse_id,
         'display_name':horse['display_name'],'identity_status':horse['identity_status'],
         'as_of':as_of,'current_race_id':current_race_id,'prior_entity_entries_count':len(prior),
         'prior_personal_discussions_count':len(ordered),'prior_personal_discussions':ordered[:limit],
         'past_selections_count':len(selections),'past_selections':selections[:limit],
         'past_top_picks_count':len(top),'past_top_picks':top[:limit],
         'eligible_pre_observation_refs':evidence[:limit],'eligible_pre_observation_refs_count':len(evidence),
         'familiarity':{'known_in_database':bool(prior),'personal_opinion_recorded':bool(ordered),
            'explicit_prior_top_pick_recorded':bool(top),'prohibit_first_meeting_claim':bool(prior or ordered),
            'prohibit_invented_past_endorsement':not bool(top),'automatic_current_selection_allowed':False},
         'excluded':excluded,'truncated':any(n>limit for n in (len(ordered),len(selections),len(top),len(evidence))),
         'source_binding':{'entity_content_hash':horse['content_hash'],'prior_entry_ids_hash':digest(sorted(x['entry_id'] for x in prior.values())),
                           'prior_entry_and_race_records_hash':digest(prior),
                           'assessment_hashes_hash':digest(sorted(accepted_hashes))},
         'source_authenticity_verified':False,'independent_execution_verified':False,'training_achievement_verified':False,
         'temporal_notes':['Prior race schedules establish record ordering, not historical source availability.',
                           'Recorded role opinions are attributed history, not independently verified personal experience.',
                           'Unknown-time observations and POST results are counted but not copied as PRE factual evidence.',
                           'A prior explicit TOP_PICK is not a recommendation for the current race.',
                           'Separate source-scoped horse IDs are never joined using display names.']}
    out['memory_hash']=digest(out)
    return out


RACE_MEMORY_SCHEMA='prism.records.race-memory/v1'
FALSE_GUARANTEES={'source_authenticity_verified','independent_execution_verified',
                  'training_achievement_verified','model_probabilities_modified',
                  'automatic_current_selection_allowed'}


def _shape(value, keys):
    if not isinstance(value,dict) or set(value)!=set(keys):
        raise ValueError('memory schema fields mismatch')


def _false(value, keys):
    if any(value.get(k) is not False for k in keys):
        raise ValueError('memory cannot establish certified guarantees')


def _past_row(value, snapshot, time_field):
    if value['race_id']==snapshot['race_id'] or stamp(value[time_field])>=stamp(snapshot['as_of']):
        raise ValueError('memory contains current/future race record')


def _verify_personal(memory, snapshot, agent, horse):
    _shape(memory, {'schema','agent_id','horse_id','display_name','identity_status','as_of','current_race_id',
        'prior_entity_entries_count','prior_personal_discussions_count','prior_personal_discussions',
        'past_selections_count','past_selections','past_top_picks_count','past_top_picks',
        'eligible_pre_observation_refs_count','eligible_pre_observation_refs','familiarity','excluded',
        'truncated','source_binding','source_authenticity_verified','independent_execution_verified',
        'training_achievement_verified','temporal_notes','memory_hash'})
    if memory['schema']!='prism.records.agent-horse-memory/v1' or memory['memory_hash']!=digest({k:v for k,v in memory.items() if k!='memory_hash'}):
        raise ValueError('personal memory integrity mismatch')
    if (memory['agent_id']!=agent or memory['horse_id']!=horse or memory['as_of']!=snapshot['as_of'] or
            memory['current_race_id']!=snapshot['race_id']):
        raise ValueError('personal memory binding mismatch')
    name=snapshot['current_names'][horse]
    if memory['display_name']!=name['display_name'] or memory['identity_status']!=name['identity_status']:
        raise ValueError('personal memory entity display mismatch')
    _false(memory, {'source_authenticity_verified','independent_execution_verified','training_achievement_verified'})
    counts=('prior_entity_entries_count','prior_personal_discussions_count','past_selections_count',
            'past_top_picks_count','eligible_pre_observation_refs_count')
    if any(type(memory[k]) is not int or memory[k]<0 for k in counts):
        raise ValueError('invalid memory counts')
    for array,count in (('prior_personal_discussions','prior_personal_discussions_count'),
                        ('past_selections','past_selections_count'),('past_top_picks','past_top_picks_count'),
                        ('eligible_pre_observation_refs','eligible_pre_observation_refs_count')):
        if not isinstance(memory[array],list) or len(memory[array])>memory[count]:
            raise ValueError('memory count/list mismatch')
        if memory['truncated'] is False and len(memory[array])!=memory[count]:
            raise ValueError('untruncated memory count mismatch')
    if type(memory['truncated']) is not bool: raise ValueError('invalid memory truncation flag')
    _shape(memory['familiarity'],{'known_in_database','personal_opinion_recorded','explicit_prior_top_pick_recorded',
        'prohibit_first_meeting_claim','prohibit_invented_past_endorsement','automatic_current_selection_allowed'})
    expected={'known_in_database':bool(memory['prior_entity_entries_count']),
              'personal_opinion_recorded':bool(memory['prior_personal_discussions_count']),
              'explicit_prior_top_pick_recorded':bool(memory['past_top_picks_count']),
              'prohibit_first_meeting_claim':bool(memory['prior_entity_entries_count'] or memory['prior_personal_discussions_count']),
              'prohibit_invented_past_endorsement':not bool(memory['past_top_picks_count']),
              'automatic_current_selection_allowed':False}
    if any(memory['familiarity'][k] is not v for k,v in expected.items()):
        raise ValueError('memory familiarity/count mismatch')
    _shape(memory['excluded'],{'current_race_entries','future_entries','unknown_race_time_entries','template_assessments',
        'future_or_unknown_discussions','invalid_binding_assessments','post_or_unknown_observations',
        'future_observations','invalid_observations','invalid_record_entries'})
    if any(type(v) is not int or v<0 for v in memory['excluded'].values()): raise ValueError('invalid exclusion count')
    _shape(memory['source_binding'],{'entity_content_hash','prior_entry_ids_hash','prior_entry_and_race_records_hash',
                                    'assessment_hashes_hash'})
    if any(not isinstance(v,str) or len(v)!=64 for v in memory['source_binding'].values()):
        raise ValueError('invalid memory source digest')
    if not isinstance(memory['temporal_notes'],list) or any(not isinstance(v,str) for v in memory['temporal_notes']):
        raise ValueError('invalid memory temporal notes')
    seen=set()
    for meeting in memory['prior_personal_discussions']:
        _shape(meeting,{'discussion_id','race_id','occurred_at','mode','history_type','prediction_hash',
                        'discussion_content_hash','opinions','independent_execution_verified'})
        if meeting['discussion_id'] in seen: raise ValueError('duplicate memory discussion')
        seen.add(meeting['discussion_id']);_past_row(meeting,snapshot,'occurred_at')
        _false(meeting,{'independent_execution_verified'})
        if meeting['mode'] not in {'ROLE_SIMULATION','INDEPENDENT_EXECUTION'}:
            raise ValueError('template/unknown memory discussion mode')
        label='ROLE_SIMULATION_ATTRIBUTED_HISTORY' if meeting['mode']=='ROLE_SIMULATION' else 'SUPPLIED_HISTORY_NOT_INDEPENDENTLY_VERIFIED'
        if meeting['history_type']!=label: raise ValueError('memory discussion attribution mismatch')
        if not isinstance(meeting['opinions'],list): raise ValueError('invalid memory opinions')
        for opinion in meeting['opinions']:
            _shape(opinion,{'assessment_id','turn_id','stage','attributed_text','content_hash','observed_fact'})
            _false(opinion,{'observed_fact'})
            if opinion['stage'] not in {'INITIAL','RESPONSE','FINAL'} or not isinstance(opinion['attributed_text'],str):
                raise ValueError('invalid memory opinion')
    for array in ('past_selections','past_top_picks'):
        seen=set()
        for selection in memory[array]:
            _shape(selection,{'race_id','discussion_id','occurred_at','agent_id','horse_id','selection','turn_id',
                'assessment_hash','history_type','explicitly_recorded','inferred_from_prose','independent_execution_verified'})
            _past_row(selection,snapshot,'occurred_at')
            _false(selection,{'inferred_from_prose','independent_execution_verified'})
            if (selection['agent_id']!=agent or selection['horse_id']!=horse or selection['explicitly_recorded'] is not True or
                    selection['selection'] not in {'TOP_PICK','CONTENDER','WATCH','AVOID'} or
                    selection['history_type'] not in {'ROLE_SIMULATION_ATTRIBUTED_HISTORY','SUPPLIED_HISTORY_NOT_INDEPENDENTLY_VERIFIED'}):
                raise ValueError('invalid memory explicit selection')
            if array=='past_top_picks' and selection['selection']!='TOP_PICK': raise ValueError('invalid top pick')
            key=(selection['discussion_id'],selection['turn_id'])
            if key in seen: raise ValueError('duplicate memory selection')
            seen.add(key)
    if memory['past_top_picks_count']>memory['past_selections_count']: raise ValueError('invalid top pick count')
    for ref in memory['eligible_pre_observation_refs']:
        _verify_ref(ref,snapshot)


def _verify_ref(ref,snapshot):
    _shape(ref,{'observation_id','race_id','source_ref','available_at','content_hash','source_authenticity_verified'})
    _false(ref,{'source_authenticity_verified'});_past_row(ref,snapshot,'available_at')
    for key in ('observation_id','race_id','source_ref','content_hash'): text(ref[key],key)


def prepare_race_memory(store, race_id, as_of, agent_ids):
    """Materialize one deterministic read-only context before a meeting."""
    text(race_id,'race_id');stamp(as_of)
    if not isinstance(agent_ids,(list,tuple)) or not agent_ids or len(agent_ids)!=len(set(agent_ids)):
        raise ValueError('unique agent IDs required')
    for agent in agent_ids: text(agent,'agent_id')
    entries=store.connection.execute('SELECT e.horse_id,e.horse_no,e.frame_no,e.jockey_id,h.display_name,h.identity_status,'
        'j.display_name AS jockey_name,j.identity_status AS jockey_status '
        'FROM entries e JOIN horses h ON h.id=e.horse_id LEFT JOIN jockeys j ON j.id=e.jockey_id '
        'WHERE e.race_id=? ORDER BY e.horse_no',(race_id,)).fetchall()
    if not entries: raise ValueError('race memory requires recorded entries')
    runners=[{k:entry[k] for k in ('horse_id','horse_no','frame_no')} for entry in entries]
    names={entry['horse_id']:{k:entry[k] for k in ('display_name','identity_status')} for entry in entries}
    riders={entry['horse_id']:(None if entry['jockey_id'] is None else {'jockey_id':entry['jockey_id'],
             'display_name':entry['jockey_name'],'identity_status':entry['jockey_status']}) for entry in entries}
    memories={agent:{row['horse_id']:agent_horse_memory(store,agent,row['horse_id'],as_of,current_race_id=race_id)
                     for row in runners} for agent in sorted(agent_ids)}
    refs={}
    for group in memories.values():
        for memory in group.values():
            for ref in memory['eligible_pre_observation_refs']:
                key=ref['observation_id']
                if key in refs and refs[key]!=ref: raise ValueError('inconsistent shared observation')
                refs[key]=ref
    out={'schema':RACE_MEMORY_SCHEMA,'race_id':race_id,'as_of':as_of,'agent_ids':sorted(agent_ids),
         'runners':runners,'current_names':names,'current_riders':riders,'agent_memories':memories,
         'shared_pre_observation_refs':[refs[k] for k in sorted(refs)],
         **{key:False for key in FALSE_GUARANTEES}}
    out['snapshot_hash']=digest(out)
    verify_race_memory(out,race_id,as_of)
    return out


def verify_race_memory(snapshot, race_id=None, as_of=None):
    """Validate one known memory envelope. Hashes never certify supplied claims.

    Optional as_of is the latest permitted snapshot time (usually prediction lock).
    """
    _shape(snapshot,{'schema','race_id','as_of','agent_ids','runners','current_names','current_riders','agent_memories',
                     'shared_pre_observation_refs','snapshot_hash',*FALSE_GUARANTEES})
    if snapshot['schema']!=RACE_MEMORY_SCHEMA or snapshot['snapshot_hash']!=digest({k:v for k,v in snapshot.items() if k!='snapshot_hash'}):
        raise ValueError('race memory integrity mismatch')
    text(snapshot['race_id'],'race_id');when=stamp(snapshot['as_of'])
    if race_id is not None and snapshot['race_id']!=race_id: raise ValueError('race memory target mismatch')
    if as_of is not None and when>stamp(as_of): raise ValueError('race memory after prediction lock')
    _false(snapshot,FALSE_GUARANTEES)
    agents=snapshot['agent_ids']
    if not isinstance(agents,list) or not agents or agents!=sorted(set(agents)):
        raise ValueError('invalid memory agent roster')
    for agent in agents: text(agent,'agent_id')
    if not isinstance(snapshot['runners'],list) or not snapshot['runners']: raise ValueError('invalid memory race roster')
    horses=set();numbers=set()
    for runner in snapshot['runners']:
        _shape(runner,{'horse_id','horse_no','frame_no'});text(runner['horse_id'],'horse_id')
        number=runner['horse_no'];frame=runner['frame_no']
        if type(number) is not int or number<1 or number in numbers or runner['horse_id'] in horses:
            raise ValueError('duplicate/invalid memory runner')
        if frame is not None and (type(frame) is not int or not 1<=frame<=8): raise ValueError('invalid memory frame')
        horses.add(runner['horse_id']);numbers.add(number)
    if not isinstance(snapshot['current_names'],dict) or set(snapshot['current_names'])!=horses:
        raise ValueError('memory entity names coverage mismatch')
    for name in snapshot['current_names'].values():
        _shape(name,{'display_name','identity_status'});text(name['display_name'],'display_name')
        if name['identity_status'] not in {'PROVISIONAL','CANONICAL'}: raise ValueError('invalid identity status')
    if not isinstance(snapshot['current_riders'],dict) or set(snapshot['current_riders'])!=horses:
        raise ValueError('memory rider association coverage mismatch')
    rider_names={}
    for rider in snapshot['current_riders'].values():
        if rider is None: continue
        _shape(rider,{'jockey_id','display_name','identity_status'})
        text(rider['jockey_id'],'jockey_id');text(rider['display_name'],'rider display_name')
        if rider['identity_status'] not in {'PROVISIONAL','CANONICAL'}: raise ValueError('invalid rider identity status')
        if rider['jockey_id'] in rider_names and rider_names[rider['jockey_id']]!=rider:
            raise ValueError('same rider identity has inconsistent display')
        rider_names[rider['jockey_id']]=rider
    if not isinstance(snapshot['agent_memories'],dict) or set(snapshot['agent_memories'])!=set(agents):
        raise ValueError('memory agent coverage mismatch')
    refs={}
    for agent,group in snapshot['agent_memories'].items():
        if not isinstance(group,dict) or set(group)!=horses: raise ValueError('memory horse coverage mismatch')
        for horse,memory in group.items():
            _verify_personal(memory,snapshot,agent,horse)
            for ref in memory['eligible_pre_observation_refs']:
                key=ref['observation_id']
                if key in refs and refs[key]!=ref: raise ValueError('inconsistent shared memory reference')
                refs[key]=ref
    shared=snapshot['shared_pre_observation_refs']
    if not isinstance(shared,list): raise ValueError('invalid shared memory references')
    for ref in shared: _verify_ref(ref,snapshot)
    if shared!=[refs[k] for k in sorted(refs)]: raise ValueError('shared references must equal eligible memory references')
    return True
