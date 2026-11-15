import { execFileSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
const root = process.cwd();
const work = join(root, '.gev-upstream');
const out = join(root, 'dist');
const upstream = 'https://github.com/bilawalsidhu/gods-eye-view.git';
rmSync(work, { recursive: true, force: true });
rmSync(out, { recursive: true, force: true });
execFileSync('git', ['clone', '--depth=1', upstream, work], { stdio: 'inherit' });

const mainPath = join(work, 'src', 'main.js');
let main = readFileSync(mainPath, 'utf8');
main = main.replace(`    // Set Google Maps API key for 3D Tiles
    const googleApiKey = import.meta.env.GOOGLE_MAPS_API_KEY;
    if (!googleApiKey) {
      throw new Error('GOOGLE_MAPS_API_KEY not found. Set it as an environment variable.');
    }
    Cesium.GoogleMaps.defaultApiKey = googleApiKey;

    // Expose API key globally for geocoding in locations.js
    window.__GOOGLE_MAPS_API_KEY__ = googleApiKey;`, `    const googleApiKey = String(import.meta.env.GOOGLE_MAPS_API_KEY || '').trim();
    if (googleApiKey) {
      Cesium.GoogleMaps.defaultApiKey = googleApiKey;
      window.__GOOGLE_MAPS_API_KEY__ = googleApiKey;
    }`);
main = main.replace(`    loaderStatus.textContent = 'Loading Google 3D Tiles...';
    let tileset = null;
    try {
      // Load Google Photorealistic 3D Tiles
      tileset = await Cesium.createGooglePhotorealistic3DTileset({
        onlyUsingWithGoogleGeocoder: true,
      });
      viewer.scene.primitives.add(tileset);
      // NOTE: Cesium World Terrain intentionally disabled — conflicts with Google 3D Tiles at high zoom.
      // Google Photorealistic 3D Tiles provide their own terrain/elevation.
      viewer.scene.globe.show = false;
    } catch (tileError) {
      console.warn('[Init] Google 3D Tiles unavailable, falling back to Cesium globe:', tileError);
      const tileErrorDetail = describeError(tileError);
      loaderStatus.textContent = \`Google 3D Tiles unavailable (\${tileErrorDetail}). Continuing in fallback mode...\`;
      // Keep Cesium globe visible as fallback instead of aborting the app.
      viewer.scene.globe.show = true;
    }`, `    let tileset = null;
    if (googleApiKey) {
      loaderStatus.textContent = 'Loading Google 3D Tiles...';
      try {
        tileset = await Cesium.createGooglePhotorealistic3DTileset({ onlyUsingWithGoogleGeocoder: true });
        viewer.scene.primitives.add(tileset);
        viewer.scene.globe.show = false;
      } catch (tileError) {
        console.warn('[Init] Google 3D Tiles unavailable, using keyless globe:', tileError);
        viewer.scene.globe.show = true;
      }
    } else {
      loaderStatus.textContent = 'Loading keyless OpenStreetMap globe...';
      viewer.scene.globe.show = true;
    }`);
if (main.includes("throw new Error('GOOGLE_MAPS_API_KEY not found")) throw new Error('Google hard-stop patch failed');
writeFileSync(mainPath, main);

// The upstream scope mask is deliberately cinematic. Earth Signal boots as an
// ordinary full-frame globe instead, while leaving the upstream feature intact
// behind the wrapper for compatibility with the rest of the application.
const scopePath = join(work, 'src', 'scopeMask.js');
let scope = readFileSync(scopePath, 'utf8');
const scopeDefault = 'let _enabled = true;';
if (!scope.includes(scopeDefault)) throw new Error('Could not locate scope-mask default');
scope = scope.replace(scopeDefault, 'let _enabled = false;');
writeFileSync(scopePath, scope);

const sharePath = join(work, 'src', 'sharelink.js');
let share = readFileSync(sharePath, 'utf8');
const shareScopeDefault = 'this._scopeEnabled = true;';
if (!share.includes(shareScopeDefault)) throw new Error('Could not locate share-link scope default');
share = share.replace(shareScopeDefault, 'this._scopeEnabled = false;');
writeFileSync(sharePath, share);

// Earth Signal's public aircraft feed is ADSB.lol itself, not a degraded
// substitute for OpenSky. Keep upstream's generic fallback logic, but remove
// the source-name special case that would falsely label this real feed FALLBACK.
const managerPath = join(work, 'src', 'data', 'manager.js');
let manager = readFileSync(managerPath, 'utf8');
const adsbFallbackClause = "\n    || (!hasExplicitFallback && /\\badsb\\.lol\\b/i.test(source))";
if (!manager.includes(adsbFallbackClause)) throw new Error('Could not locate ADSB.lol fallback classification');
manager = manager.replace(adsbFallbackClause, '');
writeFileSync(managerPath, manager);

// Require the upstream earthquake layer to remain wired to the official USGS
// public GeoJSON feed. If upstream changes this seam, fail the build rather
// than silently shipping an unverified replacement.
const earthquakesPath = join(work, 'src', 'data', 'earthquakes.js');
const earthquakes = readFileSync(earthquakesPath, 'utf8');
const usgsEarthquakeFeed = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson';
if (!earthquakes.includes(usgsEarthquakeFeed) || !earthquakes.includes('updateInterval: 60000')) {
  throw new Error('Earth Signal requires the official USGS 24h earthquake feed at a 60s refresh interval');
}

// Upstream street traffic deliberately simulates moving vehicles whenever its
// TomTom server proxy is absent. This wrapper is static Pages and does not ship
// that private proxy, so replace the module with an inert UNAVAILABLE layer.
// No synthetic vehicles are rendered or exposed to detection/voice surfaces.
const trafficPath = join(work, 'src', 'data', 'traffic.js');
const trafficDisabled = readFileSync(join(root, 'scripts', 'traffic-disabled.txt'), 'utf8');
if (!trafficDisabled.includes("status: 'unavailable'") || !trafficDisabled.includes('getDetectableObjects() { return []; }')) {
  throw new Error('Earth Signal traffic stub failed live-only invariant');
}
writeFileSync(trafficPath, trafficDisabled);

const flightsPath = join(work, 'src', 'data', 'flights.js');
let flights = readFileSync(flightsPath, 'utf8');
const oldApi = "const API_URL = '/api/opensky';";
if (!flights.includes(oldApi)) throw new Error('Could not locate flight API constant');
flights = flights.replace(oldApi, "const API_URL = 'https://api.adsb.lol/v2';");
const oldFnStart = flights.indexOf('function _flightApiUrl(viewer) {');
if (oldFnStart < 0) throw new Error('Could not locate original flight URL function');
const oldFnEndMarker = '\n}\n\n// ---------------------------------------------------------------------------\n// Click-to-track state';
const oldFnEnd = flights.indexOf(oldFnEndMarker, oldFnStart);
if (oldFnEnd < 0) throw new Error('Could not locate end of original flight URL function');
const bridge = readFileSync(join(root, 'scripts', 'adsb-flight-bridge.txt'), 'utf8');
flights = flights.slice(0, oldFnStart) + bridge + '\n' + flights.slice(oldFnEnd + 2);
const jsonMarker = '      const data = await response.json();\n      updateSignal.throwIfAborted();\n      if (!data || !Array.isArray(data.states)) {';
if (!flights.includes(jsonMarker)) throw new Error('Could not locate flight JSON seam');
flights = flights.replace(jsonMarker, '      let data = await response.json();\n      updateSignal.throwIfAborted();\n      data = _adsbLolToStateVectorSnapshot(data);\n      if (!data || !Array.isArray(data.states)) {');
flights = flights.replaceAll("'OpenSky Network'", "'ADSB.lol'");
flights = flights.replaceAll('OpenSky Network', 'ADSB.lol');
if (!flights.includes('_adsbLolToStateVectorSnapshot') || !flights.includes("const API_URL = 'https://api.adsb.lol/v2';")) {
  throw new Error('ADSB.lol live-flight bridge patch failed');
}
writeFileSync(flightsPath, flights);

execFileSync('npm', ['ci'], { cwd: work, stdio: 'inherit', env: process.env });
execFileSync('npm', ['run', 'build'], { cwd: work, stdio: 'inherit', env: process.env });
const upstreamDist = join(work, 'dist');
if (!existsSync(upstreamDist)) throw new Error('Upstream build did not produce dist/');
mkdirSync(out, { recursive: true });
cpSync(upstreamDist, out, { recursive: true });
cpSync(join(root, 'mobile.css'), join(out, 'mobile.css'));
cpSync(join(root, 'manifest.webmanifest'), join(out, 'manifest.webmanifest'));
cpSync(join(root, 'sw.js'), join(out, 'sw.js'));

const indexPath = join(out, 'index.html');
let html = readFileSync(indexPath, 'utf8');
const oldTitle = `<title>God's Eye View</title>`;
const oldBrand = `GOD'S EYE <span class="title-accent">VIEW</span>`;
const oldSubtitle = `<p class="subtitle">NO PLACE LEFT BEHIND</p>`;
if (!html.includes(oldTitle) || !html.includes(oldBrand) || !html.includes(oldSubtitle)) {
  throw new Error('Could not locate upstream branding seams');
}
html = html.replace(oldTitle, '<title>Earth Signal</title>');
html = html.replace(oldBrand, 'EARTH <span class="title-accent">SIGNAL</span>');
html = html.replace(oldSubtitle, '<p class="subtitle">PUBLIC DATA · SOURCE-VERIFIED</p>');
html = html.replace('</head>', `  <meta name="apple-mobile-web-app-capable" content="yes">\n  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n  <meta name="theme-color" content="#080b0e">\n  <link rel="manifest" href="/manifest.webmanifest">\n  <link rel="stylesheet" href="/mobile.css">\n</head>`);
const earthSignalHeader = `  <header id="earth-signal-header" aria-label="Earth Signal">\n    <div class="earth-signal-copy">\n      <strong>Earth Signal</strong>\n      <small>public world data · current conditions</small>\n    </div>\n    <span class="earth-signal-live">USGS · ADSB.lol</span>\n  </header>\n`;
html = html.replace('<body>', `<body>\n${earthSignalHeader}`);
html = html.replace('</body>', `  <script>if ('serviceWorker' in navigator) addEventListener('load',()=>navigator.serviceWorker.register('/sw.js').catch(()=>{}));</script>\n</body>`);
writeFileSync(indexPath, html);

const manifestPath = join(out, 'manifest.webmanifest');
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
manifest.name = 'Earth Signal';
manifest.short_name = 'Earth Signal';
manifest.description = 'Source-verified public Earth data and current conditions on one globe.';
manifest.theme_color = '#080b0e';
manifest.background_color = '#080b0e';
manifest.start_url = './';
manifest.scope = './';
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');

writeFileSync(join(out, '_headers'), `/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Permissions-Policy: geolocation=(self), microphone=(self)\n\n/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n`);
console.log('Earth Signal bundle ready: official USGS earthquakes + public ADSB.lol aircraft; synthetic street traffic disabled');
