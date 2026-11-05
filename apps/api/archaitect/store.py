"""Transactional SQLite project store. All writes use compare-and-swap revisions."""
import os
import sqlite3
import tempfile
from pathlib import Path
from threading import RLock
from .models import Project
from .fixtures import demo_project

_lock = RLock()
DEFAULT_DB = str(Path(tempfile.gettempdir()) / 'archaitect-demo-v03.sqlite3')

def db_path() -> str:
    return os.environ.get('ARCHAITECT_DB_PATH', DEFAULT_DB)

def _connect():
    con = sqlite3.connect(db_path(), timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=10000')
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS revisions (project_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(project_id,version))')
    return con

def _seed(con):
    project = demo_project()
    payload = project.model_dump_json()
    con.execute('INSERT OR IGNORE INTO projects (id,version,payload) VALUES (?,?,?)', (project.id,project.design.version,payload))
    con.execute('INSERT OR IGNORE INTO revisions (project_id,version,payload) VALUES (?,?,?)', (project.id,project.design.version,payload))

def read(project_id: str) -> Project | None:
    with _lock, _connect() as con:
        _seed(con)
        row = con.execute('SELECT payload FROM projects WHERE id=?',(project_id,)).fetchone()
        return Project.model_validate_json(row['payload']) if row else None

def _write(con, project: Project):
    payload=project.model_dump_json()
    con.execute('UPDATE projects SET version=?,payload=? WHERE id=?',(project.design.version,payload,project.id))
    con.execute('INSERT INTO revisions (project_id,version,payload) VALUES (?,?,?)',(project.id,project.design.version,payload))

def commit(project_id: str, proposed: Project, expected_version: int) -> Project | None:
    with _lock, _connect() as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            _seed(con)
            row=con.execute('SELECT payload,version FROM projects WHERE id=?',(project_id,)).fetchone()
            if not row or row['version']!=expected_version:
                con.execute('ROLLBACK'); return None
            current=Project.model_validate_json(row['payload'])
            if proposed.design.id!=current.design.id or proposed.id!=project_id:
                con.execute('ROLLBACK'); return None
            updated=current.model_copy(update={'design':proposed.design.model_copy(update={'version':expected_version+1})})
            _write(con,updated)
            con.execute('COMMIT')
            return updated
        except Exception:
            con.execute('ROLLBACK');raise

def undo(project_id: str, expected_version: int) -> Project | None:
    with _lock, _connect() as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            _seed(con)
            row=con.execute('SELECT payload,version FROM projects WHERE id=?',(project_id,)).fetchone()
            if not row or row['version']!=expected_version:
                con.execute('ROLLBACK');return None
            prev=con.execute('SELECT payload FROM revisions WHERE project_id=? AND version<? ORDER BY version DESC LIMIT 1',(project_id,expected_version)).fetchone()
            if not prev:
                con.execute('ROLLBACK');return None
            current=Project.model_validate_json(row['payload'])
            previous=Project.model_validate_json(prev['payload'])
            updated=current.model_copy(update={'design':previous.design.model_copy(update={'version':expected_version+1})})
            _write(con,updated)
            con.execute('COMMIT')
            return updated
        except Exception:
            con.execute('ROLLBACK');raise

def history(project_id: str) -> list[int]:
    with _lock, _connect() as con:
        _seed(con)
        return [r['version'] for r in con.execute('SELECT version FROM revisions WHERE project_id=? ORDER BY version',(project_id,)).fetchall()]


def create(project: Project) -> Project:
    """Insert a project once (idempotent). Returns the stored project, which may be an older revision of the same id."""
    with _lock, _connect() as con:
        payload = project.model_dump_json()
        con.execute('INSERT OR IGNORE INTO projects (id,version,payload) VALUES (?,?,?)', (project.id, project.design.version, payload))
        con.execute('INSERT OR IGNORE INTO revisions (project_id,version,payload) VALUES (?,?,?)', (project.id, project.design.version, payload))
        row = con.execute('SELECT payload FROM projects WHERE id=?', (project.id,)).fetchone()
        return Project.model_validate_json(row['payload'])

def sync_context(project_id: str, parcel, rules, envelope) -> Project | None:
    """Refresh parcel/rules/envelope of an existing project without touching the design or its revision number."""
    with _lock, _connect() as con:
        con.execute('BEGIN IMMEDIATE')
        try:
            row = con.execute('SELECT payload FROM projects WHERE id=?', (project_id,)).fetchone()
            if not row:
                con.execute('ROLLBACK'); return None
            updated = Project.model_validate_json(row['payload']).model_copy(update={'parcel': parcel, 'rules': rules, 'envelope': envelope})
            con.execute('UPDATE projects SET payload=? WHERE id=?', (updated.model_dump_json(), project_id))
            con.execute('COMMIT')
            return updated
        except Exception:
            con.execute('ROLLBACK'); raise

def delete(project_id: str) -> None:
    with _lock, _connect() as con:
        con.execute('DELETE FROM projects WHERE id=?', (project_id,))
        con.execute('DELETE FROM revisions WHERE project_id=?', (project_id,))
