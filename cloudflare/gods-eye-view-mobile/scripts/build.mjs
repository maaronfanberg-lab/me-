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
main = main.replace(
`    // Set Google Maps API key for 3D Tiles
    const googleApiKey = import.meta.env.GOOGLE_MAPS_API_KEY;
    if (!googleApiKey) {
      throw new Error('GOOGLE_MAPS_API_KEY not found. Set it as an environment variable.');
    }
    Cesium.GoogleMaps.defaultApiKey = googleApiKey;

    // Expose API key globally for geocoding in locations.js
    window.__GOOGLE_MAPS_API_KEY__ = googleApiKey;`,
`    const googleApiKey = String(import.meta.env.GOOGLE_MAPS_API_KEY || '').trim();
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
    }`
);
if (main.includes("throw new Error('GOOGLE_MAPS_API_KEY not found")) throw new Error('Google hard-stop patch failed');
writeFileSync(mainPath, main);

const flightsPath = join(work, 'src', 'data', 'flights.js');
let flights = readFileSync(flightsPath, 'utf8');
flights = flights.replace("const API_URL = '/api/opensky';", "const API_URL = 'https://api.adsb.lol/v2';");
const functionStart = flights.indexOf('function _flightApiUrl(viewer) {');
if (functionStart < 0) throw new Error('Could not locate _flightApiUrl');
const nextFunction = flights.indexOf('\nfunction ', functionStart + 20);
if (nextFunction < 0) throw new Error('Could not locate end of _flightApiUrl');
const bridge = readFileSync(join(root, 'scripts', 'adsb-flight-bridge.txt'), 'utf8');
flights = flights.slice(0, functionStart) + bridge + '\n' + flights.slice(nextFunction + 1);
flights = flights.replace(
  '      const data = await response.json();\n      updateSignal.throwIfAborted();',
  '      let data = await response.json();\n      updateSignal.throwIfAborted();\n      data = _adsbLolToStateVectorSnapshot(data);'
);
flights = flights.replaceAll("'OpenSky Network'", "'ADSB.lol'");
flights = flights.replaceAll('OpenSky Network', 'ADSB.lol');
if (!flights.includes('_adsbLolToStateVectorSnapshot')) throw new Error('ADSB bridge patch failed');
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
