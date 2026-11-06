# Floodline: 10-minute presentation script

About 1,350 spoken words, roughly 10 minutes at a relaxed pace. Bracketed lines are cues for what is on screen; the names in them are the links in the site's top bar (Results, Savings, Tool, Tonight, Verdict, Methods), so the presenter can jump straight there. Every number is sourced in the table at the end; if a number is not in that table, don't say it.

## 1. The pitch (about 1.5 min)

[Top of the page: the globe and the Floodline title card]

Key West floods from five things at once: the tide, heavy rain, short bursts of rain, rising seas and groundwater. City planners and emergency managers have to decide which streets will go under, and which roads are worth raising, before the water arrives.

Floodline answers that. It's a flood-risk tool for every street in Key West, built on 110 years of the city's tide gauge, NOAA elevation data and the city's own 2024 Stormwater Master Plan. It ranks roads by how often they'll flood and what it costs to raise them. Flagler Avenue comes out first: its low point has a 99% chance of flooding in a 2050 year, and raising it a foot costs about $7 to $17.5 million for each flood-year it prevents.

[Click Tool: the road table with Flagler Avenue at #1]

The people who would pay for this are cities and counties planning resilience spending, and the insurers who price flood risk.

## 2. Why it matters (about 1 min)

[Click Savings: the giant $13.5B]

Four recent Florida hurricanes, Irma, Ian, Helene and Milton, cost $13.5 billion in federal flood insurance claims in Florida alone. Irma's flood claims in the Keys came to $290 million. Helene's in Pinellas County came to $3.2 billion, and 12 people drowned there in the surge.

[Click Tool: the giant "3 in 4"]

The risk isn't rare. From the gauge record, the sea at Key West passes major flood stage about one year in 22. Over a 30-year mortgage, that is a 3 in 4 chance of it happening at least once.

## 3. Why we used a quantum computer (about 1.5 min)

Every one of these flood odds comes from running a model thousands of times with random storms and counting how often the street floods. That's Monte Carlo, and it's slow: to cut the error in half you need four times as many runs.

[Click Savings, scroll to "Real flood models are black boxes" and the giant 3.3×]

Real surge forecasting is that problem at full scale. For each advisory, NOAA runs about 630 surge simulations and has an hour to get them out. A full flood study runs hundreds of storms, and a single high-resolution ADCIRC storm-surge run takes about 2,000 core-hours.

[Same section: the "Two days of warning" paragraph]

Here's the math for a storm with about two days of warning. A 446-storm study at 2,000 core-hours each is 892,000 core-hours. On a 20,000-core allocation, that's 44.6 hours, most of the two days gone. Our measured black-box ratio is 3.3 times fewer simulator runs. That would cut the work to 270,000 core-hours, the equivalent of 13.5 hours of that cluster; with the middle ratio, 2.3 times, it's 19.4 hours. Those are counts of simulator runs on a future error-free quantum computer, not a stopwatch, and I'll come back to what that means for real time. In compute dollars, the runs saved come to $16,000 to $42,000 for a study that size, depending on how big each run is, and $177,000 to $330,000 for a Louisiana-size suite of 7,712 runs.

Quantum amplitude estimation is a quantum algorithm with a proven speedup for exactly this kind of counting. So we asked a narrow question: on a real city's flood model, where does it actually beat the best classical method?

## 4. What we found (about 2 min)

[Click Results: press Play on the race]

This race runs live in the browser. Monte Carlo throws random storms; quantum amplitude estimation homes in on the same answer, and the box under the race says how many tries each one needed this time. Each run is a little different. Averaged over 500 trials, getting within 0.001 of the true flood odds takes Monte Carlo about 245,000 runs and quantum about 8,800, which is 28 times fewer. At ten times that precision the gap grows to about 351 times.

But plain Monte Carlo is an easy opponent. The best classical method we tested combines conditional sampling with Sobol sequences, and with only the five physical flood drivers it beats quantum every time.

[Scroll up to the giant 4.3×, then down to chart 1]

Then we added the model's own uncertain settings, the soil, drainage and rainfall-curve parameters, for 13 uncertain factors in total. That's where quantum wins: 96,600 queries against 416,000 for the best classical method, 4.3 times fewer, with a 95% confidence interval of 3.5 to 5.4. It ties at 7 factors and wins from 9 on.

[Chart 2: the black-box simulator]

Real surge models are black boxes, so the classical method has to search for each threshold, about 6 runs per sample. There, quantum needs 1.6 to 3.3 times fewer simulator runs at just five drivers.

## 5. What's new (about 1 min)

We found no prior published head-to-head of quantum amplitude estimation against quasi-Monte Carlo on a real risk model, and no prior quantum study of a real city's compound flooding. The crossover point, where quantum starts to win as uncertainty grows, is a result we measured, not one we assumed.

[Results: "Where classical still wins"]

We also published our losses. The site has a table of every case where classical wins, and the repo lists every approach that failed.

## 6. Real hardware, and the honest limits (about 1.5 min)

[Results: "It runs on a real quantum computer" chart]

We ran a three-qubit version of the Key West flood circuit on IBM's ibm_fez: seven circuits, 4,000 shots each, 10 seconds of machine time. The up-and-down signal the algorithm depends on shows up on the real chip, and noise flattens it as the circuits get deeper. The peak reached 0.84 where the ideal is 1.00.

The hardware's estimate of the flood probability was 0.074; the exact answer is 0.096. Plain sampling does better today.

So, the limits. Every win we've shown counts queries on an ideal, error-free quantum computer. Today's chips need to be about a million times cleaner. Even then, quantum runs its steps one after another, while classical runs spread across many computers at once, so on wall-clock time classical still wins today. The product runs on the classical engine. We don't claim lives saved, because no source links forecast speed to deaths.

## 7. How the site is built (about 1.5 min)

[Scroll back to the top and through the Irma story]

The site is plain HTML, CSS and JavaScript on Vercel, with no framework. The opening is a Three.js scene: NASA satellite imagery of Irma, the National Hurricane Center's track, then Key West in 3D from NOAA elevation data and a USDA aerial photo. As you scroll, the water rises through the official flood stages and 6,054 road points from OpenStreetMap light up as they go under.

[Click Tonight]

The Tonight panel pulls live NOAA tide predictions and the National Weather Service rain forecast and shows which streets could flood at the next high tides. It's labelled a research prototype, not a warning.

The charts are drawn by our own code with no charting library, and the race runs both methods live in your browser. We profiled the scroll and cut the worst stutter on a slowed-down phone from about 575 milliseconds to about 75. Every push runs automated accessibility checks, axe-core and Lighthouse, and the site scores 100 on accessibility.

## 8. Close (about 30 s)

[Click Verdict]

Classical runs the tool today. What we measured is the point where quantum takes over: once a flood model carries enough uncertainty, about 9 factors or more, an error-free quantum computer needs several times fewer runs than the best classical method we know. Floodline is ready for the day that hardware exists.

## Numbers and where they come from

| Claim in the script | Value | Source |
|---|---|---|
| Flagler Ave | 99% flood chance in 2050; $7.0M to $17.5M per flood-year avoided | `road_priority.json`, site Tool section |
| Four storms, NFIP Florida | $13.5B (Irma $986M, Ian $4.87B, Helene $6.49B, Milton $1.21B) | OpenFEMA NfipClaims v3, `web/CREDITS.md` |
| Irma, Monroe County / Helene, Pinellas | $290M / $3.2B, 12 surge drownings | OpenFEMA; NHC Tropical Cyclone Reports |
| Major flood stage | about 1 year in 22 (p = 0.0458) | `copula.py` tide model, 110 years of gauge 8724580 |
| 3 in 4 over 30 years | 1 - (1 - 0.0458)^30 = 0.755, years assumed independent | computed |
| P-Surge | about 630 SLOSH runs per advisory, due within 1 hour | NOAA SLOSH MPI paper (AMS 2020), `CITATIONS.md` |
| ADCIRC run cost | about 2,000 core-hours | arXiv 1909.01836 |
| 446-storm study | FEMA-style Louisiana study | Louisiana Coastal Master Plan slides |
| 44.6 h vs 13.5 h / 19.4 h | 892,000 core-hours, 20,000-core allocation (our assumption), divided by 3.3 or 2.3 | computed |
| $15.8k to $42.0k; $177k to $330k per study | runs saved × CPU-hours per run × $0.0473; the $42.0k high case uses the 2,855 core-hour Hurricane Ike run (arXiv 2310.06199) with r = 3.3 | site Savings section |
| 245,000 vs 8,800 runs, 28× | ε = 1e-3, two-driver street model, 500 trials per point | `results.json` matched_eps |
| 351× | ε = 1e-4, QAE extrapolated | `results.json` |
| 13 factors | QAE 96,595 vs CMC+QMC 416,364 queries, 4.31× [3.51, 5.38]; tie at d = 7 | `results_wins.json` dim 13 |
| Black box | 1.6 / 2.3 / 3.3× at ε = 1e-3 / 3e-4 / 1e-4, 6-run bisection | `results_multi.json` |
| Hardware | ibm_fez, 7 circuits, 4,000 shots, 10 s; peak 0.84 vs 1.00; 0.074 vs 0.096 | `results_hw.json` |
| A million times cleaner | gate error needed about 1e-8 to 1e-9 vs about 4e-3 today | FINDINGS.md |
| Scroll stutter | worst frame 575 ± 114 ms to about 75 ms (phone, 4× CPU slowdown) | perf benchmark, perf-scroll branch |

The 20,000-core allocation is an illustration, not a real agency's machine. The 13.5-hour and 19.4-hour figures assume our five-driver black-box ratios carry over to ADCIRC, which we have not tested, and they count simulator runs, not quantum wall-clock time.
