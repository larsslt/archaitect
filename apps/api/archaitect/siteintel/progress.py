"""Project progress for the overview page: which of the six preparation steps are done and what to do next. Pure function of stored facts."""
from __future__ import annotations
from .brief import PlanningBrief
from .dossier import VerifiedConstraints

STEPS = [
    ('site', 'Grundstück'),
    ('data', 'Daten'),
    ('brief', 'Programm'),
    ('utilities', 'Anschlüsse'),
    ('rules', 'Vorschriften'),
    ('design', 'Entwurf'),
]
# where the next step is done: (page, tab)
WHERE = {'data': ('plan', 'site'), 'brief': ('plan', 'program'), 'utilities': ('plan', 'utilities'), 'rules': ('plan', 'rules'), 'design': ('studio', None)}
NEXT_DE = {
    'data': 'Geländedaten oder Luftbild fehlen – „Daten neu laden“ versucht es erneut',
    'brief': 'Bauprogramm ausfüllen (Personen, Wohnfläche, Geschosse)',
    'utilities': 'Anschlusspunkte setzen oder Leitungsauskunft anfragen',
    'rules': 'Bebauungsplan-Werte eintragen und prüfen',
    'design': 'Hausentwurf im Studio starten',
}


def compute(meta: dict, brief: PlanningBrief, verified: VerifiedConstraints | None, design_version: int | None) -> dict:
    p = brief.program
    done = {
        'site': True,
        'data': bool(meta.get('terrain_ok', False) and meta.get('ortho_ok', False)),
        'brief': bool(p.occupants and p.living_area_target_m2 and p.stories),
        'utilities': bool(brief.connections) or brief.utilities_enquiry.status != 'not_requested',
        'rules': verified is not None,
        'design': bool(design_version and design_version > 1),
    }
    steps = [{'key': k, 'label_de': l, 'done': done[k]} for k, l in STEPS]
    nxt = next((k for k, _ in STEPS if not done[k]), None)
    page, tab = WHERE.get(nxt, ('studio', None)) if nxt else ('studio', None)
    return {'steps': steps, 'done': sum(done.values()), 'total': len(STEPS), 'next': ({'key': nxt, 'label_de': NEXT_DE[nxt], 'page': page, 'tab': tab} if nxt else None)}
