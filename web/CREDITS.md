# Asset credits and licenses

Every image and terrain file in this site is real, public data made by other
people. Nothing in the 3-D scene is hand-modelled: the clouds, ground, seabed
and aerial photo are rasters downloaded once (no accounts, no API keys) and
re-encoded for the web. The only things drawn by our own code are shader
effects on top of that data (lighting, the slow cyclonic turn of the cloud
field, the flat water level, rain streaks, the amber ring at the tide gauge).

Licenses were checked on the providers' own pages on 2026-11-04.

## Globe (`assets/globe/`)

| File | What it is | Source | License |
|---|---|---|---|
| `earth-bmng-2048.webp` | Blue Marble: Next Generation, global surface mosaic | NASA, via GIBS WMS layer `BlueMarble_NextGeneration` | NASA imagery, not subject to copyright in the US; NASA acknowledged as the source ([NASA media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)) |
| `clouds-20170910-2048.webp` | Suomi NPP VIIRS corrected-reflectance true colour, global daily composite for 2017-09-10 (Irma, Jose and the rest of that day's weather) | NASA GIBS WMS layer `VIIRS_SNPP_CorrectedReflectance_TrueColor`, `TIME=2017-09-10` | As above; GIBS asks for the acknowledgement below |
| `irma-20170910-2048.webp` | Same layer and date, 12–38° N, 96–64° W at higher resolution, so Irma and the Florida Keys are sharp | NASA GIBS, same layer | As above |

> We acknowledge the use of imagery provided by services from NASA's Global
> Imagery Browse Services (GIBS), part of NASA's Earth Science Data and
> Information System (ESDIS).

The cloud layer's transparency is computed in the shader from the VIIRS
pixels themselves (bright and grey = cloud). The eye position used for the
cyclonic turn (25.83° N, 81.72° W) was read off the VIIRS frame.

## Key West (`assets/keywest/`)

Both rasters cover the same box, 81.82–81.72° W, 24.535–24.59° N.

| File | What it is | Source | License |
|---|---|---|---|
| `dem-cudem-navd88.png` | Bare-earth topobathy, NOAA NCEI Continuously Updated DEM (CUDEM) 1/9 arc-second tiles `ncei19_n24x75_w082x00_2022v1` and `ncei19_n24x75_w081x75_2022v1`, vertical datum NAVD 88 | NOAA NCEI `DEM_mosaics/DEM_all` ImageServer `exportImage`, locked to those two tiles | US Government work (NOAA), public domain; NOAA/NCEI make no warranty about the data |
| `ortho-naip-2048.webp` | Aerial photo: USDA NAIP Florida 2022 (flown 2023-01-16, 0.3 m) | USGS The National Map `USGSNAIPPlus` ImageServer `exportImage` | USDA aerial imagery is public domain; USGS-distributed data is public domain ([USGS copyrights and credits](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits)). Credit: USDA Farm Production and Conservation Business Center; USGS The National Map |
| `waternormals-512.jpg` | Tiling water normal map from the three.js examples (`examples/textures/waternormals.jpg`, tag r187), downscaled from 1024 to 512 | [three.js repository](https://github.com/mrdoob/three.js) | MIT, © 2010–2026 three.js authors |

**DEM encoding.** The float DEM is stored as an 8-bit PNG with a
piecewise-linear code so that the flood band keeps 2.5 cm steps: heights
−14, −1, 4, 30 m map to codes 0, 20, 220, 255. `js/scene.js` decodes with
the same knots. Round-trip error inside −1…4 m is at most 1.25 cm.

**Datum.** The scene draws water at `MHHW + level`. MHHW is 0.013 m above
NAVD 88 at gauge 8724580 (1.941 − 1.928 m, NOAA datum sheet cached in
`data/keywest_datums.json`, 1983–2001 epoch). The levels themselves come from
`assets/data/results.json` (`thresholds_m_above_mhhw`), plus Irma's 2.7 ft
(0.82 m) gauge peak from the NHC report below.

## Facts quoted on the page

- Hurricane Irma: landfall near Cudjoe Key around 1300 UTC on
  2017-09-10 with 115 kt winds and 931 mb; Key West NOS gauge peak 2.7 ft
  above MHHW. Cangialosi, Latto and Berg, *National Hurricane Center Tropical
  Cyclone Report: Hurricane Irma (AL112017)*,
  <https://www.nhc.noaa.gov/data/tcr/AL112017_Irma.pdf>. US Government work.
- Tide gauge position (24.5557° N, 81.8079° W): NOAA CO-OPS station
  metadata for 8724580.

## Still frames (`assets/stills/`)

`s0`–`s7` are screenshots of this site's own 3-D scene at each chapter,
rendered from the assets above. `s0` is the first-paint poster; all of them
are the fallback when WebGL is unavailable, data saving is on, or the visitor
prefers reduced motion.

## Code

- [three.js](https://threejs.org/) r187, loaded as an ES module from
  `cdn.jsdelivr.net/npm/three@0.187.0/+esm` (pinned). MIT.

## Fonts

- Space Grotesk, Inter, JetBrains Mono: Google Fonts, SIL Open Font License.

## Not used, and why

- Mapbox terrain (three-geo), Google Photorealistic 3D Tiles and Sketchfab
  models all need an account or API key.
- An earlier version used floating CC0 buoy models; they gave no sense of a
  real place and were removed.
