# 3D asset credits

None of the 3D models used in this site were modeled by hand for this project.
All are real, freely-licensed model files from other creators, downloaded and
only re-compressed (resized textures, recompressed JPEGs — same geometry and
same artwork) for web performance.

## Models

| Asset | Source | Author | License | Used for |
|---|---|---|---|---|
| Ocean Buoy | [Poly Haven](https://polyhaven.com/a/ocean_buoy) | Mateusz Sadek | CC0 1.0 | Hero section — storm/flood hazard marker |
| Lateral Sea Marker | [Poly Haven](https://polyhaven.com/a/lateral_sea_marker) | Kuutti Siitonen (additional texture wear: James Ray Cock) | CC0 1.0 | Problem section — tide/navigation marker |
| Lifebuoy | [Poly Haven](https://polyhaven.com/a/lifebuoy) | Hank Kaamura | CC0 1.0 | Verdict section — safety/risk accent |

All three ship from Poly Haven at polyhaven.com under the CC0 1.0 Universal
dedication (https://creativecommons.org/publicdomain/zero/1.0/) — public
domain, no attribution legally required. Credited above anyway.

Downloaded at the "1k" texture resolution directly from Poly Haven's file API
(`api.polyhaven.com`), then the JPEG textures were resized to 512x512 and
recompressed (mozjpeg, quality 72) with `sharp` to cut page weight; geometry
was not modified.

## Why not a Sketchfab "qubit sphere"

The brief suggested an abstract qubit/network-sphere model (common on
Sketchfab under CC0/CC-BY). Sketchfab's download endpoint requires an
authenticated account for every model, including CC0 ones (confirmed: both
`sketchfab.com/i/models/.../download` and the `api.sketchfab.com/v3` download
endpoint return `401` with no session/token). Creating an account to clear
that gate is outside what this build does unattended.

Rather than hand-model a substitute sphere (explicitly against the brief's
hard constraint — no hand-authored 3D geometry as content), the quantum/method
section uses a 2D canvas chart instead of a 3D object: it animates the three
estimators' real convergence curves straight from `results.json` (the same
numbers in the README's scaling table), which is both compliant and more
honest than an invented decorative sphere. The only 3D content on the page is
the three real downloaded models credited above, placed on a shader-animated
water plane (the plane and its motion are our own code — an effect/surface,
not modeled "content" — consistent with the brief's explicit allowance for
hand-written shaders, particles, and scene composition).

## Fonts

- **Space Grotesk** (headings) — Google Fonts, OFL.
- **Inter** (body) — Google Fonts, OFL.

## Water

The ocean surface is a plain procedural plane with a GLSL wave-displacement
and Fresnel shader (our own code, not a downloaded asset) — shaders and
procedural motion are explicitly allowed by the brief; only pre-made content
geometry is restricted to sourced files.
