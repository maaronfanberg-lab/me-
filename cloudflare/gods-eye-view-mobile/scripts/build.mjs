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

// Upstream currently hard-stops when GOOGLE_MAPS_API_KEY is absent even though
// its MapStackController already supports a keyless OSM + Re:Earth globe. For
// this privacy-oriented mobile build, remove that hard stop and start directly
// in the existing OSM stack. Google 3D is simply unavailable rather than fatal.
const mainPath = join(work, 'src', 'main.js');
let main = readFileSync(mainPath, 'utf8');
main = main.replace(
`    // Set Google Maps API key for 3D Tiles
    const googleApiKey = import.meta.env.GOOGLE_MAPS_API_KEY;
    if (!googleApiKey) {
      throw new Error('GOOGLE_MAPS_API_KEY not found. Set it as an environment variable.');
    }
    Cesium.GoogleMaps.defaultApiKey = googleApiKey;

    // Expose API key globally for geocoding in locations.js
    window.__GOOGLE_MAPS_API_KEY__ = googleApiKey;`,
`    // Privacy-first mobile build: Google is optional. The upstream map stack
    // already has a keyless OSM + Re:Earth terrain mode, so absence of a Google
    // credential must not abort initialization.
    const googleApiKey = String(import.meta.env.GOOGLE_MAPS_API_KEY || '').trim();
    if (googleApiKey) {
      Cesium.GoogleMaps.defaultApiKey = googleApiKey;
      window.__GOOGLE_MAPS_API_KEY__ = googleApiKey;
    }`
);
main = main.replace(
`    loaderStatus.textContent = 'Loading Google 3D Tiles...';
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
    }`,
`    let tileset = null;
    if (googleApiKey) {
      loaderStatus.textContent = 'Loading Google 3D Tiles...';
      try {
        tileset = await Cesium.createGooglePhotorealistic3DTileset({
          onlyUsingWithGoogleGeocoder: true,
        });
        viewer.scene.primitives.add(tileset);
        viewer.scene.globe.show = false;
      } catch (tileError) {
        console.warn('[Init] Google 3D Tiles unavailable, using keyless globe:', tileError);
        viewer.scene.globe.show = true;
      }
    } else {
      loaderStatus.textContent = 'Loading keyless OpenStreetMap globe...';
      viewer.scene.globe.show = true;
    }`
);
if (main.includes("throw new Error('GOOGLE_MAPS_API_KEY not found")) {
  throw new Error('Upstream patch failed: Google hard-stop is still present');
}
writeFileSync(mainPath, main);

// Mobile live-flight bridge. The upstream browser expects an OpenSky-shaped
// snapshot from /api/opensky. GitHub Pages has no server proxy, and OpenSky's
// current terms require a separate agreement for operational REST use. ADSB.lol
// exposes an open ODbL API, so the phone build fetches the 250 nm view around
// the camera directly and normalizes each aircraft into the state-vector shape
// the existing renderer already understands.
const flightsPath = join(work, 'src', 'data', 'flights.js');
let flights = readFileSync(flightsPath, 'utf8');
flights = flights.replace(
  "const API_URL = '/api/opensky';",
  "const API_URL = 'https://api.adsb.lol/v2';"
);
flights = flights.replace(
`function _flightApiUrl(viewer) {
  const cartographic = viewer?.camera?.positionCartographic;
  if (!cartographic) return API_URL;
  const latitude = Cesium.Math.toDegrees(cartographic.latitude);
  const longitude = Cesium.Math.toDegrees(cartographic.longitude);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return API_URL;
  const params = new URLSearchParams({
    lat: latitude.toFixed(4),
    lon: longitude.toFixed(4),
  });
  return \`${API_URL}?\${params}\`;
}`,
`function _flightApiUrl(viewer) {
  const cartographic = viewer?.camera?.positionCartographic;
  const latitude = cartographic ? Cesium.Math.toDegrees(cartographic.latitude) : 37.7749;
  const longitude = cartographic ? Cesium.Math.toDegrees(cartographic.longitude) : -122.4194;
  const lat = Number.isFinite(latitude) ? latitude : 37.7749;
  const lon = Number.isFinite(longitude) ? longitude : -122.4194;
  return \`${API_URL}/point/\${lat.toFixed(4)}/\${lon.toFixed(4)}/250\`;
}

function _adsbLolToStateVectorSnapshot(data) {
  if (!data || !Array.isArray(data.ac)) return data;
  const nowSec = Date.now() / 1000;
  const ftToM = (v) => Number.isFinite(Number(v)) ? Number(v) * 0.3048 : null;
  const fpmToMps = (v) => Number.isFinite(Number(v)) ? Number(v) * 0.00508 : null;
  const ktToMps = (v) => Number.isFinite(Number(v)) ? Number(v) * 0.514444 : null;
  const states = [];
  for (const ac of data.ac) {
    const lat = Number(ac?.lat);
    const lon = Number(ac?.lon);
    const hex = String(ac?.hex || '').trim().toLowerCase().replace(/^~/, '');
    if (!hex || !Number.isFinite(lat) || !Number.isFinite(lon)) continue;
    const onGround = ac?.alt_baro === 'ground';
    const baroAlt = onGround ? 0 : ftToM(ac?.alt_baro);
    const geomAlt = ftToM(ac?.alt_geom);
    const seenPos = Number(ac?.seen_pos);
    const seen = Number(ac?.seen);
    const timePosition = Number.isFinite(seenPos) ? nowSec - Math.max(0, seenPos) : nowSec;
    const lastContact = Number.isFinite(seen) ? nowSec - Math.max(0, seen) : timePosition;
    const state = new Array(18).fill(null);
    state[0] = hex;
    state[1] = String(ac?.flight || ac?.r || '').trim();
    state[2] = '';
    state[3] = timePosition;
    state[4] = lastContact;
    state[5] = lon;
    state[6] = lat;
    state[7] = baroAlt;
    state[8] = onGround;
    state[9] = ktToMps(ac?.gs);
    state[10] = Number.isFinite(Number(ac?.track)) ? Number(ac.track) : null;
    state[11] = fpmToMps(ac?.baro_rate ?? ac?.geom_rate);
    state[13] = geomAlt;
    states.push(state);
  }
  return { time: Math.floor(nowSec), states };
}`
);
flights = flights.replace(
  '      const data = await response.json();\n      updateSignal.throwIfAborted();',
  '      let data = await response.json();\n      updateSignal.throwIfAborted();\n      data = _adsbLolToStateVectorSnapshot(data);'
);
flights = flights.replaceAll("'OpenSky Network'", "'ADSB.lol'");
flights = flights.replaceAll('OpenSky Network', 'ADSB.lol');
if (!flights.includes('_adsbLolToStateVectorSnapshot')) {
  throw new Error('Upstream patch failed: ADSB.lol bridge was not installed');
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
html = html.replace('</head>', `  <meta name="apple-mobile-web-app-capable" content="yes">\n  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n  <meta name="theme-color" content="#05070a">\n  <link rel="manifest" href="/manifest.webmanifest">\n  <link rel="stylesheet" href="/mobile.css">\n</head>`);
html = html.replace('</body>', `  <script>if ('serviceWorker' in navigator) addEventListener('load',()=>navigator.serviceWorker.register('/sw.js').catch(()=>{}));</script>\n</body>`);
writeFileSync(indexPath, html);

writeFileSync(join(out, '_headers'), `/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Permissions-Policy: geolocation=(self), microphone=(self)\n\n/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n`);

console.log('Keyless mobile bundle ready in dist/ with ADSB.lol Live Flights');
