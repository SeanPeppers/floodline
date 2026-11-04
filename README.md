# Floodline: Key West Compound Flood Tail Probability with Quantum Amplitude Estimation

FGCU Quantum Hackathon 2026 candidate build. Self-contained, simulator-only
(`RUN_ON_HARDWARE = False` in `experiment.py`).

## Why this genre

Most of this week's builds compared one heuristic (QAOA, a QML model) with another,
and a classical control that had the same structural prior usually tied. This build
tests a claim that has a proof behind it instead: amplitude estimation (QAE) estimates
a probability to error ε with O(1/ε) oracle queries, while plain Monte Carlo needs
O(1/ε²) samples. The questions are whether the scaling actually shows up when we
measure it on a real problem, and what it costs to get it.

## The problem and the real data

**Question:** in a given year, at today's sea level, what is the probability that Key
West sees a **compound flood event** -- the annual peak water level reaches NWS
**minor flood** stage *and* the heaviest 24-hour rainfall that year is at least a
10-year event?

**Tide marginal** (`flood.py`), unchanged from an earlier single-variable build:
- NOAA CO-OPS station 8724580 (Key West, FL), `monthly_mean` product, `Highest`
  column, datum MHHW, metric, 1913-2025 (one of the longest tide-gauge records in the
  US), fetched from `api.tidesandcurrents.noaa.gov` and cached in
  `data/keywest_monthly.csv`.
- Annual maxima for years with ≥ 10 months of data (110 years), shifted to 2025 sea
  level using the fitted linear SLR trend (2.65 mm/yr), GEV-fit by maximum likelihood
  (shape c = -0.218, loc = 0.382 m, scale = 0.059 m), binned onto 2^5 = 32 bins of 4 cm.
- Threshold: NWS **minor** flood stage, 0.335 m above MHHW (`floodlevels.json`) ->
  bin 11 of 32. Marginal tide-alone tail: **0.0458** (the same 1-in-22-year number the
  single-variable build reported, now for *minor* stage instead of *major*, since minor
  is the stage that pairs sensibly with "also heavy rain" as a compound event).

**Rain marginal** (`rainfall.py`), new for this build:
- NOAA Atlas 14 (PFDS) published 24-hour annual-maximum-series return-period depths for
  the same grid point as the tide station, fetched from `hdsc.nws.noaa.gov` and cached
  in `data/keywest_pfds_ams_24h.json`. NOAA's server already fits the raw daily-rainfall
  record; it returns only 9 (return period, depth) points. We re-fit a Gumbel
  distribution to those 9 points (loc = 1.494 in, scale = 2.930 in) -- a standard
  hydrology technique for working from a published frequency curve, binned onto
  2^3 = 8 bins of 1.865 in.
- Threshold: the 10-year 24-hour depth, 7.46 in -> bin 4 of 8. There's no NWS/FEMA
  "heavy rain flood stage" analogous to the tide thresholds; 10-year is a modeling
  choice for "rain heavy enough to plausibly worsen coastal flooding in flat,
  poorly-drained terrain," not an official standard.

**Joint model** (`copula.py`): a discretized Gaussian copula links the two marginals.
Wahl et al. 2015 (*Nature Climate Change*, doi:10.1038/nclimate2736) directly studied
Key West (their tide gauge #17) and found a statistically significant **positive**
dependence between storm surge and precipitation extremes there. That sign and
significance claim is real and cited. The exact Kendall's-tau magnitude they measured
at Key West is reported only in a figure, not as an extractable table number, so the
correlation used here (τ = 0.3, ρ = sin(πτ/2) = 0.454) is an explicit **assumption**, a
representative moderate positive value, not Key West's measured number -- flagged in
`copula.py`'s module docstring, not buried.

No closed-form 2-D joint CDF is ever handed to either estimator. The circuit loads the
tide marginal, reads off a coarse tide "regime" from its top 2 bits (4 regimes), and
controlled-loads one of 4 conditional rain distributions depending on that regime -- a
discretized Rosenblatt/copula construction. The classical estimators sample from the
exact same generative model (draw a tide bin, then a rain bin conditioned on that
draw's regime), never by inverting a 2-D CDF.

**Target:** a = **0.1090** (the compound event is about 2.4× more likely than the tide
threshold alone, since rain exceedance has meaningful probability too and the two are
positively correlated). Both the quantum and the classical estimators target this same
`a`; the comparison is about how fast each one converges.

## Method

**Circuit** (`qae.py` + `copula.py`, 17 logical qubits):
- `A` loads the 32-bin tide marginal on 5 qubits, then controlled-loads one of 4
  regime-conditional 8-bin rain distributions on 3 more qubits (gated by the tide's top
  2 bits), then two `IntegerComparatorGate`s (tide ≥ bin 11, rain ≥ bin 4) and a `ccx`
  into an objective qubit that fires only when both hit.
- `Q = A S0 A† S_χ` is built with `grover_operator`, same as the single-variable build.
  P(objective = 1) after `Q^m A` is sin²((2m+1)θ), a = sin²θ. The smoke test checks this
  against the circuit to ~1e-13 for both the tide-only and the compound circuit
  specifically (see `exact_hit_probs`'s docstring in `qae.py` for why checking only the
  simpler circuit wouldn't have been enough).

**Quantum estimator:** maximum-likelihood amplitude estimation (MLAE; Suzuki et al.,
2020). It runs `Q^m A` for m ∈ {0, 1, 2, 4, …, 2^(K-2)} with 100 shots each and
maximizes the joint binomial likelihood. Unlike canonical QAE it needs no QPE and no
controlled-Q. K runs from 1 to 7, so the largest Grover power is m = 32 -- smaller than
the single-variable build's m = 512, because this circuit's Grover step is ~5× more
gate-dense (see Hardware realism below) and `exact_hit_probs`'s one-shot exact
simulation cost scales with total gate count.

**Query accounting:** one call of `A` or `A†` counts as one query, which is the same unit
as one classical draw from the joint model. A shot of `Q^m A` costs 2m+1 queries. The
simulator speed-up is to compute P(obj = 1) for each m once -- by composing `A` then `Q`
up to the largest needed m with a probability checkpoint spliced in at every scheduled
m, decomposing the whole assembled circuit to elementary gates, and running it once on
Aer's exact statevector backend -- and then draw binomial shots from those probabilities.
This is mathematically identical to running the sampler; the smoke test checks it
against `StatevectorSampler`.

**Classical arms**, run at exactly the same query budgets:
1. **Plain Monte Carlo:** N iid draws from the joint model, counting compound
   exceedances. This is exactly Binomial(N, a).
2. **Sobol QMC (2-D):** a scrambled 2-D Sobol low-discrepancy sequence pushed through
   `copula.compound_hits` (tide bin from one Sobol coordinate, rain bin from the other,
   conditioned on the regime). The single-variable build's control was 1-D stratified
   sampling; that trick doesn't generalize to a joint 2-D distribution, so this is the
   honest smarter-than-plain-MC classical control for a 2-D problem.

**Measurement discipline:**
- 500 seeded trials per (arm, budget). Error is RMSE against `a`.
- The scaling exponent comes from an OLS fit of log RMSE on log queries for K ≥ 3 (5
  budget points, fewer than the single-variable build's 9, because K_MAX is smaller
  here -- see Method above). The 95% CI comes from 2000 bootstrap resamples of trials.
  We report α in queries ∝ ε^(-α), where α = -1/slope.
- Queries needed at matched ε targets are read off each bootstrap fit, with the CI of
  the paired ratio.

## Results (`results.json`, `results.png`)

![query scaling](results.png)

**Fitted scaling exponent α (queries ∝ ε^-α), 95% bootstrap CI:**

| arm | α | 95% CI | textbook |
|---|---|---|---|
| MLAE (quantum) | **1.06** | [1.01, 1.12] | 1 |
| plain Monte Carlo | **2.06** | [1.94, 2.20] | 2 |
| Sobol QMC (classical, 2-D) | **1.16** | [1.12, 1.20] | 1 in 1-D; degrades with dimension |

The plain-MC exponent matches 2 inside its CI. QMC's exponent (1.16) is visibly above 1
and above the single-variable build's 1-D stratified-sampling exponent (0.98) -- exactly
the expected signature of quasi-Monte Carlo's discrepancy bound degrading with
dimension (O((log N)^d / N) in d dimensions), not noise. MLAE's exponent still matches
textbook 1 inside its CI even at this deeper, more gate-dense circuit.

**Queries needed at matched error ε** (median of bootstrap fits, ratio CI paired):

| ε (relative ε) | MLAE | plain MC | MC / MLAE | Sobol QMC | QMC / MLAE |
|---|---|---|---|---|---|
| 1e-3 (0.9%) | 8.2k | 107k | **13.1×** [10.6, 16.5] | 1.8k | 0.22× [0.20, 0.24] |
| 3e-4 (0.28%) | 29.2k | 1.28M | **43.6×** [30.5, 65.2] | 7.2k | 0.25× [0.22, 0.28] |
| 1e-4 (0.09%) | 93.4k | 12.3M | **131×** [80, 231] | 25.6k | 0.27× [0.23, 0.33] |

MLAE needs 3.7-4.6× more queries than Sobol QMC across this range -- smaller than the
single-variable build's 8× gap over 1-D stratified sampling. That shrinkage is the same
dimensionality effect as the α numbers above, seen from the other side: a smarter
classical method still wins here, but its margin over QAE narrows as the problem gains
a dimension, which is the direction the "QAE matters in high dimensions" argument
predicts.

## Demo

`results.png` is a static log-log plot; a judge at a table needs the convergence
itself, not a chart of it. `demo.py` animates one live run of all three estimators
against the same real compound tide+rain model, stepping through the same geometric
query budgets as the benchmark:

- Three colored dots/lines climb toward a dashed horizontal line (the true compound
  tail probability, a = 0.1090) as the query count (shown live, top-left) grows.
- A vertical marker drops in for quantum MLAE and Sobol QMC the moment each reaches its
  exact queries-to-converge number already reported above (ε = 1e-3 row): **8.2k** and
  **1.8k** respectively. Those numbers come straight from `results.json`'s `matched_eps`
  table, not from the single animated run, so an unlucky draw on demo day can't
  contradict the measured result. Plain Monte Carlo's convergence point (**107k**
  queries) never gets a marker: it's genuinely off the ~13k-query animated range, which
  is itself the visible point, not a limitation of the demo.
- In about 30-40 seconds a judge watches the quantum line settle in a few thousand
  queries, the smart classical control (Sobol QMC) settle even sooner, and plain Monte
  Carlo still visibly wandering with no end in sight by the time the animation stops --
  the same honest verdict as above, just visible instead of read off a table.

Run: `uv run python demo.py` (precompute ~40s -- dominated by the same one-shot exact
circuit simulation `experiment.py` does -- then a looping animated window; needs a
display, so run it locally rather than over SSH).

## Hardware realism (the big caveat)

Each circuit was transpiled to IBM Heron (`FakeFez`, heavy-hex, CZ basis, opt level 3):

| | CZ gates | depth |
|---|---|---|
| `A` (compound state prep + both comparators) | 1,437 | 4,505 |
| `Q` (one Grover step) | 3,677 | 11,048 |
| `Q^m A`, m = 1 | 5,114 | 15,553 |
| `Q^m A`, m = 4 | 16,145 | 48,697 |
| `Q^m A`, m = 32 (largest Grover power run) | 119,101 | 358,041 |

Both `A` and `Q` are far heavier than the single-variable build's (137 CZ / 720 CZ) --
roughly 10× and 5× respectively -- because the regime-gated, multiply-controlled rain
state prep is expensive to synthesize. The median FakeFez CZ error is 3.9e-3, so a
circuit gets roughly 1/0.0039 ≈ 256 CZ before noise dominates; `A` alone is already
5.6× over that budget before a single Grover step runs. The noisy simulation (Aer, real
FakeFez calibration data restricted to the 17 qubits actually used -- see
`restricted_noise` in `experiment.py` -- 40 shots) shows this directly:

| m | ideal P(obj=1) | noisy P(obj=1) |
|---|---|---|
| 0 | 0.109 | 0.425 |
| 1 | 0.717 | 0.450 |

Even `m = 0` -- just the state-prep circuit, no Grover step at all -- is already almost
a coin flip under noise, and the noisy MLAE estimate from these two points is 0.508
when the true value is 0.109 (absolute error 0.40). This is a starker failure than the
single-variable build saw at the same Grover powers, exactly because the compound
circuit's state prep alone is already several multiples of the device's CZ budget. We
ran only m ∈ {0, 1} here (not {0, 1, 2, 4}) and at 40 shots instead of 4,000: at this
circuit's cost, m = 2 alone would take over 20 minutes to simulate noisily, and the
qualitative conclusion -- today's hardware washes out the signal before the first
Grover step even finishes -- is already visible at m = 1.

## Verdict

**What this demonstrates:**
- The quadratic query-complexity separation between QAE and **plain Monte Carlo** is
  real and measurable on a real-data, two-variable compound-event problem, not just
  asserted. The exponents were fitted from 500-trial curves with CIs: α = 1.06
  [1.01, 1.12] for QAE against α = 2.06 [1.94, 2.20] for MC.
- In query count, MLAE needs 13× fewer queries than plain MC at ~1% relative error and
  about 131× fewer at ~0.1%.
- Going from one random variable to two visibly narrows the gap between QAE and the
  best classical control (Sobol QMC): its exponent rises from 0.98 (1-D stratified
  sampling, single-variable build) to 1.16 (2-D Sobol), and its query-count margin over
  MLAE shrinks from ~8× to ~3.7-4.6×. That's the actual, measured shape of "QMC degrades
  with dimension, QAE doesn't" on a real instance, not an assertion about what would
  happen at higher dimension.
- This is a simulator-only, ideal-circuit result.

**What it does not demonstrate:**
1. **Still no advantage over the best classical method at this dimension.** Sobol QMC
   needs about 3.7-4.6× fewer queries than MLAE at every ε tested here. The quadratic
   speed-up is over plain MC only. The gap that matters -- QAE vs. the best classical
   control -- is closing as dimension grows (8× at d=1, ~4× at d=2 here), which is
   suggestive but is two data points, not a trend fit. A genuinely high-dimensional,
   non-smooth simulator (many correlated random inputs, path-dependent dynamics) is
   where QMC's curse of dimensionality would plausibly flip the sign; that circuit's
   state preparation would also be far deeper than this one.
2. **No practical hardware speed-up today, more so than before.** This compound
   circuit's state prep alone (1,437 CZ) is 5.6× the device's noise budget before any
   Grover step runs; the single-variable build's was only 0.5× it. Adding a second
   correlated random variable made the "is this feasible on a NISQ device" verdict
   worse, not better.
3. **Query count is not wall-clock time.** One quantum query costs much more than one
   classical draw (gate times, shots, readout, error-correction overhead). Those constant
   factors can absorb a quadratic speed-up at any precision people actually need.
4. **Two of the three numbers behind `a` are models, and one is an assumption.** The
   GEV tide fit and the Gumbel rain fit each have their own parameter uncertainty, far
   larger than ε = 1e-4. The correlation between them (τ = 0.3) is an explicit stand-in
   for a number the cited study measured but didn't publish as extractable data, not a
   fitted or looked-up value. A better estimator of `a` does not make the compound
   flood probability better known, and here it especially doesn't fix the weakest input.

**Bottom line:** this is a genuine and correctly measured demonstration of QAE's
theoretical query scaling, now on a two-variable compound event instead of one. It is
still not evidence of a quantum advantage for this flood problem, either now on
hardware or in principle against a sensible classical method at this dimension -- but
the margin by which the best classical method wins shrank when the problem gained a
dimension, which is the direction the theory says it should. Pitch it as "we measured
the provable part, and we measured which way the classical advantage moves as the
problem gets harder," not as "quantum beats classical."

## Files

- `flood.py`: NOAA tide fetch and cache, detrending, GEV fit, discretization.
- `rainfall.py`: NOAA Atlas 14 rainfall fetch and cache, Gumbel fit, discretization.
- `copula.py`: discretized Gaussian-copula joint model, compound state-prep circuit,
  honest classical joint sampler.
- `qae.py`: `A`, `Q`, the MLAE schedule and estimator, exact hit probabilities.
- `experiment.py`: the three-arm benchmark, scaling fits, hardware cost, restricted
  noisy run, plot.
- `smoke_test.py`: circuit vs closed form (both the single-variable and the compound
  circuit) vs `StatevectorSampler`, MC equivalence, and a tiny end-to-end run.
- `demo.py`: live animated convergence demo for the hackathon table (see Demo above).

## Run

```
uv sync
uv run python smoke_test.py   # ~30s
uv run python experiment.py   # ~7 min, writes results.json and results.png
uv run python demo.py         # ~40s precompute, then an animated window (needs a display)
uv run ruff check . && uv run mypy .
```

`.env` is needed only if `RUN_ON_HARDWARE` or `SAVE_ACCOUNT` is flipped (see
`.env.example`). The hardware path is intentionally not built; the noisy-simulation
section above shows why.
