"""Clearly marked synthetic geometry: only marketing listing facts are verified."""
from .models import BuildingDesign, Parcel, PlanningRule, Point, Project
SOURCE='https://www.e-netz-suedhessen.de/bauen-anschliessen/baugrundstuecke-und-flaechen/infos-zu-baugrundstuecken/baugebiete-in-fuerth-schuetzengasse'

def demo_project():
    return Project(
        id='fuerth-schuetzengasse-2-10',
        parcel=Parcel(id='demo-parcel', name='Demo parcel (synthetic)',
            points=[Point(x=0,y=0),Point(x=21.1,y=0),Point(x=21.1,y=20),Point(x=0,y=20)],
            advertised_area_m2=422, source_url=SOURCE),
        design=BuildingDesign(center_x=10.55,center_y=10,width_m=10,depth_m=9),
        rules=[
            PlanningRule(id='DEMO_MAX_STOREYS',kind='MAX_STOREYS',value=2),
            PlanningRule(id='DEMO_MAX_FOOTPRINT',kind='MAX_FOOTPRINT',value=130),
            PlanningRule(id='DEMO_MAX_HEIGHT',kind='MAX_HEIGHT',value=9),
        ])
