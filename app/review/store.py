import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=8)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self):
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS runs(
              id TEXT PRIMARY KEY,
              request_key TEXT UNIQUE NOT NULL,
              created_at TEXT NOT NULL,
              profile TEXT NOT NULL,
              status TEXT NOT NULL,
              revision INTEGER NOT NULL,
              payload TEXT NOT NULL,
              comment TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS comparisons(
              id TEXT PRIMARY KEY,
              request_key TEXT UNIQUE NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              baseline_run_id TEXT NOT NULL,
              candidate_run_id TEXT NOT NULL,
              baseline_status TEXT NOT NULL DEFAULT '',
              baseline_revision INTEGER NOT NULL DEFAULT 0,
              candidate_status TEXT NOT NULL DEFAULT '',
              candidate_revision INTEGER NOT NULL DEFAULT 0,
              payload TEXT NOT NULL
            );
            CREATE VIEW IF NOT EXISTS retrospectives AS SELECT * FROM comparisons;
            CREATE VIEW IF NOT EXISTS comparison_records AS SELECT * FROM comparisons;
            CREATE VIEW IF NOT EXISTS comparison_reviews AS SELECT * FROM comparisons;
            ''')

    def find_by_request(self, request_key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE request_key=?", (request_key,)).fetchone()
        return dict(row) if row else None

    def create(self, request_key, profile, payload):
        existing = self.find_by_request(request_key)
        if existing:
            return existing
        run_id = uuid.uuid4().hex[:12]
        with self.connect() as db:
            db.execute("INSERT INTO runs(id,request_key,created_at,profile,status,revision,payload) VALUES(?,?,?,?,?,?,?)",
                       (run_id, request_key, datetime.now(timezone.utc).isoformat(), profile, "DRAFT", 0,
                        json.dumps(payload, ensure_ascii=False)))
        return self.get(run_id)

    def get(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def review(self, run_id, decision, comment, expected_revision):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                return None, "missing"
            if row["revision"] != expected_revision:
                return None, "stale"
            db.execute("UPDATE runs SET status=?, revision=revision+1, comment=? WHERE id=?",
                       (decision, comment, run_id))
        return self.get(run_id), None

    def list_runs(self, limit=200):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM runs ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def find_comparison_by_request(self, request_key):
        with self.connect() as db:
            row = db.execute("SELECT * FROM comparisons WHERE request_key=?", (request_key,)).fetchone()
        return dict(row) if row else None

    def get_comparison(self, comparison_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM comparisons WHERE id=?", (comparison_id,)).fetchone()
        return dict(row) if row else None

    def list_comparisons(self, limit=100):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM comparisons ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_comparison(self, request_key, baseline_run_id, candidate_run_id,
                          baseline_status, baseline_revision, candidate_status,
                          candidate_revision, payload):
        existing = self.find_comparison_by_request(request_key)
        if existing:
            return existing
        comparison_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self.connect() as db:
                db.execute(
                    """INSERT INTO comparisons(
                        id, request_key, created_at, updated_at, baseline_run_id, candidate_run_id,
                        baseline_status, baseline_revision, candidate_status, candidate_revision, payload
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (comparison_id, request_key, now, now, baseline_run_id, candidate_run_id,
                     baseline_status, baseline_revision, candidate_status, candidate_revision,
                     json.dumps(payload, ensure_ascii=False)),
                )
        except sqlite3.IntegrityError:
            return self.find_comparison_by_request(request_key)
        return self.get_comparison(comparison_id)

    def update_comparison(self, comparison_id, baseline_status, baseline_revision,
                         candidate_status, candidate_revision, payload):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute(
                """UPDATE comparisons
                   SET updated_at=?, baseline_status=?, baseline_revision=?,
                       candidate_status=?, candidate_revision=?, payload=?
                   WHERE id=?""",
                (now, baseline_status, baseline_revision, candidate_status, candidate_revision,
                 json.dumps(payload, ensure_ascii=False), comparison_id),
            )
        return self.get_comparison(comparison_id)

    def count_comparisons(self):
        with self.connect() as db:
            return int(db.execute("SELECT COUNT(*) AS n FROM comparisons").fetchone()["n"])

    # Business-language aliases for “复盘记录”.
    def find_retrospective_by_request(self, request_key):
        return self.find_comparison_by_request(request_key)

    def get_retrospective(self, retrospective_id):
        return self.get_comparison(retrospective_id)

    def list_retrospectives(self, limit=100):
        return self.list_comparisons(limit)

    def create_retrospective(self, *args, **kwargs):
        return self.create_comparison(*args, **kwargs)

    def update_retrospective(self, retrospective_id, *args, **kwargs):
        return self.update_comparison(retrospective_id, *args, **kwargs)

    def count_retrospectives(self):
        return self.count_comparisons()

    save_comparison = create_comparison
    insert_comparison = create_comparison
    put_comparison = create_comparison
    save_retrospective = create_retrospective
