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

console.log('Cloudflare Pages bundle ready in dist/');
