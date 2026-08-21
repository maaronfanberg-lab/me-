(() => {
  const ENDPOINT = '__LEVIATHAN_SIGNAL_ENDPOINT__';
  const enabled = /^https:\/\//.test(ENDPOINT);
  const source = 'github-pages-v1';

  function post(path, payload) {
    if (!enabled) return Promise.resolve({ ok: false, disabled: true });
    return fetch(ENDPOINT + path, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...payload, source }),
      keepalive: true
    }).then(r => r.json().catch(() => ({ ok: r.ok }))).catch(() => ({ ok: false }));
  }

  function once(key, fn) {
    try {
      if (sessionStorage.getItem(key)) return;
      sessionStorage.setItem(key, '1');
    } catch (_) {}
    fn();
  }

  const boot = () => {
    once('leviathan_signal_page_view', () => post('/event', { type: 'page_view' }));

    const power = document.getElementById('power');
    if (power) power.addEventListener('click', () => once('leviathan_signal_power', () => post('/event', { type: 'power_on' })), { passive: true });

    const box = document.getElementById('marketSignal');
    const open = document.getElementById('marketOpen');
    const form = document.getElementById('marketForm');
    const status = document.getElementById('marketStatus');
    if (!box || !open || !form || !status) return;

    open.addEventListener('click', () => {
      once('leviathan_signal_interest_click', () => post('/event', { type: 'interest_click' }));
      form.hidden = false;
      open.hidden = true;
      const first = form.querySelector('input[name="intent"]');
      if (first) first.focus();
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const intent = String(data.get('intent') || '');
      const email = String(data.get('email') || '').trim();
      const comment = String(data.get('comment') || '').trim();
      if (!intent) {
        status.textContent = 'Choose YES, MAYBE, or NO first.';
        return;
      }
      status.textContent = 'SENDING…';
      const result = await post('/interest', { intent, email, comment });
      if (result && result.ok) {
        form.hidden = true;
        status.textContent = 'SIGNAL RECEIVED — THANK YOU.';
        status.style.color = 'var(--teal)';
      } else {
        status.textContent = enabled ? 'COULD NOT SEND. TRY AGAIN.' : 'SIGNAL COLLECTOR IS DEPLOYING.';
        status.style.color = 'var(--crimson)';
      }
    });
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
