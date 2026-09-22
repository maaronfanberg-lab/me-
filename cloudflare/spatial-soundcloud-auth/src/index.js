const TOKEN_URL = 'https://secure.soundcloud.com/oauth/token';

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff'
    }
  });
}

function methodNotAllowed(allow) {
  return new Response('Method Not Allowed', { status: 405, headers: { allow } });
}

function requireEnv(env) {
  const required = [
    'SOUNDCLOUD_CLIENT_ID',
    'SOUNDCLOUD_CLIENT_SECRET',
    'SOUNDCLOUD_REDIRECT_URI'
  ];
  const missing = required.filter((key) => !env[key]);
  if (missing.length) throw new Error(`Missing worker configuration: ${missing.join(', ')}`);
}

async function readJSON(request) {
  const type = request.headers.get('content-type') || '';
  if (!type.toLowerCase().includes('application/json')) {
    throw new TypeError('Expected application/json');
  }

  const contentLength = Number(request.headers.get('content-length') || 0);
  if (contentLength > 16_384) throw new RangeError('Request body too large');
  return request.json();
}

function formBody(entries) {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(entries)) {
    if (value !== undefined && value !== null) body.set(key, String(value));
  }
  return body;
}

async function soundCloudToken(env, fields) {
  requireEnv(env);

  const response = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: {
      accept: 'application/json; charset=utf-8',
      'content-type': 'application/x-www-form-urlencoded'
    },
    body: formBody({
      ...fields,
      client_id: env.SOUNDCLOUD_CLIENT_ID,
      client_secret: env.SOUNDCLOUD_CLIENT_SECRET
    })
  });

  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    payload = { error: 'invalid_soundcloud_response' };
  }

  // Never reflect secrets or request credentials. SoundCloud's token payload itself
  // is intentionally returned to the authenticated app so it can store it in Keychain.
  return json(payload, response.status);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    try {
      if (url.pathname === '/health') {
        if (request.method !== 'GET' && request.method !== 'HEAD') {
          return methodNotAllowed('GET, HEAD');
        }
        return json({
          ok: true,
          service: 'spatial-soundcloud-auth',
          configured: Boolean(env.SOUNDCLOUD_CLIENT_ID && env.SOUNDCLOUD_CLIENT_SECRET)
        });
      }

      if (url.pathname === '/config') {
        if (request.method !== 'GET') return methodNotAllowed('GET');
        if (!env.SOUNDCLOUD_CLIENT_ID || !env.SOUNDCLOUD_REDIRECT_URI) {
          return json({ error: 'worker_not_configured' }, 503);
        }
        return json({
          client_id: env.SOUNDCLOUD_CLIENT_ID,
          redirect_uri: env.SOUNDCLOUD_REDIRECT_URI,
          authorize_url: 'https://secure.soundcloud.com/authorize'
        });
      }

      if (url.pathname === '/oauth/exchange') {
        if (request.method !== 'POST') return methodNotAllowed('POST');
        const body = await readJSON(request);
        const code = String(body.code || '').trim();
        const verifier = String(body.code_verifier || '').trim();
        const redirectURI = String(body.redirect_uri || '').trim();

        if (!code || !verifier || !redirectURI) {
          return json({ error: 'missing_code_verifier_or_redirect_uri' }, 400);
        }
        if (redirectURI !== env.SOUNDCLOUD_REDIRECT_URI) {
          return json({ error: 'redirect_uri_mismatch' }, 400);
        }
        if (verifier.length < 43 || verifier.length > 128) {
          return json({ error: 'invalid_code_verifier_length' }, 400);
        }

        return soundCloudToken(env, {
          grant_type: 'authorization_code',
          code,
          redirect_uri: redirectURI,
          code_verifier: verifier
        });
      }

      if (url.pathname === '/oauth/refresh') {
        if (request.method !== 'POST') return methodNotAllowed('POST');
        const body = await readJSON(request);
        const refreshToken = String(body.refresh_token || '').trim();
        if (!refreshToken) return json({ error: 'missing_refresh_token' }, 400);

        return soundCloudToken(env, {
          grant_type: 'refresh_token',
          refresh_token: refreshToken
        });
      }

      return new Response('Not Found', { status: 404 });
    } catch (error) {
      const status = error instanceof TypeError || error instanceof RangeError ? 400 : 500;
      return json({ error: status === 400 ? error.message : 'internal_error' }, status);
    }
  }
};
