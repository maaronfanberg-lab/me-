const SOUNDCLOUD_API = 'https://api.soundcloud.com';
const SOUNDCLOUD_AUTH = 'https://secure.soundcloud.com';
const SESSION_VERSION = 1;
const STATE_MAX_AGE_MS = 10 * 60 * 1000;

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      ...extraHeaders,
    },
  });
}

function corsHeaders(env, request) {
  const origin = request.headers.get('origin') || '';
  if (origin !== env.ALLOWED_ORIGIN) return {};
  return {
    'access-control-allow-origin': origin,
    'access-control-allow-methods': 'GET,POST,OPTIONS',
    'access-control-allow-headers': 'authorization,content-type',
    'access-control-expose-headers': 'x-pocket-session',
    'vary': 'Origin',
  };
}

function withCors(response, env, request) {
  const headers = new Headers(response.headers);
  const cors = corsHeaders(env, request);
  Object.keys(cors).forEach((key) => headers.set(key, cors[key]));
  return new Response(response.body, { status: response.status, headers });
}

function base64url(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function fromBase64url(value) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function randomURLSafe(byteCount) {
  const bytes = new Uint8Array(byteCount);
  crypto.getRandomValues(bytes);
  return base64url(bytes);
}

async function sha256Bytes(text) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return new Uint8Array(digest);
}

async function sessionKey(env) {
  if (!env.SOUNDCLOUD_CLIENT_SECRET) throw new Error('soundcloud_not_configured');
  const material = await sha256Bytes(`${env.SOUNDCLOUD_CLIENT_SECRET}\nPocketSpatialSessionV1`);
  return crypto.subtle.importKey('raw', material, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
}

async function seal(env, value) {
  const key = await sessionKey(env);
  const iv = new Uint8Array(12);
  crypto.getRandomValues(iv);
  const plaintext = new TextEncoder().encode(JSON.stringify(value));
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext);
  const combined = new Uint8Array(iv.length + ciphertext.byteLength);
  combined.set(iv, 0);
  combined.set(new Uint8Array(ciphertext), iv.length);
  return base64url(combined);
}

async function openSealed(env, token) {
  const bytes = fromBase64url(token);
  if (bytes.length < 13) throw new Error('invalid_session');
  const iv = bytes.slice(0, 12);
  const ciphertext = bytes.slice(12);
  const key = await sessionKey(env);
  let plaintext;
  try {
    plaintext = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext);
  } catch {
    throw new Error('invalid_session');
  }
  const value = JSON.parse(new TextDecoder().decode(plaintext));
  if (!value || value.v !== SESSION_VERSION) throw new Error('invalid_session');
  return value;
}

function callbackURL(request) {
  const url = new URL(request.url);
  return `${url.protocol}//${url.host}/oauth/callback`;
}

function configured(env) {
  return Boolean(env.SOUNDCLOUD_CLIENT_ID && env.SOUNDCLOUD_CLIENT_SECRET);
}

async function tokenExchange(env, fields) {
  const body = new URLSearchParams();
  Object.keys(fields).forEach((key) => body.set(key, fields[key]));
  body.set('client_id', env.SOUNDCLOUD_CLIENT_ID);
  body.set('client_secret', env.SOUNDCLOUD_CLIENT_SECRET);

  const response = await fetch(`${SOUNDCLOUD_AUTH}/oauth/token`, {
    method: 'POST',
    headers: {
      accept: 'application/json; charset=utf-8',
      'content-type': 'application/x-www-form-urlencoded',
    },
    body,
  });
  const text = await response.text();
  let payload;
  try { payload = JSON.parse(text); } catch { payload = { error: 'invalid_soundcloud_response' }; }
  if (!response.ok) {
    const error = new Error('soundcloud_token_error');
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function sessionFromTokenPayload(payload) {
  return {
    v: SESSION_VERSION,
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    expires_at: Date.now() + (Number(payload.expires_in || 3600) * 1000),
    scope: payload.scope || null,
  };
}

async function validSession(env, encrypted) {
  let session = await openSealed(env, encrypted);
  let rotated = null;
  if (Date.now() + 5 * 60 * 1000 >= Number(session.expires_at || 0)) {
    const payload = await tokenExchange(env, {
      grant_type: 'refresh_token',
      refresh_token: session.refresh_token,
    });
    session = sessionFromTokenPayload(payload);
    rotated = await seal(env, session);
  }
  return { session, rotated };
}

function bearer(request) {
  const auth = request.headers.get('authorization') || '';
  const match = auth.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : null;
}

async function soundCloudGET(pathOrURL, accessToken) {
  const url = new URL(pathOrURL, SOUNDCLOUD_API);
  if (url.protocol !== 'https:' || url.host !== 'api.soundcloud.com') throw new Error('untrusted_soundcloud_url');
  const response = await fetch(url.toString(), {
    headers: {
      accept: 'application/json; charset=utf-8',
      Authorization: `OAuth ${accessToken}`,
    },
  });
  const text = await response.text();
  let data;
  try { data = JSON.parse(text); } catch { data = { error: 'invalid_soundcloud_response' }; }
  if (!response.ok) {
    const error = new Error('soundcloud_api_error');
    error.status = response.status;
    error.payload = data;
    throw error;
  }
  return data;
}

async function collectOwnTracks(accessToken, maxItems = 100) {
  const result = [];
  let next = '/me/tracks?limit=50&linked_partitioning=true';
  while (next && result.length < maxItems) {
    const page = await soundCloudGET(next, accessToken);
    const collection = Array.isArray(page.collection) ? page.collection : [];
    for (let i = 0; i < collection.length && result.length < maxItems; i += 1) result.push(collection[i]);
    next = page.next_href || null;
    if (!collection.length) break;
  }
  return result;
}

function cleanTrack(track) {
  return {
    urn: track.urn || (track.id ? `soundcloud:tracks:${track.id}` : null),
    title: track.title || 'Untitled',
    permalink_url: track.permalink_url || null,
    artwork_url: track.artwork_url || null,
    license: track.license || null,
    access: track.access || null,
    duration: track.duration || null,
    downloadable: Boolean(track.downloadable),
    streamable: track.streamable !== false,
    user: track.user ? {
      username: track.user.username || null,
      permalink_url: track.user.permalink_url || null,
    } : null,
    spatial_eligible: true,
    spatial_eligibility_reason: 'own_upload',
  };
}

async function apiResponse(request, env, handler) {
  const encrypted = bearer(request);
  if (!encrypted) return withCors(json({ error: 'not_connected' }, 401), env, request);
  try {
    const { session, rotated } = await validSession(env, encrypted);
    const result = await handler(session);
    const headers = rotated ? { 'x-pocket-session': rotated } : {};
    return withCors(json(result, 200, headers), env, request);
  } catch (error) {
    const status = error.message === 'invalid_session' ? 401 : (error.status || 500);
    const body = status === 401
      ? { error: 'session_expired' }
      : { error: error.message || 'internal_error', detail: error.payload || null };
    return withCors(json(body, status), env, request);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return withCors(new Response(null, { status: 204 }), env, request);
    }

    if (url.pathname === '/health') {
      return withCors(json({
        ok: true,
        app: 'pocket-spatial-soundcloud-auth',
        configured: configured(env),
        app_url: env.APP_URL,
        callback_url: callbackURL(request),
      }), env, request);
    }

    if (url.pathname === '/oauth/start') {
      if (!configured(env)) return json({ error: 'soundcloud_not_configured' }, 503);
      const verifier = randomURLSafe(48);
      const challenge = base64url(await sha256Bytes(verifier));
      const redirectUri = callbackURL(request);
      const state = await seal(env, {
        v: SESSION_VERSION,
        verifier,
        issued_at: Date.now(),
        redirect_uri: redirectUri,
        return_url: env.APP_URL,
      });
      const authorize = new URL(`${SOUNDCLOUD_AUTH}/authorize`);
      authorize.searchParams.set('client_id', env.SOUNDCLOUD_CLIENT_ID);
      authorize.searchParams.set('redirect_uri', redirectUri);
      authorize.searchParams.set('response_type', 'code');
      authorize.searchParams.set('code_challenge', challenge);
      authorize.searchParams.set('code_challenge_method', 'S256');
      authorize.searchParams.set('state', state);
      authorize.searchParams.set('display', 'popup');
      return Response.redirect(authorize.toString(), 302);
    }

    if (url.pathname === '/oauth/callback') {
      if (!configured(env)) return json({ error: 'soundcloud_not_configured' }, 503);
      const code = url.searchParams.get('code');
      const stateToken = url.searchParams.get('state');
      if (!code || !stateToken) return json({ error: 'missing_code_or_state' }, 400);
      try {
        const state = await openSealed(env, stateToken);
        if (Date.now() - Number(state.issued_at || 0) > STATE_MAX_AGE_MS) throw new Error('oauth_state_expired');
        if (state.redirect_uri !== callbackURL(request)) throw new Error('oauth_redirect_mismatch');
        if (state.return_url !== env.APP_URL) throw new Error('oauth_return_mismatch');
        const payload = await tokenExchange(env, {
          grant_type: 'authorization_code',
          redirect_uri: state.redirect_uri,
          code_verifier: state.verifier,
          code,
        });
        const session = await seal(env, sessionFromTokenPayload(payload));
        const returnURL = new URL(env.APP_URL);
        returnURL.hash = `sc_session=${encodeURIComponent(session)}`;
        return Response.redirect(returnURL.toString(), 302);
      } catch (error) {
        const returnURL = new URL(env.APP_URL);
        returnURL.hash = `sc_error=${encodeURIComponent(error.message || 'oauth_failed')}`;
        return Response.redirect(returnURL.toString(), 302);
      }
    }

    if (url.pathname === '/api/me' && request.method === 'GET') {
      return apiResponse(request, env, async (session) => {
        const me = await soundCloudGET('/me', session.access_token);
        return {
          user: {
            urn: me.urn || (me.id ? `soundcloud:users:${me.id}` : null),
            username: me.username || null,
            permalink_url: me.permalink_url || null,
            avatar_url: me.avatar_url || null,
          },
        };
      });
    }

    if (url.pathname === '/api/tracks' && request.method === 'GET') {
      return apiResponse(request, env, async (session) => {
        const tracks = await collectOwnTracks(session.access_token, 100);
        return { tracks: tracks.map(cleanTrack) };
      });
    }

    if (url.pathname === '/api/signout' && request.method === 'POST') {
      return apiResponse(request, env, async (session) => {
        try {
          await fetch(`${SOUNDCLOUD_AUTH}/sign-out`, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ access_token: session.access_token }),
          });
        } catch {}
        return { ok: true };
      });
    }

    return withCors(json({ error: 'not_found' }, 404), env, request);
  },
};
