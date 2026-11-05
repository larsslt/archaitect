from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from archaitect.solar import SolarRequest, solar_position
from archaitect.main import app

FRANKFURT = ZoneInfo('Europe/Berlin')

def request(hour, month=6, day=21):
    return SolarRequest(latitude=50.11,longitude=8.68,height_m=8,
                        timestamp=datetime(2026,month,day,hour,tzinfo=FRANKFURT))

def test_summer_midday_sun_is_high_and_to_south():
    result = solar_position(request(13))
    assert 55 < result.elevation_deg < 65
    assert 150 < result.azimuth_deg < 210
    assert result.sun_above_horizon
    assert result.shadow_north_m > 0

def test_winter_midday_sun_is_low_and_shadow_longer():
    summer=solar_position(request(13))
    winter=solar_position(request(12,12,21))
    assert winter.elevation_deg < summer.elevation_deg
    assert winter.shadow_length_m > summer.shadow_length_m

def test_night_does_not_make_a_fake_shadow():
    result=solar_position(request(2))
    assert not result.sun_above_horizon
    assert result.shadow_length_m is None

def test_timezone_required():
    client=TestClient(app)
    body={'latitude':50.11,'longitude':8.68,'height_m':8,'timestamp':'2026-06-21T12:00:00'}
    assert client.post('/simulation/solar',json=body).status_code==422

def test_solar_endpoint():
    client=TestClient(app)
    body={'latitude':50.11,'longitude':8.68,'height_m':8,'timestamp':'2026-06-21T13:00:00+02:00'}
    response=client.post('/simulation/solar',json=body)
    assert response.status_code == 200
    assert response.json()['sun_above_horizon']
