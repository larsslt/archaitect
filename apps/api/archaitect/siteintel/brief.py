"""Planning brief: what the user wants to build and what they know about the plot — structured so that an AI can retrieve it reliably.

Rules: free text lives in dedicated *_de fields; everything else is typed. Unknown stays ``None`` (never a guessed default). User-supplied
connection points are marked USER_SUPPLIED; nothing in the brief is treated as verified building law.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator

SCHEMA = 'archaitect.planning-brief/1'
ConnectionKind = Literal['wasser', 'abwasser', 'regenwasser', 'gas', 'strom', 'telekom', 'fernwaerme']
Basement = Literal['none', 'partial', 'full', 'unknown']
Roof = Literal['sattel', 'walm', 'pult', 'flach', 'zelt', 'kruppelwalm', 'egal']
Energy = Literal['geg', 'kfw55', 'kfw40', 'passivhaus', 'unknown']
Heating = Literal['waermepumpe', 'fernwaerme', 'gas', 'pellets', 'strom', 'unknown']
Access = Literal['standard', 'barrierearm', 'barrierefrei']


class Room(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    area_m2: float | None = Field(default=None, gt=0, le=500)
    count: int = Field(default=1, ge=1, le=20)
    notes_de: str = Field(default='', max_length=300)


class Program(BaseModel):
    occupants: int | None = Field(default=None, ge=1, le=30)
    bedrooms: int | None = Field(default=None, ge=0, le=20)
    bathrooms: int | None = Field(default=None, ge=0, le=10)
    home_office: bool | None = None
    living_area_target_m2: float | None = Field(default=None, gt=20, le=1500, description='Wohnfläche, Zielwert')
    stories: int | None = Field(default=None, ge=1, le=8)
    basement: Basement = 'unknown'
    roof_types: list[Roof] = []
    garages: int | None = Field(default=None, ge=0, le=6)
    carports: int | None = Field(default=None, ge=0, le=6)
    style_keywords_de: list[str] = Field(default=[], max_length=12)
    materials_de: list[str] = Field(default=[], max_length=12)
    energy_standard: Energy = 'unknown'
    heating: Heating = 'unknown'
    accessibility: Access = 'standard'
    budget_eur_max: float | None = Field(default=None, gt=0)
    rooms: list[Room] = Field(default=[], max_length=40)


class ConnectionPoint(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    kind: ConnectionKind
    lon: float
    lat: float
    status: Literal['USER_SUPPLIED', 'AUTHORITY_PLAN', 'ESTIMATE'] = 'USER_SUPPLIED'
    note_de: str = Field(default='', max_length=300)
    depth_m: float | None = Field(default=None, ge=0, le=10)
    diameter_mm: float | None = Field(default=None, ge=0, le=2000)

    @field_validator('lon')
    @classmethod
    def _lon(cls, v: float) -> float:
        if not 7.5 <= v <= 10.5:
            raise ValueError('Punkt liegt außerhalb Hessens')
        return v

    @field_validator('lat')
    @classmethod
    def _lat(cls, v: float) -> float:
        if not 49.2 <= v <= 51.8:
            raise ValueError('Punkt liegt außerhalb Hessens')
        return v


class UtilitiesEnquiry(BaseModel):
    status: Literal['not_requested', 'requested', 'received'] = 'not_requested'
    via: str = Field(default='', max_length=80, description='z. B. BIL-Portal oder Name des Netzbetreibers')
    note_de: str = Field(default='', max_length=300)


class Orientation(BaseModel):
    living_towards: Literal['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW', 'egal'] = 'egal'
    garden_side: Literal['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW', 'egal'] = 'egal'
    entrance_from_street: bool = True


class PlanningBrief(BaseModel):
    schema_version: str = SCHEMA
    title: str = Field(default='Neues Wohnhaus', max_length=120)
    program: Program = Program()
    wishes_de: str = Field(default='', max_length=4000)
    avoid_de: str = Field(default='', max_length=2000)
    orientation: Orientation = Orientation()
    connections: list[ConnectionPoint] = Field(default=[], max_length=40)
    utilities_enquiry: UtilitiesEnquiry = UtilitiesEnquiry()
    notes_de: str = Field(default='', max_length=4000)
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec='seconds'))
