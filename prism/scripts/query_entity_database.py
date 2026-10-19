"""Read-only horse/jockey lookup. Output includes POST/UNKNOWN history, not PRE features."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from prism_records import RecordStore


def query(path, kind=None, search=None, entity_id=None, limit=20,
          agent_id=None, as_of=None, current_race_id=None):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be 1..100')
    if kind not in {None, 'horse', 'jockey'}:
        raise ValueError('unknown entity kind')
    if (search is not None or entity_id is not None) and kind is None:
        raise ValueError('entity kind required')
    if search is not None and entity_id is not None:
        raise ValueError('choose search or ID')
    if any(x is not None for x in (agent_id, as_of, current_race_id)):
        if kind != 'horse' or entity_id is None or not agent_id or not as_of:
            raise ValueError('agent memory requires horse ID, agent ID and timezone-aware as-of')
    store = RecordStore(path, read_only=True)
    try:
        if kind is None:
            return store.summary()
        if entity_id is not None:
            profile = store.horse_profile(entity_id) if kind == 'horse' else store.jockey_profile(entity_id)
            if agent_id is not None:
                from prism_records.memory import agent_horse_memory
                profile['agent_memory'] = agent_horse_memory(store, agent_id, entity_id, as_of, current_race_id, limit)
            return profile
        table, relation = ('horses', 'horse_id') if kind == 'horse' else ('jockeys', 'jockey_id')
        if search is not None and not isinstance(search, str):
            raise ValueError('search must be text')
        pattern = (search or '').replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        rows = store.connection.execute(
            'SELECT id,display_name,identity_status,canonical_id,'
            '(SELECT COUNT(*) FROM entries e WHERE e.' + relation + '=m.id) AS entry_count '
            'FROM ' + table + ' m WHERE display_name LIKE ? ESCAPE \'\\\' '
            'ORDER BY display_name,id LIMIT ?', ('%' + pattern + '%', limit)).fetchall()
        return {'schema': 'prism.records.search/v1', 'kind': kind,
                'matches': [dict(row) for row in rows], 'limit': limit,
                'source_authenticity_verified': False,
                'note': 'Names are lookup labels, not canonical identity proof. History includes POST and unknown-time data.'}
    finally:
        store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--kind', choices=('horse', 'jockey'))
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--search'); target.add_argument('--id')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--agent-id'); parser.add_argument('--as-of'); parser.add_argument('--current-race')
    args = parser.parse_args()
    print(json.dumps(query(args.db, args.kind, args.search, args.id, args.limit,
                           args.agent_id, args.as_of, args.current_race), ensure_ascii=False, indent=2))
