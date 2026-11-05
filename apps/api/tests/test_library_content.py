"""Every library object and house must build to a valid IFC/mesh (preview) and pass the plausibility audit."""
import json
from pathlib import Path

import pytest

from archaitect.bim import logic, objects, thumbs
from archaitect.bim.catalog import C
from archaitect.siteintel.bim_api import LIBRARY_HOUSES

NEW_HOUSES = ("klassik_lib", "pultdach_lib", "reetdach_lib", "mediterran_lib", "kapelle_lib", "speicher_lib", "orangerie_lib",
             "schloss_lib", "rathaus_lib", "hangvilla_lib", "jugendstil_lib", "gutshof_lib", "palais_lib", "lodge_lib", "muehle_lib", "palladio_lib")
SPECS = Path(thumbs.__file__).parent / "specs"


def test_every_object_base_type_exists():
    for kind, (cat, base, over, label) in objects.LIBRARY_OBJECTS.items():
        assert base in C, kind
        assert label and cat
        assert set(over) <= set(C[base]["params"]), kind


@pytest.mark.parametrize("kind", [k for k in objects.LIBRARY_OBJECTS if k in objects.G2_OBJECTS or k.endswith(("_large", "_slim", "_1", "_row", "_post"))])
def test_object_preview_builds(kind):
    assert thumbs.mesh_file(kind, LIBRARY_HOUSES).exists()


@pytest.mark.parametrize("name", NEW_HOUSES)
def test_new_house_builds_and_audits_clean(name):
    assert name in LIBRARY_HOUSES
    spec = json.loads((SPECS / f"{name}.json").read_text(encoding="utf-8"))
    done, _notes = logic.complete(spec)
    assert logic.audit(done) == []
    assert thumbs.mesh_file(name, LIBRARY_HOUSES).exists()


def test_english_ui_dictionary_covers_library():
    """The English UI (apps/web/app/lib/i18n-en.json) must name every library category, object and house."""
    path = Path(__file__).resolve().parents[2] / "web" / "app" / "lib" / "i18n-en.json"
    en = json.loads(path.read_text(encoding="utf-8"))
    from archaitect.siteintel.bim_api import _library_spec
    names = {cat for cat, *_ in objects.LIBRARY_OBJECTS.values()} | {v[3] for v in objects.LIBRARY_OBJECTS.values()}
    names |= {(_library_spec(h).get("name") or h) for h in LIBRARY_HOUSES}
    international = {"Bungalow", "Café", "Garage", "Pergola", "Pool", "Tiny House", "Loft", "Kita", "Whirlpool"}     # identical in English
    missing = sorted(n for n in names if n not in en and n not in international)
    print(missing)
    assert not missing, missing
