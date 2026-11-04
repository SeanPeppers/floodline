# Asset credits

## Map imagery

The hero's "zoom from the Gulf of Mexico into Key West" is two static JPEG
stills — not a live map widget. Each is stitched from a small, fixed grid of
real OpenStreetMap raster tiles (`tile.openstreetmap.org`), fetched **once**
while building this page and committed as static assets
(`web/assets/map/region-wide.jpg`, `web/assets/map/keywest-close.jpg`). The
page itself never calls the tile server — every visitor's browser just loads
our own JPEGs from our own static hosting, the same way the rest of the site
works.

This, rather than a live Leaflet map doing the zoom at runtime, is a
deliberate reading of the OSM tile usage policy
(operations.osmfoundation.org/policies/tiles/): it explicitly flags
"headless automated panning or zooming to force rendering" of tiles nobody
is actually looking at as against policy. An animated fly-to on every page
load, for every visitor, is exactly that. A one-time, polite, rate-limited
fetch (25 tile requests total, one pass, proper `User-Agent`) followed by
serving our own static images at runtime is not.

- **Data**: &copy; OpenStreetMap contributors, Open Database License (ODbL)
  1.0 &mdash; openstreetmap.org/copyright. Attribution shown on-page (bottom-right
  of the hero), as the license requires.
- **Tiles**: standard OSM "Carto" raster tile style, `tile.openstreetmap.org`,
  fetched directly (no API key or account needed).
- **Region-wide still**: 3&times;3 grid of z6 tiles centered near 27&deg;N,
  84&deg;W (Gulf of Mexico / Florida peninsula).
- **Key West still**: 4&times;4 grid of z13 tiles centered on Key West,
  24.5565&deg;N, 81.78&deg;W.
- Both re-encoded as JPEG (quality 82) after stitching; no other edits.

## The flood water

The rising-water overlay on top of the map is a hand-drawn canvas 2D
animation (sine-wave bands, eased rise, idle bob) &mdash; our own code, not a
downloaded asset or model. It's a mood effect, not a to-scale flood model;
the actual quantified flood-stage numbers live in the Method section's chart
and tables, driven by real `results.json` data.

## Why not 3D models

An earlier version of this page used three downloaded CC0 Poly Haven glTF
models (a buoy, a sea marker, a lifebuoy) floating on a shader water plane.
User feedback was that the composition didn't land &mdash; disconnected
objects over a generic gradient, no sense of a real place. They've been
removed in favor of the map treatment above, which ties the page directly to
the actual place (Key West) the flood-risk number is about.

### Why not a Sketchfab "qubit sphere" either

The brief also floated an abstract qubit/network-sphere model, common on
Sketchfab under CC0/CC-BY. Sketchfab's download endpoint requires an
authenticated account for every model, including CC0 ones (confirmed: both
`sketchfab.com/i/models/.../download` and the `api.sketchfab.com/v3`
download endpoint return `401` with no session/token) &mdash; outside what this
build does unattended. Rather than hand-model a substitute (against the
brief's hard constraint on hand-authored 3D content), the Method section
uses a 2D canvas chart instead, animating the three estimators' real
convergence curves straight from `results.json`.

## Fonts

- **Space Grotesk** (headings) &mdash; Google Fonts, OFL.
- **Inter** (body) &mdash; Google Fonts, OFL.
