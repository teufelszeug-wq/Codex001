"""Private, content-addressed artifacts and a durable, resumable job ledger."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sqlite3

from prism_engine.contracts import digest


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory, now=utcnow):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.now = now
        self.db = sqlite3.connect(self.directory / 'operations.sqlite', timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS artifacts (
                race_id TEXT, kind TEXT, key TEXT, content_hash TEXT, path TEXT,
                persisted_at TEXT, PRIMARY KEY(race_id,kind,key));
            CREATE TABLE IF NOT EXISTS jobs (
                race_id TEXT PRIMARY KEY, status TEXT, detail TEXT, updated_at TEXT);
        ''')

    def close(self):
        self.db.close()

    @staticmethod
    def safe(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', value):
            raise ValueError('unsafe artifact identity')
        return value

    @contextmanager
    def lock(self, race_id):
        path = self.directory / (self.safe(race_id) + '.lock')
        with path.open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError('RACE_ALREADY_RUNNING') from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def save(self, race_id, kind, key, payload):
        """Freeze bytes first, then record their actual durable receipt time.

        A repeated identical key is a cache hit. A changed payload must use a new
        key; it can never replace a preceding-day prediction or provider output.
        """
        self.safe(race_id); self.safe(kind); self.safe(key)
        content_hash = digest(payload)
        existing = self.get(race_id, kind, key)
        if existing:
            if existing['content_hash'] != content_hash:
                raise ValueError('IMMUTABLE_ARTIFACT_CONFLICT')
            return existing
        target = self.directory / 'artifacts' / race_id / kind
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = target / (content_hash + '.json')
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()
        try:
            with path.open('xb') as handle:
                os.chmod(path, 0o600)
                handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError('ARTIFACT_INTEGRITY_FAILURE')
        fd = os.open(target, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        persisted_at = self.now()
        with self.db:
            self.db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?)',
                            (race_id, kind, key, content_hash, str(path), persisted_at))
        return self.get(race_id, kind, key)

    def get(self, race_id, kind, key):
        row = self.db.execute('SELECT content_hash,path,persisted_at FROM artifacts '
                              'WHERE race_id=? AND kind=? AND key=?',
                              (race_id, kind, key)).fetchone()
        if row is None:
            return None
        payload = json.loads(Path(row[1]).read_text(encoding='utf-8'))
        if digest(payload) != row[0]:
            raise ValueError('ARTIFACT_INTEGRITY_FAILURE')
        return {'content_hash': row[0], 'path': row[1], 'persisted_at': row[2],
                'payload': payload}

    def status(self, race_id, status, detail):
        self.safe(race_id)
        with self.db:
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?) ON CONFLICT(race_id) '
                            'DO UPDATE SET status=excluded.status,detail=excluded.detail,'
                            'updated_at=excluded.updated_at',
                            (race_id, status, json.dumps(detail, ensure_ascii=False), self.now()))

    def jobs(self):
        return [dict(zip(('race_id', 'status', 'detail', 'updated_at'), row))
                for row in self.db.execute('SELECT * FROM jobs ORDER BY race_id')]
