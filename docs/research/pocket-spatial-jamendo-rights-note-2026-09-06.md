# Jamendo rights note for Pocket Spatial testing

Jamendo's tracks API exposes both a stream URL (`audio`) and the track's Creative Commons license URL (`license_ccurl`). Pocket Spatial's development path requests `ccnd=false` and also performs a local license check before enabling the spatial test. Tracks with missing license metadata or a NoDerivatives license are rejected.

This is a live-processing test, not a download/export feature. Pocket Spatial does not expose Jamendo's download URL, does not record the stream, and does not persist transformed audio. If the project later adds recording, exporting, redistribution, or commercial use, that is a separate rights review because attribution, ShareAlike, and NonCommercial conditions may become relevant even when a track permits derivatives.
