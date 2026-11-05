from archaitect.siteintel.generation_fit import conflicts, correction_request


def test_explicit_storeys_only_against_known_limit():
    assert conflicts('7 Etagen', {'max_storeys': 5})
    assert not conflicts('5 Vollgeschosse', {'max_storeys': 5})
    assert not conflicts('7 Etagen', {'max_storeys': None})
    assert not conflicts('modernes Haus', {'max_storeys': 5})


def test_correction_preserves_explicit_requirements():
    text = correction_request('Haus mit 9 x 12 m', 'kein Standort')
    assert '9 x 12 m' in text
    assert 'Keine festen Nutzermaße' in text


def test_brief_preserves_non_rectangular_geometry_and_unknown_limits():
    from shapely.geometry import Polygon
    from archaitect.siteintel.regs import SiteCtx
    from archaitect.siteintel.generation_fit import brief
    site = Polygon([(0, 0), (10, 0), (10, 3), (3, 3), (3, 10), (0, 10)])
    ctx = SiteCtx(site=site, area_m2=site.area, existing=[], neighbours=[], roads=[], verified=None, envelope=None)
    data = brief(ctx)
    assert data['free_area_m2'] == 51
    assert data['free_geometry']['type'] == 'Polygon'
    assert data['max_storeys'] is None
    assert len(data['free_geometry']['coordinates'][0]) == 7


def test_preflight_does_not_call_model_or_save(monkeypatch):
    from types import SimpleNamespace
    from archaitect.siteintel import bim_api, generation_fit
    monkeypatch.setattr(bim_api, '_R', lambda: SimpleNamespace(_need=lambda pid: None))
    monkeypatch.setattr(bim_api, '_site', lambda pid: (None, None, None))
    monkeypatch.setattr(generation_fit, 'brief', lambda ctx: {'max_storeys': 5, 'free_area_m2': 100})
    def unexpected(*args, **kwargs):
        raise AssertionError('Model must not be called for a known conflict')
    monkeypatch.setattr(bim_api, '_configure_llm', unexpected)
    result = bim_api.create('p', bim_api.CreateBody(text='Ich möchte 7 Etagen'))
    assert result['status'] == 'questions'
    assert '5' in result['questions'][0]


def test_generation_context_includes_hbo_without_inventing_local_ratios():
    from shapely.geometry import box
    from archaitect.siteintel.regs import SiteCtx
    from archaitect.siteintel.generation_fit import brief
    data = brief(SiteCtx(site=box(0, 0, 20, 20), area_m2=400, existing=[], neighbours=[], roads=[], verified=None, envelope=None))
    assert data['hbo_setbacks']['factor_h'] == 0.4
    assert data['hbo_setbacks']['minimum_m'] == 2.5
    assert data['hbo_setbacks']['status'] == 'INDICATIVE_PROJECT_REVIEW_REQUIRED'
    assert data['grz'] is None and data['gfz'] is None


def test_brief_carries_design_frame_from_surroundings():
    from shapely.geometry import box
    from types import SimpleNamespace as NS
    from archaitect.siteintel import generation_fit, reference
    from archaitect.siteintel.regs import Existing
    site = box(0, 0, 20, 30)
    nb = [Existing('n1', box(22.5, 0, 31, 10), 2, 7.0), Existing('n2', box(22.5, 12, 31, 22), 3, 10.0), Existing('n3', box(22.0, 24, 31, 30), 3, 10.0), Existing('far', box(500, 0, 510, 10), 9, 30.0)]
    ctx = NS(site=site, neighbours=nb, existing=[], verified=None, roads=[], area_m2=600.0, hard_region=lambda m: site, kept=lambda m: [], src={}, envelope=None)
    ctx.reference = reference.build(ctx, {'geschosszahl': 'II-III'})
    data = generation_fit.brief(ctx)
    frame = data['design_frame']
    assert frame['max_storeys'] == {'value': 3, 'binding': False, 'basis': 'CONTEXT_REFERENCE'}
    assert frame['max_height_m']['value'] == 10.0 and frame['setback_m']['binding'] is False
    assert data['grz'] is None and data['max_storeys'] is None      # unknown binding values stay unknown


def test_binding_values_win_over_the_reference_frame():
    from types import SimpleNamespace as NS
    from archaitect.siteintel import reference
    ctx = NS(reference={'max_storeys': 5, 'max_height_m': 16.0}, verified=NS(max_stories=2, max_building_height_meters=None, setback_lines_offset_meters=None, grz=None, gfz=None),
             src={'max_stories': 'USER_LIMIT'})
    eff = reference.effective(ctx)
    assert eff['max_storeys'] == {'value': 2, 'binding': True, 'basis': 'USER_LIMIT'}
    assert eff['max_height_m']['binding'] is False


def test_zone_storeys_parse():
    from archaitect.siteintel.reference import parse_zone_storeys
    assert parse_zone_storeys('II') == (2, 2) and parse_zone_storeys('II-III') == (2, 3) and parse_zone_storeys(None) == (None, None)
