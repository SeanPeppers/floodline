# Novelties

What Floodline does that we did not find in prior published work, with the evidence for each
claim and its limits. "We found no prior published ..." means the team's literature search
(recorded in the research reports and summarized in [CITATIONS.md](CITATIONS.md)) turned up
nothing; it is not a claim that no such work exists. Results and their numbers are in
[FINDINGS.md](FINDINGS.md).

## 1. QAE against quasi-Monte Carlo on a real risk model

**What we did.** Benchmarked ideal QAE (MLAE) against scrambled Sobol QMC, at matched error and
with bootstrap CIs, on a Key West compound-flood model with 2 to 5 physical drivers. QAE needs
fewer queries than plain QMC from d* ≈ 3.5-4.9 drivers; at d = 5 and ε = 1e-4, QMC needs
3.5× [3.1, 3.9] more.

**Prior art.** Published QAE applications in risk compare against plain Monte Carlo: Woerner
and Egger (arXiv:1806.06893) for VaR/CVaR, Kaneko et al. (arXiv:2011.02165) for credit risk,
Tabarraei (arXiv:2607.18996, arXiv:2602.09847).

**Why we think it is new.** The literature report found no published QAE-vs-QMC head-to-head,
including in the survey arXiv:2303.04945, and no published work showing QAE beating
conditional MC, QMC, importance sampling or MLMC on a real risk model.

**Evidence.** `README_multidriver.md`, `experiment_multi.py`, `results_multi.json`;
two-driver baseline in `README.md`, `results.json`.

**Caveat.** QAE is simulated from the closed-form law (fault-free). Plain QMC is not the
strongest classical method; conditional MC + Sobol beats QAE on the same physical model.

## 2. QAE on a real city's compound flood

**What we did.** Built a five-driver flood model of a Key West street (annual-max water level,
24-h rain, 3-h burst, sea-level rise, groundwater) with a nonlinear drainage rule whose
constants come from the City of Key West 2024 Stormwater Master Plan, NOAA CO-OPS 8724580,
NOAA Atlas 14 and the NOAA 2022 SLR report, then built the full QAE circuit for it.

**Prior art.** Kirke (arXiv:2603.15664) applies QAE to insurance loss and concludes that
"discretisation, not estimation, is the current bottleneck". A flood QML paper
(arXiv:2407.01001) uses no amplitude estimation.

**Why we think it is new.** The literature report found no published flood or hydrology QAE
work beyond Kirke.

**Evidence.** `multidriver.py`, `multidriver_circuit.py`, `drainage.py`, `README_multidriver.md`
(every constant sourced or flagged as an assumption). The model reproduces the SMP's 2.06 ft
peak stage at node N3210 as 2.07 ft.

**Caveat.** Several inputs are assumptions (drainage calibration, tide-rain τ, concurrent
annual maxima, catchment ratio). The model is built to test estimators on a realistic
structure, not to forecast flooding on a given street.

## 3. Crossover against the strongest classical estimator under epistemic uncertainty

**What we did.** Added eight epistemic parameters (curve number, soil depth, outfall share,
catchment ratio, gravity-well start, three tide-GEV parameters) as random inputs. Against
conditional MC on Sobol points, ideal QAE ties at d = 7 and wins from d = 9; at d = 13 it needs
4.3× [3.5, 5.4] fewer queries at ε = 1e-4. The classical exponent rises from 1.31 to 1.68;
QAE's stays at 1.0.

**Prior art.** The only proven separation from the best classical algorithm the literature
report found is for nested expectations (arXiv:2502.05094, arXiv:2602.08120).

**Why we think it is new.** We found no prior published measurement of a QAE crossover against
conditional MC + QMC on any real model.

**Evidence.** `README_wins.md`, `experiment_wins.py`, `results_wins.json`, `check_wins_cv.py`.

**Caveat.** Query count only, with ideal QAE. The circuit for continuous epistemic inputs needs
a coherent arithmetic oracle nobody has built. Three of the eight ranges are judgment calls.
At ε = 1e-3, closer to the model's own uncertainty, the result is a tie or loss at every d.

## 4. Circuit validated against the closed form to 30 qubits

**What we did.** Built the five-driver A (Grover-Rudolph loading, Cuccaro adders, two QROM
lookups, a comparator) and checked P(obj = 1) after Q^m A against sin²((2m+1)θ) by exact
statevector simulation: to 2.6e-14 at 20 qubits on CPU, and up to 30 qubits on a Colab NVIDIA L4
(cuStateVec), maximum error 1.0e-13.

**Prior art.** The project files cite no comparable validation to compare against.

**Why we think it is new.** We make no priority claim here; this is the evidence that the
construction is correct at more than toy scale.

**Evidence.** `test_multidriver.py`, `validate_gpu.py`, table in `README_multidriver.md`.

**Caveat.** The full benchmark circuit is 52 qubits and is not simulated; full-scale QAE
statistics assume it is correct and fault-free.

## 5. Hybrid QAE + control-variate engine, and why it falls short

**What we did.** Built a hybrid that removes a classical control variate and estimates the
residual with variance-adaptive layered MLAE (71-qubit circuit, validated at 20 qubits to
1.6e-14). Measured why it underdelivers: an ideal mean estimator would save 3.3-8× over plain
QAE, but amplitude encoding pays for the residual's range, recovering 0.9-1.15× with a 1k-cell
CV and 1.5-2.5× with a 64k-cell CV by the per-layer constant. Matched-ε, the hybrid needs
0.70-0.73× plain QAE's queries on the 6.0 ft street and ties on the 3.0 ft street.

**Prior art.** Montanaro (arXiv:1504.06987) and Kothari and O'Donnell (arXiv:2208.07544) give
the O(σ/ε) estimators the hybrid approximates.

**Why we think it is new.** We found no prior published measurement of how much of the
control-variate gain amplitude encoding keeps on a real model.

**Evidence.** `hybrid.py`, `hybrid_circuit.py`, `test_hybrid.py`, `experiment_hybrid.py`,
`results_hybrid.json`, `README_hybrid.md`.

**Caveat.** CMC+QMC needs 2.0-16× less work than the hybrid at every ε tested. A full
Montanaro implementation might close part of the gap.

## 6. Black-box compute savings tied to real surge workflows

**What we did.** Took the measured black-box ratios (1.6×, 2.3×, 3.3× fewer simulator runs at
d = 5) and applied them to published workloads: NOAA P-Surge (~630 SLOSH runs per advisory,
due within an hour), a 446-storm FEMA Louisiana study, the Louisiana 2017 suite (7,712 runs,
~10M CPU-hours), ADCIRC+SWAN run costs, and AWS pricing at $0.0473 per CPU-hour. Estimated
savings: $15.8k-$42.0k for a FEMA-style study, $177k-$330k for the Louisiana suite,
$11-$21 per P-Surge advisory.

**Prior art.** Sources in CITATIONS.md, "Operational surge models and compute costs".

**Why we think it is new.** We found no prior published estimate linking measured QAE query
ratios to operational surge-model budgets.

**Evidence.** `README_multidriver.md` (ratios); the site's "What it could save" section and
`web/CREDITS.md` (inputs and formula).

**Caveat.** Assumes the ratios carry over from our model to SLOSH/ADCIRC (untested), a
simulator compiled to a reversible circuit, and fault-tolerant hardware near 1e-8 to 1e-9
two-qubit error. Quantum machine cost is not counted and likely exceeds the savings. QAE
queries are sequential while P-Surge's runs are parallel.

## 7. A usable tool

**What we did.** Shipped three things a planner can run. `floodline_tool.py` estimates flood
probability for any year, NOAA scenario and elevation with a swappable backend (`classical`,
`quantum-sim`, `quantum-resource`). `road_priority.py` ranks 365 named Key West streets by
expected flooded miles in 2050 and prices raising them per flood-year avoided, from Monroe
County costs ($9.6M and $23.9M per mile). The site's "Tonight in Key West" panel pulls NOAA
tide predictions, observed water level and the NWS rain forecast and colours each road piece by
its 3DEP elevation.

**Prior art.** None claimed; this is application work.

**Evidence.** `floodline_tool.py`, `floodline_cli.py`, `road_priority.py`, `road_priority.csv`,
`web/js/tonight.js`, `web/js/floodrule.js`, `check_floodrule_port.py`.

**Caveat.** Absolute probabilities depend on the drainage calibration (rescaling it moves the
city-wide flooded share from 56% to 19%). The street ranking is robust at the top (Spearman
ρ = 0.91) and calibration-dependent below it. The 1-ft raise height paired with the road costs
is our assumption.

## 8. Caught a 42% rain-fit error

**What we did.** Found that the original two-parameter Gumbel fit to NOAA Atlas 14 put the
2-year 24-h depth at 2.57 in, where NOAA publishes 4.40 in (42% low), and replaced it with a
three-parameter GEV within 0.23 in (5.2%) of all nine published depths, and within 3.3% for the
3-h series. All results were rerun; the five-driver a at the benchmark street rose from 0.325
to 0.6148.

**Prior art.** NOAA Atlas 14 Volume 9 Version 2 depths.

**Why we think it is new.** This is a correction to our own earlier build, not a research
claim. It is listed because it changed every downstream number.

**Evidence.** `rainfall.py`, `test_multidriver.py` (asserts the 6% bound), `README.md`,
`README_multidriver.md` ("What changed: Gumbel to GEV rain").

**Caveat.** The fit is to nine published return-period depths, not to raw rain data.

## 9. Ran on real IBM hardware

**What we did.** Ran a 3-qubit QAE circuit for the Key West compound flood on IBM's `ibm_fez`
on 2026-11-05 (job `dbmbikl8mdtc73d7m170`). One qubit per driver: the rectangle rule (annual-max
tide at or above the NWS minor stage and 24-h rain at or above the 10-year depth) only depends
on which side of each threshold a driver falls, so the one-bit coarsening is exact and keeps the
real-data a = 0.0959. The job ran Grover depths m = 0 to 6 at 4,000 shots each, 12 to 192
two-qubit gates per circuit, in 10 s of QPU time. Measured P(obj = 1):

| m | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| ideal | 0.096 | 0.656 | 1.000 | 0.650 | 0.092 | 0.100 | 0.662 |
| noisy sim | 0.111 | 0.623 | 0.896 | 0.625 | 0.207 | 0.233 | 0.568 |
| `ibm_fez` | 0.128 | 0.616 | 0.842 | 0.580 | 0.247 | 0.314 | 0.574 |

MLAE on the hardware counts (m = 0, 1, 2, 4) gives a = 0.0738 against the exact 0.0959.

**Prior art.** The literature search did not cover QAE runs on hardware, so we cannot say
whether a flood QAE has run on a device before.

**Why it matters.** We make no priority claim. The run shows that the Grover oscillation QAE
depends on survives on a real device for this circuit, damped by noise as depth grows.

**Evidence.** `hw_demo.py` (`dry` for the ideal and noisy simulation, `run` for the QPU),
`results_hw.json`.

**Caveat.** Noise biases the estimate low by 0.022, about 10 times the standard error of plain
Monte Carlo with the same 16,000 samples (0.0023), so today's hardware does not beat
classical. Three qubits is a toy; the five-driver benchmark circuit needs two-qubit error near 1e-8 (`README_multidriver.md`, "Hardware").
