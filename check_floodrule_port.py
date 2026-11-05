"""Cross-check the browser port of the street flood rule (web/js/floodrule.js) against multidriver.py.

  uv run python check_floodrule_port.py   # needs node on PATH

Draws random (coastal stage, groundwater, 24-h rain, 3-h burst, street elevation) cases over and
beyond the ranges the "Tonight" panel feeds the rule, plus hand-picked edge cases (no rain, tide
above the street, burst larger than the 24-h total), evaluates the flood margin in both languages
and reports the largest absolute difference. Exits non-zero above 1e-9 ft or on any flip of the
flood decision.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

import multidriver as md

ROOT = Path(__file__).resolve().parent
N_RANDOM = 200
TOL = 1e-9


def margin_py(drain: md.Drainage, c: float, g: float, p24: float, p3: float, z: float) -> float:
    """The flood test of multidriver.py's docstring, built only from its own functions."""
    a = (np.array(x) for x in (c, g, p24, p3))
    c_, g_, p24_, p3_ = a
    r = md.burst_runoff(p24_, p3_, g_, z)
    d = drain.capacity(c_, g_, z)
    pond = md.CATCH_RATIO * np.maximum(r - d, 0) / 12
    return float(max(c, g, z) - z + pond - md.TOL_FT)


def main() -> None:
    k = json.loads((ROOT / "web/assets/data/floodrule.json").read_text())
    drain = md.calibrate_drainage()
    if not (np.isclose(k["k_out"], drain.k_out) and np.isclose(k["k_well"], drain.k_well)):
        sys.exit("floodrule.json is stale: rerun `uv run python web_data.py`")
    rng = np.random.default_rng(7)
    mhhw = md.mhhw_navd_ft()
    cases = [
        [
            rng.uniform(-1.5, 4.0),
            mhhw + rng.uniform(0.0, 2.0),
            p24 := rng.uniform(0, 12) * rng.integers(0, 2),
            rng.uniform(0, 1.2) * p24,
            rng.uniform(-1.0, 8.0),
        ]
        for _ in range(N_RANDOM)
    ]
    cases += [[0.5, mhhw + 1.0, 0.0, 0.0, 1.0], [3.0, mhhw + 1.0, 2.0, 1.0, 1.0], [1.0, mhhw + 0.5, 5.99, 3.49, 4.0],
              [1.0, mhhw + 1.5, 3.0, 6.0, 2.0], [-1.0, mhhw + 0.5, 0.01, 0.01, 0.2]]  # fmt: skip
    py = [margin_py(drain, *map(float, cs)) for cs in cases]
    js_src = (
        "import { floodMargin } from './web/js/floodrule.js';"
        "import fs from 'node:fs';"
        "const k = JSON.parse(fs.readFileSync('web/assets/data/floodrule.json', 'utf8'));"
        "const cases = JSON.parse(fs.readFileSync(0, 'utf8'));"
        "console.log(JSON.stringify(cases.map((c) => floodMargin(k, ...c))));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", js_src], input=json.dumps(cases), cwd=ROOT,
                         capture_output=True, text=True, check=True)  # fmt: skip
    js = json.loads(out.stdout)
    diff = np.abs(np.array(js) - np.array(py))
    flips = int(sum((a >= 0) != (b >= 0) for a, b in zip(js, py)))
    floods = int(sum(b >= 0 for b in py))
    print(
        f"{len(cases)} cases ({floods} flood in Python): max |JS - Python| = {diff.max():.2e} ft, decision flips = {flips}"
    )
    if diff.max() > TOL or flips:
        sys.exit(1)


if __name__ == "__main__":
    main()
