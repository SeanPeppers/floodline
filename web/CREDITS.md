# Asset credits and licenses

Every image and terrain file in this site is real, public data made by other
people. Nothing in the 3-D scene is hand-modelled: the clouds, ground, seabed
and aerial photo are rasters downloaded once (no accounts, no API keys) and
re-encoded for the web. The only things drawn by our own code are shader
effects on top of that data (lighting, the slow cyclonic turn of the cloud
field, the flat water level, rain streaks, the amber ring at the tide gauge,
and the cloud layers the camera falls through above Key West).

**Cloud pass and rain (illustration).** Between the globe and the island the
camera drops through a stack of horizontal cloud layers 8–15 km above the
tile. Their coverage and tone are sampled from the same MODIS Terra tile at
that spot; the finer structure is fbm noise, because Terra's ~380 m pixels
are a smooth grey at that range. The layer heights, the grey fog inside them
and the overcast lighting at the island are artistic choices, not a
cloud-base or visibility measurement. The rain is a particle effect (wind
lean and density grow with scroll); it does not show Irma's measured rainfall.

Licenses were checked on the providers' own pages on 2026-11-04 (Natural
Earth, GIBS layers and HURDAT2 rechecked 2026-11-05).

## Globe (`assets/globe/`)

| File | What it is | Source | License |
|---|---|---|---|
| `earth-bmng-2048.webp` | Blue Marble: Next Generation, global surface mosaic | NASA, via GIBS WMS layer `BlueMarble_NextGeneration` | NASA imagery, not subject to copyright in the US; NASA acknowledged as the source ([NASA media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)) |
| `clouds-20170910-2048.webp` | Suomi NPP VIIRS corrected-reflectance true colour, global daily composite for 2017-09-10 (afternoon passes, ~18–19 UTC over Florida) | NASA GIBS WMS layer `VIIRS_SNPP_CorrectedReflectance_TrueColor`, `TIME=2017-09-10` | As above; GIBS asks for the acknowledgement below |
| `irma-terra-20170910-2048.webp` | 12–38° N, 96–64° W. MODIS Terra corrected-reflectance true colour, 2017-09-10. Terra's descending pass crossed the Florida Straits at about **15:50 UTC** (GIBS `OrbitTracks_Terra_Descending`), 2 h 50 min after the Cudjoe Key landfall. The two no-data wedges between Terra swaths (6.9% of the frame, all far from Irma) are filled from the VIIRS layer above, same day, ~18–19 UTC | NASA GIBS WMS layers `MODIS_Terra_CorrectedReflectance_TrueColor` and `VIIRS_SNPP_CorrectedReflectance_TrueColor`, `TIME=2017-09-10` | As above |
| `keys-terra-20170910-2048.webp` | 22–28° N, 85–78° W, same Terra pass at ~290 px/deg, so the eye and the Keys are sharp on the descent | NASA GIBS, `MODIS_Terra_CorrectedReflectance_TrueColor` | As above |

> We acknowledge the use of imagery provided by services from NASA's Global
> Imagery Browse Services (GIBS), part of NASA's Earth Science Data and
> Information System (ESDIS).

**Processing.** Both Terra files get one tone curve, identity below 45%
brightness and `0.45 + 0.55·((v − 0.45)/0.55)^3` above it, because the eye
sits inside saturated cloud tops and does not show otherwise. Nothing is
painted in or moved. The cloud layer's transparency is computed in the
shader from the pixels themselves (bright and grey = cloud). The shader also
turns the cloud field slightly (at most ~0.15 rad) about the eye as you
scroll; that motion is ours, not the satellite's.

**Eye position.** The darkest point of the eye in the Terra frame is
25.16° N, 81.69° W. The NHC best track interpolated linearly to 15:50 UTC
gives 25.21° N, 81.61° W, about 9 km away. The track's two Florida
landfalls are Cudjoe Key (24.7° N, 81.5° W, 13:00 UTC) and Marco Island
(25.9° N, 81.7° W, 19:30 UTC); the Key West gauge (24.56° N, 81.81° W) is
about 35 km (22 mi) west-southwest of the first.

## Track and coastline (`assets/data/`)

| File | What it is | Source | License |
|---|---|---|---|
| `irma-track.json` | NHC best-track fixes for Irma (AL112017), 8–11 Sep 2017, with landfall flags | NOAA NHC HURDAT2 Atlantic file `hurdat2-1851-2025-092326.txt`, <https://www.nhc.noaa.gov/data/hurdat/> | US Government work, public domain |
| `coast-ne10m.json` | 1:10m coastline cropped to 14–34° N, 98–66° W, rounded to 0.01° | [Natural Earth](https://www.naturalearthdata.com/), `ne_10m_coastline` via the `nvkelso/natural-earth-vector` repository | Public domain |

The track is drawn on the globe just above the cloud tops as a plain line,
with place-name labels only (Key West and the Cudjoe Key, Marco Island and
Cuba landfalls; a label hides when it would cover a higher-priority one or
leave the screen). No times are drawn on the globe; the image time versus
landfall time is stated in the chapter text.

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
rendered from the assets above (all re-rendered 2026-11-05 with the
decluttered track, the cloud descent and the overcast, rainy island). `s0` is the first-paint poster; all of them
are the fallback when WebGL is unavailable, data saving is on, or the visitor
prefers reduced motion.

## Results data (`assets/data/`)

`results.json`, `results_multi.json` (per-budget error arrays removed) and
`cli-example.txt` (the recorded `floodline_cli.py` run in
`README_multidriver.md`) are copied from the repo root by
`node web/sync-data.mjs`. `crossover.json` is the toy study's output. The
CLI's road points come from OpenStreetMap (© OpenStreetMap contributors,
ODbL) with USGS 3DEP elevations (public domain).

`road_priority.json` (top 100 streets, with the two road-cost sources in
`meta.costs`) is written by `uv run python road_priority.py`.

## "What it could save" and road-raising costs

Opened and checked 2026-11-05. Savings = runs × (1 − 1/r) × CPU-hours per
run × $0.0473, with r the measured black-box ratio (1.6 / 2.3 / 3.3).

| Figure on the page | Source |
|---|---|
| ~630 SLOSH runs per P-Surge advisory; results due within an hour | NOAA, SLOSH MPI paper (AMS 2020), <https://slosh.nws.noaa.gov/docs/data/SLOSH_MPI_AMS-2020.pdf> |
| FEMA Louisiana study, 446 synthetic storms; Louisiana 2017 suite, 7,712 simulations, ~10M CPU-hours | Louisiana Coastal Master Plan, HPC User Forum 2015, <https://hpcuserforum.com/presentations/colorado-sept2015/LouisianaCoastalMasterPlan.pdf> |
| ~2,000 core-hours per ADCIRC+SWAN run | arXiv 1909.01836, <https://arxiv.org/abs/1909.01836> |
| Hurricane Ike ADCIRC+SWAN, 1,064 cores × 2.683 h = 2,855 core-hours | arXiv 2310.06199, <https://arxiv.org/abs/2310.06199> |
| $9.0793/h ÷ 192 vCPU = $0.0473 per CPU-hour (AWS hpc7a.96xlarge, region unstated) | Vantage, <https://instances.vantage.sh/aws/ec2/hpc7a.96xlarge> |
| $9.6M per road mile | Florida Specifier, 2023-03-04, <https://floridaspecifier.com/issues/v44n6/monroe-county-caps-roads-plan-with-1-6-billion-in-projects/> |
| $21M for 4,633 ft of road (Twin Lakes pilot), $23.9M per mile | Keys Weekly, 2024-08-22, <https://keysweekly.com/?p=84561> |

The 1-ft raise height paired with those road costs is our assumption.

## Road flood layer and "Tonight in Key West"

| File | What it is | Source | License |
|---|---|---|---|
| `assets/data/streets.json` | Key West public road centrelines (primary to living_street, Overpass snapshot in `data/keywest_osm_roads.json`), cut into one ~30 m piece per elevation sample, 6,054 samples, coordinates rounded to 1e-5° | OpenStreetMap via Overpass; elevations USGS 3DEP 1 m bare-earth DEM (`getSamples`, NAVD 88) | Roads © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright); elevations public domain. `streets.json` is a derived database under the ODbL |
| `assets/data/floodrule.json` | Constants of the five-driver street flood rule and the calibrated drainage capacity, plus P(flood in a year) vs elevation for 2050 under each NOAA 2022 scenario | `uv run python web_data.py --planning` (multidriver.py, floodline_cli.py) | Ours |

Both are rebuilt by `uv run python web_data.py` (add `--planning` for the
2050 curves, a few minutes). `check_floodrule_port.py` checks the browser
port of the rule (`js/floodrule.js`) against the Python.

The 3-D layer colours each road piece red when the bathtub level is at or
above its 3DEP elevation and amber within 15 cm of it, in the scene's own
datum (m NAVD 88 = 0.013 + m above MHHW). The Tonight panel fetches, in the
browser, NOAA CO-OPS tide predictions and observed water level for 8724580
and the NWS `api.weather.gov` gridded rain forecast (KEY office). Both APIs
are keyless and send `Access-Control-Allow-Origin: *`; nothing about the
visitor is sent. The map behind it is the NAIP photo above.

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

## Hurricane costs ("What's at stake")

- NOAA NCEI Billion-Dollar Weather and Climate Disasters, events CSV 1980-2024: https://www.ncei.noaa.gov/access/billions/
- NHC Tropical Cyclone Reports (Irma AL112017, Ian AL092022, Helene AL092024, Milton AL142024): https://www.nhc.noaa.gov/data/tcr/
- OpenFEMA NFIP claims API v3, Florida claims summed by storm (as of 2026-09-08): https://www.fema.gov/api/open/v3/NfipClaims
