# Asset credits

## Map imagery

The hero's base layer is two static JPEG stills (not a live map widget),
stitched from a small, fixed grid of real OpenStreetMap raster tiles
(`tile.openstreetmap.org`), fetched **once** while building this page and
committed as static assets (`web/assets/map/region-wide.jpg`,
`web/assets/map/keywest-close.jpg`). The page itself never calls that tile
server — every visitor's browser just loads our own JPEGs from our own
static hosting, the same way the rest of the site works. See "Why not a
live raster map" below for why this exists at all now that a live layer
(next section) sits on top of it.

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

## Live map layer (MapLibre GL JS + OpenFreeMap)

`web/js/map.js` lazy-loads a live, interactive-capable map on top of the
stills above, after the browser goes idle (or after ~1.5s if
`requestIdleCallback` isn't available), so it never delays first paint. If
the library or the tile style fails to load for any reason (offline,
blocked, slow network), this script removes its own container and the
stills above are simply the whole picture — not a fallback bolted on after
a failure, the base state.

- **Library**: [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/)
  v4.7.1 via the `unpkg.com` CDN, no bundler, no build step. License:
  BSD-3-Clause (verified against the actual `LICENSE.txt` served from the
  CDN, not assumed from a marketing page). No account or API token — this
  is the open-source fork of Mapbox GL JS specifically because Mapbox GL JS
  itself requires a Mapbox account/token, which this project's hard
  constraints rule out.
- **Tiles/style**: [OpenFreeMap](https://openfreemap.org) "Liberty" vector
  style, `tiles.openfreemap.org`. OpenFreeMap itself is MIT-licensed; the
  underlying map data is still &copy; OpenStreetMap contributors (ODbL),
  same as the stills above. No account, API key, or usage cap — OpenFreeMap
  explicitly serves live, interactive, panning/zooming map clients (unlike
  raw `tile.openstreetmap.org`, whose usage policy is why the stills exist
  at all; see "Why not a live raster map" below).
- The live layer is mounted `interactive: false` (no drag-pan/scroll-zoom
  handlers attached) so it can't trap scroll/touch gestures on mobile — it
  reads as a living background, not a widget visitors have to fight with.
- A single pulsing marker over Key West is a plain DOM element styled with
  CSS `@keyframes` (`.map-pulse-marker`, in `css/style.css`) via
  MapLibre's `Marker` API — no extra marker/heatmap plugin.

### Why not a live raster map

The two stills exist because of a deliberate reading of the OSM raster-tile
usage policy (operations.osmfoundation.org/policies/tiles/): it explicitly
flags "headless automated panning or zooming to force rendering" of tiles
nobody is actually looking at as against policy — an animated fly-to on
every page load, for every visitor, against `tile.openstreetmap.org`
directly, is exactly that. A one-time, polite, rate-limited fetch (25 tile
requests total, one pass, proper `User-Agent`) followed by serving our own
static images at runtime is not, and remains the base layer. The live
MapLibre/OpenFreeMap layer above is a separate, compliant path: OpenFreeMap
is a dedicated vector-tile host meant for exactly this kind of live,
interactive client, not the raster endpoint the policy is warning about.

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

## Icons

The small icons in the "live readout" command panel (epsilon/queries/alpha
chips) are hand-drawn inline SVG paths, not a downloaded icon library —
three simple glyphs weren't worth a new CDN request and a license to track.

## Fonts

- **Space Grotesk** (headings) &mdash; Google Fonts, OFL.
- **Inter** (body) &mdash; Google Fonts, OFL.
- **JetBrains Mono** (data/metrics/timestamps/tables) &mdash; Google Fonts,
  OFL. Added as extra weights on the same existing Google Fonts request
  (one URL, no new connection).
