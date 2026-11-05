"""Frontier foundation contracts: evidence, scenario, goal, variant and bounded run.

Additive v0.5 extension, offline by default. No model calls, no persistence
side effects, no legal assessment. Missing provenance stays UNKNOWN.
"""
import math
from typing import Literal
from pydantic import BaseModel, Field, field_validator

from .models import BuildingDesign, EvidenceStatus

# Supported rule kinds for the first foundation slice. Unknown kinds are
# rejected visibly instead of silently defaulted.
SUPPORTED_CONDITION_KINDS = ('MAX_STOREYS', 'MAX_FOOTPRINT', 'MAX_HEIGHT', 'ROOF_PITCH')

# Page convention: page_index is 0-based into the extracted PDF page list.
# Display layers must render it as page_index + 1.
PAGE_CONVENTION = 'page_index is 0-based; UI shows page_index + 1'


def _finite(value: float, name: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return value


class EvidenceRecord(BaseModel):
    """One extracted rule candidate with its provenance."""

    document_id: str = Field(min_length=1)
    document_sha256: str = Field(min_length=8)
    page_index: int = Field(ge=0)
    quote: str = Field(min_length=1)
    kind: str
    value: float | None = None
    unit: str | None = None
    status: EvidenceStatus = EvidenceStatus.EXTRACTED

    @field_validator('value')
    @classmethod
    def _value_finite(cls, value: float | None) -> float | None:
        if value is not None:
            _finite(value, 'value')
        return value

    @field_validator('status')
    @classmethod
    def _never_self_verified(cls, status: EvidenceStatus) -> EvidenceStatus:
        # Parser/adapter output must never arrive as VERIFIED. Promotion to
        # VERIFIED is a separate, unimplemented human/official-source step.
        if status == EvidenceStatus.VERIFIED:
            raise ValueError('extracted evidence must not arrive as VERIFIED')
        return status


class ScenarioCondition(BaseModel):
    """A user-confirmed condition adopted into the investigated scenario."""

    rule_id: str = Field(min_length=1)
    kind: str
    value: float
    unit: str | None = None
    evidence_id: str = Field(min_length=1)
    adopted: bool = False

    @field_validator('kind')
    @classmethod
    def _supported_kind(cls, kind: str) -> str:
        if kind not in SUPPORTED_CONDITION_KINDS:
            raise ValueError(f'unsupported rule kind: {kind}')
        return kind

    @field_validator('value')
    @classmethod
    def _value_finite(cls, value: float) -> float:
        return _finite(value, 'value')


class GoalSpec(BaseModel):
    """Structured user goal. Weights are transparent scenario assumptions."""

    objective: Literal['max_gross_floor_area', 'min_ridge_height', 'balanced']
    max_variants: int = Field(default=3, ge=1, le=3)
    note: str = Field(default='', max_length=480)


class VariantMetrics(BaseModel):
    footprint_m2: float
    gross_floor_area_m2: float
    ridge_height_m: float
    storeys: int

    @field_validator('footprint_m2', 'gross_floor_area_m2', 'ridge_height_m')
    @classmethod
    def _finite_metric(cls, value: float) -> float:
        return _finite(value, 'metric')


class CounterExample(BaseModel):
    """Verifier finding: which condition failed, by how much."""

    condition_id: str
    observed: float
    limit: float
    design_param: str

    @field_validator('observed', 'limit')
    @classmethod
    def _finite_counter(cls, value: float) -> float:
        return _finite(value, 'counter')


class VariantCandidate(BaseModel):
    """One deterministically computed candidate with metrics and findings."""

    design: BuildingDesign
    metrics: VariantMetrics
    violations: list[CounterExample] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return len(self.violations) == 0


RunState = Literal[
    'queued', 'planning', 'searching', 'verifying',
    'repairing', 'ready', 'cancelled', 'failed', 'no_solution',
]

TERMINAL_STATES: tuple[str, ...] = ('ready', 'cancelled', 'failed', 'no_solution')

_ALLOWED: dict[str, tuple[str, ...]] = {
    'queued': ('planning', 'cancelled'),
    'planning': ('searching', 'cancelled', 'failed'),
    'searching': ('verifying', 'cancelled', 'failed', 'no_solution'),
    'verifying': ('repairing', 'ready', 'no_solution', 'cancelled', 'failed'),
    'repairing': ('searching', 'cancelled', 'failed', 'no_solution'),
}

MAX_MODEL_CALLS = 4
MAX_REPAIRS = 2


class RunRecord(BaseModel):
    """Typed state machine for one bounded plan-check-repair run."""

    run_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    design_version: int = Field(ge=1)
    scenario_version: int = Field(ge=1)
    goal: GoalSpec
    state: RunState = 'queued'
    model_calls: int = Field(default=0, ge=0)
    repairs: int = Field(default=0, ge=0)
    log: list[str] = Field(default_factory=list)

    def advance(self, target: RunState) -> 'RunRecord':
        if self.state in TERMINAL_STATES:
            raise ValueError(f'run is terminal in {self.state}')
        if target not in _ALLOWED.get(self.state, ()):
            raise ValueError(f'illegal transition {self.state} -> {target}')
        if target == 'repairing':
            if self.repairs >= MAX_REPAIRS:
                raise ValueError('repair budget exhausted')
            return self.model_copy(update={'state': target, 'repairs': self.repairs + 1,
                                           'log': [*self.log, f'{self.state} -> {target}']})
        return self.model_copy(update={'state': target, 'log': [*self.log, f'{self.state} -> {target}']})

    def record_model_call(self) -> 'RunRecord':
        if self.model_calls >= MAX_MODEL_CALLS:
            raise ValueError('model call budget exhausted')
        return self.model_copy(update={'model_calls': self.model_calls + 1})

    def finish(self, outcome: RunState) -> 'RunRecord':
        if outcome not in TERMINAL_STATES:
            raise ValueError('finish requires a terminal state')
        if self.state in TERMINAL_STATES:
            raise ValueError(f'run is terminal in {self.state}')
        if outcome == 'ready' and self.state not in ('verifying',):
            raise ValueError('ready is only reachable from verifying')
        if outcome == 'no_solution' and self.state not in ('searching', 'verifying', 'repairing'):
            raise ValueError('no_solution is not reachable from here')
        if outcome in ('cancelled', 'failed'):
            return self.model_copy(update={'state': outcome, 'log': [*self.log, f'{self.state} -> {outcome}']})
        return self.model_copy(update={'state': outcome, 'log': [*self.log, f'{self.state} -> {outcome}']})


def gross_floor_area_approx(design: BuildingDesign, footprint_m2: float) -> float:
    """Rough gross floor area = footprint x storeys. NOT living area (WoFlV)."""
    _finite(footprint_m2, 'footprint_m2')
    return round(footprint_m2 * design.storeys, 2)
