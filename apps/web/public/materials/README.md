# Materialien / Licht (Aufgabe 13)

## Pipeline
- Ein Renderer: `SiteScene` (`apps/web/app/studio/scene3d.ts`) + `EntwurfScene`
  (`apps/web/app/entwurf/scene.ts`) + Geometrie aus `apps/web/app/entwurf/bauform.ts`.
- Kein neuer KI-Bildweg, keine Renderfarm, keine externen Anbieter.
- PBR-Parameter zentral: `apps/web/app/entwurf/materials.ts`
  (`PBR_PARAMS`, `makePbrMaterial`, `applyMetricUVs`, `applyShadowFlags`).
- `MAT_DEFAULTS` in `bauform.ts` nutzt dieselben Zielwerte (Putz, Holz, Beton,
  Dach/Ziegel/Blech, Glas, Rahmen/Metall).

## Materialwerte (roughness/metalness, auf ACES/Exposure ~1.0 abgestimmt)
- Putz `#e6e3db`, roughness 0.94, metalness 0.0
- Holz `#a97a4e`, roughness 0.72, metalness 0.0
- Beton `#b9bab5`/`#c9c7c0`, roughness 0.90–0.92, metalness 0.0
- Dach `#5b6067`, roughness 0.85 · Ziegel `#7a3d30`, roughness 0.82 ·
  Blech `#8d949c`, roughness 0.50, metalness 0.60
- Glas `#a8c0cf`, roughness 0.08, metalness 0.0, opacity 0.38, transparent,
  `depthWrite: false`, `DoubleSide` (keine schwarzen Loecher)
- Rahmen/Metall `#3a3f46`, roughness 0.42, metalness 0.75

## Metrische UVs
- `applyMetricUVs(geo, sizeU_m, sizeV_m)` skaliert 0..1-UVs (Box/Streifen) auf Meter,
  damit Texturen auf allen Fassaden gleich wirken.
- `ExtrudeGeometry` liefert bereits Meter-UVs und bleibt unveraendert.

## Licht / Schatten / Farbe
- Renderer (Bestand, `studio/scene3d.ts`): `SRGBColorSpace`, `ACESFilmicToneMapping`,
  Exposure 1.05, `PCFSoftShadowMap`, Hemisphere + DirectionalLight mit
  `bias -0.0003` / `normalBias 0.04` (keine schwebenden Schatten, kein Peter-Panning).
- `EntwurfScene.updateSun/applyMode` erzwingt schwarzen Hintergrund/Grundstueck
  (`#000000`/`#080808`) auch nach Kamera-/Lichtwechsel; kein Luftbild im Entwurf.
- Glas wirft keinen Schatten (`castShadow = false`), empfaengt aber Schatten;
  alle opaken Meshes `castShadow + receiveShadow` (Erdung, kein Schweben).

## Assets / Lizenzen
- Keine externen Texturen, keine CDN-Abhaengigkeit, keine HDR/EXR-Dateien.
- Alle Materialien sind prozedurale `MeshStandardMaterial`-Werte (eigene Arbeit,
  keine Lizenzpflicht). three.js ist unter `public/vendor/three` vendored (MIT,
  siehe `public/vendor/three/LICENSE`).
- Herkunft: eigene PBR-Zielwerte, abgestimmt auf ACES-Pipeline des bestehenden
  Renderers; keine kopierten Texturen.

## Grenzen (offen)
- Keine gemessenen FPS/Build-Screenshots in dieser Aufgabe (Browserpruefung und
  Produktionsbuild sind separates Gate); visuelle Pruefung aller Fassaden
  (N/S/O/W, Draufsicht, Perspektive) steht aus und ist dokumentiert.
