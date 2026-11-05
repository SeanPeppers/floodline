# Floodline hybrid: classical conditioning plus a quantum mean of the residual

## Verdict

**The hybrid does not beat the best classical method, and it does not even tie it.** Counted in
table reads (rule evaluations), conditional MC on Sobol points (CMC+QMC) needs 2.0-16× less work
than the hybrid on both benchmark streets at every precision we tested. All 95% CIs exclude 1.
In oracle queries alone, before the hybrid's classical overhead, CMC+QMC still needs 1.8-4.5×
fewer. Against plain QAE the hybrid ties on the 3.0 ft street and needs 0.70-0.73× the queries
on the 6.0 ft street. The control variate helps a little, but amplitude encoding cannot cash in
most of the variance it removes.

The extrapolated break-even surface (below) has the hybrid winning on table reads only at
ε ≲ 1e-6 to 4e-5 for d = 5-12 drivers. Past 12 drivers it never wins, because the coarse
control-variate grid grows exponentially with d. **In wall-clock time on fault-tolerant hardware
it never wins at any precision a flood decision could use.** The model's own uncertainty already
caps useful precision near ε ≈ 3e-3: the GEV bootstrap moves a by ±0.03.

## Construction (`hybrid.py`, `hybrid_circuit.py`)

Everything runs on the five-driver discretized model of `multidriver.py` (benchmark grid, 2050
NOAA Intermediate). The classical and quantum parts split the work like this:

1. **Classical analytic conditioning.** The flood rule is monotone in the 3-h burst P3, so
   P(flood | W, P24, S, O) depends on the cell only through `(p24, G >> 2, t = T_int[C, G])`.
   That makes it one lookup table, `ptab`, of 2^15 entries, built from the existing R table by
   one `searchsorted` per (p24, G) pair. `test_hybrid.py` checks that it equals `Model.cond_prob`
   on all 2^18 cells. The quantum oracle reads p(x) from this table, so it needs no coherent
   bisection.
2. **Classical control variate.** g(x) is p at the midpoint of x's coarse cell, with low bits
   dropped per driver. W and P24 never drop below their copula-regime bits. Its exact mean
   costs one table read per coarse cell. We tried four coarse grids: 1k, 8k, 16k and 64k cells.
3. **Quantum mean of the residual** r = p − g ∈ [−1, 1]. The circuit loads (W, P24, S, O) with
   Grover-Rudolph and reads g by QROM into a 14-bit register. It forms C = W + S and G = S + O
   with Cuccaro adders, reads T by QROM, then reads p by QROM (14-bit fixed point). It computes
   Y = P + (2^14 − 1 − G) with one more adder. A uniformly controlled RY on Y then rotates the
   objective qubit by 2·arcsin(√y), where y is the [0, 1] amplitude of one residual layer.
4. **Layers (variance-adaptive, Montanaro-style).** Amplitude estimation of a [−1, 1] variable
   pays for the range, not the spread. So r is cut into dyadic layer-cake pieces for r > 0 and
   r < 0 (cuts 0, 2^−(L−1), …, 1/2, 1). Each piece runs its own MLAE (100 shots per Grover power,
   the same as the plain QAE arm). A 2^10-point classical pilot picks L. Every layer runs even if
   the pilot never saw it, because skipping a layer would bias the result.

Estimate = exact CV mean + Σ layer estimates. Only p's fixed-point rounding biases it, by
≤ 2^−15. The measured bias is −1.3e-5 at 3.0 ft and −4e-6 at 6.0 ft, under 1% of ε = 1e-4 when
added in quadrature.

### The tide-alone discontinuity, and what we did about it

Our first design split the tide-alone region (T = 0, where p = 1 without rain) off exactly and
classically. We measured its effect before keeping it, and it did nothing. The residual's sd was
0.14756 with the split and 0.14756 without it at 3.0 ft, and 0.0381 / 0.0381 at 6.0 ft. With
the split, sup|r| was still 1. The ±1 jumps do not come from the tide-alone region, which holds
only 1.3% of the mass at 3.0 ft. They come from coarse cells that straddle jumps in the drainage
threshold T, where the coarse midpoint and the fine cell sit on opposite sides of a tide or
groundwater step. We dropped the split; `ptab[., ., t = 0] = 1` handles the tide-alone region for
free. The layer split above is the variance-adaptive answer to the remaining jumps. A finer CV
grid shrinks them (P(|r| > 0.3) falls from 7.2% to 2.5% at 3.0 ft between 1k and 64k cells), but
each extra cell costs a classical read.

### Why the CV doesn't help much

| street | a | sd, indicator (plain QAE) | sd of p (CMC) | sd of r, 1k / 64k CV | hybrid constant, 1k / 64k CV |
|---|---|---|---|---|---|
| 3.0 ft | 0.6148 | 0.487 | 0.360 | 0.148 / 0.086 | 0.536 / 0.332 |
| 6.0 ft | 0.0944 | 0.292 | 0.202 | 0.038 / 0.021 | 0.255 / 0.119 |

A Montanaro / Kothari-O'Donnell mean estimator costs O(σ/ε) for the variable it receives
(Kothari and O'Donnell, arXiv:2208.07544: error σ/n after O(n) runs of the code). With the
residual's sd it would need 3.3-8× fewer queries than plain QAE, which matches the 4-8× the
research report predicted. MLAE on amplitude-encoded layers pays width × √(a_k(1 − a_k)) per
layer instead (the "hybrid constant" column, with equal shots per layer). That gets 0.9-1.15×
with the cheap 1k CV and 1.5-2.5× with the 64k CV. The 64k CV costs 65,536 classical reads,
which is more than CMC+QMC needs for the whole answer at ε = 1e-4. A full Montanaro
implementation (Montanaro, arXiv:1504.06987) would close part of this gap, at the price of
log factors and many more layers.

## Validation (`test_hybrid.py`)

At reduced resolution the circuit has 20 qubits: all four non-leaf drivers, the CV QROM, both
adders, the T and p QROMs, the residual adder and the arcsin-√ rotation, with b = 2 and n_k = 2.
We use exact Aer statevector simulation through `qae.exact_hit_probs`, which composes the
un-flattened circuits and decomposes once. P(obj = 1) after Q^m A_h matches sin²((2m+1)θ_k)
with a_k computed by enumeration, to at most 1.6e-14, for m = 0, 1, 2, 4. This holds for all
four layers of a two-level split, in both signs. The real reduced-grid CV is one-signed, so the
test fills the CV table with seeded random values to exercise r > 0. The gate counter matches
the built circuit's CCX and CX counts. ptab equals `Model.cond_prob` on all 2^18 benchmark
cells. The estimator identity holds to 1e-15 for every CV grid.

Full-resolution hybrid statistics use the closed-form law, as `experiment_multi.py` does for QAE.
That **assumes a correct, fault-free circuit at 71 qubits**. The reduced-scale test is the
evidence that the construction is correct.

## Scaling (`experiment_hybrid.py` → `results_hybrid.json`)

The protocol follows `experiment_multi.py`. Truth comes from exact enumeration. CMC+QMC runs
128 Sobol replicates with N = 2^8..2^18. QAE and the hybrid each run 300 MLAE trials with
K = 1..12, fitted from K = 3. α comes from an OLS fit of log RMSE on log queries, with
2000-resample bootstrap 95% CIs. Matched-ε counts are read off each bootstrap fit. **A ratio
whose CI contains 1 is a tie, not a win.** The measured MLAE constant is RMSE·queries/√(a(1−a))
= 17.75 (3.0 ft) and 17.37 (6.0 ft).

### Exponents α (queries ∝ ε^−α), 95% CI

| street | CMC+QMC | plain QAE | hybrid 1k | hybrid 8k | hybrid 16k | hybrid 64k | enumeration |
|---|---|---|---|---|---|---|---|
| 3.0 ft | 1.36 [1.33, 1.39] | 1.03 [1.02, 1.05] | 1.00 [0.99, 1.02] | 1.27 [1.12, 1.34] | 1.05 [1.03, 1.07] | 0.97 [0.96, 0.99] | exact, 2.6e5 reads |
| 6.0 ft | 1.36 [1.32, 1.40] | 1.02 [1.01, 1.04] | 1.52 [1.11, 1.65] | 1.03 [1.02, 1.05] | 1.00 [0.99, 1.01] | 1.61 [1.22, 1.77] | exact, 2.6e5 reads |

The α > 1 hybrid fits (8k at 3.0 ft; 1k and 64k at 6.0 ft) all have a rare layer
(a_k ~ 1e-4 to 1e-3) whose MLAE is non-asymptotic at shallow depth. Their wide CIs say so.
Treat those as non-asymptotic, not as a worse rate. If the CV grid is picked per ε from the
fitted curves, the cost envelope has a slope of 0.75-0.79, which looks like the Heinrich
quantum rate of 0.80. It is an extrapolation across four grids built partly from those
unreliable fits. It is not a measurement.

### Matched ε, best CV grid per ε (median; 95% CI)

Hybrid total = quantum queries + coarse CV cells + all four pilots (4 × 2,048 reads). CMC+QMC
counts one ptab read per sample (white-box, the same table the quantum oracle reads). A
black-box simulator would need a 6-step bisection per sample, shown as ×6.

| street | ε | hybrid queries | hybrid total | CMC+QMC | CMC+QMC ×6 | plain QAE | enumeration | hybrid total ÷ CMC+QMC | hybrid queries ÷ QAE |
|---|---|---|---|---|---|---|---|---|---|
| 3.0 ft | 1e-3 | 9.9k (1k CV) | 19.1k | 2.4k | 14.2k | 9.2k | 262k | **8.0 [7.5, 8.7]** | 1.08 [1.02, 1.14] |
| 3.0 ft | 3e-4 | 33.0k | 42.2k | 12.2k | 73.1k | 31.9k | 262k | **3.5 [3.2, 3.7]** | tie, 1.04 [0.98, 1.09] |
| 3.0 ft | 1e-4 | 99.2k | 108k | 54.1k | 325k | 99.3k | 262k | **2.0 [1.8, 2.2]** | tie, 1.00 [0.94, 1.07] |
| 6.0 ft | 1e-3 | 3.6k (1k CV) | 12.9k | 0.81k | 4.9k | 5.2k | 262k | **15.9 [14.1, 18.2]** | 0.70 [0.61, 0.95] |
| 6.0 ft | 3e-4 | 12.8k (8k CV) | 29.2k | 4.2k | 25.0k | 17.8k | 262k | **7.0 [6.5, 7.6]** | 0.72 [0.69, 0.75] |
| 6.0 ft | 1e-4 | 39.7k (8k CV) | 56.1k | 18.5k | 111k | 54.6k | 262k | **3.0 [2.8, 3.2]** | 0.73 [0.69, 0.76] |

CMC+QMC wins every cell. The hybrid beats black-box CMC+QMC (×6) at ε ≤ 3e-4 on the 3.0 ft
street (0.31-0.62×) and at ε = 1e-4 on the 6.0 ft street (0.47-0.54×). That comparison gives the
quantum side a white-box table the classical side is denied, so we do not count it as a win.

## Break-even surface (`experiment_hybrid.breakeven`)

This section extrapolates from the measured d = 5 constants. It is a model, not a measurement.

**Assumptions**:

1. CMC+QMC's exponent follows the Novak-Heinrich randomized rate for a (d−1)-dimensional
   r-smooth integrand, α_c(d) = 1/(1/2 + r/(d−1)). r = 0.94 is fitted to the measured
   α_c(5) = 1.36, which gives α_c(d) = 1.36, 1.52, 1.62, 1.71, 1.78 at d = 5, 7, 9, 12, 16.
   Its constant is pinned at the measured d = 5 query count at ε = 1e-3.
2. The hybrid keeps α = 1 and its measured d = 5 constant. Its CV grid keeps the same bits per
   driver, so the CV costs cells_5^((d−1)/4) reads.
3. One A_h costs Toffoli_5 × (d−1)/4. That assumes an arithmetic oracle linear in d; the QROMs
   as built grow exponentially, so this is generous. Toffoli_5 = 58k on the 3.0 ft street
   (652k CX-equivalent, 71 logical qubits).
4. A Toffoli takes 170 µs: Babbush et al., arXiv:2011.04149, surface code with d = 30, 1 µs
   cycles, physical error about 1e-3. One QPU and one CPU core. A classical sample takes 1.8 µs,
   measured `Model.cond_prob` on this laptop, scaled by (d−1)/4.
5. Two-qubit error for the unencoded circuit: the deepest MLAE circuit must succeed half the
   time, so p2q ≤ ln 2 / CX(deepest).

| d | α_c | ε* where hybrid wins on table reads (3.0 / 6.0 ft) | p2q needed there | ε* where hybrid wins on wall clock |
|---|---|---|---|---|
| 5 | 1.36 | 1.6e-5 / 1.0e-5 | 5e-10 / 8e-10 | ~1e-24 (≈1e18 years of QPU time) |
| 6 | 1.45 | 4.0e-5 / 1.6e-5 | 8e-10 / 7e-10 | ~5e-20 |
| 8 | 1.58 | 3.2e-5 / 2.5e-6 | 6e-10 / 1e-10 | ~1e-16 |
| 10 | 1.65 | 6.3e-6 / none | 1e-10 | ~5e-15 |
| 12 | 1.71 | 1.3e-6 / none | 1e-11 | ~4e-14 |
| ≥ 13 | ≥ 1.73 | none (CV grid cost explodes) | | ~1e-13 (≈1e8 years) |

On table reads the hybrid wins only at precisions 100× finer than the model's own uncertainty,
and only below 13 drivers. On wall clock there is no break-even at any usable precision: a
Toffoli costs about 100× more than a whole classical sample, and one A_h is 58k Toffolis. This
matches Babbush et al.'s conclusion that quadratic speedups rarely pay off on early
fault-tolerant machines. Unencoded, every row needs two-qubit error ≤ 1e-9, about six orders of
magnitude below today's ~1e-3.

## Engine (`hybrid.estimate`, `floodline_tool.py`)

`estimate(cfg, eps, backend)` with three backends:

- `classical`: CMC+QMC on the benchmark grid. It doubles N until the 95% half-width ≤ ε. Seconds.
- `quantum-sim`: the hybrid circuit at the 20-qubit reduced grid. Aer statevector gives P(obj)
  per Grover power, shots are drawn binomially from it, then MLAE.
- `quantum-resource`: picks the cheapest CV grid from the pilots, then reports queries, qubits,
  Toffoli/CX, the deepest circuit, the p2q it needs and fault-tolerant hours. Nothing runs.

```
$ uv run python floodline_tool.py --year 2050 --scenario intermediate --elevation 3.0 --eps 1e-4
  P(flood > 6 in, any given year) = 0.6148 +- 7.6e-05 (95%), 524,288 conditional samples, 1.4 s
$ uv run python floodline_tool.py --year 2050 --scenario intermediate --elevation 3.0 --backend quantum-resource --eps 1e-4
  to reach +-0.0001 (RMSE) with the hybrid: 93,227 oracle queries (plain QAE up to 87,500); CV grid 2,048 cells,
  1 residual layer(s) per sign, 10,240 classical table reads
  circuit: 73 logical qubits, one A_h = 116,206 Toffoli / 1,268,658 CX-equivalent; deepest Q^128 A_h = 326,082,482 CX
  needs 2-qubit error <= 2.1e-09 for 50% success unencoded; fault-tolerant at 170 us/Toffoli: 511.6 h
$ uv run python floodline_tool.py --elevation 2.0 --backend quantum-sim
  reduced grid (20 qubits): hybrid estimate 0.3067, exact on the same grid 0.3095, |error| 2.8e-03 with 28,000 oracle queries, 87 s
```

The CLI's grid widens S to 5 bits for 2050 (`floodline_cli.grid_for`), so its "1k" CV has 2,048
cells and A_h is larger than on the benchmark grid. The quantum-sim error (2.8e-3 from 28k
queries) is ordinary MLAE noise at this budget; its answer is for the 20-qubit reduced grid, a
different model from the classical line.

## Road-raising priority (`road_priority.py`)

`road_priority.py` uses the 6,054 road points `multidriver.py` samples (one every ~30 m of OSM
centreline, USGS 3DEP 1 m lidar). It regroups them into 754 OSM ways and then 365 named
streets. P(z) comes from the five-driver model (CMC+QMC) on a 0.25 ft grid for 2026 and
2030-2050, under the Intermediate and High scenarios.

A street's low point is the 10th percentile of its samples, because single seawall pixels reach
−1.6 ft. Streets are ranked by expected flooded miles per year in 2050 (Intermediate), because
the low-point probability saturates at 1. "Flood-years avoided per foot" sums P(z_low) −
P(z_low + 1 ft) over 2026-2050 (Intermediate). The script writes `road_priority.csv`,
`road_priority.json` and `web/assets/data/road_priority.json` (the top 100).

| # | street | mi | low ft | P 2026 | P 2050 int | P 2050 high | flooded mi/yr 2050 int | flood-yrs avoided /ft | $/flood-yr avoided @ $9.6M/mi |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Flagler Avenue | 4.69 | 1.41 | 0.89 | 0.99 | 1.00 | 3.85 | 6.4 | $7.0M |
| 2 | South Roosevelt Blvd | 2.91 | 2.37 | 0.61 | 0.80 | 0.90 | 1.83 | 7.7 | $3.6M |
| 3 | North Roosevelt Blvd | 2.59 | 2.82 | 0.48 | 0.67 | 0.80 | 1.24 | 7.1 | $3.5M |
| 4 | Front Street | 1.37 | 0.75 | 1.00 | 1.00 | 1.00 | 0.93 | 3.0 | $4.4M |
| 5 | College Road | 1.76 | 2.51 | 0.57 | 0.76 | 0.88 | 0.92 | 7.7 | $2.2M |
| 6 | Sigsbee Road | 1.52 | 1.95 | 0.75 | 0.91 | 0.97 | 0.88 | 7.5 | $2.0M |
| 7 | Fogarty Avenue | 0.92 | 1.35 | 0.91 | 1.00 | 1.00 | 0.86 | 6.2 | $1.4M |
| 8 | Harris Avenue | 0.98 | 1.44 | 0.88 | 0.99 | 1.00 | 0.82 | 6.5 | $1.4M |
| 9 | Patterson Avenue | 0.87 | 1.40 | 0.89 | 0.99 | 1.00 | 0.81 | 6.4 | $1.3M |
| 10 | 5th Street | 1.02 | 1.93 | 0.75 | 0.92 | 0.97 | 0.78 | 7.4 | $1.3M |

**Costs.** Every figure was read on the page cited:

- Monroe County's roads plan: "$1.6 billion, at a cost of $9.6 million/mile" for 116 of 311
  county road miles by 2045. Florida Specifier, 2023-03-04,
  https://floridaspecifier.com/issues/v44n6/monroe-county-caps-roads-plan-with-1-6-billion-in-projects/
- Twin Lakes pilot, Key Largo: "$21 million", "4,633 linear feet of road" (Shaw Dr, Crane St,
  Adams Dr), which works out to $23.9M per mile all-in, drainage included. Keys Weekly,
  2024-08-22, https://keysweekly.com/?p=84561

Neither page states a raise height. Pairing the $/mile with a 1-ft raise is our **assumption**,
so treat the $ per flood-year column as an order of magnitude. The JSON also gives the Twin Lakes
version, which is 2.5× higher. We found no City of Key West street-raising cost on a page we
could open. These are Monroe County projects, not City of Key West ones.

**Which flood model, and how much the choice matters.** We use the five-driver model with the
LOS-anchored drainage, the same model as the CLI and the benchmark. It is the only one that
takes elevation, year and scenario as inputs; `drainage.py` is calibrated to one node. The two
disagree at SMP node N3210 (Patterson Ave, 1.12 ft, today): a = 0.967 here against 0.640 in
the 2-driver model. To test the ranking, we scaled the five-driver drainage capacity up 10.3×
until N3210 matched 0.640, then reran 2050 Intermediate. The city-wide expected flooded share
falls from 56% to 19%, so absolute numbers depend heavily on drainage calibration. The ranking
holds up better: Spearman ρ = 0.91 on flooded miles, Flagler Ave stays #1, Fogarty, Patterson,
Front and Harris stay in the top 5, and the two top-25 lists share 13 streets. The streets that
fall are the ones flooded by rain more than tide: College Rd drops from 5 to 93 and North
Roosevelt from 3 to 52. Read the order as robust at the top and calibration-dependent below it.
Read the probabilities as a ranking tool, not a forecast. Centreline lidar also sits above
gutters, so it understates exposure.

## Limitations

1. Full-scale circuits are costed and checked against the closed form, not simulated. The
   construction is verified at 20 qubits.
2. Hybrid shots are equal across layers. An optimal split could save up to 2×, but MLAE with
   fewer than ~30 shots per power proved unstable at depth, so we do not claim that saving.
3. The break-even surface extrapolates d = 5 constants with stated rate models. We have no data
   at d > 5.
4. The oracle reads classically precomputed tables (ptab 2^15, T 2^12, CV ≤ 2^16 entries). That
   precompute is shared with the classical arm and is not charged to either side.

## Files

`hybrid.py` (estimator, engine), `hybrid_circuit.py` (A_h, gate counter), `test_hybrid.py`
(~2 min), `experiment_hybrid.py` (~7 min on 4 cores, writes `results_hybrid.json`),
`floodline_tool.py` (CLI with `--backend`), and `road_priority.py` (~8 min).
