"""Phase-3 search/verifier/repair tests: deterministic, offline, honest counts."""
import math

import pytest

from archaitect.fixtures import demo_project
from archaitect.scenario import GoalSpec, RunRecord, ScenarioCondition, VariantCandidate
from archaitect.search import (
    SearchSpace,
    generate_candidates,
    measure,
    rank,
    repair_once,
    run_search,
    verify_design,
)


def _project(**design_overrides):
    project = demo_project()
    data = project.design.model_dump()
    data.update(design_overrides)
    project.design = project.design.model_validate(data)
    return project


def _conditions():
    return [
        ScenarioCondition(rule_id='SYN_MAX_STOREYS', kind='MAX_STOREYS',
                          value=2.0, unit='storeys',
                          evidence_id='doc-test#p1', adopted=True),
        ScenarioCondition(rule_id='SYN_MAX_FOOTPRINT', kind='MAX_FOOTPRINT',
                          value=100.0, unit='m2',
                          evidence_id='doc-test#p1', adopted=True),
    ]


def _run(**overrides):
    params = {'run_id': 'r', 'project_id': 'p', 'design_version': 1,
              'scenario_version': 1, 'goal': GoalSpec(objective='balanced')}
    params.update(overrides)
    return RunRecord(**params)


def test_verifier_names_condition_observed_limit_and_param():
    project = _project(width_m=15.0)  # 135 m2 footprint
    findings = verify_design(project.parcel, project.design, _conditions())
    assert len(findings) == 1
    finding = findings[0]
    assert finding.condition_id == 'SYN_MAX_FOOTPRINT'
    assert finding.observed == pytest.approx(135.0)
    assert finding.limit == 100.0
    assert finding.design_param == 'width_m'


def test_verifier_reports_containment_and_storeys():
    project = _project(center_x=30.0, storeys=3)
    findings = verify_design(project.parcel, project.design, _conditions())
    ids = {f.condition_id for f in findings}
    assert ids == {'PARCEL_CONTAINMENT', 'SYN_MAX_STOREYS'}


def test_repair_case_violating_proposal_rejected_fitting_variant_offered():
    """Prescribed case: violating seed is excluded, a repaired variant wins."""
    project = _project(width_m=15.0, depth_m=9.0)  # infeasible seed
    run, variants = run_search(
        project.parcel, project.design, _conditions(),
        GoalSpec(objective='max_gross_floor_area'),
        SearchSpace(widths=[15.0], depths=[9.0], storeys_options=[2]),
        _run())
    assert run.state == 'ready'
    assert run.repairs >= 1
    assert all(v.feasible for v in variants)
    assert all(v.metrics.footprint_m2 <= 100.0 for v in variants)
    assert all(v.metrics.footprint_m2 != pytest.approx(135.0) for v in variants)
    assert 'repairing' in ' '.join(run.log)


def test_impossible_search_space_yields_no_solution_never_faked():
    project = demo_project()
    impossible = [ScenarioCondition(rule_id='SYN_ZERO_STOREYS', kind='MAX_STOREYS',
                                    value=0.0, unit='storeys',
                                    evidence_id='doc-test#p1', adopted=True)]
    run, variants = run_search(
        project.parcel, project.design, impossible,
        GoalSpec(objective='balanced'),
        SearchSpace(widths=[5.0], depths=[5.0], storeys_options=[1]),
        _run())
    assert run.state == 'no_solution'
    assert variants == []


def test_repair_budget_enforced_by_run_record():
    # Off-parcel, too many storeys and too large: needs three repairs,
    # so the third one must refuse with an exhausted budget.
    project = _project(center_x=30.0, storeys=3, width_m=15.0, depth_m=15.0)
    with pytest.raises(ValueError, match='repair budget'):
        run_search(project.parcel, project.design, _conditions(),
                   GoalSpec(objective='balanced'),
                   SearchSpace(widths=[15.0], depths=[15.0], storeys_options=[3]),
                   _run())


def test_fewer_variants_than_max_when_space_is_small():
    project = demo_project()
    _, variants = run_search(
        project.parcel, project.design, [],
        GoalSpec(objective='balanced', max_variants=3),
        SearchSpace(widths=[10.0], depths=[9.0], storeys_options=[2]),
        _run())
    assert len(variants) == 1


def test_repair_never_touches_conditions_or_evidence():
    project = _project(width_m=15.0)
    conditions = _conditions()
    snapshot = [c.model_dump() for c in conditions]
    run_search(project.parcel, project.design, conditions,
               GoalSpec(objective='balanced'),
               SearchSpace(widths=[15.0], depths=[9.0], storeys_options=[2]),
               _run(), evidence_ids=['doc-test#p1'])
    assert [c.model_dump() for c in conditions] == snapshot


def test_search_rejects_oversize_space_and_nan_input():
    project = demo_project()
    big = SearchSpace(widths=[float(w) for w in range(10)],
                      depths=[float(d) for d in range(10)],
                      storeys_options=[1, 2, 3])
    with pytest.raises(ValueError, match='too large'):
        generate_candidates(project.design, big)
    bad = project.design.model_copy(update={'width_m': math.nan})
    with pytest.raises(ValueError, match='finite'):
        verify_design(project.parcel, bad, [])


def test_ranking_is_transparent_and_capped():
    project = demo_project()
    space = SearchSpace(widths=[8.0, 10.0], depths=[7.0, 9.0], storeys_options=[1, 2])
    grid = generate_candidates(project.design, space)
    assert len(grid) == 8
    checked = [VariantCandidate(
        design=d, metrics=measure(d, project.parcel),
        violations=verify_design(project.parcel, d, []), evidence_ids=[])
        for d in grid]
    top = rank(checked, GoalSpec(objective='max_gross_floor_area', max_variants=2))
    assert len(top) == 2
    assert top[0].metrics.gross_floor_area_m2 >= top[1].metrics.gross_floor_area_m2
    assert repair_once(project.design, project.parcel, []) is None
