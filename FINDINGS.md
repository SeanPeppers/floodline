# Findings: where quantum wins and where it loses

## Verdict

Ideal, fault-free quantum amplitude estimation (QAE) beats the strongest classical estimator we know in one measured regime. Once the flood model's own parameter uncertainty is folded in as extra random inputs (13 dimensions), QAE needs **4.3× [3.5, 5.4] fewer oracle queries than conditional Monte Carlo on Sobol points (CMC+QMC) at ε = 1e-4**. It also beats plain Monte Carlo by 28-351×, plain Sobol QMC from about 4 drivers up, and a black-box simulator by up to 3.3×. Every one of these wins is counted in queries. In total work, wall-clock time and real hardware, classical wins every case we measured, and the hardware needed is roughly a million times cleaner than today's.

All ratios below are classical queries ÷ QAE queries unless stated, so a ratio above 1 means QAE needs fewer. Brackets are 95% bootstrap CIs. A ratio whose CI contains 1 is a tie. "ε" is absolute RMSE on the flood probability a. Rows marked "extrapolated" use fitted lines beyond the largest budget actually run.

## What is new

We found no prior published head-to-head of QAE against quasi-Monte Carlo on a real risk model, and no prior QAE study of a real city's compound flood; the closest work is Kirke (arXiv:2603.15664) on insurance loss. Floodline measures QAE against plain MC, Sobol QMC, conditional MC + Sobol, exact enumeration, and a black-box simulator on a Key West model built from the City's 2024 Stormwater Master Plan, finds the crossover against the strongest of them once epistemic uncertainty is included (d ≈ 7-8), and validates the circuit against the closed form up to 30 qubits. Details, prior art and caveats for each claim are in [NOVELTIES.md](NOVELTIES.md). Sources are in [CITATIONS.md](CITATIONS.md).

## Where our algorithm wins

Every win, with the exact conditions under which it holds:

- **13-dimension model, against CMC+QMC (the strongest classical estimator).** 4.3× [3.5, 5.4] at ε = 1e-4 and 2.1× [1.8, 2.4] at ε = 3e-4. Ideal QAE, white-box query counting, 5 physical drivers plus 8 epistemic parameters. Tie at ε = 1e-3 (0.93 [0.79, 1.07]). `README_wins.md`, `results_wins.json`.
- **9 and 10 dimensions, against CMC+QMC.** 3.0× [2.5, 3.6] (d = 9) and 3.0× [2.6, 3.6] (d = 10) at ε = 1e-4; 1.51× [1.30, 1.72] and 1.53× [1.38, 1.71] at ε = 3e-4. Losses at ε = 1e-3. `results_wins.json`.
- **Against plain Monte Carlo, at every size tested.** Two-driver realistic rule: 27.7× [21.8, 36.5], 105× [72, 162] and 351× [213, 632] at ε = 1e-3, 3e-4, 1e-4 (the last two extrapolated for MLAE). Five-driver model: 76-246×. Fitted exponents α 0.91 (QAE) vs 2.01 (MC) on the two-driver rule. `README.md`, `README_multidriver.md`.
- **Against plain Sobol QMC from about 4 drivers.** Crossover d* = 3.5-4.9 depending on ε and street. At d = 5, 3.5× [3.1, 3.9] at ε = 1e-4, 2.1× [1.9, 2.3] at 3e-4, 1.20× [1.10, 1.31] at 1e-3 (3.0 ft street). At d = 13, 14.5× [11.4, 18.4] at ε = 1e-4. `README_multidriver.md`, `results_wins.json`.
- **Against a black-box simulator at d = 5.** If each conditional sample costs a 6-run bisection, QAE needs 1.6×, 2.3× and 3.3× fewer runs at ε = 1e-3, 3e-4, 1e-4 on the 3.0 ft street, and tie / 1.5× / 2.1× on the 6.0 ft street. At d ≤ 4 classical still wins (at most 0.66×). `README_multidriver.md`.
- **Hybrid QAE + control variate against plain QAE, 6.0 ft street.** The hybrid needs 0.70-0.73× plain QAE's queries at all three ε. On the 3.0 ft street it ties. The 1.5-2.5× figure for a 64k-cell control variate is a per-layer constant estimate, not a measured matched-ε ratio. `README_hybrid.md`.
- **Against exact enumeration, in query count only, on fine grids.** At 1/32-ft resolution QAE needs ~1.0e5 queries against 6.7e7 enumeration evaluations. In total gate operations it loses by four orders of magnitude. `README_multidriver.md`.
- **Rare events at h = 2 ft (a = 5.0e-3), narrow window.** 1.34× [1.19, 1.51] over rain-CMC at relative ε = 3e-3 and 1.89× [1.62, 2.21] at 1e-3, under the ideal QAE law only. Enumeration beats QAE at 1e-3, and the MLAE actually simulated needs 3.7e5 queries. `README_wins.md`.

## Ledger

| Opponent | Result (classical ÷ QAE queries) | Regime and conditions | Source |
|---|---|---|---|
| Plain MC | **QAE wins** 27.7× [21.8, 36.5] / 105× [72, 162] / 351× [213, 632] at ε = 1e-3 / 3e-4 / 1e-4; 76-246× on the five-driver model | 2-driver realistic rule, a = 0.640; α 0.91 [0.89, 0.94] vs 2.01 [1.90, 2.15]. The 3e-4 and 1e-4 rows are extrapolated for MLAE | `README.md`, `results.json`, `README_multidriver.md` |
| Sobol QMC, 2 drivers | **Classical wins**: MLAE needs 4.0× [3.8, 4.2] / 3.0× [2.8, 3.3] / 2.3× [2.1, 2.7] more | Realistic drainage boundary; QMC α 1.14 did not degrade (Δα −0.04 [−0.09, +0.02]) | `README.md` |
| Sobol QMC, 3-5 drivers | **QAE wins from d* ≈ 3.5-4.9**. d = 5: 3.5× [3.1, 3.9] at 1e-4 | 3.0 ft street d* = 4.7 / 4.0 / 3.5; 6.0 ft street 4.9 / 4.1 / 3.6 at ε = 1e-3 / 3e-4 / 1e-4. QMC α rises 1.09 → 1.47 | `README_multidriver.md`, `results_multi.json` |
| CMC+QMC, 2-5 physical drivers | **Classical wins all 24 cells**. d = 5: 0.18-0.55×; d ≤ 4: 0.014-0.11× | Integer-table model, both streets, all ε | `README_multidriver.md` |
| CMC+QMC, epistemic dimensions | d = 5: 0.65 [0.58, 0.73]; d = 7: tie 1.12 [0.96, 1.32]; d = 9: 3.0 [2.5, 3.6]; d = 10: 3.0 [2.6, 3.6]; **d = 13: 4.3 [3.5, 5.4]** | ε = 1e-4, ideal QAE, white-box counting. At ε = 3e-4 QAE wins from d = 9; at 1e-3 ties or losses everywhere | `README_wins.md`, `results_wins.json` |
| Exact enumeration | **Classical wins on total work**: 2.6e5 rule evaluations, zero error, vs ~1e5 queries × 1.5e5 CX at d = 5 | Query-count win for QAE only on the 1/32-ft grid (1.0e5 vs 6.7e7 evaluations) | `README_multidriver.md` |
| Hybrid vs CMC+QMC | **Classical wins**: CMC+QMC needs 2.0-16× less work in table reads, 1.8-4.5× fewer in oracle queries alone | Both streets, ε = 1e-3 to 1e-4, all CIs exclude 1 | `README_hybrid.md`, `results_hybrid.json` |
| Hybrid vs plain QAE | 6.0 ft: hybrid needs 0.70-0.73×. 3.0 ft: 1.08 [1.02, 1.14] at 1e-3, ties at 3e-4 and 1e-4 | Equal shots per layer; best CV grid per ε | `README_hybrid.md` |
| Black-box simulator (CMC+QMC ×6) | **QAE wins** 1.6× / 2.3× / 3.3× (3.0 ft); tie 1.08× [0.95, 1.20] / 1.5× / 2.1× (6.0 ft) | d = 5 only; ×6 is a fixed bisection cost; smarter threshold search would shrink it | `README_multidriver.md` |
| Rare events | **Classical wins** except one cell. h = 0.5 / 1 ft: 0.20, 0.36. h = 3 / 5 ft: 0.043, 0.008. h = 2 ft: 1.34 [1.19, 1.51] | Relative ε = 3e-3; QAE given its ideal law because 100-shot MLAE stalls for a < 1e-2; tide-CMC dominates the deep tail | `README_wins.md` |
| Nested expectation | Not a measured result. Model QAE α = 1.14 vs nested CMC+QMC 2.6 [2.3, 3.1], MLMC 2.5 [2.2, 2.9] | Classical numbers extrapolated 30-10⁴× past the data; reference SE exceeds the 1% target | `README_wins.md` |
| Many streets / memory | **Classical wins** (analysis, not run) | One classical sample answers every street (rule is monotone in elevation); enumeration streams in O(chunk) memory | `README_wins.md` |
| Real hardware | **Fails.** 2-driver A is 11,384 CZ, about 44× the noise budget; noisy P(obj = 1) = 0.50 at m = 0 and 1 vs ideal 0.640 and 0.124 | FakeFez snapshot, median CZ error 3.9e-3. d = 5, ε = 1e-4 needs two-qubit error ≈ 9e-9 | `README.md`, `README_multidriver.md` |
| Wall clock | **Classical wins at any usable precision.** Hybrid break-even near ε ≈ 1e-24 at d = 5 (≈1e18 years of QPU time) | 170 µs per Toffoli (arXiv:2011.04149) vs 1.8 µs per classical sample. The CLI's resource backend reports 511.6 fault-tolerant hours where CMC+QMC takes 1.4 s | `README_hybrid.md` |

## The headline win

On the five physical drivers alone, CMC+QMC beats ideal QAE at every ε: at d = 5 and ε = 1e-4 it needs 0.65× [0.58, 0.73] of QAE's queries in `README_wins.md` (floating-point rule, a = 0.6430) and 0.55× [0.52, 0.59] in `README_multidriver.md` (integer tables, a = 0.6148). `experiment_wins.py` then adds eight epistemic parameters the Stormwater Master Plan and the NOAA tide fit leave uncertain: curve number and soil depth (d = 7), outfall share and catchment ratio (d = 9), gravity-well start (d = 10), and the three tide-GEV parameters (d = 13). Drainage is recalibrated for every sample, so the flood boundary moves with the parameters and the conditional integrand stays discontinuous in 12 dimensions.

| d | CMC+QMC α | QAE α | ratio at ε = 1e-4 | ratio at ε = 3e-4 |
|---|---|---|---|---|
| 5 | 1.31 [1.26, 1.36] | 0.97 | 0.65 [0.58, 0.73] | 0.45 [0.41, 0.49] |
| 7 | 1.52 [1.44, 1.61] | 0.99 | 1.12 [0.96, 1.32], tie | 0.63 [0.55, 0.71] |
| 9 | 1.64 [1.57, 1.72] | 1.01 | 3.0 [2.5, 3.6] | 1.51 [1.30, 1.72] |
| 10 | 1.62 [1.54, 1.71] | 1.00 | 3.0 [2.6, 3.6] | 1.53 [1.38, 1.71] |
| 13 | 1.68 [1.59, 1.78] | 1.01 | **4.3 [3.5, 5.4]** | 2.1 [1.8, 2.4] |

The classical exponent climbs from 1.31 to 1.68 while QAE stays at 1.0, so the crossover sits at d ≈ 7-8 at ε = 1e-4. A control variate does not rescue the classical side (RMSE 1.21e-4 plain vs 1.18e-4 with the CV at N = 2^18, at twice the cost per sample), and enumeration is ruled out because the epistemic inputs are continuous.

What limits it: the counts are queries, not work. The d = 5 circuit A is already 149k CX through lookup tables, and folding 8 continuous parameters into those tables would multiply their address space by about 2^32; a coherent arithmetic oracle would be needed, and nobody has built one. Three of the eight parameter ranges are judgment calls, and the crossover depends on them. ε = 1e-4 is far tighter than the model's own uncertainty (the GEV bootstrap alone spreads a by about ±0.016), and at ε = 1e-3 the result is a tie or a loss at every d.

## The other wins

**Plain Monte Carlo.** The quadratic speed-up shows up cleanly on every model. On the two-driver realistic rule MLAE's fitted exponent is 0.91 [0.89, 0.94] against plain MC's 2.01 [1.90, 2.15], and MC needs 27.7× to 351× more queries. On the five-driver model plain MC needs 76-246× more. This is the textbook result; it is real but nobody would use plain MC here.

**Sobol QMC from about four drivers.** With two drivers Sobol QMC wins by 2.3-4.0×, because on a 32-bin grid any boundary is a union of axis-aligned boxes. On the five-driver model QMC's exponent rises with d (1.09, 1.20, 1.31, 1.47 for d = 2-5) toward the He-Owen 2d/(d+1) limit, and QAE overtakes it at d* = 3.5-4.9. The resolution check shows the penalty is real at realistic grid sizes: QMC's d = 5 exponent is 1.21 on a coarse grid, 1.40 on the benchmark grid and 1.58 on a fine one.

**Black-box simulator.** If the flood model cannot be inverted analytically, conditional MC must bisect for each rain threshold, about 6 runs per sample. At d = 5 QAE then needs 1.6×, 2.3× and 3.3× fewer simulator runs on the 3.0 ft street. The savings estimate prices this against real workflows, assuming fault-tolerant hardware that does not exist yet: $15.8k-$42.0k for a 446-storm FEMA-style study, $177k-$330k for the Louisiana 2017 suite, and $11-$21 per P-Surge advisory, whose real limit is its one-hour deadline. Method and sources are on the site's "How we calculated this" panel.

**Hybrid against plain QAE.** Splitting off a classical control variate and estimating the residual with layered MLAE cuts queries to 0.70-0.73× of plain QAE on the 6.0 ft street and ties on the 3.0 ft street. An ideal variance-adaptive mean estimator would save 3.3-8×; amplitude encoding pays for the residual's range rather than its spread and recovers 0.9-1.15× with a 1k-cell CV and 1.5-2.5× with a 64k-cell CV, by the per-layer constant.

## The losses

- **CMC+QMC on the physical model.** Integrating the 3-h rain burst exactly (the rule is monotone in it) and running Sobol over the rest is the best arm in all 24 (street, d, ε) cells. It needs 0.18-0.55× QAE's queries at d = 5 and 0.014-0.11× at d ≤ 4.
- **Enumeration on total work.** At d = 5 the discretized model is solved exactly with 2.6e5 rule evaluations. QAE needs ~1e5 applications of a 1.5e5-CX circuit.
- **Hybrid against CMC+QMC.** 2.0-16× more work in table reads, 1.8-4.5× more in oracle queries alone, every CI excluding 1.
- **Rare events.** The deep tail (h ≥ 3 ft) is tide-driven, so integrating the tide exactly leaves QAE needing 23-125× more queries (ratios 0.043 and 0.008). Shallow events are not rare enough to need help.
- **Many outputs and memory.** One classical sample answers every street at once because the rule is monotone in elevation; enumeration streams in constant memory. Analysis only.
- **Wall clock.** A Toffoli at 170 µs costs about 100× a whole classical sample (1.8 µs), and one hybrid A is 58k Toffolis. The hybrid break-even on wall clock sits at ε ≈ 1e-24 for d = 5, about 1e18 years of QPU time.
- **Hardware.** The two-driver realistic circuit is 19 qubits and its A alone is about 44× the FakeFez noise budget; the noisy simulation returns a coin flip (0.50). At d = 5 and ε = 1e-4 the deepest circuit, Q^256 A, has 7.7e7 CX and needs two-qubit error near 9e-9 to succeed half the time; the hybrid needs ≤ 1e-9. Against the recorded 3.9e-3 median CZ error that is about 4e5 to 4e6 times cleaner, the "about a million times" in the pitch.

## Negative and blocked experiments

- **Irma forecast-track surge model (not shipped).** A parametric surge model (Holland wind profile plus steady wind setup, fitted on the 11 other hurricanes passing within 250 km of Key West since 1996) predicted 0.63 ft on Irma's best track against the 2.69 ft above MHHW observed at NOAA 8724580 (17:42 UTC, 10 Sep 2017; the observed peak was re-checked against the CO-OPS API). That is 2.06 ft too low, and the street flood rule starts mattering near 1 ft, so the per-street forecast-track counts were not shipped. The cause: none of the calibration storms had Irma's north-wind setup. The code and the real NHC a-deck archive are on the unmerged branch `worktree-agent-a5a20bc9099952862` (WIP commit 9d7fdab).
- **Realistic boundary did not hurt QMC (two drivers).** The hypothesis that a curved drainage boundary would raise QMC's exponent failed: Δα = −0.04 [−0.09, +0.02]. The five-driver resolution study later showed the penalty appears only on finer grids.
- **Nested expectation.** The model favours quantum by 3e3-1e5×, but every classical number is extrapolated 30-10⁴× past the largest budget and the classical designs were not tuned. Not a pitch number.
- **Importance sampling.** Useless for events with a ≈ 0.1-0.7, and worse than CMC+QMC at every depth in the rare-event study because its weights blow up in the tail.
- **Tide-alone split in the hybrid.** Measured before keeping it: the residual's sd was 0.14756 with and without it. Dropped.
- **Real hardware run.** Not attempted at full scale. The 10-QPU-minute toy demo (1-bit drivers) needs an IBM account; no repo file records a hardware run yet.

## Known tensions

**Hybrid break-even vs the measured epistemic crossover.** The hybrid README does not say the hybrid never breaks even up to 12 drivers. It says the hybrid wins on table reads only at ε ≲ 1e-6 to 4e-5 for d = 5-12, and never at d ≥ 13 because its control-variate grid grows exponentially. The measured crossover in `README_wins.md` (QAE ahead from d ≈ 7-8 at ε = 1e-4) is a different comparison, and the READMEs explain most of the gap:

1. *Which quantum method.* The break-even is for the hybrid, which pays for coarse CV cells (cells_5^((d−1)/4)) and four pilots. The epistemic crossover is plain ideal QAE, which pays neither.
2. *Measured vs extrapolated.* The break-even extrapolates d = 5 constants with a Novak-Heinrich rate α_c(d) = 1/(1/2 + r/(d−1)), pinned at the d = 5 count at ε = 1e-3. The epistemic study measured α directly.
3. *Which dimensions.* The break-even adds physical drivers to an r-smooth integrand. The epistemic study adds parameters that move the drainage threshold, keeping the integrand discontinuous.

The exponents agree well where they overlap: the model predicts α_c = 1.52 / 1.62 at d = 7 / 9 and the epistemic study measured 1.52 / 1.64. What remains open is the constant. No run has put the hybrid, plain QAE and CMC+QMC on the same epistemic model, so whether the hybrid's overhead alone explains the shift from ε ≈ 3e-5 to 1e-4 is not settled.

**How tight ε needs to be.** The project quotes three model-uncertainty spreads: ±0.03 (`README_hybrid.md`), ±0.016 (`README_wins.md`, GEV bootstrap at d = 13) and a ∈ [0.319, 0.376] (an earlier performance audit, from the older Gumbel-rain build where a = 0.325). All put useful precision near ε ≈ 1e-3 to 3e-3, where QAE does not beat CMC+QMC at any d.

**Two drainage calibrations.** At node N3210 the two-driver model gives a = 0.640 and the five-driver model 0.97 (0.967 in `README_hybrid.md`). Tide-only probabilities agree (0.217 vs 0.210). Scaling five-driver drainage 10.3× to match drops the city-wide flooded share from 56% to 19%, while the street ranking holds at the top (Spearman ρ = 0.91).

**Small exponent differences between runs.** CMC+QMC's d = 5 exponent is 1.31 (`README_wins.md`), 1.33 (`README_multidriver.md`), 1.36 (`README_hybrid.md`) and 1.32 (the performance audit). These are separate runs with different rule implementations and budgets; their CIs overlap.

## The honest pitch

"We measured QAE's quadratic advantage over Monte Carlo on a physically grounded Key West flood model, and found the one regime where it also beats the strongest classical estimator: once the model's own parameter uncertainty is integrated in, ideal QAE needs 4.3× fewer queries at 13 dimensions. That is a query count. Collecting it needs fault-tolerant hardware about a million times less noisy than today's and an oracle nobody has built, so we measured where the crossover is instead of claiming an advantage we don't have."
