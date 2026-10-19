"""Quarantine imported dialogue without inventing historical PRE availability.

The source must be the complete JSON document, not a derived engine prediction.
These records do not enter the PRE-only conversation memory or training tables.
"""
import json
from hashlib import sha256
from .store import digest, encode, text
from .memory import stamp, race_time


SCHEMA = '''CREATE TABLE IF NOT EXISTS legacy_dialogue_imports (
 id TEXT PRIMARY KEY, source_ref TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 imported_at TEXT NOT NULL, race_id TEXT NOT NULL REFERENCES races(id),
 phase TEXT NOT NULL CHECK(phase IN ('UNKNOWN','POST')),
 payload_json TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS legacy_dialogue_race ON legacy_dialogue_imports(race_id);
'''
IMMUTABILITY_TRIGGERS = (
    '''CREATE TRIGGER IF NOT EXISTS legacy_dialogue_no_update
       BEFORE UPDATE ON legacy_dialogue_imports
       BEGIN SELECT RAISE(ABORT,'legacy dialogue is append-only'); END''',
    '''CREATE TRIGGER IF NOT EXISTS legacy_dialogue_no_delete
       BEFORE DELETE ON legacy_dialogue_imports
       BEGIN SELECT RAISE(ABORT,'legacy dialogue is append-only'); END''',
    '''CREATE TRIGGER IF NOT EXISTS legacy_dialogue_no_replace
       BEFORE INSERT ON legacy_dialogue_imports
       WHEN EXISTS (SELECT 1 FROM legacy_dialogue_imports WHERE id=NEW.id)
       BEGIN SELECT RAISE(ABORT,'legacy dialogue identity already exists'); END''',
)
MODES = {'TEMPLATE', 'ROLE_SIMULATION', 'INDEPENDENT_EXECUTION', 'UNKNOWN'}
SELECTIONS = {'TOP_PICK', 'CONTENDER', 'WATCH', 'AVOID'}


def _document(source_bytes):
    if not isinstance(source_bytes, bytes):
        raise ValueError('complete source bytes required')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out: raise ValueError('duplicate source JSON key')
            out[key] = value
        return out
    value = json.loads(source_bytes.decode('utf-8-sig'), object_pairs_hook=unique,
                       parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    if not isinstance(value, dict): raise ValueError('source JSON object required')
    return value


def stage_legacy_dialogue(store, source_bytes, *, source_ref, imported_at, horse_map):
    """Archive one source atomically; source horse IDs need explicit existing entries.

    Format: race_id, recorded_at (nullable), execution_mode, turns, selections.
    Turns require turn_id, agent_id, horse_id (nullable), stage, text. Additional
    source keys are preserved, never interpreted as verified claims. Imports are
    UNKNOWN unless the declared meeting time is demonstrably after race cutoff.
    Even a claimed earlier timestamp cannot establish PRE availability.
    """
    text(source_ref, 'source_ref'); imported = stamp(imported_at)
    document = _document(source_bytes)
    race_id = text(document.get('race_id'), 'race_id')
    mode = document.get('execution_mode', 'UNKNOWN')
    if mode not in MODES: raise ValueError('unsupported execution mode')
    occurred = document.get('recorded_at')
    if occurred is not None and stamp(occurred) > imported:
        raise ValueError('recorded_at after import receipt')
    turns = document.get('turns')
    selections = document.get('selections', [])
    if not isinstance(turns, list) or not turns: raise ValueError('nonempty source turns required')
    if not isinstance(selections, list): raise ValueError('explicit selections list required')
    by_id = {}; source_horses = set()
    for turn in turns:
        if not isinstance(turn, dict): raise ValueError('turn object required')
        tid = text(turn.get('turn_id'), 'turn_id')
        if tid in by_id: raise ValueError('duplicate turn_id')
        text(turn.get('agent_id'), 'agent_id'); text(turn.get('text'), 'turn text')
        if turn.get('stage') not in {'INTRO','QUESTION','INITIAL','RESPONSE','FINAL'}:
            raise ValueError('explicit source stage required')
        horse = turn.get('horse_id')
        if horse is not None: source_horses.add(text(horse, 'source horse_id'))
        by_id[tid] = turn
    if not isinstance(horse_map, dict) or set(horse_map) != source_horses:
        raise ValueError('exact explicit horse mapping required')
    if any(not isinstance(h,str) or not h for h in horse_map.values()) or len(set(horse_map.values())) != len(horse_map):
        raise ValueError('ambiguous horse mapping')
    selected = set(); top_agents = set()
    for selection in selections:
        if not isinstance(selection,dict) or set(selection) != {'agent_id','horse_id','turn_id','selection'}:
            raise ValueError('selection fields mismatch')
        turn = by_id.get(selection['turn_id'])
        if (turn is None or turn['stage'] != 'FINAL' or selection['horse_id'] is None or
                selection['horse_id'] != turn.get('horse_id') or selection['agent_id'] != turn['agent_id'] or
                selection['selection'] not in SELECTIONS or selection['turn_id'] in selected):
            raise ValueError('selection must bind to an explicit FINAL turn')
        selected.add(selection['turn_id'])
        if selection['selection'] == 'TOP_PICK':
            if selection['agent_id'] in top_agents: raise ValueError('multiple TOP_PICK for one agent')
            top_agents.add(selection['agent_id'])
    conn = store.connection
    race = conn.execute('SELECT * FROM races WHERE id=?',(race_id,)).fetchone()
    if race is None: raise ValueError('missing exact race identity')
    metadata = json.loads(race['metadata_json'])
    if digest(metadata) != race['content_hash']: raise ValueError('race integrity mismatch')
    bindings = {}
    for source_horse, db_horse in horse_map.items():
        entry = conn.execute('SELECT * FROM entries WHERE race_id=? AND horse_id=?',(race_id,db_horse)).fetchone()
        if entry is None: raise ValueError('mapped horse missing exact race entry')
        body = {k:entry[k] for k in ('race_id','horse_no','horse_id','jockey_id','frame_no')}
        body['details'] = json.loads(entry['details_json'])
        if digest(body) != entry['content_hash']: raise ValueError('entry integrity mismatch')
        bindings[source_horse] = {'horse_id':db_horse,'entry_id':entry['id'],'entry_hash':entry['content_hash']}
    phase = 'UNKNOWN'
    if metadata.get('cutoff') is not None and occurred is not None:
        if stamp(occurred) > stamp(metadata['cutoff']): phase = 'POST'
    source_hash = sha256(source_bytes).hexdigest()
    payload = {'schema':'prism.records.legacy-dialogue/v1','source_ref':source_ref,
               'source_sha256':source_hash,'source_text_utf8':source_bytes.decode('utf-8'),
               'document':document,'bindings':bindings,
               'race_content_hash':race['content_hash'],'imported_at':imported_at,
               'phase':phase,'source_authenticity_verified':False,
               'independent_execution_verified':False,'training_achievement_verified':False,
               'historical_pre_availability_verified':False}
    record_id = 'legacy_dialogue_' + digest([source_ref,source_hash,race_id])
    with store.transaction():
        # execute individual DDL statements; executescript would commit an outer transaction.
        for statement in SCHEMA.split(';'):
            if statement.strip(): conn.execute(statement)
        for statement in IMMUTABILITY_TRIGGERS:
            conn.execute(statement)
        old = conn.execute('SELECT * FROM legacy_dialogue_imports WHERE id=?',(record_id,)).fetchone()
        if old:
            previous=json.loads(old['payload_json'])
            # Idempotent reruns keep the first import receipt, not a later invented timestamp.
            expected={**payload,'imported_at':previous['imported_at']}
            if digest(previous)!=old['content_hash'] or previous != expected:
                raise ValueError('immutable legacy import conflict')
            inserted=False
        else:
            conn.execute('INSERT INTO legacy_dialogue_imports VALUES(?,?,?,?,?,?,?,?)',
                         (record_id,source_ref,source_hash,imported_at,race_id,phase,encode(payload),digest(payload)))
            inserted=True
    return {'record_id':record_id,'inserted':inserted,'phase':phase,'execution_mode':mode,
            'source_turn_count':len(turns),'explicit_selection_count':len(selections),
            'explicit_top_pick_count':sum(s['selection']=='TOP_PICK' for s in selections),
            'pre_assessment_rows':0,'verified_independent_assessments':0}


def legacy_agent_horse_history(store, agent_id, horse_id, *, as_of, current_race_id=None):
    """Read attributed archive history visible by import receipt, never PRE evidence.

    Unknown meeting times remain visible as unknown; callers must not paraphrase
    them as proven pre-race endorsements. Templates/unknown modes are excluded.
    """
    text(agent_id,'agent_id'); text(horse_id,'horse_id'); now=stamp(as_of)
    if store.connection.execute('SELECT id FROM horses WHERE id=?',(horse_id,)).fetchone() is None:
        raise KeyError(horse_id)
    table=store.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='legacy_dialogue_imports'").fetchone()
    records=[]; excluded=0
    if table:
        for row in store.connection.execute('SELECT * FROM legacy_dialogue_imports ORDER BY imported_at,id'):
            payload=json.loads(row['payload_json'])
            if (digest(payload)!=row['content_hash'] or payload.get('imported_at')!=row['imported_at'] or
                    payload.get('source_ref')!=row['source_ref'] or payload.get('source_sha256')!=row['source_sha256'] or
                    payload.get('document',{}).get('race_id')!=row['race_id'] or payload.get('phase')!=row['phase']):
                raise ValueError('legacy history integrity mismatch')
            source=payload.get('source_text_utf8')
            if (not isinstance(source,str) or sha256(source.encode('utf-8')).hexdigest()!=row['source_sha256'] or
                    _document(source.encode('utf-8'))!=payload['document']):
                raise ValueError('legacy original source binding mismatch')
            doc=payload['document']
            if stamp(row['imported_at'])>now or row['race_id']==current_race_id: continue
            race=store.connection.execute('SELECT * FROM races WHERE id=?',(row['race_id'],)).fetchone()
            if race is None or race['content_hash']!=payload['race_content_hash'] or digest(json.loads(race['metadata_json']))!=race['content_hash']:
                raise ValueError('legacy race binding integrity mismatch')
            scheduled,_=race_time(json.loads(race['metadata_json']))
            if scheduled is None or scheduled>=now: continue
            if doc.get('execution_mode','UNKNOWN') not in {'ROLE_SIMULATION','INDEPENDENT_EXECUTION'}:
                excluded+=1; continue
            keys={k for k,v in payload['bindings'].items() if v['horse_id']==horse_id}
            for key in keys:
                bound=payload['bindings'][key]
                entry=store.connection.execute('SELECT * FROM entries WHERE id=?',(bound['entry_id'],)).fetchone()
                if entry is None or entry['horse_id']!=horse_id or entry['race_id']!=row['race_id'] or entry['content_hash']!=bound['entry_hash']:
                    raise ValueError('legacy horse binding integrity mismatch')
                body={k:entry[k] for k in ('race_id','horse_no','horse_id','jockey_id','frame_no')}
                body['details']=json.loads(entry['details_json'])
                if digest(body)!=entry['content_hash']:
                    raise ValueError('legacy entry content integrity mismatch')
            opinions=[t for t in doc['turns'] if t.get('horse_id') in keys and t['agent_id']==agent_id]
            if not opinions: continue
            tids={t['turn_id'] for t in opinions}
            records.append({'record_id':row['id'],'race_id':row['race_id'],'source_ref':row['source_ref'],
                'source_sha256':row['source_sha256'],'recorded_at':doc.get('recorded_at'),
                'imported_at':row['imported_at'],'phase':row['phase'],'execution_mode':doc['execution_mode'],
                'history_type':'ARCHIVED_ATTRIBUTION_NOT_PRE_EVIDENCE','opinions':opinions,
                'explicit_selections':[s for s in doc.get('selections',[]) if s['turn_id'] in tids],
                'source_authenticity_verified':False,'independent_execution_verified':False})
    result={'schema':'prism.records.legacy-agent-history/v1','agent_id':agent_id,'horse_id':horse_id,
            'as_of':as_of,'current_race_id':current_race_id,'records':records,'excluded_template_or_unknown_mode':excluded,
            'pre_evidence_allowed':False,'automatic_current_selection_allowed':False,
            'historical_pre_availability_verified':False,'training_achievement_verified':False}
    result['history_hash']=digest(result)
    return result
