"""Immutable, source-scoped horse/jockey records with atomic imports.

Identity integrity is not source authenticity or historical availability proof.
Source-scoped provisional identities are never merged using names alone.
"""
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(encode(value).encode()).hexdigest()


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label+' must be nonempty text')
    return value


SCHEMA = '''
CREATE TABLE IF NOT EXISTS horses (
 id TEXT PRIMARY KEY, source_key TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
 canonical_id TEXT UNIQUE, identity_status TEXT NOT NULL CHECK(identity_status IN ('PROVISIONAL','CANONICAL')),
 profile_json TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jockeys (
 id TEXT PRIMARY KEY, source_key TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
 canonical_id TEXT UNIQUE, identity_status TEXT NOT NULL CHECK(identity_status IN ('PROVISIONAL','CANONICAL')),
 profile_json TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entity_sources (
 kind TEXT NOT NULL CHECK(kind IN ('horses','jockeys')), source_key TEXT NOT NULL,
 entity_id TEXT NOT NULL, PRIMARY KEY(kind, source_key));
CREATE TABLE IF NOT EXISTS races (
 id TEXT PRIMARY KEY, metadata_json TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entries (
 id TEXT PRIMARY KEY, race_id TEXT NOT NULL REFERENCES races(id), horse_no INTEGER NOT NULL CHECK(horse_no>0),
 horse_id TEXT NOT NULL REFERENCES horses(id), jockey_id TEXT REFERENCES jockeys(id),
 frame_no INTEGER CHECK(frame_no BETWEEN 1 AND 8), details_json TEXT NOT NULL, content_hash TEXT NOT NULL,
 UNIQUE(race_id,horse_no), UNIQUE(race_id,horse_id));
CREATE TABLE IF NOT EXISTS observations (
 id TEXT PRIMARY KEY, horse_id TEXT NOT NULL REFERENCES horses(id), race_id TEXT NOT NULL REFERENCES races(id),
 payload_json TEXT NOT NULL, source_ref TEXT NOT NULL, available_at TEXT,
 temporal_class TEXT NOT NULL, phase TEXT NOT NULL CHECK(phase IN ('PRE','POST','UNKNOWN')),
 mode TEXT NOT NULL, content_hash TEXT NOT NULL,
 FOREIGN KEY(race_id,horse_id) REFERENCES entries(race_id,horse_id));
CREATE TABLE IF NOT EXISTS discussions (
 id TEXT PRIMARY KEY, race_id TEXT NOT NULL REFERENCES races(id),
 phase TEXT NOT NULL CHECK(phase IN ('PRE','POST','UNKNOWN')), occurred_at TEXT,
 mode TEXT NOT NULL, prediction_hash TEXT, payload_json TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assessments (
 id TEXT PRIMARY KEY, discussion_id TEXT NOT NULL REFERENCES discussions(id),
 entry_id TEXT REFERENCES entries(id), horse_id TEXT REFERENCES horses(id), jockey_id TEXT REFERENCES jockeys(id),
 subject_type TEXT NOT NULL DEFAULT 'HORSE' CHECK(subject_type IN ('HORSE','JOCKEY')),
 phase TEXT NOT NULL CHECK(phase IN ('PRE','POST','UNKNOWN')), mode TEXT NOT NULL, prediction_hash TEXT,
 agent_id TEXT NOT NULL, turn_id TEXT NOT NULL, claim_type TEXT NOT NULL,
 verified_independent INTEGER NOT NULL DEFAULT 0 CHECK(verified_independent IN (0,1)),
 training_achievement_verified INTEGER NOT NULL DEFAULT 0 CHECK(training_achievement_verified IN (0,1)),
 payload_json TEXT NOT NULL, content_hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS entries_horse ON entries(horse_id,race_id);
CREATE INDEX IF NOT EXISTS entries_jockey ON entries(jockey_id,race_id);
CREATE INDEX IF NOT EXISTS observations_horse ON observations(horse_id,race_id);
CREATE INDEX IF NOT EXISTS observations_race ON observations(race_id);
CREATE INDEX IF NOT EXISTS discussions_race ON discussions(race_id,phase);
CREATE INDEX IF NOT EXISTS assessments_horse ON assessments(horse_id,discussion_id);
CREATE INDEX IF NOT EXISTS assessments_jockey ON assessments(jockey_id,discussion_id);
CREATE INDEX IF NOT EXISTS assessments_entry ON assessments(entry_id);
CREATE INDEX IF NOT EXISTS assessments_discussion ON assessments(discussion_id);
CREATE TRIGGER IF NOT EXISTS assessment_entry_integrity BEFORE INSERT ON assessments
WHEN NEW.entry_id IS NOT NULL
BEGIN
 SELECT CASE WHEN NOT EXISTS (
  SELECT 1 FROM entries e JOIN discussions d ON d.id=NEW.discussion_id
  WHERE e.id=NEW.entry_id AND e.race_id=d.race_id
  AND (NEW.horse_id IS NULL OR NEW.horse_id=e.horse_id)
  AND (NEW.jockey_id IS NULL OR NEW.jockey_id=e.jockey_id)
 ) THEN RAISE(ABORT,'assessment entry identity mismatch') END;
END;
'''


class RecordStore:
    def __init__(self, path, read_only=False):
        if read_only and str(path)==':memory:': raise ValueError('read-only database requires a file')
        if str(path) != ':memory:' and not read_only:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        target=Path(path).resolve().as_uri()+'?mode=ro' if read_only else str(path)
        self.connection = sqlite3.connect(target, isolation_level=None, uri=read_only)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys=ON')
        if not read_only: self.connection.executescript(SCHEMA)
        self.conn = self.connection
        self._transaction_counter = 0

    def close(self):
        self.connection.close()

    @contextmanager
    def transaction(self):
        self._transaction_counter += 1
        savepoint = 'records_'+str(self._transaction_counter)
        self.connection.execute('SAVEPOINT '+savepoint)
        try:
            yield self
        except BaseException:
            self.connection.execute('ROLLBACK TO '+savepoint)
            self.connection.execute('RELEASE '+savepoint)
            raise
        else:
            self.connection.execute('RELEASE '+savepoint)

    def _immutable(self, table, values):
        # Table names originate from this module, never user input.
        old = self.connection.execute('SELECT * FROM '+table+' WHERE id=?',(values['id'],)).fetchone()
        if old:
            if any(old[k] != value for k,value in values.items()):
                raise ValueError('immutable '+table+' identity has different content')
            return values['id']
        keys = list(values)
        try:
            self.connection.execute('INSERT INTO '+table+' ('+','.join(keys)+') VALUES ('+
                                    ','.join('?' for _ in keys)+')',[values[k] for k in keys])
        except sqlite3.IntegrityError as exc:
            raise ValueError('record relationship or immutable identity rejected') from exc
        return values['id']

    def _entity(self, kind, source_key, display_name, profile, canonical_id):
        text(source_key,'source_key');text(display_name,'display_name')
        if profile is None: profile = {}
        if not isinstance(profile,dict): raise ValueError('profile must be an object')
        if canonical_id is not None: text(canonical_id,'canonical_id')
        identity = [kind,'CANONICAL',canonical_id] if canonical_id is not None else [kind,'SOURCE',source_key]
        entity_id = kind[:-1]+'_'+digest(identity)
        content = {'display_name':display_name,'canonical_id':canonical_id,'profile':profile}
        with self.transaction():
            alias = self.connection.execute('SELECT entity_id FROM entity_sources WHERE kind=? AND source_key=?',
                                            (kind,source_key)).fetchone()
            if alias and alias['entity_id'] != entity_id:
                raise ValueError('source identity cannot be remapped')
            old = self.connection.execute('SELECT * FROM '+kind+' WHERE id=?',(entity_id,)).fetchone()
            if old:
                if old['content_hash'] != digest(content):
                    raise ValueError('immutable entity identity has different content')
            else:
                self._immutable(kind, {'id':entity_id,'source_key':source_key,'display_name':display_name,
                    'canonical_id':canonical_id,'identity_status':'CANONICAL' if canonical_id is not None else 'PROVISIONAL',
                    'profile_json':encode(profile),'content_hash':digest(content)})
            if not alias:
                self.connection.execute('INSERT INTO entity_sources(kind,source_key,entity_id) VALUES(?,?,?)',
                                        (kind,source_key,entity_id))
        return entity_id

    def add_horse(self, source_key, display_name, profile=None, canonical_id=None):
        return self._entity('horses',source_key,display_name,profile,canonical_id)

    def add_jockey(self, source_key, display_name, profile=None, canonical_id=None):
        return self._entity('jockeys',source_key,display_name,profile,canonical_id)

    def add_race(self, race_id, metadata):
        text(race_id,'race_id')
        if not isinstance(metadata,dict): raise ValueError('metadata must be an object')
        with self.transaction():
            return self._immutable('races',{'id':race_id,'metadata_json':encode(metadata),'content_hash':digest(metadata)})

    def add_entry(self, race_id, horse_no, horse_id, jockey_id=None, frame_no=None, details=None):
        if type(horse_no) is not int or horse_no<1: raise ValueError('invalid horse number')
        if frame_no is not None and (type(frame_no) is not int or not 1<=frame_no<=8):
            raise ValueError('invalid frame number')
        if details is None: details={}
        if not isinstance(details,dict): raise ValueError('details must be an object')
        content={'race_id':race_id,'horse_no':horse_no,'horse_id':horse_id,'jockey_id':jockey_id,
                 'frame_no':frame_no,'details':details}
        with self.transaction():
            return self._immutable('entries',{'id':'entry_'+digest([race_id,horse_no]),'race_id':race_id,
                'horse_no':horse_no,'horse_id':horse_id,'jockey_id':jockey_id,'frame_no':frame_no,
                'details_json':encode(details),'content_hash':digest(content)})

    def add_observation(self, horse_id, race_id, payload, source_ref, available_at=None,
                        temporal_class='UNKNOWN_TIMESTAMP'):
        if not isinstance(payload,dict): raise ValueError('payload must be an object')
        text(source_ref,'source_ref');text(temporal_class,'temporal_class')
        entry=self.connection.execute('SELECT e.*,h.canonical_id,h.source_key FROM entries e '
            'JOIN horses h ON h.id=e.horse_id WHERE e.race_id=? AND e.horse_id=?',(race_id,horse_id)).fetchone()
        if entry is None: raise ValueError('observation requires matching race entry')
        for key, expected in (('race_id',race_id),('horse_id',horse_id),('horse_no',entry['horse_no']),
                              ('available_at',available_at),('temporal_class',temporal_class)):
            if key in payload and payload[key] != expected:
                raise ValueError('observation payload/argument binding mismatch: '+key)
        identity=payload.get('horse_identity')
        if isinstance(identity,dict):
            for key,expected in (('horse_id',horse_id),('horse_no',entry['horse_no']),
                                 ('canonical_id',entry['canonical_id']),('source_key',entry['source_key'])):
                if key in identity and identity[key] is not None and identity[key]!=expected:
                    raise ValueError('observation horse identity mismatch')
        elif identity is not None and identity not in {horse_id,entry['canonical_id'],entry['source_key']}:
            raise ValueError('observation horse identity mismatch')
        if available_at is not None:
            if not isinstance(available_at,str) or datetime.fromisoformat(available_at.replace('Z','+00:00')).tzinfo is None:
                raise ValueError('available_at requires a timezone')
        phase=payload.get('phase','UNKNOWN');mode=payload.get('mode','UNSPECIFIED')
        if phase not in {'PRE','POST','UNKNOWN'}: raise ValueError('invalid observation phase')
        text(mode,'mode')
        if temporal_class not in {'UNKNOWN_TIMESTAMP','PRE_AVAILABLE','LATE_PRE','POST_ONLY'}:
            raise ValueError('invalid temporal class')
        race=self.connection.execute('SELECT metadata_json FROM races WHERE id=?',(race_id,)).fetchone()
        if race is None: raise ValueError('unknown observation race')
        cutoff=json.loads(race['metadata_json']).get('cutoff')
        cutoff_dt=None
        if cutoff is not None:
            cutoff_dt=datetime.fromisoformat(cutoff.replace('Z','+00:00'))
            if cutoff_dt.tzinfo is None: raise ValueError('race cutoff requires a timezone')
        available_dt=datetime.fromisoformat(available_at.replace('Z','+00:00')) if available_at else None
        if temporal_class=='UNKNOWN_TIMESTAMP' and (available_at is not None or phase=='PRE'):
            raise ValueError('unknown timestamp cannot establish PRE availability')
        if phase=='PRE' or temporal_class=='PRE_AVAILABLE':
            if (phase!='PRE' or temporal_class!='PRE_AVAILABLE' or available_dt is None or
                    cutoff_dt is None or available_dt>cutoff_dt):
                raise ValueError('PRE requires explicit available-before-cutoff evidence metadata')
            forbidden={'result','results','post_result','finish_position','actual_finish','payouts','win_payout_per_100_yen',
                       'winners','winner','settlement','refund_yen','payout_yen','payout_excluding_refund_yen',
                       'profit_yen','win_payouts','refund_keys','target_result','official_result','finish_order'}
            def reject_results(value):
                if isinstance(value,dict):
                    if set(value)&forbidden: raise ValueError('result-bearing PRE observation rejected')
                    if 'temporal_class' in value and value['temporal_class']!='PRE_AVAILABLE':
                        raise ValueError('unknown or post source cannot become PRE')
                    if 'available_at' in value:
                        at=value['available_at']
                        if not isinstance(at,str): raise ValueError('unknown source timestamp cannot become PRE')
                        dt=datetime.fromisoformat(at.replace('Z','+00:00'))
                        if dt.tzinfo is None or dt>cutoff_dt:
                            raise ValueError('source timestamp cannot establish PRE')
                    if value.get('phase') in {'POST','UNKNOWN'} or value.get('mode')=='HISTORICAL_RECONSTRUCTION':
                        raise ValueError('non-PRE source cannot become PRE')
                    for child in value.values(): reject_results(child)
                elif isinstance(value,list):
                    for child in value: reject_results(child)
            reject_results(payload)
        if temporal_class=='LATE_PRE' and (phase!='UNKNOWN' or available_dt is None or
                                           cutoff_dt is None or available_dt<=cutoff_dt):
            raise ValueError('LATE_PRE requires late availability and UNKNOWN phase')
        if temporal_class=='POST_ONLY' and (phase!='POST' or
                (available_dt is not None and cutoff_dt is not None and available_dt<cutoff_dt)):
            raise ValueError('POST_ONLY timing/phase mismatch')
        content={'horse_id':horse_id,'race_id':race_id,'payload':payload,'source_ref':source_ref,
                 'available_at':available_at,'temporal_class':temporal_class}
        with self.transaction():
            return self._immutable('observations',{'id':'observation_'+digest([horse_id,race_id,source_ref]),
                'horse_id':horse_id,'race_id':race_id,'payload_json':encode(payload),'source_ref':source_ref,
                'available_at':available_at,'temporal_class':temporal_class,'phase':phase,'mode':mode,
                'content_hash':digest(content)})

    @staticmethod
    def _decode(row):
        value=dict(row)
        for key in list(value):
            if key.endswith('_json'):
                value[key[:-5]]=json.loads(value.pop(key))
        return value

    def _profile(self, kind, entity_id):
        entity=self.connection.execute('SELECT * FROM '+kind+' WHERE id=?',(entity_id,)).fetchone()
        if entity is None: raise KeyError(entity_id)
        field='horse_id' if kind=='horses' else 'jockey_id'
        entries=self.connection.execute('SELECT e.*,r.metadata_json AS race_metadata_json FROM entries e '
            'JOIN races r ON r.id=e.race_id WHERE e.'+field+'=? ORDER BY e.race_id,e.horse_no',(entity_id,)).fetchall()
        assessments=self.connection.execute('SELECT a.*,d.race_id,d.occurred_at FROM assessments a '
            'JOIN discussions d ON d.id=a.discussion_id LEFT JOIN entries e ON e.id=a.entry_id '
            'WHERE a.'+field+'=? OR e.'+field+'=? ORDER BY d.race_id,a.id',(entity_id,entity_id)).fetchall()
        if kind=='horses':
            observations=self.connection.execute('SELECT * FROM observations WHERE horse_id=? ORDER BY race_id,id',
                                                 (entity_id,)).fetchall()
        else:
            observations=self.connection.execute('SELECT o.* FROM observations o JOIN entries e '
                'ON e.race_id=o.race_id AND e.horse_id=o.horse_id WHERE e.jockey_id=? ORDER BY o.race_id,o.id',
                (entity_id,)).fetchall()
        subject='HORSE' if kind=='horses' else 'JOCKEY'
        direct=[self._decode(x) for x in assessments if x['subject_type']==subject]
        related=[self._decode(x) for x in assessments if x['subject_type']!=subject]
        return {'entity':self._decode(entity),'entries':[self._decode(x) for x in entries],
                'observations':[self._decode(x) for x in observations],
                'assessments':direct,
                'related_horse_assessments' if kind=='jockeys' else 'related_jockey_assessments':related,
                'source_authenticity_verified':False,'training_achievement_verified':False}

    def horse_profile(self, entity_id): return self._profile('horses',entity_id)

    def jockey_profile(self, entity_id): return self._profile('jockeys',entity_id)

    def summary(self):
        counts={table:self.connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                for table in ('horses','jockeys','races','entries','observations','discussions','assessments')}
        counts['provisional_horses']=self.connection.execute("SELECT COUNT(*) FROM horses WHERE identity_status='PROVISIONAL'").fetchone()[0]
        counts['provisional_jockeys']=self.connection.execute("SELECT COUNT(*) FROM jockeys WHERE identity_status='PROVISIONAL'").fetchone()[0]
        return {'schema':'prism.records.summary/v1','counts':counts,'name_only_canonical_merge':False,
                'source_authenticity_verified':False,'training_achievement_verified':False}
