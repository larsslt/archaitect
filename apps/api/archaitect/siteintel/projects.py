"""Project store: one folder per planning project (JSON + the orthophoto). Plain files, no server, easy to inspect and back up.

Layout  <root>/<id>/project.json  assessment.json  sitepack.json  ortho.png  verified.json
"""
from __future__ import annotations
import json
import os
import shutil
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .brief import PlanningBrief
from .dossier import PlanningLimits, VerifiedConstraints
from .models import SiteAssessment
from .sitepack import SitePack

_ID = re.compile(r'^p_[0-9a-f]{12}$')
_LOCK = threading.Lock()


def default_root() -> Path:
    env = os.environ.get('ARCHAITECT_SITEINTEL_PROJECTS')
    return Path(env) if env else Path(__file__).resolve().parents[4] / '.local' / 'siteintel-projects'


class ProjectStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_root()

    def _dir(self, pid: str) -> Path:
        if not _ID.match(pid):
            raise KeyError(pid)
        return self.root / pid

    def create(self, a: SiteAssessment, pack: SitePack, name: str | None, override: bool) -> dict:
        pid = 'p_' + uuid.uuid4().hex[:12]
        d = self.root / pid
        with _LOCK:
            d.mkdir(parents=True, exist_ok=False)
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            title = name or (f'Flurstück {a.parcel.label}' if a.parcel else 'Neues Projekt')
            meta = {'id': pid, 'name': title, 'created_at': now, 'updated_at': now, 'lat': a.lat, 'lon': a.lon, 'override_blocked': override,
                    'parcel_label': a.parcel.label if a.parcel else None, 'verdict': a.verdict.value, 'design_mode': a.design_mode.value,
                    'gemeinde': a.land_value.gemeinde if a.land_value else None, 'area_m2': a.parcel.area_alkis_m2 if a.parcel else None, 'headline_de': a.headline_de,
                    'terrain_ok': pack.manifest['terrain']['status'] == 'OK', 'ortho_ok': pack.manifest['ortho']['status'] == 'OK', 'pinned': False}
            (d / 'project.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
            (d / 'assessment.json').write_text(a.model_dump_json(indent=1), encoding='utf-8')
            (d / 'sitepack.json').write_text(json.dumps(pack.manifest, ensure_ascii=False), encoding='utf-8')
            if pack.ortho:
                (d / 'ortho.png').write_bytes(pack.ortho)
            (d / 'brief.json').write_text(PlanningBrief(title=title).model_dump_json(indent=1), encoding='utf-8')
        return meta

    def exists(self, pid: str) -> bool:
        try:
            return (self._dir(pid) / 'project.json').exists()
        except KeyError:
            return False

    def meta(self, pid: str) -> dict:
        return self._flags(self._dir(pid), json.loads((self._dir(pid) / 'project.json').read_text(encoding='utf-8')))

    @staticmethod
    def _flags(d, m: dict) -> dict:
        """Projects created before the data flags existed would show 'Daten fehlen' although terrain and orthophoto are stored: derive them from the site pack."""
        if 'terrain_ok' in m and 'ortho_ok' in m:
            return m
        try:
            pk = json.loads((d / 'sitepack.json').read_text(encoding='utf-8'))
            m = {**m, 'terrain_ok': pk.get('terrain', {}).get('status') == 'OK', 'ortho_ok': pk.get('ortho', {}).get('status') == 'OK' and (d / 'ortho.png').exists()}
        except (OSError, ValueError):
            m = {**m, 'terrain_ok': False, 'ortho_ok': False}
        return m

    def assessment(self, pid: str) -> SiteAssessment:
        return SiteAssessment.model_validate_json((self._dir(pid) / 'assessment.json').read_text(encoding='utf-8'))

    def pack(self, pid: str) -> dict:
        return json.loads((self._dir(pid) / 'sitepack.json').read_text(encoding='utf-8'))

    def ortho(self, pid: str) -> bytes | None:
        p = self._dir(pid) / 'ortho.png'
        return p.read_bytes() if p.exists() else None

    def brief(self, pid: str) -> PlanningBrief:
        return PlanningBrief.model_validate_json((self._dir(pid) / 'brief.json').read_text(encoding='utf-8'))

    def save_brief(self, pid: str, b: PlanningBrief) -> PlanningBrief:
        b = b.model_copy(update={'updated_at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
        d = self._dir(pid)
        with _LOCK:
            (d / 'brief.json').write_text(b.model_dump_json(indent=1), encoding='utf-8')
            m = self.meta(pid)
            m['updated_at'] = b.updated_at
            (d / 'project.json').write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding='utf-8')
        return b

    def verified(self, pid: str) -> VerifiedConstraints | None:
        p = self._dir(pid) / 'verified.json'
        return VerifiedConstraints.model_validate_json(p.read_text(encoding='utf-8')) if p.exists() else None

    def save_verified(self, pid: str, v: VerifiedConstraints) -> None:
        with _LOCK:
            (self._dir(pid) / 'verified.json').write_text(v.model_dump_json(indent=1), encoding='utf-8')

    def limits(self, pid: str) -> PlanningLimits | None:
        p = self._dir(pid) / 'limits.json'
        return PlanningLimits.model_validate_json(p.read_text(encoding='utf-8')) if p.exists() else None

    def save_limits(self, pid: str, lim: PlanningLimits | None) -> None:
        p = self._dir(pid) / 'limits.json'
        with _LOCK:
            if lim is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(lim.model_dump_json(indent=1), encoding='utf-8')
        self.touch(pid)

    # ---- overview helpers
    def update_meta(self, pid: str, **fields) -> dict:
        with _LOCK:
            m = self.meta(pid)
            m.update({k: v for k, v in fields.items() if v is not None})
            m['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            (self._dir(pid) / 'project.json').write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding='utf-8')
            return m

    def touch(self, pid: str) -> None:
        self.update_meta(pid)

    def save_thumb(self, pid: str, data: bytes, info: dict) -> None:
        with _LOCK:
            (self._dir(pid) / 'thumb.jpg').write_bytes(data)
        self.update_meta(pid, thumb=info)

    def thumb(self, pid: str) -> bytes | None:
        p = self._dir(pid) / 'thumb.jpg'
        return p.read_bytes() if p.exists() else None

    def delete(self, pid: str) -> None:
        with _LOCK:
            shutil.rmtree(self._dir(pid))

    def duplicate(self, pid: str, name: str | None = None) -> dict:
        new = 'p_' + uuid.uuid4().hex[:12]
        with _LOCK:
            shutil.copytree(self._dir(pid), self.root / new)
            m = self.meta(new)
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            m.update({'id': new, 'name': name or f'{m["name"]} (Kopie)', 'created_at': now, 'updated_at': now})
            (self.root / new / 'project.json').write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding='utf-8')
        return m

    def list(self, limit: int = 50) -> list[dict]:
        out = []
        if self.root.exists():
            for d in self.root.iterdir():
                if _ID.match(d.name) and (d / 'project.json').exists():
                    out.append(self._flags(d, json.loads((d / 'project.json').read_text(encoding='utf-8'))))
        return sorted(out, key=lambda m: m['updated_at'], reverse=True)[:limit]

    # ---- site pack replacement (several parcels) and the studio design with revisions
    def replace_pack(self, pid: str, pack: SitePack) -> None:
        d = self._dir(pid)
        with _LOCK:
            (d / 'sitepack.json').write_text(json.dumps(pack.manifest, ensure_ascii=False), encoding='utf-8')
            if pack.ortho:
                (d / 'ortho.png').write_bytes(pack.ortho)

    def design(self, pid: str):
        from .massing import Massing
        p = self._dir(pid) / 'design' / 'current.json'
        return Massing.model_validate_json(p.read_text(encoding='utf-8')) if p.exists() else None

    def save_design(self, pid: str, m, expected_version: int | None):
        """Append a revision. ``expected_version`` must equal the current version (optimistic locking); None only for the very first design."""
        d = self._dir(pid) / 'design'
        with _LOCK:
            d.mkdir(exist_ok=True)
            cur = d / 'current.json'
            now_v = json.loads(cur.read_text(encoding='utf-8'))['version'] if cur.exists() else 0
            if (expected_version or 0) != now_v:
                raise ValueError(f'Version veraltet: gespeichert ist {now_v}, erwartet {expected_version}.')
            m = m.model_copy(update={'version': now_v + 1})
            body = m.model_dump_json(indent=1)
            (d / f'v{now_v + 1:04d}.json').write_text(body, encoding='utf-8')
            cur.write_text(body, encoding='utf-8')
        self.touch(pid)
        return m

    def design_history(self, pid: str) -> list[dict]:
        d = self._dir(pid) / 'design'
        out = []
        if d.exists():
            for f in sorted(d.glob('v*.json')):
                j = json.loads(f.read_text(encoding='utf-8'))
                out.append({'version': j['version'], 'source': j.get('source'), 'volumes': len(j.get('volumes', [])), 'saved_at': datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(timespec='seconds')})
        return out

    def design_revision(self, pid: str, version: int):
        from .massing import Massing
        f = self._dir(pid) / 'design' / f'v{version:04d}.json'
        return Massing.model_validate_json(f.read_text(encoding='utf-8')) if f.exists() else None

    def save_reference(self, pid: str, name: str, data: bytes, info: dict) -> dict:
        d = self._dir(pid) / 'refs'
        rid = 'r_' + uuid.uuid4().hex[:10]
        ext = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp', 'application/pdf': '.pdf'}.get(info.get('media_type', ''), '.bin')
        with _LOCK:
            d.mkdir(exist_ok=True)
            (d / f'{rid}{ext}').write_bytes(data)
            rec = {'id': rid, 'name': name[:120], 'file': f'{rid}{ext}', 'bytes': len(data), 'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), **info}
            (d / f'{rid}.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
        return rec

    def references(self, pid: str) -> list[dict]:
        d = self._dir(pid) / 'refs'
        return sorted((json.loads(f.read_text(encoding='utf-8')) for f in d.glob('r_*.json')), key=lambda r: r['created_at']) if d.exists() else []

    def update_reference(self, pid: str, rid: str, **fields) -> dict:
        f = self._dir(pid) / 'refs' / f'{rid}.json'
        if not re.match(r'^r_[0-9a-f]{10}$', rid) or not f.exists():
            raise KeyError(rid)
        with _LOCK:
            rec = json.loads(f.read_text(encoding='utf-8'))
            rec.update(fields)
            f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
        return rec

    def reference_bytes(self, pid: str, rid: str) -> tuple[bytes, dict]:
        rec = next((r for r in self.references(pid) if r['id'] == rid), None)
        if rec is None:
            raise KeyError(rid)
        return (self._dir(pid) / 'refs' / rec['file']).read_bytes(), rec

    def delete_reference(self, pid: str, rid: str) -> None:
        rec = next((r for r in self.references(pid) if r['id'] == rid), None)
        if rec is None:
            raise KeyError(rid)
        with _LOCK:
            (self._dir(pid) / 'refs' / rec['file']).unlink(missing_ok=True)
            (self._dir(pid) / 'refs' / f'{rid}.json').unlink(missing_ok=True)
