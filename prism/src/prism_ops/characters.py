"""Freeze supplied Notion character records without inventing persona settings.

Hashes establish snapshot integrity, not the truth of a source or its timestamp.
The caller must fetch the canonical database before building this snapshot.
"""
from copy import deepcopy
from urllib.parse import urlparse

from prism_engine.contracts import digest, timestamp


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + ' required')
    return value


def _notion_url(value):
    parsed = urlparse(_text(value, 'Notion source URL'))
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or parsed.username or parsed.password or
            not (host in {'notion.so', 'www.notion.so', 'app.notion.com'} or host.endswith('.notion.site')) or
            not parsed.path.strip('/')):
        raise ValueError('explicit Notion page/database URL required')
    return value


def _record(value):
    required = {'agent_id', 'name', 'role', 'configuration', 'source_page_url'}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError('character record fields rejected')
    record = deepcopy(value)
    for field in ('agent_id', 'name', 'role'):
        _text(record[field], field)
    _notion_url(record['source_page_url'])
    config = record['configuration']
    if not isinstance(config, (dict, str)) or not config:
        raise ValueError('canonical character configuration required')
    if isinstance(config, str) and not config.strip():
        raise ValueError('canonical character configuration required')
    digest(record)  # Reject non-JSON and non-finite configuration values.
    return record


def build_character_snapshot(records, *, source_url, captured_at):
    _notion_url(source_url)
    timestamp(captured_at)
    if not isinstance(records, list) or not records:
        raise ValueError('canonical character records required')
    checked = [_record(value) for value in records]
    if len({r['agent_id'] for r in checked}) != len(checked):
        raise ValueError('duplicate character identity')
    if len({r['source_page_url'] for r in checked}) != len(checked):
        raise ValueError('duplicate character source page')
    snapshot = {'schema': 'prism.characters.snapshot/v1', 'source_url': source_url,
                'captured_at': captured_at, 'records': sorted(checked, key=lambda r: r['agent_id']),
                'source_authenticity_verified': False}
    snapshot['snapshot_hash'] = digest(snapshot)
    return snapshot


def verify_character_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError('character snapshot required')
    expected = build_character_snapshot(snapshot.get('records'), source_url=snapshot.get('source_url'),
                                        captured_at=snapshot.get('captured_at'))
    if snapshot != expected:
        raise ValueError('character snapshot integrity mismatch')
    return True


def get_character(snapshot, agent_id):
    verify_character_snapshot(snapshot)
    selected = next((r for r in snapshot['records'] if r['agent_id'] == agent_id), None)
    if selected is None:
        raise ValueError('character absent from canonical snapshot')
    character = {'schema': 'prism.character/v1', **deepcopy(selected),
                 'character_snapshot_hash': snapshot['snapshot_hash'],
                 'snapshot_source_url': snapshot['source_url'],
                 'snapshot_captured_at': snapshot['captured_at']}
    character['character_hash'] = digest(character)
    return character


def verify_character(character):
    required = {'schema', 'agent_id', 'name', 'role', 'configuration', 'source_page_url',
                'character_snapshot_hash', 'snapshot_source_url', 'snapshot_captured_at', 'character_hash'}
    if not isinstance(character, dict) or set(character) != required:
        raise ValueError('sealed character required')
    if character['schema'] != 'prism.character/v1':
        raise ValueError('character schema rejected')
    _record({k: character[k] for k in ('agent_id', 'name', 'role', 'configuration', 'source_page_url')})
    _notion_url(character['snapshot_source_url'])
    timestamp(character['snapshot_captured_at'])
    if (not isinstance(character['character_snapshot_hash'], str) or
            len(character['character_snapshot_hash']) != 64 or
            character['character_hash'] != digest({k: v for k, v in character.items() if k != 'character_hash'})):
        raise ValueError('character integrity mismatch')
    return True
