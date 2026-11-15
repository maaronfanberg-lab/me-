// Deep Water: measured one-shot capture. No generated waveform or synthetic sample insertion.
function DEEP_CAPTURE(parser) {
  'use strict';
  const SEEDLINK = 'wss://rtserve.earthscope.org/seedlink';
  const ARCHIVE = 'https://service.earthscope.org/fdsnws/dataselect/1/query';
  const STALE_MS = 2 * 60 * 1000;
  const SEGMENT_MS = 15 * 60 * 1000;
  const HOUR_MS = 60 * 60 * 1000;

  function stationParts(station) {
    if (!Array.isArray(station) || station.length < 5) throw new Error('Invalid station');
    const [net, sta, loc, cha, name] = station;
    if (![net, sta, loc, cha].every(v => /^[A-Za-z0-9-]+$/.test(v))) throw new Error('Invalid station ID');
    if (!/^[A-Za-z0-9]{3}$/.test(cha)) throw new Error('A three-character channel is required');
    return {net, sta, loc, cha, name, id: net + '.' + sta + '.' + loc + '.' + cha};
  }

  function archiveURL(station, at) {
    const s = stationParts(station);
    const time = n => new Date(n).toISOString().slice(0, 19);
    return ARCHIVE + '?net=' + encodeURIComponent(s.net) +
      '&sta=' + encodeURIComponent(s.sta) +
      '&loc=' + encodeURIComponent(s.loc) +
      '&cha=' + encodeURIComponent(s.cha) +
      '&starttime=' + time(at - HOUR_MS) + '&endtime=' + time(at) + '&nodata=404';
  }

  // A SeedLink 4 packet has a variable-length, 17-byte-plus-station header.
  // Only its miniSEED 2 payload is passed to our miniSEED 2 reader.
  function decodeSeedLinkPacket(buffer, station) {
    const s = stationParts(station), b = new Uint8Array(buffer);
    if (b.length === 3 && b[0] === 69 && b[1] === 78 && b[2] === 68) return {ended: true};
    if (b.length < 17 || b[0] !== 83 || b[1] !== 69) throw new Error('Invalid SeedLink packet header');
    const view = new DataView(buffer);
    const length = view.getUint32(4, true), idLen = b[16], offset = 17 + idLen;
    if (offset + length !== b.length || length < 48) throw new Error('Invalid SeedLink packet length');
    const stationID = String.fromCharCode.apply(null, b.subarray(17, offset));
    if (stationID !== s.net + '_' + s.sta) return {records: []};
    if (b[2] !== 50 || b[3] !== 68) return {records: []}; // miniSEED 2 data packets only
    const payload = buffer.slice(offset, offset + length);
    const recs = parser.parse(payload).filter(r => r && Number.isFinite(r.start) &&
      r.rate > 0 && r.samples && r.samples.length > 0);
    return {records: recs};
  }

  function newestEnd(records) {
    return records.reduce((max, r) => Math.max(max, r.start + 1000 * r.samples.length / r.rate), 0);
  }

  // Reconstruct a contiguous measured section, using timestamps to skip overlaps.
  // A data gap starts a new run; we never fill it with invented zeros.
  function contiguousLatest(records, station, source) {
    const s = stationParts(station);
    const recs = records.filter(r => r && Number.isFinite(r.start) && Number.isFinite(r.rate) &&
      r.rate > 0 && r.rate < 10000 && r.samples && r.samples.length &&
      r.samples.length < 2000000).sort((a, b) => a.start - b.start);
    if (!recs.length) throw new Error('No measured samples in response');
    const tail = newestEnd(recs);
    let rate = 0, startT = 0, expected = 0, values = [];
    for (const r of recs) {
      if (r.start + 1000 * r.samples.length / r.rate < tail - SEGMENT_MS) continue;
      const step = 1000 / r.rate;
      if (!rate || Math.abs(r.rate - rate) / rate > 0.00001 || r.start > expected + step * 1.5) {
        rate = r.rate; startT = r.start; expected = r.start; values = [];
      }
      const skip = Math.max(0, Math.ceil((expected - r.start - step * 0.25) / step));
      for (let i = skip; i < r.samples.length; i++) {
        const t = r.start + i * step, value = Number(r.samples[i]);
        if (t < expected - step * 0.25) continue;
        if (t > expected + step * 1.5) { values = []; startT = t; }
        if (Number.isFinite(value)) { values.push(value); expected = t + step; }
      }
    }
    if (values.length < 2) throw new Error('Not enough contiguous measured samples');
    // Limit audio/CSV to the most recent 15 minutes, without modifying the raw amplitudes.
    const limit = Math.min(values.length, Math.ceil(SEGMENT_MS * rate / 1000), 1200000);
    if (limit !== values.length) { startT += (values.length - limit) * 1000 / rate; values = values.slice(-limit); }
    const endT = startT + values.length * 1000 / rate;
    return {raw: Float64Array.from(values), rate, startT, endT, name: s.name, id: s.id, source};
  }

  function streamRecords(station, at, SocketClass) {
    return new Promise((resolve, reject) => {
      if (!SocketClass) { reject(new Error('WebSocket unavailable')); return; }
      const s = stationParts(station), collected = [];
      let socket, stage = 0, done = false, timer;
      const finish = error => {
        if (done) return;
        done = true; clearTimeout(timer);
        try { if (socket && socket.readyState < 2) socket.close(); } catch (_) {}
        if (collected.length) resolve(collected);
        else reject(error || new Error('No SeedLink miniSEED samples'));
      };
      try {
        socket = new SocketClass(SEEDLINK);
        socket.binaryType = 'arraybuffer';
        timer = setTimeout(() => finish(new Error('SeedLink timed out')), 13000);
        socket.onopen = () => socket.send('HELLO');
        socket.onmessage = async e => {
          if (done) return;
          try {
            if (typeof e.data === 'string') {
              const msg = e.data.trim();
              if (/^ERROR/i.test(msg)) { finish(new Error('SeedLink: ' + msg.slice(0, 140))); return; }
              if (stage === 0 && /^SeedLink/i.test(msg)) { stage = 1; socket.send('SLPROTO 4.0'); }
              else if (stage === 1 && /^OK/i.test(msg)) { stage = 2; socket.send('STATION ' + s.net + '_' + s.sta); }
              else if (stage === 2 && /^OK/i.test(msg)) {
                stage = 3;
                socket.send('SELECT ' + s.loc + '_' + s.cha[0] + '_' + s.cha[1] + '_' + s.cha[2] + '.2D');
              } else if (stage === 3 && /^OK/i.test(msg)) {
                stage = 4;
                socket.send('DATA ALL ' + new Date(at - SEGMENT_MS).toISOString() + ' ' + new Date(at).toISOString());
              } else if (stage === 4 && /^OK/i.test(msg)) {
                stage = 5;
                socket.send('ENDFETCH');
              }
              return;
            }
            if (stage < 5) return;
            const b = e.data instanceof ArrayBuffer ? e.data : await e.data.arrayBuffer();
            const packet = decodeSeedLinkPacket(b, station);
            if (packet.ended) { finish(); return; }
            collected.push(...packet.records);
          } catch (error) { finish(error); }
        };
        socket.onerror = () => finish(new Error('SeedLink socket error'));
        socket.onclose = () => finish(new Error('SeedLink closed without samples'));
      } catch (error) { finish(error); }
    });
  }

  async function archiveRecords(station, at, fetcher) {
    if (!fetcher) throw new Error('Fetch unavailable');
    const ctrl = typeof AbortController === 'function' ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), 14000) : null;
    try {
      const r = await fetcher(archiveURL(station, at), {cache: 'no-store', ...(ctrl ? {signal: ctrl.signal} : {})});
      if (!r.ok) throw new Error(r.status === 404 ? 'No archived samples' : 'Archive HTTP ' + r.status);
      const b = await r.arrayBuffer();
      return parser.parse(b).filter(r => r && Number.isFinite(r.start) && r.rate > 0 && r.samples && r.samples.length);
    } finally { if (timer) clearTimeout(timer); }
  }

  // Stream first. The archive is queried only once when the stream is old/unavailable.
  async function capture(station, options = {}) {
    const at = options.at || Date.now();
    const SocketClass = options.SocketClass === null ? null :
      (options.SocketClass || (typeof WebSocket !== 'undefined' ? WebSocket : null));
    const fetcher = options.fetcher || (typeof fetch !== 'undefined' ? fetch.bind(globalThis) : null);
    let best = null, errors = [];
    try {
      const recs = await streamRecords(station, at, SocketClass);
      best = contiguousLatest(recs, station, 'SeedLink');
    } catch (e) { errors.push('stream: ' + (e.message || e)); }
    if (!best || at - best.endT > STALE_MS) {
      try {
        const archived = contiguousLatest(await archiveRecords(station, at, fetcher), station, 'EarthScope archive');
        if (!best || archived.endT > best.endT) best = archived;
      } catch (e) { errors.push('archive: ' + (e.message || e)); }
    }
    if (!best) throw new Error(errors.join('; ') || 'No measured samples');
    best.ageMs = Math.max(0, at - best.endT);
    best.warning = best.ageMs > STALE_MS ? 'Not fresh: newest measured sample is older than 2 minutes' : '';
    best.errors = errors;
    return best;
  }

  function csv(recording) {
    const s = ['timestamp_utc,amplitude_counts,station'];
    const rate = recording.rate, raw = recording.raw;
    for (let i = 0; i < raw.length; i++) {
      s.push(new Date(recording.startT + i * 1000 / rate).toISOString() +
        ',' + raw[i] + ',' + recording.id);
    }
    return s.join('\r\n') + '\r\n';
  }

  return {decodeSeedLinkPacket, contiguousLatest, streamRecords, archiveRecords,
    archiveURL, capture, csv, STALE_MS};
}
if (typeof module !== 'undefined') module.exports = DEEP_CAPTURE;
