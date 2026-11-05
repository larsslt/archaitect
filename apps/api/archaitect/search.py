"""Phase-3 deterministic search, independent verifier and bounded repair.

Offline by design: no model calls, no persistence writes, no source or
budget changes. Repair adjusts only draft design parameters, never
conditions, evidence or limits. A sampled best is reported as such --
never as a globally proven optimum.
"""
from pydantic import BaseModel, Field

from .geometry import footprint_polygon, parcel_polygon
from .models import BuildingDesign, Parcel
from .scenario import (
    CounterExample,
    GoalSpec,
    RunRecord,
    ScenarioCondition,
    VariantCandidate,
    VariantMetrics,
    gross_floor_area_approx,
)

MIN_DIM_M = 5.0
DIM_STEP_M = 1.0
MAX_CANDIDATES = 27


class SearchSpace(BaseModel):
    """Bounded grid around the current draft. Small by design."""

    widths: list[float] = Field(default=[8.0, 10.0, 12.0])
    depths: list[float] = Field(default=[7.0, 9.0, 11.0])
    storeys_options: list[int] = Field(default=[1, 2])

    def candidates(self) -> int:
        return len(self.widths) * len(self.depths) * len(self.storeys_options)


def _finite_or_raise(value: float, name: str) -> float:
    import math
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return value


def verify_design(parcel: Parcel, design: BuildingDesign,
                  conditions: list[ScenarioCondition]) -> list[CounterExample]:
    """Independent deterministic check. Returns one finding per violation."""
    _finite_or_raise(design.width_m, 'width_m')
    _finite_or_raise(design.depth_m, 'depth_m')
    _finite_or_raise(design.ridge_height_m, 'ridge_height_m')
    findings: list[CounterExample] = []
    parcel_shape = parcel_polygon(parcel)
    footprint = footprint_polygon(design)
    if not parcel_shape.covers(footprint):
        findings.append(CounterExample(
            condition_id='PARCEL_CONTAINMENT',
            observed=round(footprint.area, 3),
            limit=round(parcel_shape.area, 3),
            design_param='center_x',
        ))
    for condition in conditions:
        if condition.kind == 'MAX_STOREYS':
            observed: float = float(design.storeys)
            param = 'storeys'
        elif condition.kind == 'MAX_FOOTPRINT':
            observed = float(footprint.area)
            param = 'width_m'
        elif condition.kind == 'MAX_HEIGHT':
            observed = float(design.ridge_height_m)
            param = 'ridge_height_m'
        elif condition.kind == 'ROOF_PITCH':
            observed = float(design.roof_pitch_deg)
            param = 'roof_pitch_deg'
        else:  # pragma: no cover - guarded at adoption already
            continue
        if observed > condition.value + 1e-8:
            findings.append(CounterExample(
                condition_id=condition.rule_id,
                observed=round(observed, 3),
                limit=condition.value,
                design_param=param,
            ))
    return findings


def measure(design: BuildingDesign, parcel: Parcel) -> VariantMetrics:
    area = float(footprint_polygon(design).area)
    return VariantMetrics(
        footprint_m2=round(area, 2),
        gross_floor_area_m2=gross_floor_area_approx(design, area),
        ridge_height_m=design.ridge_height_m,
        storeys=design.storeys,
    )


def generate_candidates(base: BuildingDesign, space: SearchSpace) -> list[BuildingDesign]:
    """Deterministic grid. Raises before computing when unbounded."""
    if space.candidates() > MAX_CANDIDATES:
        raise ValueError(f'search space too large: {space.candidates()} > {MAX_CANDIDATES}')
    if space.candidates() == 0:
        raise ValueError('empty search space')
    out: list[BuildingDesign] = []
    for width in space.widths:
        for depth in space.depths:
            for storeys in space.storeys_options:
                if width < MIN_DIM_M or depth < MIN_DIM_M:
                    continue
                data = base.model_dump()
                data.update({'width_m': width, 'depth_m': depth, 'storeys': storeys})
                out.append(BuildingDesign.model_validate(data))
    if not out:
        raise ValueError('empty search space after dimension floor')
    return out


def rank(candidates: list[VariantCandidate], goal: GoalSpec) -> list[VariantCandidate]:
    """Transparent ordering, no hidden weights. Lexicographic by objective."""
    feasible = [c for c in candidates if c.feasible]
    if goal.objective == 'max_gross_floor_area':
        key = lambda c: (-c.metrics.gross_floor_area_m2, c.metrics.ridge_height_m)
    elif goal.objective == 'min_ridge_height':
        key = lambda c: (c.metrics.ridge_height_m, -c.metrics.gross_floor_area_m2)
    else:  # balanced: more floor area first, lower height breaks ties
        key = lambda c: (-c.metrics.gross_floor_area_m2, c.metrics.ridge_height_m)
    return sorted(feasible, key=key)[:goal.max_variants]


def repair_once(design: BuildingDesign, parcel: Parcel,
                violations: list[CounterExample]) -> BuildingDesign | None:
    """One deterministic fix for the first violation. None = unrepairable."""
    if not violations:
        return None
    first = violations[0]
    data = design.model_dump()
    if first.condition_id == 'PARCEL_CONTAINMENT':
        centroid = parcel_polygon(parcel).centroid
        data.update({'center_x': round(centroid.x, 2), 'center_y': round(centroid.y, 2)})
    elif first.design_param == 'storeys':
        if design.storeys <= 1:
            return None
        data['storeys'] = design.storeys - 1
    elif first.design_param == 'width_m':
        # Single computed shrink to fit: largest fitting depth/width on the
        # step grid, so one repair suffices instead of many 1 m iterations.
        import math as _math
        limit = first.limit
        fitting_depth = _math.floor(limit / design.width_m / DIM_STEP_M) * DIM_STEP_M
        fitting_width = _math.floor(limit / design.depth_m / DIM_STEP_M) * DIM_STEP_M
        if MIN_DIM_M <= fitting_depth < design.depth_m:
            data['depth_m'] = round(fitting_depth, 2)
        elif MIN_DIM_M <= fitting_width < design.width_m:
            data['width_m'] = round(fitting_width, 2)
        else:
            return None
    elif first.design_param == 'ridge_height_m':
        if design.ridge_height_m - 0.5 < design.eave_height_m:
            return None
        data['ridge_height_m'] = round(design.ridge_height_m - 0.5, 2)
    elif first.design_param == 'roof_pitch_deg':
        if design.roof_pitch_deg <= 0:
            return None
        data['roof_pitch_deg'] = round(max(0.0, design.roof_pitch_deg - 5.0), 2)
    else:  # pragma: no cover - verifier only emits known params
        return None
    return BuildingDesign.model_validate(data)


def run_search(parcel: Parcel, base: BuildingDesign,
               conditions: list[ScenarioCondition], goal: GoalSpec,
               space: SearchSpace, run: RunRecord,
               evidence_ids: list[str] | None = None
               ) -> tuple[RunRecord, list[VariantCandidate]]:
    """Bounded plan-check-repair loop. Returns the run and honestly few variants.

    The sampled best is NOT a globally proven optimum; an empty search
    space yields no_solution, never faked variants.
    """
    evidence = evidence_ids or []
    # Search and repair consume no model calls; only the repair budget.
    run = run.advance('planning').advance('searching')
    grid = generate_candidates(base, space)
    run = run.advance('verifying')
    checked = [VariantCandidate(design=d, metrics=measure(d, parcel),
                                violations=verify_design(parcel, d, conditions),
                                evidence_ids=evidence) for d in grid]
    feasible = rank(checked, goal)
    if feasible:
        return run.finish('ready'), feasible
    # Bounded repair: fix the least-violated candidate, re-verify, repeat.
    pool = sorted(checked, key=lambda c: (len(c.violations), -c.metrics.gross_floor_area_m2))
    while True:
        candidate = pool[0]
        run = run.advance('repairing')
        fixed = repair_once(candidate.design, parcel, candidate.violations)
        run = run.advance('searching').advance('verifying')
        if fixed is None:
            return run.finish('no_solution'), []
        rechecked = VariantCandidate(design=fixed, metrics=measure(fixed, parcel),
                                     violations=verify_design(parcel, fixed, conditions),
                                     evidence_ids=evidence)
        if rechecked.feasible:
            return run.finish('ready'), rank([rechecked], goal)
        pool = [rechecked]
