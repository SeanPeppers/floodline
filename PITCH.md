# Floodline: pitch and video brief

Context for anyone making the pitch video or slides. Every number here is in the repo with a source; see [FINDINGS.md](FINDINGS.md), [NOVELTIES.md](NOVELTIES.md) and [CITATIONS.md](CITATIONS.md). If a number isn't on this page, don't put it in the video.

## One line

Floodline tells Key West which streets flood tonight and which roads to raise first, and it measures exactly where a quantum computer starts beating the best classical math on the same flood model.

## The problem (why anyone should care)

- Four recent Florida hurricanes (Irma 2017, Ian 2022, Helene 2024, Milton 2024) cost $13.5B in federal flood-insurance payouts on Florida claims alone (OpenFEMA NFIP).
- Irma: $290M in flood claims in Monroe County (the Keys) alone; 3 drownings in the Keys.
- Helene: $3.2B in flood claims in Pinellas County, where 12 people drowned in the surge.
- Milton: NOAA's hurricane center says a track shift of under 30 nautical miles north would have sent a significant surge into Tampa Bay.
- Key West floods from tide, rain, drainage, groundwater and sea-level rise at the same time ("compound flooding"), which is harder to model than any one of them.

Do not add these numbers together, and do not say Floodline or quantum computing would have saved this money. They show the stakes.

## What Floodline does today (the product)

- **Tonight:** pulls live NOAA tide and National Weather Service rain data and shows which Key West streets are likely to flood at the next high tide.
- **2050 planning view:** the same street map under NOAA's 2022 sea-level-rise scenarios.
- **Which road to raise first:** ranks 365 streets by expected flooded road-miles per year in 2050. Flagler Avenue is first: its low point has a 99% chance of flooding in a 2050 year. Raising it 1 ft costs about $7.0M-$17.5M per flood-year avoided (Monroe County's $9.6M/mile plan cost to the Twin Lakes pilot's $23.9M/mile).
- Built on the City of Key West's own 2024 Stormwater Master Plan rules, 110 years of the Key West tide gauge, and USGS street elevations.
- The classical engine answers in about 1 second on a laptop.

Who would use it: City of Key West and Monroe County public works and emergency management, road-raising and stormwater planners, residents deciding whether to move a car tonight. Who would pay: municipalities and counties planning resilience spending, insurers and reinsurers pricing compound-flood risk.

## The quantum result (the research)

- Quantum amplitude estimation needs 28-351× fewer samples than standard Monte Carlo on this flood model.
- It beats the smarter standard method (Sobol quasi-Monte Carlo) once flooding depends on about 4 or more factors.
- **Headline:** once the model's own uncertain settings are included (13 uncertain factors), ideal quantum needs **4.3× fewer queries** than the best classical method we know (95% CI 3.5-5.4×). The crossover is at about 7-8 factors.
- Real surge forecasting runs black-box simulators (NOAA P-Surge runs about 630 per advisory under a 1-hour deadline). There, quantum needs 1.6-3.3× fewer simulator runs. At study scale that is roughly $16k-$330k of computing per study, on hardware that doesn't exist yet.
- **Real hardware run:** we ran a 3-qubit version of the Key West tide-and-rain flood circuit on IBM's `ibm_fez` quantum computer (7 circuits, 4,000 shots each, 10 s of machine time). The up-and-down Grover signal that quantum amplitude estimation relies on shows up on the real chip, and noise flattens it as the circuits get deeper (peak 0.84 measured against 1.00 ideal).
- The hardware estimate of the flood probability is 0.074 against the model's exact 0.096: noise biases it, and plain sampling does better. This shows the method runs on a real device, not that it wins there.

Required honesty, in the video too:
- These are query counts on ideal, error-free quantum hardware. Today's hardware is about a million times too noisy.
- On today's computers, classical wins. The product runs on the classical engine.
- We don't estimate lives saved; no source links forecast speed to deaths.

## What's new

We found no prior published head-to-head of quantum amplitude estimation against quasi-Monte Carlo on a real risk model, and no prior quantum study of a real city's compound flood. Details in [NOVELTIES.md](NOVELTIES.md).

## Video brief (60-90 s)

Suggested beats:
1. **Hook (0-10 s):** storm surge and flooded streets; text: "$13.5B in Florida flood claims, four storms."
2. **The place (10-20 s):** Key West from above; "Floodline: compound-flood risk, street by street."
3. **The product (20-45 s):** screen recording of the real site: the hurricane-to-island scroll, Tonight's street map, the road-raising table with Flagler Ave at #1.
4. **The quantum result (45-70 s):** the site's "quantum advantage vs factors" chart; "4.3× fewer queries at 13 factors, on ideal hardware."
   Then a few seconds of screen recording of the site's hardware chart: "We ran it on a real IBM quantum computer. The signal is there; noise blurs it."
5. **Honest close (70-90 s):** "Classical runs the tool today. We measured exactly where quantum takes over." Team names, FGCU Quantum Hackathon 2026.

Rules for AI-generated footage (Higgsfield or similar):
- Use generated footage only for mood shots (storm, water, skyline). Label nothing generated as real footage of a specific storm or street.
- Every chart, map and number on screen must come from a screen recording of the real site or the repo, never generated.
- No fake news clips, logos of NOAA/FEMA/the City, or real people's likenesses.
- Don't show the quantum computer "saving" money or lives.
