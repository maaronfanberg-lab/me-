# Jamendo browser transport note

Pocket Spatial uses Jamendo JSONP for catalog discovery during the iPhone 6 development test. This avoids depending on modern fetch/CORS behavior for the API request itself while keeping the actual audio stream subject to a separate CORS/Web Audio capability test. The audio path is never inferred from the catalog request succeeding.
