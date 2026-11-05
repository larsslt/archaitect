"""Grounded generation context and explicit-input preflight; no inferred planning law."""
from __future__ import annotations

import re
from shapely.geometry import mapping
from .massing import Massing
from .regs import limits, HBO_FACTOR, HBO_MIN_M, HBO_SOURCE


def brief(ctx):
    m = Massing(volumes=[{'id': 'generation-context'}])
    region = ctx.hard_region(m)
    data = limits(m, ctx)
    data['hbo_setbacks'] = {'factor_h': HBO_FACTOR, 'minimum_m': HBO_MIN_M, 'source': HBO_SOURCE, 'status': 'INDICATIVE_PROJECT_REVIEW_REQUIRED', 'instructions': 'Reserve setback space at design time; account for wall height, terrain and roof. This is not a fixed uniform parcel inset; exceptions remain open.'}
    data['grz'] = getattr(ctx.verified, 'grz', None)
    data['gfz'] = getattr(ctx.verified, 'gfz', None)
    from . import reference
    ref = getattr(ctx, 'reference', None)
    data['neighbourhood_reference'] = ref or {'binding': False, 'basis': 'CONTEXT_REFERENCE', 'note_de': 'Keine Umgebungswerte ableitbar.'}
    data['design_frame'] = reference.effective(ctx)        # per value: binding (verified/user) or reference from the surroundings
    data['free_geometry'] = mapping(region)
    data['free_area_m2'] = round(region.area, 2)
    data['geometry_frame'] = 'local metres, x east, y north; retain existing buildings'
    data['instructions'] = ('Design inside free_geometry including all exterior parts. Area alone does not prove fit. '
        'Keep explicit user dimensions and storey counts. If those cannot fit, ask a concrete question. '
        'Otherwise choose compact dimensions and omit optional extras that cannot fit. '
        'Unknown limits are unknown, not unlimited or approved. Never remove existing buildings implicitly. '
        'design_frame is the frame to build in: binding values are limits; values with binding=false come from the surroundings (permit probably needed above them) - respect them as well, unless the user explicitly asks for more.')
    return data


def conflicts(text, data):
    """Conservative detection of explicit numeric storey counts; no guessed natural-language numbers."""
    maximum = data.get('max_storeys')
    if maximum is None:
        return []
    matches = re.findall(r'\b(\d{1,2})\s*(?:Etagen|Vollgeschosse|Geschosse|Stockwerke)\b', text, re.I)
    return [f'Gewünscht sind {n} Geschosse; die hinterlegte Grenze beträgt {maximum}. Bitte die Geschosszahl anpassen.'
            for n in sorted(set(map(int, matches))) if n > maximum]


def correction_request(original, error):
    return (original + '\n\nKORREKTUR DES ENTWURFS: Die deterministische Prüfung hat Folgendes festgestellt: '
            + str(error) + '\nErzeuge einen neuen, geometrisch passenden Entwurf unter denselben Nutzeranforderungen. '
            'Keine festen Nutzermaße oder Geschosszahlen ändern. Wenn das unmöglich ist, status questions mit konkreter Rückfrage liefern. '
            'Keine Grundstücksgrenzen, Rechtswerte oder Abrissannahmen verändern.')
