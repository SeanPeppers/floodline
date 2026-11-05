# Citations

Every outside source Floodline relies on, deduplicated and grouped by topic. Each entry gives
the author or organization, title, year, an arXiv ID or URL where the project files give one,
and what the project uses it for.

**Status** has two values:

- **verified**: a project README, `web/CREDITS.md` or one of the team's research reports says
  the page was opened and the quoted figure or license was checked there. Reports marked
  "main thread verified" were rechecked by the lead session; literature entries marked
  "verified (abstract)" were checked against the abstract page by a research agent.
- **from project docs**: cited in the project's files, but no file records that the page was
  opened. Read these before quoting them to a judge.

Where the files give no paper title, the entry names the topic in plain words instead. URLs are
copied from the project files. Entries without a URL had none in the files, and none
was added. Where the files give only an arXiv ID, only the ID is listed.

Sources: `README.md`, `README_multidriver.md`, `README_hybrid.md`, `README_wins.md`,
`web/CREDITS.md`, `web/index.html`, `web/assets/data/road_priority.json` (`meta.costs`), and the
team's research reports (perf, quantum-where, literature, savings, damages, fact-check, Key West
drainage sources, Key West extra drivers).

## Quantum algorithms and lower bounds

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| Suzuki et al., "Amplitude estimation without phase estimation", *Quantum Inf. Process.* 19, 75 | 2020 (arXiv 2019) | arXiv:1904.10246 | MLAE, the quantum estimator in every benchmark | verified |
| Brassard, Høyer, Mosca, Tapp, "Quantum Amplitude Amplification and Estimation" | 2000 | arXiv:quant-ph/0005055 | The O(1/ε) amplitude-estimation bound. The fact-check notes the theorem is in the body, not the abstract | verified |
| Montanaro, quantum mean estimation (topic, no title in project docs) | 2015 | arXiv:1504.06987 | Variance-adaptive quantum mean estimation; O(1/ε) vs Ω(1/ε²) queries for a black-box simulator; the layered hybrid design | from project docs |
| Kothari, O'Donnell, quantum mean estimation | 2022 | arXiv:2208.07544 | O(σ/ε) mean estimator; the ideal hybrid speed-up (3.3-8×) that amplitude encoding fails to reach | from project docs |
| Novak, quantum complexity of integration | 2000 | arXiv:quant-ph/0008124 | Quantum vs classical rates for Hölder-class integrands | from project docs |
| Heinrich, quantum summation and integration | 2001 | arXiv:quant-ph/0105116 | Quantum rate 0.80 for Hölder classes; the hybrid cost-envelope comparison | from project docs |
| Blanchet, Hamoudi, Szegedy, Wang, quantum nested expectation (NeurIPS 2025) | 2025 | arXiv:2502.05094 | Optimal-up-to-polylog nested-expectation algorithm; best-case model for the nested axis | verified (abstract) |
| Sun, Wang, Blanchet, quantum nested expectation | 2026 | arXiv:2602.08120 | "almost quadratic speedup over the best classical algorithm"; nested axis | verified |
| Kirke, QAE for insurance loss (topic, no title in project docs) | 2026 | arXiv:2603.15664 | Only prior flood-adjacent QAE work found; "discretisation, not estimation, is the current bottleneck" | verified |
| Kaneko, Miyamoto, Takeda, Yoshino, QAE for credit risk | 2020 | arXiv:2011.02165 | Black-box high-dimension example; compares against plain MC only | verified (abstract) |
| Stamatopoulos, Mazzola, Woerner, Zeng, quantum Greeks | 2021 | arXiv:2111.12509 | Further quadratic advantage in the number of sensitivities | verified (abstract) |
| Huggins et al., estimating many expectation values | 2021 | arXiv:2111.09283 | O(√M/ε) for M outputs; the many-outputs axis | verified (abstract) |
| Cornelissen, Hamoudi, Jerbi, multivariate mean estimation | 2021 | arXiv:2111.09787 | Quantum beats any classical estimator only at high precision; many-outputs axis | verified (abstract) |
| Power-law amplitude estimation (no authors in project docs) | 2020 | arXiv:2012.03348 | Coherent depth needed to tie CMC+QMC (~740 A-calls at ε = 1e-4) | from project docs |
| Tanaka et al., noise-aware MLAE | 2020 | arXiv:2006.16223 | Noisy-hardware toy demo fit | from project docs |
| Herbert, arithmetic state preparation | 2021 | arXiv:2101.02240 | Arithmetic oracle that avoids Grover-Rudolph loading | from project docs |
| Grover-Rudolph state preparation | | none in project docs | State loading in `multidriver_circuit.py` and `hybrid_circuit.py` | from project docs |
| Babbush et al., QROM by unary iteration | 2018 | none in project docs | The two QROM lookups in the five-driver oracle | from project docs |
| Cuccaro et al., ripple-carry adder | | none in project docs | C = W + S, G = S + O adders and the comparator | from project docs |
| Draper, QFT adder | | none in project docs | The two-driver adder oracle (`copula.flood_oracle`) | from project docs |

## Classical estimators (QMC, CMC, MLMC)

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| He and Owen, randomized QMC rate 2d/(d+1) for indicators with a smooth boundary | | none in project docs | Predicted Sobol QMC exponent; the toy crossover study and the d-driver explanation | from project docs |
| Novak-Heinrich randomized rate for r-smooth integrands | | see Novak and Heinrich above | α_c(d) model in the hybrid break-even surface | from project docs |
| Survey cited by the literature report (no authors or title in project docs) | 2023 | arXiv:2303.04945 | Checked for a QAE-vs-QMC head-to-head; none found | from project docs |
| Woerner, Egger, quantum risk analysis (VaR/CVaR) | 2018 | arXiv:1806.06893 | Set aside: compares against plain MC only | from project docs |
| An et al., quantum MLMC for SDEs | 2020 | arXiv:2012.06283 | Set aside: different structure | from project docs |
| Tabarraei, QAE studies | 2026 | arXiv:2607.18996, arXiv:2602.09847 | Set aside: compare against plain MC only | from project docs |

Sobol sequences, conditional Monte Carlo, importance sampling and randomized MLMC are used as
standard methods; the project files cite no specific paper for them.

## Hardware and resource estimates

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| Babbush et al., early fault-tolerant cost of quadratic speedups (topic, no title in project docs) | 2020 | arXiv:2011.04149 | 170 µs per Toffoli (surface code, d = 30, 1 µs cycles); quadratic speedups rarely pay on early fault-tolerant machines | from project docs |
| Chakrabarti et al., threshold for quantum advantage in derivative pricing | 2020 | arXiv:2012.03819 | ~8k logical qubits and T-depth 54 million as a reference resource bar | verified (abstract) |
| IBM `FakeFez` calibration snapshot (qiskit-ibm-runtime) | | none | Median CZ error 3.9e-3 and noisy simulation. A recorded snapshot, not a live device spec | from project docs |
| NVIDIA L4 on Google Colab (cuStateVec, Aer) | | none | GPU statevector validation up to 30 qubits | from project docs |

## Flood, drainage and Key West data

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| NOAA CO-OPS station 8724580 (Key West), monthly `Highest` water level, 1913-2025 | | station 8724580 | Annual-max tide, GEV fit, 110 usable years | verified |
| NOAA CO-OPS datums for 8724580 | | <https://tidesandcurrents.noaa.gov/benchmarks/8724580.html> | MHHW 0.013 m above NAVD88 | verified |
| NOAA CO-OPS flood levels API for 8724580 | | <https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/8724580/floodlevels.json> | NWS minor / moderate / major stages; cross-check of the drainage rule | verified |
| NOAA sea-level trend for 8724580 | | <https://www.tidesandcurrents.noaa.gov/sltrends/sltrends_station.shtml>; API <https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/product/sealvltrends.json?station=8724580> | Published 2.64 ± 0.15 mm/yr, against the project's own 2.65 mm/yr fit | verified (search snippet for the table; API fetched) |
| NOAA 2022 Sea Level Rise Technical Report (Sweet et al.), projections for 8724580 | 2022 | <https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/product/slr_projections.json?station=8724580> | SLR driver S; scenarios in the CLI and road priority | verified |
| NOAA Atlas 14 Volume 9 Version 2 PFDS, 24-h and 3-h AMS depths at the gauge | | <https://hdsc.nws.noaa.gov/cgi-bin/new/cgi_readH5.py>; <https://hdsc.nws.noaa.gov/cgi-bin/new/fe_text_mean.csv> | Rain marginals (GEV fit); drainage calibration | verified |
| City of Key West, *2024 Stormwater Master Plan Update* (Feb 2024) | 2024 | <https://www.cityofkeywest-fl.gov/DocumentCenter/View/12555/Stormwater-Master-Plan_Final_02_2024> | Every drainage constant: N3210 stages (Table 3-4), design storms (Table 2-2), curve numbers (Table 2-6), gravity wells (sec 2.3.4.8), groundwater offset (sec 2.1.2), 6-inch road tolerance, 5-yr level of service | verified |
| Wahl, Jain, Bender, Meyers, Luther, compound flooding from storm surge and rainfall, *Nature Climate Change* 5, 1093-1097 | 2015 | doi:10.1038/nclimate2736; PDF copy <https://chs.erdc.dren.mil/Library/References/Other_Topics/Compound_Hazards/B_Bivariate/Wahl_et_al_2015_IncreasingRiskOfCompoundFlooding.pdf> | Basis for tide-rain dependence. Key West is gauge 17; its τ appears only in Fig. 1b, so τ is an assumption | verified (Key West significance not stated in text) |
| Jane et al., compound flooding in Miami-Dade, *NHESS* 20, 2681 | 2020 | <https://nhess.copernicus.org/articles/20/2681/2020/> | τ < 0.3 for South Florida; supports the 0.1-0.3 prior | verified |
| USGS 3DEP 1 m lidar DEM (`getSamples`, NAVD88) | | none | Elevations of 6,054 road points | verified (license) |
| NOAA NCEI Continuously Updated DEM (CUDEM) 1/9 arc-second, tiles `ncei19_n24x75_w082x00_2022v1`, `ncei19_n24x75_w081x75_2022v1` | 2022 | NCEI `DEM_mosaics/DEM_all` ImageServer | 3-D terrain of Key West on the site | verified (license) |
| USDA NAIP Florida 2022 (flown 2023-01-16, 0.3 m), via USGS The National Map `USGSNAIPPlus` | 2022 | <https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits> | Aerial photo on the site and behind the Tonight map | verified (license) |
| OpenStreetMap contributors, Key West road centrelines via Overpass (ODbL 1.0) | | <https://www.openstreetmap.org/copyright> | 6,054 road points, 365 named streets for exposure and road priority | verified |
| NOAA NHC HURDAT2 Atlantic best track, file `hurdat2-1851-2025-092326.txt` | 2026 | <https://www.nhc.noaa.gov/data/hurdat/> | Irma (AL112017) track on the globe | verified (license) |
| Cangialosi, Latto, Berg, *NHC Tropical Cyclone Report: Hurricane Irma (AL112017)* | 2018 | <https://www.nhc.noaa.gov/data/tcr/AL112017_Irma.pdf> | Landfall time, intensity; Key West gauge peak 2.7 ft above MHHW; Monroe damage quotes | from project docs |
| NWS `api.weather.gov` gridded forecast (KEY office) and CO-OPS predictions / observed water level | | <https://www.weather.gov/key/> | Live inputs to the "Tonight in Key West" panel | from project docs |

Consulted while building the model but not used for any number in it:

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| Southeast Florida Regional Climate Change Compact, 2019 unified SLR projection | 2019 | <https://southeastfloridaclimatecompact.org/announcements/the-compact-releases-its-3rd-regionally-unified-sea-level-rise-projection/> | Cross-check of NOAA SLR ranges | verified |
| Danchuk (Compact), Key West SLR slides | 2020 | <https://southeastfloridaclimatecompact.org/wp-content/uploads/2020/06/1.-Dr.-Sam-Danchuk-Relevance-of-SLR-projection.pdf> | Per-curve values could not be parsed | verified (partial) |
| Southeast Florida Compact vulnerability assessment | 2012 | <https://southeastfloridaclimatecompact.org/wp-content/uploads/2014/09/vulnerability-assessment.pdf> | Key West average elevation 4.7 ft | verified |
| McKenzie, USGS WRI 90-4115 | 1990 | <https://pubs.usgs.gov/publication/wri904115> | Groundwater tracks the tide; search excerpt only | from project docs |
| Monroe County / HDR Roads Elevation Study Update | 2021 | <https://monroecounty-fl.gov/DocumentCenter/View/29266/Item-B-8-HDR-Roads-Elevation-Study-Update-20210621> | Segment elevations; no city-wide share found | verified |
| NWS Key West Idalia event summary | 2023 | <https://www.weather.gov/media/key/TropicalEventSummary/PSHKEY_2023AL10_Idalia_Summary.pdf> | Tide-driven street flooding example (gauge max 1.47 ft MHHW) | verified |
| NWS Key West Florida Keys weather brief, 7 Oct 2025 | 2025 | <https://keycolonybeach.net/wp-content/uploads/2025/10/2025-OCT07-1100-FloridaKeysWXBrief-1.pdf> | "little or no drainage" at high tide, qualitative | verified |
| News report, Key West rain of 24 Feb 2025 (6.87 in) | 2025 | <https://www.yahoo.com/news/key-west-flooded-rain-nearly-022604858.html> | Rain-only sanity check | verified (partial) |

## Operational surge models and compute costs

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| NOAA, SLOSH MPI paper (AMS 2020) | 2020 | <https://slosh.nws.noaa.gov/docs/data/SLOSH_MPI_AMS-2020.pdf> | ~630 SLOSH runs per P-Surge advisory; results due within an hour | verified |
| Louisiana Coastal Master Plan, HPC User Forum talk | 2015 | <https://hpcuserforum.com/presentations/colorado-sept2015/LouisianaCoastalMasterPlan.pdf> | FEMA Louisiana study, 446 synthetic storms; 2017 suite of 7,712 runs, ~10M CPU-hours | verified |
| ADCIRC+SWAN cost study | 2019 | arXiv:1909.01836, <https://arxiv.org/abs/1909.01836> | ~2,000 core-hours per ADCIRC+SWAN run | verified |
| Hurricane Ike ADCIRC+SWAN study | 2023 | arXiv:2310.06199, <https://arxiv.org/abs/2310.06199> | 1,064 cores × 2.683 h = 2,855 core-hours | verified |
| Vantage, AWS `hpc7a.96xlarge` pricing | 2026 | <https://instances.vantage.sh/aws/ec2/hpc7a.96xlarge> | $9.0793/h ÷ 192 vCPU = $0.0473 per CPU-hour (region unstated) | verified |

## Hurricane damage and insurance

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| NOAA NCEI, Billion-Dollar Weather and Climate Disasters, events 1980-2024 | 2025 | <https://www.ncei.noaa.gov/access/billions/>; CSV <https://www.ncei.noaa.gov/access/billions/events-US-1980-2024.csv> | Total cost and deaths for Irma, Ian, Helene, Milton | verified |
| NHC Tropical Cyclone Reports: Ian (AL092022), Helene (AL092024), Milton (AL142024) | 2023-2025 | <https://www.nhc.noaa.gov/data/tcr/> | Florida deaths, surge deaths, Tampa Bay track-shift quote | from project docs |
| OpenFEMA NFIP Claims API v3 (as of 2026-09-08) | 2026 | <https://www.fema.gov/api/open/v3/NfipClaims> | Florida and county NFIP claims and payouts per storm | from project docs |
| OpenFEMA FemaWebDisasterSummaries (DR-4337, DR-4673, DR-4828, DR-4834) | 2026 | none | FEMA IHP and PA obligations | from project docs |
| Florida Office of Insurance Regulation, catastrophe reporting | 2025 | <https://floir.gov/tools-and-data/catastrophe-reporting> | Claims count and estimated insured loss per storm | from project docs |

## Road-raising costs

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| Florida Specifier, "Monroe County caps roads plan with $1.6 billion in projects" | 2023 | <https://floridaspecifier.com/issues/v44n6/monroe-county-caps-roads-plan-with-1-6-billion-in-projects/> | $9.6M per road mile; the default cost in `road_priority.json` | verified |
| Keys Weekly, Twin Lakes resilient roads pilot | 2024 | <https://keysweekly.com/?p=84561> | $21M for 4,633 ft of road, $23.9M per mile all-in | verified |

Neither source states a raise height. Pairing the cost with a 1-ft raise is the project's
assumption.

## Imagery, 3-D assets and code

| Source | Year | ID / URL | Used for | Status |
|---|---|---|---|---|
| NASA Blue Marble: Next Generation, via GIBS layer `BlueMarble_NextGeneration` | | <https://www.nasa.gov/nasa-brand-center/images-and-media/> | Globe surface | verified (license) |
| NASA GIBS, Suomi NPP VIIRS corrected reflectance, 2017-09-10 | 2017 | GIBS layer `VIIRS_SNPP_CorrectedReflectance_TrueColor` | Globe clouds; fills Terra swath gaps | verified (license) |
| NASA GIBS, MODIS Terra corrected reflectance, 2017-09-10 (and `OrbitTracks_Terra_Descending` for pass time) | 2017 | GIBS layer `MODIS_Terra_CorrectedReflectance_TrueColor` | Irma and Florida Keys imagery | verified (license) |
| Natural Earth, `ne_10m_coastline` (`nvkelso/natural-earth-vector`) | | <https://www.naturalearthdata.com/> | Globe coastline | verified (license) |
| three.js r187 (MIT), and its `waternormals.jpg` example texture | 2026 | <https://threejs.org/>; <https://github.com/mrdoob/three.js> | 3-D renderer; water normal map | verified (license) |
| Space Grotesk, Inter, JetBrains Mono (Google Fonts, SIL OFL) | | <https://fonts.googleapis.com> | Site typography | from project docs |

CUDEM, NAIP, 3DEP, OSM and HURDAT2 are listed under Key West data above.

## Surveyed and set aside

The research reports looked at these and decided they do not apply to Floodline. They are
listed so a judge's question about them has an answer.

| Source | ID | Why set aside | Status |
|---|---|---|---|
| Quantum fluid PDE solver, bounded polynomial advantage | arXiv:2512.03758 | Flood models are limited by grid and bathymetry, not turbulence | from project docs |
| Fluid-simulation resource estimate (1e21-1e39) | arXiv:2406.06323 | Same | from project docs |
| Copy lower bounds for nonlinear PDEs (KdV, Euler) | arXiv:2603.12161 | Same | from project docs |
| Carleman linearization limit | arXiv:2011.03185 | Same | from project docs |
| Optimization scaling on random spin glasses | arXiv:2401.07184 | Road budget is a small knapsack solved exactly by DP | from project docs |
| Quantum disaster-logistics feasibility papers | arXiv:2606.19589, arXiv:2602.10951, arXiv:2312.02279 | Feasibility only, no advantage shown | from project docs |
| HHL for diffusion | arXiv:2004.06516 | Rejected direction | from project docs |
| Wave-equation Hamiltonian simulation | arXiv:1711.05394 | Rejected direction | from project docs |
| Coupled-oscillator exponential speedup | arXiv:2303.13012 | Needs compact oracle access | from project docs |
| QML ensemble forecasting | arXiv:2307.00523 | Rejected direction | from project docs |
| DQI for logistics | arXiv:2408.08292 | Rejected direction | from project docs |
| Flood QML | arXiv:2407.01001 | No amplitude estimation | from project docs |
| Quantum optimal stopping | arXiv:2111.15332 | Not relevant | from project docs |
| Quantum damage assessment from imagery | arXiv:2603.13689 | Single classical baseline | from project docs |
| Quantum relief routing | arXiv:2412.15665 | "still outperformed by purely classical methods" | from project docs |
