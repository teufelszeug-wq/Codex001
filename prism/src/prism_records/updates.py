"""Append-only, source-versioned entity facts and point-in-time selection.

Callers must verify source authenticity. Names never resolve an entity identity.
Retirement is a relation on a new version, never a rewrite of an old fact.
"""
from datetime import datetime
import json
import re
import sqlite3

from .store import digest, encode, text


DDL = '''
CREATE TABLE IF NOT EXISTS entity_fact_versions (
 id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 race_id TEXT NOT NULL REFERENCES races(id), fact_key TEXT NOT NULL,
 source_ref TEXT NOT NULL, versioned_source_ref TEXT NOT NULL,
 schema_id TEXT NOT NULL, payload_json TEXT NOT NULL, content_hash TEXT NOT NULL,
 available_at TEXT, recorded_at TEXT NOT NULL, temporal_class TEXT NOT NULL,
 phase TEXT NOT NULL, review_status TEXT NOT NULL,
 prior_id TEXT REFERENCES entity_fact_versions(id), observation_id TEXT REFERENCES observations(id),
 integrity_hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS fact_subject ON entity_fact_versions(subject_type,entity_id,race_id,fact_key);
CREATE TRIGGER IF NOT EXISTS fact_no_update BEFORE UPDATE ON entity_fact_versions
BEGIN SELECT RAISE(ABORT,'fact versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS fact_no_delete BEFORE DELETE ON entity_fact_versions
BEGIN SELECT RAISE(ABORT,'fact versions are immutable'); END;
'''


def instant(value, label):
    text(value, label)
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError(label+' requires a timezone')
    return dt


class SourceUpdates:
    """Read versions without DDL; create the ledger lazily on first append.

    ``current`` is the authoritative view for revised facts. The base store's
    observation list intentionally preserves superseded observations and must
    not be used as a list of currently accepted values.
    """

    def __init__(self, store):
        self.store = store
        self.conn = store.connection

    def _has_schema(self):
        return self.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                 "AND name='entity_fact_versions'").fetchone() is not None

    def ensure_schema(self):
        if self._has_schema():
            return
        if self.conn.in_transaction:
            raise ValueError('initialize update schema outside a record transaction')
        try:
            self.conn.executescript(DDL)
        except sqlite3.OperationalError as exc:
            raise ValueError('append requires a writable RecordStore') from exc

    def append(self, *, subject_type, entity_id, race_id, fact_key, payload,
               source_ref, schema_id, recorded_at, available_at=None,
               temporal_class='UNKNOWN_TIMESTAMP', phase='UNKNOWN',
               prior_id=None, correction=False):
        self.ensure_schema()
        # Even cached appends are mutations by API contract. A zero-row write
        # checks the SQLite connection's actual permissions without changing a
        # version, relying on an absent RecordStore.read_only flag, or guessing
        # permissions from the file's mode bits.
        try:
            self.conn.execute('UPDATE entity_fact_versions SET id=id WHERE 0')
        except sqlite3.OperationalError as exc:
            raise ValueError('append requires a writable RecordStore') from exc
        if subject_type not in {'HORSE', 'JOCKEY'}:
            raise ValueError('subject_type must be HORSE or JOCKEY')
        for label, value in [('entity_id', entity_id), ('race_id', race_id),
                             ('fact_key', fact_key), ('source_ref', source_ref), ('schema_id', schema_id)]:
            text(value, label)
        if not isinstance(payload, dict):
            raise ValueError('payload must be an object')
        if type(correction) is not bool:
            raise ValueError('correction must be boolean')
        recorded = instant(recorded_at, 'recorded_at')
        available = instant(available_at, 'available_at') if available_at else None
        if available and available > recorded:
            raise ValueError('recorded_at cannot precede availability')
        column = 'horse_id' if subject_type == 'HORSE' else 'jockey_id'
        entry = self.conn.execute('SELECT * FROM entries WHERE race_id=? AND '+column+'=?',
                                  (race_id, entity_id)).fetchone()
        if entry is None:
            raise ValueError('fact requires matching entity race entry')
        for key, expected in [('race_id', race_id), (column, entity_id),
                              ('available_at', available_at), ('phase', phase),
                              ('temporal_class', temporal_class), ('schema', schema_id)]:
            if key in payload and payload[key] != expected:
                raise ValueError('fact payload binding mismatch: '+key)
        if 'horse_no' in payload and (subject_type != 'HORSE' or payload['horse_no'] != entry['horse_no']):
            raise ValueError('horse number requires exact horse identity')
        if subject_type == 'JOCKEY' and ('horse_id' in payload or 'horse_identity' in payload):
            raise ValueError('jockey-level fact must not imply a specific horse identity')
        if subject_type == 'HORSE' and 'jockey_id' in payload and payload['jockey_id'] != entry['jockey_id']:
            raise ValueError('fact jockey binding mismatch')
        if subject_type == 'JOCKEY' and 'jockey_identity' in payload:
            jockey = self.conn.execute('SELECT * FROM jockeys WHERE id=?', (entity_id,)).fetchone()
            identity_value = payload['jockey_identity']
            if isinstance(identity_value, dict):
                for key, expected in [('jockey_id', entity_id), ('source_key', jockey['source_key']),
                                      ('canonical_id', jockey['canonical_id'])]:
                    if key in identity_value and identity_value[key] != expected:
                        raise ValueError('jockey identity mismatch')
            elif identity_value not in {entity_id, jockey['source_key'], jockey['canonical_id']}:
                raise ValueError('jockey identity mismatch')
        cutoff = json.loads(self.conn.execute('SELECT metadata_json FROM races WHERE id=?',
                                             (race_id,)).fetchone()[0]).get('cutoff')
        cutoff_dt = instant(cutoff, 'cutoff') if cutoff else None
        if phase not in {'PRE', 'POST', 'UNKNOWN'}:
            raise ValueError('invalid phase')
        if temporal_class == 'UNKNOWN_TIMESTAMP':
            if available is not None or phase == 'PRE':
                raise ValueError('unknown timestamp cannot establish PRE')
        elif temporal_class == 'PRE_AVAILABLE':
            if phase != 'PRE' or available is None or cutoff_dt is None or available > cutoff_dt:
                raise ValueError('PRE requires available-before-cutoff evidence')
        elif temporal_class == 'POST_ONLY':
            if phase != 'POST' or (available and cutoff_dt and available < cutoff_dt):
                raise ValueError('invalid POST timing')
        elif temporal_class == 'LATE_PRE':
            if phase != 'UNKNOWN' or available is None or cutoff_dt is None or available <= cutoff_dt:
                raise ValueError('invalid late availability')
        else:
            raise ValueError('invalid temporal class')
        if phase == 'PRE' and temporal_class != 'PRE_AVAILABLE':
            raise ValueError('PRE requires PRE_AVAILABLE')
        forbidden = {'result','results','post_result','finish_position','actual_finish','payouts',
                     'win_payout_per_100_yen','winners','winner','settlement','refund_yen','payout_yen',
                     'payout_excluding_refund_yen','profit_yen','win_payouts','refund_keys','target_result',
                     'official_result','finish_order'}
        if phase == 'PRE' and any(part in forbidden for part in re.split(r'[./:]', fact_key.lower())):
            raise ValueError('result-bearing PRE fact key rejected')
        def check_pre(value):
            if isinstance(value, dict):
                if set(value) & forbidden:
                    raise ValueError('result-bearing PRE fact rejected')
                if value.get('phase', 'PRE') != 'PRE' or value.get('temporal_class', 'PRE_AVAILABLE') != 'PRE_AVAILABLE':
                    raise ValueError('unknown or post source cannot become PRE')
                if value.get('mode') == 'HISTORICAL_RECONSTRUCTION':
                    raise ValueError('reconstruction cannot become PRE')
                if 'available_at' in value and (value['available_at'] is None or
                        instant(value['available_at'], 'nested available_at') > cutoff_dt):
                    raise ValueError('nested source cannot establish PRE')
                for child in value.values(): check_pre(child)
            elif isinstance(value, list):
                for child in value: check_pre(child)
        if phase == 'PRE': check_pre(payload)
        content_hash = digest({'schema': schema_id, 'payload': payload})
        version_hash = digest([content_hash, available_at, temporal_class, phase])
        versioned_ref = source_ref+'#prism-version='+version_hash
        identity = 'fact_'+digest([subject_type, entity_id, race_id, fact_key, versioned_ref])
        with self.store.transaction():
            old = self.conn.execute('SELECT * FROM entity_fact_versions WHERE id=?', (identity,)).fetchone()
            if old:
                self._verified(old)
                if prior_id is not None and old['prior_id'] != prior_id:
                    raise ValueError('cached fact has a different prior binding')
                return {'status': 'CACHE_HIT', 'version': self.store._decode(old)}
            stream = self.history(subject_type, entity_id, race_id, fact_key)
            prior = next((r for r in stream if r['id'] == prior_id), None) if prior_id else None
            if prior_id and prior is None:
                raise ValueError('prior must belong to same entity, race and fact')
            if correction and prior is None:
                raise ValueError('correction requires explicit prior version')
            if prior is None:
                own = [r for r in stream if r['source_ref'] == source_ref and r['review_status'] == 'ACCEPTED']
                prior = own[-1] if own else None
            if prior:
                if recorded < instant(prior['recorded_at'], 'prior recorded_at'):
                    raise ValueError('update cannot precede its prior')
                if prior['temporal_class'] != 'PRE_AVAILABLE' and phase == 'PRE':
                    raise ValueError('non-PRE prior cannot be promoted to PRE')
                if prior['review_status'] != 'ACCEPTED' and not correction:
                    raise ValueError('pending prior needs explicit correction review')
                retired = {r['prior_id'] for r in stream if r['review_status'] == 'ACCEPTED' and r['prior_id']}
                if prior['id'] in retired:
                    raise ValueError('prior version has already been retired')
            current = self.current(subject_type, entity_id, race_id, fact_key, as_of=recorded_at,
                                   include_unknown=True)
            conflicts = [r for r in current if r['content_hash'] != content_hash and
                         r['id'] != (prior['id'] if prior else None)]
            status = 'PENDING_CONFLICT' if conflicts else 'ACCEPTED'
            if 'review_status' in payload and payload['review_status'] != status:
                raise ValueError('payload review status contradicts computed review')
            observation_id = None
            if subject_type == 'HORSE' and status == 'ACCEPTED':
                observation_id = self.store.add_observation(entity_id, race_id,
                    {**payload, 'phase': phase}, versioned_ref, available_at, temporal_class)
            values = dict(id=identity, subject_type=subject_type, entity_id=entity_id, race_id=race_id,
                          fact_key=fact_key, source_ref=source_ref, versioned_source_ref=versioned_ref,
                          schema_id=schema_id, payload_json=encode(payload), content_hash=content_hash,
                          available_at=available_at, recorded_at=recorded_at, temporal_class=temporal_class,
                          phase=phase, review_status=status, prior_id=prior['id'] if prior else None,
                          observation_id=observation_id)
            values['integrity_hash'] = digest(values)
            self.store._immutable('entity_fact_versions', values)
            before = prior['payload'] if prior else {}
            changes = {key: {'before': before.get(key), 'after': payload.get(key),
                             'before_present': key in before, 'after_present': key in payload}
                       for key in sorted(set(before) | set(payload))
                       if (key in before) != (key in payload) or before.get(key) != payload.get(key)}
            return {'status': status, 'changed': prior is not None and prior['content_hash'] != content_hash,
                    'changes': changes,
                    'retired_version_id': prior['id'] if prior and status == 'ACCEPTED' else None,
                    'conflicting_version_ids': [r['id'] for r in conflicts],
                    'version': self.store._decode(self.conn.execute(
                        'SELECT * FROM entity_fact_versions WHERE id=?', (identity,)).fetchone())}

    def history(self, subject_type, entity_id, race_id, fact_key):
        if not self._has_schema():
            return []
        rows = self.conn.execute('SELECT * FROM entity_fact_versions WHERE subject_type=? AND entity_id=? '
                                 'AND race_id=? AND fact_key=? ORDER BY rowid',
                                 (subject_type, entity_id, race_id, fact_key)).fetchall()
        return [self._verified(row) for row in rows]

    def _verified(self, row):
        values = dict(row)
        expected = values.pop('integrity_hash')
        if expected != digest(values):
            raise ValueError('fact ledger integrity mismatch')
        return self.store._decode(row)

    @staticmethod
    def _current_rows(rows, at, include_unknown=False):
        rows = [r for r in rows if instant(r['recorded_at'], 'recorded_at') <= at and
                ((r['available_at'] is not None and instant(r['available_at'], 'available_at') <= at)
                 or (include_unknown and r['available_at'] is None))]
        accepted = [r for r in rows if r['review_status'] == 'ACCEPTED']
        retired = {r['prior_id'] for r in accepted if r['prior_id']}
        return [r for r in accepted if r['id'] not in retired]

    def observation_selection(self, horse_ids, *, as_of):
        """Read and verify managed observations once for an entire race roster.

        Returns (all managed observation IDs, IDs accepted at the requested time).
        Legacy observations absent from the ledger are left to existing guards.
        """
        at = instant(as_of, 'as_of')
        horse_ids = sorted(set(horse_ids))
        if not horse_ids or not self._has_schema():
            return set(), set()
        records = self.conn.execute("SELECT * FROM entity_fact_versions WHERE subject_type='HORSE' "
            'AND entity_id IN ('+','.join('?' for _ in horse_ids)+') ORDER BY rowid', horse_ids).fetchall()
        rows = [self._verified(row) for row in records]
        managed = {r['observation_id'] for r in rows if r['observation_id']}
        groups = {}
        for row in rows:
            groups.setdefault((row['entity_id'], row['race_id'], row['fact_key']), []).append(row)
        selected = {r['observation_id'] for group in groups.values()
                    for r in self._current_rows(group, at) if r['observation_id']}
        return managed, selected

    def current(self, subject_type, entity_id, race_id, fact_key, *, as_of, include_unknown=False):
        at = instant(as_of, 'as_of')
        return self._current_rows(self.history(subject_type, entity_id, race_id, fact_key), at, include_unknown)
