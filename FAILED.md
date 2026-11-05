# What failed: the full search behind Floodline

This file lists what we tried and lost, rejected or abandoned, so the wins in [FINDINGS.md](FINDINGS.md) can be read against the whole search. Each entry gives what we tried, why we expected it to work, what happened, why it failed, and where the evidence lives. "Session record" means the result was verified during the build session but no file in this repo records it.

Conventions follow FINDINGS.md: ratios are classical queries ÷ QAE queries, so a ratio below 1 means classical needed fewer; brackets are 95% bootstrap CIs; ε is absolute RMSE on the flood probability a.

## A. Quantum approaches that lost

### A1. Single-driver QAE against stratified sampling

- **Tried:** the first build estimated a one-driver (tide) flood probability with MLAE, plain Monte Carlo and 1-D stratified sampling.
- **Why we expected a win:** QAE's quadratic speed-up over Monte Carlo.
- **What happened:** MLAE beat plain MC by 11.5× [10.9, 12.1] to 94× [82, 107]. Stratified sampling needed 0.12-0.13× MLAE's queries at every ε, about 8× fewer.
- **Why it failed:** in one dimension stratification also converges at O(1/N), and evaluating the fitted CDF costs nothing. The stratified control was later superseded by Sobol QMC once the model went multi-driver.
- **Evidence:** first-commit `README.md` (git `9e84ac7`); commit `c593871` message.

### A2. Realistic drainage boundary to slow down Sobol QMC (two drivers)

- **Tried:** replacing the rectangle flood rule with a curved drainage boundary, on the hypothesis that a non-axis-aligned boundary would raise QMC's exponent and narrow the gap to QAE.
- **What happened:** QMC's exponent did not move, Δα = −0.04 [−0.09, +0.02]. Sobol QMC still needed 2.3-4.0× fewer queries than MLAE (3.2-3.4× on the rectangle rule).
- **Why it failed:** on a 32-bin grid any boundary is a union of axis-aligned boxes, so QMC sees boxes. The five-driver resolution study later showed the penalty appears only on finer grids.
- **Evidence:** `README.md` (Verdict), `results.json`, `results_rectangle.json`.

### A3. Pure QAE against conditional MC on Sobol points, physical drivers only

- **Tried:** ideal QAE against CMC+QMC (rain burst integrated exactly, Sobol over the rest) on the five-driver model, two streets, three ε.
- **Why we expected a win:** QMC's exponent degrades with dimension while QAE's stays at 1.
- **What happened:** CMC+QMC won all 24 (street, d, ε) cells: 0.18-0.55× QAE's queries at d = 5 and 0.014-0.11× at d ≤ 4.
- **Why it failed:** integrating the monotone rain dimension exactly leaves a low-dimensional, nearly smooth integrand that Sobol handles well. QAE only overtook it after eight epistemic parameters were added (FINDINGS.md, headline win).
- **Evidence:** `README_multidriver.md`, `results_multi.json`.

### A4. QAE against exact enumeration

- **What happened:** at d = 5 enumeration solves the discretized model exactly with 2.6e5 rule evaluations; QAE needs about 1e5 applications of a 1.5e5-CX circuit. QAE wins on query count only on the 1/32-ft grid (1.0e5 vs 6.7e7 evaluations) and loses by four orders of magnitude in gate operations.
- **Evidence:** `README_multidriver.md`.

### A5. Hybrid QAE plus classical control variate

- **Tried:** split off a classical control variate, estimate the residual with layered MLAE.
- **Why we expected a win:** a variance-adaptive mean estimator (Montanaro, Kothari-O'Donnell) on the residual would need 3.3-8× fewer queries than plain QAE. The performance audit ranked this the best remaining idea.
- **What happened:** CMC+QMC needed 2.0-16× less work than the hybrid in table reads and 1.8-4.5× fewer oracle queries alone, all CIs excluding 1. Against plain QAE the hybrid needed 0.70-0.73× on the 6.0 ft street and tied on the 3.0 ft street.
- **Why it failed:** amplitude encoding pays for the residual's range, not its spread. It recovered 0.9-1.15× with a 1k-cell control variate and 1.5-2.5× with a 64k-cell one, against the ideal 3.3-8×, and the 64k grid alone costs more classical reads than CMC+QMC needs for the whole answer at ε = 1e-4.
- **Evidence:** `README_hybrid.md`, `results_hybrid.json`; scratchpad `perf/report.md`.

### A6. Wall-clock time

- **What happened:** at 170 µs per Toffoli (arXiv:2011.04149) one Toffoli costs about 100× a whole classical sample (1.8 µs). The hybrid's wall-clock break-even at d = 5 sits near ε ≈ 1e-24, about 1e18 years of QPU time. The CLI's resource backend reports 511.6 fault-tolerant hours where CMC+QMC takes 1.4 s.
- **Evidence:** `README_hybrid.md` (break-even surface).

### A7. Rare events

- **Tried:** P(depth ≥ h) at relative error, on the theory that rare events are where sampling struggles.
- **What happened:** classical won every depth but one. h = 0.5 and 1 ft: 0.20 and 0.36. h = 3 and 5 ft: 0.043 and 0.008, because the deep tail is tide-driven and tide-CMC integrates it away. h = 2 ft: QAE 1.34× [1.19, 1.51] ahead at relative 3e-3, but only under the ideal QAE law; enumeration beats it at 1e-3 and the MLAE we actually simulated needs 3.7e5 queries.
- **Evidence:** `README_wins.md`, `results_wins.json`.

### A8. Nested expectation

- **Why we expected a win:** the literature search found nested expectations to be the only proven separation from the best classical algorithm (arXiv:2502.05094, 2602.08120).
- **What happened:** a cost model favours quantum by 3e3-1e5×, but every classical number is extrapolated 30-10⁴× past the largest budget run, the classical designs were not tuned, and the reference SE exceeds the 1% target. The performance audit had already rejected it for Key West: the inner expectation is exact and cheap, the outer one smooth and low-dimensional.
- **Evidence:** `README_wins.md` (section C); scratchpad `perf/report.md`, `lit/report.md`.

### A9. Many streets and memory

- **What happened (analysis, not run):** one classical sample answers every street because the rule is monotone in elevation, and enumeration streams in constant memory. The "city-wide any road floods" variant reduces to the lowest road.
- **Evidence:** `README_wins.md`; scratchpad `perf/report.md`.

### A10. The 13-dimension win at useful precision

- **What happened:** the headline 4.3× [3.5, 5.4] holds at ε = 1e-4. At ε = 1e-3 it is a tie or a loss at every d (0.93 [0.79, 1.07] at d = 13). The model's own uncertainty (±0.016 from the GEV bootstrap, ±0.03 in `README_hybrid.md`) puts useful precision near 1e-3 to 3e-3.
- **Evidence:** `README_wins.md`, FINDINGS.md ("How tight ε needs to be").

## B. Modelling attempts that failed or were replaced

### B1. Rectangle flood rule

- **Tried:** "annual-max tide ≥ NWS minor AND 24-h rain ≥ 10-year depth".
- **What happened:** P(tide ≥ minor) = 0.963, so the "compound" event (a = 0.0959) was almost entirely the rain condition, close to a 1-D problem, and a rectangle is Sobol's best case. The old README also reported 0.0458 as the minor-stage probability (it is the major-stage one) and called the AND event "2.4× more likely than the tide threshold alone", which is impossible.
- **Replaced by:** the drainage model of node N3210 from the 2024 Stormwater Master Plan (`drainage.py`).
- **Evidence:** `README.md` ("What this branch changed, and one correction").

### B2. Gumbel rain fit

- **Tried:** two-parameter Gumbel fit by OLS to the nine NOAA Atlas 14 depths.
- **What happened:** the 2-year 24-h depth came out 2.57 in against NOAA's 4.40 in (42% low; 26% low for 3 h), and the "10-year" depth sat near an 8-year exceedance.
- **Replaced by:** a three-parameter GEV within 0.23 in (5.2%) of every 24-h depth and 3.3% for 3 h (`rainfall.py`). The five-driver a at the benchmark street moved from 0.3250 to 0.6148. Pearson III (4.1%) and three-parameter lognormal (1.7%) were also fitted to the 3-h series; GEV was kept so both durations share one fit.
- **Evidence:** `README_multidriver.md` ("What changed: Gumbel to GEV rain"), `NOVELTIES.md` §8, `test_multidriver.py`.

### B3. Irma forecast-track ("spaghetti") surge layer

- **Tried:** run every NHC forecast track for Irma (AL112017 a-deck archive, 107 tracks per cycle) through a parametric surge model and count flooded streets per track. The model combined a Holland wind profile, Atkinson-Holliday pressure-wind, Vickery-Wadhera Rmax, Powell-capped drag and Dean-Dalrymple setup, fitted on the 11 other hurricanes within 250 km of Key West since 1996.
- **What happened:** it predicted 0.63 ft above MHHW for Irma against 2.69 ft observed at NOAA 8724580 (17:42 UTC, 10 Sep 2017), 2.06 ft low. Leave-one-out error on the other storms was about 0.6 ft, with Wilma 1.5 ft low. Three alternative formulations still missed Irma by 1.2-2.0 ft.
- **Why it failed:** no calibration storm had Irma's north-wind setup. The street flood rule starts mattering near 1 ft, so the layer was not shipped.
- **Evidence:** FINDINGS.md (Negative and blocked experiments); unmerged branch `worktree-agent-a5a20bc9099952862` (commit `9d7fdab`, `spaghetti.py`); component list, track count and leave-one-out figures from the session record.

### B4. Importance sampling

- **What happened:** useless for events with a ≈ 0.1-0.7, and IS plus CMC on Sobol was worse than plain CMC+QMC at every depth in the rare-event study because the exponential-tilt weights blow up in the tail.
- **Evidence:** `README_multidriver.md`, `README_wins.md`, `results_wins.json`.

### B5. Conditional MC with iid draws

- **What happened:** it loses badly at d = 5 because integrating P3 leaves P24's variance in place. The Sobol points over the remaining integrand are what make CMC+QMC strong.
- **Evidence:** `README_multidriver.md`.

### B6. Tide-alone split in the hybrid

- **Tried:** handling the tide-alone flood region classically before the quantum residual.
- **What happened:** the residual's sd was 0.14756 with and without it. Dropped.
- **Evidence:** `README_hybrid.md`.

### B7. Control variate on the classical side at d = 13

- **What happened:** RMSE 1.21e-4 plain vs 1.18e-4 with the control variate at N = 2^18, at twice the cost per sample. It does not rescue CMC+QMC.
- **Evidence:** FINDINGS.md (headline win), `README_wins.md`.

### B8. Two drainage calibrations (unresolved)

- **What happened:** at node N3210 the two-driver model gives a = 0.640 and the five-driver model 0.97 (0.967 in `README_hybrid.md`). Tide-only probabilities agree (0.217 vs 0.210). Scaling five-driver drainage 10.3× to match drops the city-wide flooded share from 56% to 19%, while the street ranking holds at the top (Spearman ρ = 0.91). We have not reconciled them.
- **Evidence:** FINDINGS.md ("Two drainage calibrations").

## C. Research directions rejected after literature search

### C1. "Quantum knows floods sooner" (7-day lead time)

Rejected. Flood lead time is limited by weather predictability and input data, not by the speed of the estimator, so a faster estimator buys no warning time. Evidence: session record.

### C2. Flood aftermath: damage imagery, relief routing, insurance loss

No evidence of advantage. Imagery damage assessment (arXiv:2603.13689) compares against a single classical baseline. Relief routing (arXiv:2412.15665) is "still outperformed by purely classical methods". Insurance loss (Kirke, arXiv:2603.15664) finds "strong classical baselines win when analytical access is available". Evidence: scratchpad `savings/report.md`, `quantum_where/report.md`.

### C3. Other QAE uses on Key West (performance audit)

| Idea | Why rejected |
|---|---|
| VaR / CVaR | Enumeration gives the full CDF |
| City-wide "any road floods" | Reduces to the lowest road (drivers are city-wide, rule monotone in elevation) |
| Nested expectation | Inner is exact and cheap, outer smooth and low-dimensional (see A8) |
| Non-smooth damage functions | CMC needs only monotonicity |
| Rare events | a = 0.1-0.4 is not rare (later tested anyway, A7) |
| Iterative / Bayesian AE | About 2× better constants, same depth trade-off |
| Better Grover-Rudolph state preparation | Still forfeits the speed-up |

Evidence: scratchpad `perf/report.md`.

### C4. Quantum methods for flood, hurricane and coastal risk generally

| Idea | Why rejected |
|---|---|
| Quantum fluid PDE solvers | Bounded polynomial advantage for selected outputs only (arXiv:2512.03758); resource estimates of 1e21-1e39 (2406.06323); copy lower bounds (2603.12161); Carleman limit R < √2 (2011.03185). Flood models are limited by grid and bathymetry, not turbulence |
| HHL for diffusion | arXiv:2004.06516 |
| Wave-equation Hamiltonian simulation | arXiv:1711.05394 |
| Coupled-oscillator exponential speed-up | Needs compact oracle access (2303.13012, 2307.00523) |
| QML ensemble forecasting | arXiv:2307.00523 |
| DQI for relief logistics | arXiv:2408.08292 |
| Shelter, evacuation and road-raising optimization | Scaling evidence only on random spin glasses (2401.07184); disaster papers claim feasibility only (2606.19589, 2602.10951, 2312.02279); the road budget is a small knapsack solved exactly by dynamic programming |

Evidence: scratchpad `quantum_where/report.md`.

### C5. Papers checked and set aside

Tabarraei (arXiv:2607.18996, 2602.09847) and Woerner & Egger VaR/CVaR (1806.06893) compare only against plain MC. An et al. quantum MLMC for SDEs (2012.06283) does not match our structure. The survey arXiv:2303.04945 has no QAE vs QMC head-to-head. Flood QML (2407.01001) uses no amplitude estimation. Optimal stopping (2111.15332) is irrelevant here. Evidence: scratchpad `lit/report.md`.

## D. Engineering and infrastructure dead ends

### D1. Real hardware

- **Tried:** noisy simulation of the 19-qubit two-driver circuit on a FakeFez calibration snapshot (median CZ error 3.9e-3).
- **What happened:** A alone is 11,384 CZ, about 44× the noise budget. Noisy P(obj = 1) was 0.50 at m = 0 and 1 against ideal 0.640 and 0.124, a coin flip. At d = 5 and ε = 1e-4 the deepest circuit has 7.7e7 CX and needs two-qubit error near 9e-9 (the hybrid ≤ 1e-9), about 4e5-4e6 times cleaner than the snapshot.
- **What still fits:** a 3-qubit demo with 1-bit tide and 1-bit rain (a = 0.1728, A = 12 CZ). Noisy simulation shows Grover oscillations through m = 6 and noise-aware MLAE reaches RMSE 1.39e-3, better than MC per shot but worse per query.
- **Hardware run (2026-11-05):** `hw_demo.py` ran a 3-qubit version (exact coarsening of the rectangle rule, a = 0.0959) on ibm_fez, 4,000 shots per depth, m = 0-6, 10 s of QPU time. The oscillation survives but damps (P = 0.842 at m = 2 vs ideal 1.000; 12 to 192 two-qubit gates), and MLAE gives a = 0.0738 vs exact 0.0959. It runs; it does not beat classical.
- **Evidence:** `README.md`, `README_multidriver.md`, FINDINGS.md, `hw_demo.py`, `results_hw.json`; scratchpad `perf/report.md` and `perf/tiny_hw.py`.

### D2. Large-GPU validation on Colab

- **Tried:** exact statevector validation past 30 qubits on an A100 or H100.
- **What happened:** neither was available (capacity and quota). Validation stopped at 30 qubits on an NVIDIA L4 (24 GB); 31 and 32 qubits need 32 and 64 GB.
- **Evidence:** `README_multidriver.md`, `validate_gpu.py`; A100/H100 unavailability from the session record.

### D3. Coherent arithmetic oracle

- **What happened:** not built. The QROM lookup-table oracle is already 149k CX at d = 5, and folding the eight continuous epistemic parameters into its tables would multiply the address space by about 2^32. An arithmetic oracle is estimated at 1e4-1e5 Toffolis for 16-bit drivers. Even built, it would beat enumeration at fine resolution, not CMC+QMC.
- **Evidence:** `README_multidriver.md` (limitation 4), `README_wins.md`.

### D4. MLAE with 100 shots per power on small amplitudes

- **What happened:** for a < 1e-2 its RMSE stalls past about 2e5 queries because it locks onto the wrong fringe; at h = 5 ft it would need 7e8 queries. The rare-event study gives QAE its ideal law instead, so as not to hand classical a fake win.
- **Evidence:** `README_wins.md`.

## E. Site and product ideas dropped

### E1. Lives-saved estimate

Dropped. No source we found links forecast speed, surge lead time or resolution to casualties, so any number would have been invented. Evidence: scratchpad `savings/report.md`; session record.

### E2. Floating 3D buoy hero

Three CC0 buoy and marker models on a shader water plane gave no sense of a real place. Replaced with a zoom into Key West built from stills. Evidence: `web/CREDITS.md`, commit `eea9877`.

### E3. Interactive MapLibre hero map

Removed at the user's request. The commit that removed it (`d7e411d`) cites desktop Lighthouse performance, which had fallen to about 53-57 from parsing the ~800 KB MapLibre bundle (commit `c593871`). The static crossfade stills stayed.

### E4. Stale stratified-sampling numbers on the site

The site kept showing the single-driver model (stratified sampling beating QAE by about 8×) after the compound model replaced it. Fixed in commit `c593871`, which also renamed the classical control to Sobol QMC.

### E5. Tonight panel inside the Claude artifact preview

The live "Tonight in Key West" panel fails to load inside the artifact preview sandbox and works when the site is served normally. Commit `f142006` makes the panel show the underlying error. Evidence: session record.
