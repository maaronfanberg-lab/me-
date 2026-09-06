# Jamendo CI note

The Pocket Spatial iPhone 6 workflow intentionally tests both deterministic code behavior and current network behavior. Deterministic tests validate the exact license-filter and request-builder functions from `apps/pocket-spatial-jamendo.js`. The live smoke test separately verifies that Jamendo's published test client still returns derivative-permitting tracks, that an `audio` stream yields bytes, and that the returned stream permits CORS from the Pocket Spatial GitHub Pages origin.

A CI pass does not prove iPhone 6 Web Audio PCM access. That remains a physical-device runtime test performed inside the page with the analyser probe. CI proves only the server/API/CORS prerequisites and browser-code compatibility.
