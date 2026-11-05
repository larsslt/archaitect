"""Solar position and idealized rectangular building shadow.

NOAA-style approximation, suitable for an illustrative prototype, not a certified
sunlight or planning-law assessment. Azimuth clockwise from true north.
"""
from datetime import datetime
from math import asin, atan2, cos, degrees, floor, pi, radians, sin, tan
from pydantic import BaseModel, Field

class SolarRequest(BaseModel):
    latitude: float = Field(ge=-89.9, le=89.9)
    longitude: float = Field(ge=-180, le=180)
    timestamp: datetime
    height_m: float = Field(gt=0, le=250)

    @property
    def is_timezone_aware(self):
        return self.timestamp.utcoffset() is not None

class SolarResponse(BaseModel):
    elevation_deg: float
    azimuth_deg: float
    shadow_length_m: float | None
    shadow_east_m: float | None
    shadow_north_m: float | None
    sun_above_horizon: bool
    calculation: str = 'APPROXIMATE_SOLAR_GEOMETRY'
    disclaimer: str = 'Idealized flat terrain and simple height; excludes roof shape, vegetation and neighbouring buildings.'

def solar_position(request: SolarRequest) -> SolarResponse:
    if not request.is_timezone_aware:
        raise ValueError('timestamp must include an explicit UTC offset')
    instant = request.timestamp
    day = instant.timetuple().tm_yday
    local_hour = instant.hour + instant.minute / 60 + instant.second / 3600
    gamma = 2 * pi / 365 * (day - 1 + (local_hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868*cos(gamma) - 0.032077*sin(gamma) - 0.014615*cos(2*gamma) - 0.040849*sin(2*gamma))
    decl = (0.006918 - 0.399912*cos(gamma) + 0.070257*sin(gamma) - 0.006758*cos(2*gamma) + 0.000907*sin(2*gamma) - 0.002697*cos(3*gamma) + 0.00148*sin(3*gamma))
    offset_hours = instant.utcoffset().total_seconds()/3600
    tst = (local_hour*60 + eqtime + 4*request.longitude - 60*offset_hours) % 1440
    hour_angle = radians(tst/4 - 180)
    lat = radians(request.latitude)
    sin_elevation = sin(lat)*sin(decl) + cos(lat)*cos(decl)*cos(hour_angle)
    elevation = asin(max(-1, min(1, sin_elevation)))
    # atan2 produces solar azimuth measured clockwise from north.
    azimuth = (degrees(atan2(sin(hour_angle),cos(hour_angle)*sin(lat) - tan(decl)*cos(lat))) + 180) % 360
    above = elevation > radians(0.1)
    if not above:
        return SolarResponse(elevation_deg=round(degrees(elevation),3),azimuth_deg=round(azimuth,3),shadow_length_m=None,shadow_east_m=None,shadow_north_m=None,sun_above_horizon=False)
    length = request.height_m/tan(elevation)
    opposite = radians((azimuth+180)%360)
    return SolarResponse(elevation_deg=round(degrees(elevation),3),azimuth_deg=round(azimuth,3),shadow_length_m=round(length,3),shadow_east_m=round(length*sin(opposite),3),shadow_north_m=round(length*cos(opposite),3),sun_above_horizon=True)
