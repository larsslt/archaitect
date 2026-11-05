"""Conservative constraint evaluator: unverified legal rules NEVER yield PASS."""
from shapely.geometry import Polygon
from .geometry import footprint_polygon, parcel_polygon
from .models import EvidenceStatus, Project, Status, ValidationResponse, ValidationResult

def validate(project: Project) -> ValidationResponse:
    parcel = parcel_polygon(project.parcel)
    footprint = footprint_polygon(project.design)
    results: list[ValidationResult] = []
    def append(rule_id, ok, message, observed=None, maximum=None, evidence=EvidenceStatus.DEMO_ASSUMPTION):
        status = Status.UNKNOWN if evidence != EvidenceStatus.VERIFIED else (Status.PASS if ok else Status.FAIL)
        results.append(ValidationResult(rule_id=rule_id, status=status, message=message, observed_value=observed, permitted_value=maximum, evidence_status=evidence))

    # Physical containment is valid for the supplied boundary, but must be qualified
    # if the underlying geometry is synthetic.
    append('PARCEL_CONTAINMENT', parcel.covers(footprint),
           'Footprint fits inside supplied parcel' if parcel.covers(footprint) else 'Footprint exceeds supplied parcel',
           evidence=project.parcel.geometry_status)
    for rule in project.rules:
        if rule.value is None:
            results.append(ValidationResult(rule_id=rule.id, status=Status.UNKNOWN, message='Rule value missing', evidence_status=rule.review_status))
            continue
        if rule.kind == 'MAX_STOREYS':
            actual = project.design.storeys
        elif rule.kind == 'MAX_FOOTPRINT':
            actual = footprint.area
        elif rule.kind == 'MAX_HEIGHT':
            actual = project.design.ridge_height_m
        elif rule.kind == 'ROOF_PITCH':
            actual = project.design.roof_pitch_deg
        elif rule.kind == 'BUILDING_ENVELOPE' and project.envelope and len(project.envelope) >= 3:
            env = Polygon([(p.x, p.y) for p in project.envelope])
            ok = env.is_valid and env.covers(footprint)
            append(rule.id, ok, 'Footprint inside the buildable envelope (uniform setback only; Baugrenzen, Baulasten and Leitungsrechte are not modelled)', round(footprint.difference(env).area, 3), 0.0, rule.review_status)
            continue
        else:
            results.append(ValidationResult(rule_id=rule.id, status=Status.UNKNOWN, message='Rule requires georeferenced envelope geometry', evidence_status=rule.review_status))
            continue
        append(rule.id, actual <= rule.value + 1e-8, 'Checked against supplied constraint (not a legal approval)', round(actual, 3), rule.value, rule.review_status)
    overall = Status.FAIL if any(r.status == Status.FAIL for r in results) else (Status.UNKNOWN if any(r.status == Status.UNKNOWN for r in results) else Status.PASS)
    return ValidationResponse(results=results, footprint_m2=round(footprint.area,2), parcel_area_m2=round(parcel.area,2), overall=overall)
