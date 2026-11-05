"""Foundation contract tests: evidence/scenario/run invariants (offline)."""
import math

import pytest

from archaitect.fixtures import demo_project
from archaitect.models import EvidenceStatus
from archaitect.scenario import (
    CounterExample,
    EvidenceRecord,
    GoalSpec,
    RunRecord,
    ScenarioCondition,
    VariantCandidate,
    VariantMetrics,
    gross_floor_area_approx,
)


def _evidence(**overrides):
    base = {
        'document_id': 'doc-synth-001',
        'document_sha256': 'abc123ef45678901',
        'page_index': 0,
        'quote': 'Maximal zwei Vollgeschosse.',
        'kind': 'MAX_STOREYS',
        'value': 2.0,
        'unit': 'storeys',
    }
    base.update(overrides)
    return EvidenceRecord(**base)


def test_evidence_never_arrives_verified():
    with pytest.raises(ValueError):
        _evidence(status=EvidenceStatus.VERIFIED)


def test_evidence_rejects_nan_and_bad_page():
    with pytest.raises(ValueError):
        _evidence(value=float('nan'))
    with pytest.raises(ValueError):
        _evidence(value=float('inf'))
    with pytest.raises(ValueError):
        _evidence(page_index=-1)


def test_unknown_kind_rejected_visibly():
    with pytest.raises(ValueError, match='unsupported rule kind'):
        ScenarioCondition(rule_id='X', kind='GRZ', value=0.4, evidence_id='doc-synth-001')


def test_grz_grc_must_not_alias_to_footprint():
    # GRZ (site coverage ratio) is semantically distinct from an absolute
    # MAX_FOOTPRINT value and must be rejected, not silently computed.
    with pytest.raises(ValueError, match='unsupported rule kind'):
        ScenarioCondition(rule_id='GRZ-1', kind='GRZ', value=0.4, evidence_id='doc-synth-001')


def test_missing_value_stays_unknown_without_default():
    record = _evidence(value=None)
    assert record.value is None


def test_run_state_machine_happy_path():
    run = RunRecord(run_id='r1', project_id='p', design_version=1, scenario_version=1,
                    goal=GoalSpec(objective='balanced'))
    run = run.record_model_call().advance('planning').advance('searching').advance('verifying')
    done = run.finish('ready')
    assert done.state == 'ready'
    assert done.log == ['queued -> planning', 'planning -> searching',
                        'searching -> verifying', 'verifying -> ready']


def test_run_repair_budget_enforced():
    run = RunRecord(run_id='r2', project_id='p', design_version=1, scenario_version=1,
                    goal=GoalSpec(objective='balanced'))
    run = run.advance('planning').advance('searching').advance('verifying').advance('repairing')
    assert run.repairs == 1
    run = run.advance('searching').advance('verifying').advance('repairing')
    assert run.repairs == 2
    run = run.advance('searching').advance('verifying')
    with pytest.raises(ValueError, match='repair budget'):
        run.advance('repairing')


def test_run_model_call_budget_enforced():
    run = RunRecord(run_id='r3', project_id='p', design_version=1, scenario_version=1,
                    goal=GoalSpec(objective='balanced'))
    for _ in range(4):
        run = run.record_model_call()
    with pytest.raises(ValueError, match='model call budget'):
        run.record_model_call()


def test_run_illegal_transitions_rejected():
    run = RunRecord(run_id='r4', project_id='p', design_version=1, scenario_version=1,
                    goal=GoalSpec(objective='balanced'))
    with pytest.raises(ValueError, match='illegal transition'):
        run.advance('verifying')
    with pytest.raises(ValueError, match='reachable'):
        run.finish('ready')
    finished = run.finish('cancelled')
    with pytest.raises(ValueError, match='terminal'):
        finished.advance('planning')


def test_counter_example_names_condition_and_params():
    design = demo_project().design
    metrics = VariantMetrics(footprint_m2=90.0, gross_floor_area_m2=180.0,
                             ridge_height_m=8.0, storeys=2)
    candidate = VariantCandidate(
        design=design, metrics=metrics,
        violations=[CounterExample(condition_id='DEMO_MAX_FOOTPRINT', observed=150.0,
                                    limit=130.0, design_param='width_m')],
        evidence_ids=['doc-synth-001'])
    assert not candidate.feasible
    assert candidate.violations[0].design_param == 'width_m'


def test_gross_floor_area_is_not_living_area():
    design = demo_project().design  # 10 x 9 m, 2 storeys
    assert gross_floor_area_approx(design, 90.0) == 180.0
    with pytest.raises(ValueError):
        gross_floor_area_approx(design, math.nan)
