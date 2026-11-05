"""Erzeugt docs/BIBLIOTHEK.md aus materials/library.json und bimrender/catalog.py (nie von Hand pflegen).
Aufruf: python tools/catalog_doc.py"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bimrender import catalog, library, typologies  # noqa: E402

ROADMAP = """## Ausbaustufen (Pareto)

| Stufe | Inhalt | Status |
|---|---|---|
| 1 | Putzfarben, Ziegel/Klinker, Naturstein, Dachdeckungen, Hölzer, Lacke, Metalle, Glas, Beläge; Fenster-/Türtypen, Bögen, Sprossen, Gewände, Läden, Gesimse, Ecksteine, Lisenen, Säulen, Konsolen, Vordach, Treppe, Schornstein, Fallrohr, Leuchte, Schild, Zaun; Walm-/Pultdach; fünf Fachwerkmuster | fertig |
| 2 | Mansard- und Bohlendach, Türme/Kuppeln/Zwiebelhelme (auch Polygonturm), Erker (eckig/geknickt), Arkade, Markise, Bossenwerk, Zahnschnitt, Dachrinne, Ortgangbrett, Dachfenster, Garagen- und Ladentür | fertig |
| 2b | Gaubenformen (Schleppgaube, Giebelgaube, Fledermaus), Loggia/Balkontypen mit Geländerarten, Rollladenkasten, Sprossenteilung nach Stilepochen, Fenster in Gambrel-/Mansard-Giebeln, Dachaufbauten auf Mansard | geplant |
| 3 | Moderne Bauweisen: Solar (Flachdach/Satteldach), Technikaufbau, Rampe, Terrasse, Carport, Stützmauer, Außentreppe, Sheddach, Geländertypen (Stäbe/Glas/Vollbrüstung/Seile), französische Tür, Glas je Öffnung, Fassadenplatten und Vorhangfassadenglas; Kompaktnotation `storeys`/`repeat` | fertig |
| 3b | Logikschicht (`logic.py`): Balkon/Terrasse/Loggia/Außentreppe/Eingangstreppe/Rampe erhalten automatisch passende Tür, Vordach über Tür, Überlappungs- und Carport-Prüfung; Loggia (vorgesetzt), Strebepfeiler, Pylon, Stellplätze | fertig |
| 3c | Konfliktlöser (`logic.resolve`): Fenster werden an Türen/Erkern/Balkonplatten/Gesims beschnitten oder entfernt, Fallrohr/Lampe/Schild/Pilaster/Säule rücken auf freie Stelle, Vordach wird neben Fenstern gekürzt; alles als Warnung „Automatisch ergänzt“ | fertig |
| 5 | Gartenobjekte: Baum, Hecke, Strauch, Beet, Weg, Pool, Bank, Gartenset, Gartenleuchte (Gras wächst nicht durch Weg/Pool/Beet) | fertig |
| 4 | Ornament: Zahnschnitt, Konsolfries, Pilasterkapitelle (ionisch, korinthisch), Giebelfelder mit Relief, Schnitzwerk an Fachwerkbalken, Balkonkonsolen, Türmchen/Dachreiter, Zwiebel- und Kegelhelm, Fialen, Maßwerkfenster, Rosette; Natursteinmauern mit unregelmäßigem Verband; Pflanzen (Rankgerüst, Spalierobst) | geplant |
| 5 | Innenausbau-Katalog (Küchen, Bäder, Treppentypen, Türzargen, Fußleisten), Möbelfamilien nach Stil | geplant |
"""


COVERAGE = {
    "efh_satteldach": ("abgenommen", "Spec 2 (Landhaus) und Spec 3 (Solarhaus)"),
    "doppel_reihenhaus": ("Katalog deckt ab", "mehrere Volumen Stoß an Stoß, nicht gerendert"),
    "stadtvilla_walmdach": ("abgenommen", "Spec 2 (Turmvilla)"),
    "bungalow_flach": ("Katalog deckt ab", "nicht gerendert"),
    "fachwerkhaus": ("abgenommen", "Referenzfall des Projekts"),
    "bauernhaus_scheune": ("abgenommen", "Spec 2 (Scheune); Giebelfenster bei gambrel fehlen"),
    "reetdachhaus": ("Katalog deckt ab", "Material thatch vorhanden, Gaube nur Standardform"),
    "villa_historisch": ("abgenommen", "Spec 1 und 2"),
    "mehrfamilienhaus": ("abgenommen", "Spec 3 (Wohnblock mit Balkonen, Solar, Außentreppe)"),
    "blockrand_gruenderzeit": ("teilweise", "Mansard, Erker, Gesimse ok; Stuckornament fehlt"),
    "plattenbau": ("teilweise", "Loggia nur vorgesetzt (nicht eingerückt); Balkone mit Tür-Logik ok"),
    "buero_glas": ("abgenommen", "Spec 3 (Bürohaus mit Glasraster)"),
    "buero_beton": ("Katalog deckt ab", "wie Bürohaus mit Faserzement/Beton"),
    "gewerbehalle": ("abgenommen", "Spec 3 (Halle mit Sheddach, Sektionaltoren, Rampe)"),
    "supermarkt_handel": ("abgenommen", "Spec 3 (Supermarkt mit Pylon, Stellplätzen, Rampe)"),
    "schule_kita": ("abgenommen", "Spec 3 (Schulpavillon mit Terrasse, Carport)"),
    "kirche": ("teilweise", "Kapelle mit Spitzbogen und Strebepfeilern abgenommen; Turmkirche nur per tower-Bauteil, Gewölbe nicht"),
    "moderner_kubus": ("abgenommen", "Villa Kubus"),
    "hochhaus_turm": ("teilweise", "Raster per repeat ok; runde Baukörper und Kern nicht"),
}


def main():
    lib = {k: v for k, v in library.load().items() if not v.get("render_only")}
    groups = defaultdict(list)
    for k, v in lib.items():
        groups[v["group"]].append((k, v))
    out = ["# Bauteil- und Materialbibliothek", "",
           "Automatisch erzeugt mit `python tools/catalog_doc.py`. Quellen: `materials/library.json` (Materialien), `bimrender/catalog.py` (Bauteile).", "",
           f"**{len(lib)} Materialien, {len(catalog.C)} parametrische Komponenten, Öffnungs-Typfamilien, 6 Dachformen, 5 Fachwerkmuster.**", "",
           "## Materialien", ""]
    for g in sorted(groups):
        out += [f"### {g} ({len(groups[g])})", "", "| Schlüssel | Bezeichnung | Shader | auch gemeint |", "|---|---|---|---|"]
        for k, v in groups[g]:
            out.append(f"| `{k}` | {v['label']} | {v['shader']['kind']} | {', '.join(v.get('aliases', []))} |")
        out.append("")
    out += ["## Gebäudetypologien und ehrliche Abdeckung", "",
            "Keine gemessene Prozentzahl: die Tabelle sagt, was gerendert und geprüft wurde und wo der Katalog Lücken hat.", "",
            "| Typologie | Status | Hinweis |", "|---|---|---|"]
    for k, d in typologies.T.items():
        st, note = COVERAGE.get(k, ("offen", ""))
        out.append(f"| `{k}` – {d['label']} | {st} | {note} |")
    out += ["", "Bekannte Lücken: eingerückte Loggien (nur vorgesetzt), runde Baukörper (nur Türme), Gewölbe, Stuckornament, Gauben nur als Standardform, Fenster in Gambrel-/Mansardgiebeln, Gelände/Topografie, Vegetation nur einfach.", ""]
    out += ["## Komponenten (`components[]`)", ""]
    for t, d in catalog.C.items():
        out += [f"### `{t}` – {d['label']}", "", "| Parameter | Typ/Bereich | Standard | Bedeutung |", "|---|---|---|---|"]
        for k, (ty, default, lo, hi, txt) in d["params"].items():
            rng = f"{lo}..{hi}" if ty in ("n", "i") else "|".join(map(str, lo)) if ty == "e" else {"st": "Materialschlüssel", "b": "bool", "p": "Punktliste"}.get(ty, "")
            out.append(f"| `{k}` | {rng} | {'' if default is None else default} | {txt} |")
        out.append("")
    out += ["## Öffnungen, Dächer, Fachwerk", "", "```", catalog.prompt_table().split("# Typen an Öffnungen", 1)[1].strip(), "```", "", ROADMAP]
    p = ROOT / "docs" / "BIBLIOTHEK.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("geschrieben", p, len(out), "Zeilen")


if __name__ == "__main__":
    main()
