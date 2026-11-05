"""Versioned domain contracts; local coordinates use meters, NOT WGS84 degrees."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class EvidenceStatus(str, Enum):
    VERIFIED = 'VERIFIED'
    EXTRACTED = 'EXTRACTED'
    DEMO_ASSUMPTION = 'DEMO_ASSUMPTION'

class Status(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNKNOWN = 'UNKNOWN'

class Point(BaseModel):
    x: float
    y: float

class Parcel(BaseModel):
    id: str
    name: str
    points: list[Point] = Field(min_length=3)
    coordinate_system: str = 'LOCAL_METRIC_DEMO'
    geometry_status: EvidenceStatus = EvidenceStatus.DEMO_ASSUMPTION
    advertised_area_m2: float | None = None
    source_url: str | None = None

class BuildingDesign(BaseModel):
    id: str = 'design-001'
    version: int = Field(default=1, ge=1)
    center_x: float
    center_y: float
    width_m: float = Field(gt=0, le=100)
    depth_m: float = Field(gt=0, le=100)
    rotation_deg: float = Field(default=0, ge=-360, le=360)
    storeys: int = Field(default=2, ge=1, le=10)
    eave_height_m: float = Field(default=6.0, gt=0)
    ridge_height_m: float = Field(default=8.0, gt=0)
    roof_type: Literal['flat','gable'] = 'gable'
    roof_pitch_deg: float = Field(default=30.0, ge=0, le=80)

    @model_validator(mode='after')
    def check_heights(self):
        if self.ridge_height_m < self.eave_height_m:
            raise ValueError('ridge height must not be below eave height')
        return self

class PlanningRule(BaseModel):
    id: str
    kind: Literal['MAX_STOREYS','MAX_FOOTPRINT','BUILDING_ENVELOPE','MAX_HEIGHT','ROOF_PITCH']
    value: float | None = None
    review_status: EvidenceStatus = EvidenceStatus.DEMO_ASSUMPTION
    source_url: str | None = None
    source_quote: str | None = None
    page: int | None = None

class ValidationResult(BaseModel):
    rule_id: str
    status: Status
    message: str
    observed_value: float | None = None
    permitted_value: float | None = None
    evidence_status: EvidenceStatus

class Project(BaseModel):
    id: str
    parcel: Parcel
    design: BuildingDesign
    rules: list[PlanningRule]
    envelope: list[Point] | None = None   # buildable envelope in the parcel's coordinates (only set from verified constraints)

class PreviewRequest(BaseModel):
    design: BuildingDesign

class CommitRequest(BaseModel):
    design: BuildingDesign
    expected_version: int = Field(ge=1)

class ValidationResponse(BaseModel):
    results: list[ValidationResult]
    footprint_m2: float
    parcel_area_m2: float
    overall: Status
