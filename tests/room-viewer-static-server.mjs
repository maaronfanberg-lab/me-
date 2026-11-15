import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = process.cwd();
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

function safePath(urlPath) {
  let clean = decodeURIComponent((urlPath || '/').split('?')[0]);
  if (clean.endsWith('/')) clean += 'index.html';
  const full = path.resolve(root, '.' + clean);
  if (!full.startsWith(root + path.sep) && full !== root) return null;
  return full;
}

const server = http.createServer((req, res) => {
  const file = safePath(req.url);
  if (!file) {
    res.writeHead(403).end('forbidden');
    return;
  }
  fs.readFile(file, (error, data) => {
    if (error) {
      res.writeHead(error.code === 'ENOENT' ? 404 : 500).end(String(error.code || error));
      return;
    }
    res.writeHead(200, {
      'content-type': mime[path.extname(file)] || 'application/octet-stream',
      'cache-control': 'no-store',
    });
    res.end(data);
  });
});

server.listen(4173, '0.0.0.0', () => {
  console.log('Room viewer simulator server listening on 4173');
});
