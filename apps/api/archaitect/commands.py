"""Allowlisted deterministic building commands. The future LLM may propose these JSON actions."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from .models import BuildingDesign

class DesignCommand(BaseModel):
    action: Literal['resize_building','rotate_building','move_building','set_storeys']
    width_m: float | None = Field(default=None, gt=0, le=100)
    depth_m: float | None = Field(default=None, gt=0, le=100)
    rotation_deg: float | None = Field(default=None, ge=-360, le=360)
    center_x: float | None = None
    center_y: float | None = None
    storeys: int | None = Field(default=None, ge=1, le=10)

    @model_validator(mode='after')
    def enforce_arguments(self):
        required={'resize_building': ('width_m','depth_m'), 'rotate_building':('rotation_deg',),
                  'move_building':('center_x','center_y'),'set_storeys':('storeys',)}
        allowed=set(required[self.action]); provided={k for k in ['width_m','depth_m','rotation_deg','center_x','center_y','storeys'] if getattr(self,k) is not None}
        if not provided or not provided.issubset(allowed):
            raise ValueError('Missing expected parameters or extra parameters for action')
        return self

def apply_command(design: BuildingDesign, command: DesignCommand) -> BuildingDesign:
    update={k: v for k,v in command.model_dump(exclude={'action'}).items() if v is not None}
    return BuildingDesign.model_validate({**design.model_dump(), **update})
