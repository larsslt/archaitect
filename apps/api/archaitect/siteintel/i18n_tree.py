"""Translate the free-text values of an export (JSON tree) from German to English.
Keys, ids, codes, numbers, URLs and single-word status values stay untouched; only sentences/phrases are sent
through the cached UI translator (bim_api.i18n_en)."""
from __future__ import annotations

import re

_CODE = re.compile(r"^[\w\-./:#@=+,;()\[\]%°²³ ]*$")
_MAX_STRINGS = 800


def _wanted(s: str) -> bool:
    s = s.strip()
    if len(s) < 6 or not re.search(r"[A-Za-zÄÖÜäöüß]{3}", s):
        return False
    if s.startswith(("http://", "https://", "/", "data:")):
        return False
    if " " not in s:  # single tokens = ids / enum values, keep machine-readable
        return False
    if re.fullmatch(r"[0-9a-f\-]{16,}", s):
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", s) and not re.search(r"[A-Za-zäöü]{4}.*\s[A-Za-zäöü]{4}", s):
        return False
    return True


def _collect(o, acc: dict):
    if isinstance(o, str):
        if _wanted(o):
            acc[o.strip()[:2000]] = None
    elif isinstance(o, list):
        for x in o:
            _collect(x, acc)
    elif isinstance(o, dict):
        for v in o.values():
            _collect(v, acc)


def _apply(o, m: dict):
    if isinstance(o, str):
        k = o.strip()[:2000]
        return m.get(k, o) if k in m and len(o.strip()) <= 2000 else o
    if isinstance(o, list):
        return [_apply(x, m) for x in o]
    if isinstance(o, dict):
        return {k: _apply(v, m) for k, v in o.items()}
    return o


def translate_tree(obj):
    from .bim_api import I18nBody, i18n_en
    acc: dict = {}
    _collect(obj, acc)
    texts = list(acc)[:_MAX_STRINGS]
    m: dict = {}
    for i in range(0, len(texts), 40):
        try:
            m.update(i18n_en(I18nBody(texts=texts[i:i + 40]))["map"])
        except Exception:  # noqa: BLE001 - best effort, leave German
            continue
    return _apply(obj, m)


def translate_text(text: str) -> str:
    """Multi-line plain text (README): translate line by line."""
    lines = text.split("\n")
    m = translate_tree([l for l in lines if l.strip()])
    it = iter(m)
    return "\n".join(next(it) if l.strip() else l for l in lines)
