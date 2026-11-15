export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin') || '';
    const allowed = new Set([
      'https://maaronfanberg-lab.github.io',
      'http://localhost:3000',
      'http://127.0.0.1:3000'
    ]);
    const cors = {
      'Access-Control-Allow-Origin': allowed.has(origin) ? origin : 'https://maaronfanberg-lab.github.io',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Allow-Methods': 'POST, OPTIONS, GET',
      'Vary': 'Origin'
    };
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    if (url.pathname === '/health') return json({ ok: true, model: 'gpt-5.6-sol' }, 200, cors);
    if (url.pathname !== '/chat' || request.method !== 'POST') return json({ error: 'Not found' }, 404, cors);
    if (!allowed.has(origin)) return json({ error: 'Origin not allowed' }, 403, cors);
    if (!env.OPENAI_API_KEY) return json({ error: 'Server is missing OPENAI_API_KEY' }, 500, cors);
    try {
      const body = await request.json();
      const system = typeof body.system === 'string' ? body.system : '';
      const history = Array.isArray(body.history) ? body.history.slice(-30) : [];
      const continuity = body.continuity && typeof body.continuity === 'object' ? body.continuity : {};
      const message = typeof body.message === 'string' ? body.message.trim() : '';
      if (!message) return json({ error: 'Empty message' }, 400, cors);
      const continuityText = `\n\nSARAH CONTINUITY\n${JSON.stringify(continuity).slice(0, 18000)}`;
      const input = [
        { role: 'developer', content: [{ type: 'input_text', text: system + continuityText }] },
        ...history.map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: [{ type: 'input_text', text: String(m.content || '').slice(0, 12000) }] })),
        { role: 'user', content: [{ type: 'input_text', text: message }] }
      ];
      const r = await fetch('https://api.openai.com/v1/responses', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.OPENAI_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: 'gpt-5.6-sol',
          input,
          reasoning: { effort: 'low' },
          store: false,
          max_output_tokens: 1800
        })
      });
      const data = await r.json();
      if (!r.ok) return json({ error: data?.error?.message || `OpenAI returned ${r.status}` }, r.status, cors);
      const reply = extractText(data);
      if (!reply) return json({ error: 'The model returned no text.' }, 502, cors);
      return json({ reply }, 200, cors);
    } catch (e) {
      return json({ error: e?.message || 'Relay error' }, 500, cors);
    }
  }
};

function extractText(data) {
  if (typeof data.output_text === 'string' && data.output_text.trim()) return data.output_text.trim();
  const parts = [];
  for (const item of data.output || []) {
    for (const c of item.content || []) {
      if (c.type === 'output_text' && c.text) parts.push(c.text);
      else if (typeof c.text === 'string') parts.push(c.text);
    }
  }
  return parts.join('\n').trim();
}

function json(value, status, extra = {}) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...extra }
  });
}
