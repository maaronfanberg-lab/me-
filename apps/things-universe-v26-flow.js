'use strict';
/* things-universe-v26-flow.js
 *
 * Fluid-motion layer for Things Universe v26.
 *
 * INSTALL: load as the LAST script tag in things-universe-v26.html,
 * after things-universe-v24-init.js.
 *
 * It overrides draw() and physicsFrame() while keeping references to the
 * originals. With FLOW.on === false it calls those originals verbatim.
 */

(function () {
  var required = {
    draw: typeof draw,
    physicsFrame: typeof physicsFrame,
    kick: typeof kick,
    rootIdSet: typeof rootIdSet,
    linkEnds: typeof linkEnds,
    ownerAnchor: typeof ownerAnchor,
    nodeColor: typeof nodeColor,
    hash: typeof hash
  };
  var missing = Object.keys(required).filter(function (k) { return required[k] !== 'function'; });
  if (missing.length) {
    console.error('[flow] ABORTED — expected globals not found: ' + missing.join(', ') +
      '. Load this file after things-universe-v20-core.js. v26 is unmodified.');
    return;
  }

  var _draw = draw;
  var _physics = physicsFrame;

  var FLOW = window.FLOW = {
    on: true,
    pull: 2.6,
    slack: 0.6,
    idle: 0.055,
    bloom: 620,
    halo: 1500
  };

  var backOut = function (t) {
    var c1 = 1.70158, c3 = c1 + 1;
    return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
  };

  function stamp(now) {
    for (var i = 0; i < N.length; i++) {
      var n = N[i];
      if (n.born === undefined) n.born = now;
      var s = (n.owners && n.owners.size) || 1;
      if (n._share === undefined) n._share = s;
      else if (s > n._share) { n._share = s; n.sharedAt = now; }
    }
    for (var j = 0; j < L.length; j++) if (L[j].born === undefined) L[j].born = now;
  }

  draw = function () {
    if (!ctx) return;
    if (!FLOW.on) return _draw();

    var now = performance.now();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);
    ctx.translate(view.x, view.y);
    ctx.scale(view.k, view.k);

    var k = view.k, margin = 150 / k,
      minX = (-view.x) / k - margin, maxX = (width - view.x) / k + margin,
      minY = (-view.y) / k - margin, maxY = (height - view.y) / k + margin;

    var visible = new Set(), i, n;
    for (i = 0; i < N.length; i++) {
      n = N[i];
      if (n.x >= minX && n.x <= maxX && n.y >= minY && n.y <= maxY) visible.add(n.id);
    }
    var roots = rootIdSet();
    ctx.lineCap = 'round';

    for (var ei = 0; ei < L.length; ei++) {
      var e = L[ei], ends = linkEnds(e), p = ends[0], q = ends[1];
      if (!p || !q || (!visible.has(p.id) && !visible.has(q.id))) continue;
      var ea = Math.min(1, (now - (e.born || now)) / FLOW.bloom);
      if (ea <= 0) continue;
      ctx.globalAlpha = ea;
      ctx.beginPath();
      ctx.moveTo(p.x, p.y);
      ctx.lineTo(q.x, q.y);
      var sharedEdge = e.bridge || p.owners.size > 1 || q.owners.size > 1;
      ctx.strokeStyle = sharedEdge ? 'rgba(219,201,139,.34)' : 'rgba(120,229,221,.14)';
      ctx.lineWidth = (sharedEdge ? .8 : .38) / Math.max(.34, Math.sqrt(k));
      if (sharedEdge) ctx.setLineDash([4 / k, 6 / k]); else ctx.setLineDash([]);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    var showLabels = N.length < 90 ? k > .44 : N.length < 350 ? k > .76 : k > 1.08;
    var showEdgeLabels = k > 2.5 && N.length < 400;

    if (showEdgeLabels) {
      ctx.font = '5.5px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif';
      ctx.fillStyle = 'rgba(185,198,219,.62)';
      for (var li = 0; li < L.length; li++) {
        var le = L[li], lends = linkEnds(le), la = lends[0], lb = lends[1];
        if (!la || !lb || (!visible.has(la.id) && !visible.has(lb.id))) continue;
        var txt = (le.rel || '').slice(0, 26);
        ctx.strokeStyle = 'rgba(7,16,24,.96)';
        ctx.lineWidth = 2 / k;
        ctx.strokeText(txt, (la.x + lb.x) / 2, (la.y + lb.y) / 2);
        ctx.fillText(txt, (la.x + lb.x) / 2, (la.y + lb.y) / 2);
      }
    }

    for (i = 0; i < N.length; i++) {
      n = N[i];
      if (!visible.has(n.id)) continue;

      var root = roots.has(n.id);
      var base = root ? 6.2 : n.owners.size > 1 ? 3.3 : 1.75;
      var g = Math.min(1, (now - (n.born || now)) / FLOW.bloom);
      var r = base * backOut(g);
      if (r <= 0.05) continue;

      if (n.sharedAt) {
        var hp = (now - n.sharedAt) / FLOW.halo;
        if (hp < 1) {
          ctx.globalAlpha = (1 - hp) * .7;
          ctx.beginPath();
          ctx.arc(n.x, n.y, base + hp * 30 / k, 0, Math.PI * 2);
          ctx.strokeStyle = '#b7a0ff';
          ctx.lineWidth = 1.3 / k;
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      }

      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      ctx.fillStyle = nodeColor(n);
      ctx.globalAlpha = (n === selected || n === dragNode ? 1 : .9) * Math.min(1, g * 1.4);
      ctx.fill();
      if (n === selected || n === dragNode) {
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.1 / k;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      if (showLabels || root || n === selected || n === dragNode) {
        var fs = Math.max(5.8, Math.min(9.5, 7.5 / Math.sqrt(Math.max(.32, k))));
        var lt = n.l.length > 36 ? n.l.slice(0, 34) + '…' : n.l;
        ctx.globalAlpha = g;
        ctx.font = fs + 'px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif';
        ctx.strokeStyle = 'rgba(7,16,24,.98)';
        ctx.lineWidth = 2.6 / k;
        ctx.fillStyle = '#eaf2ff';
        ctx.strokeText(lt, n.x + r + 2.7, n.y + 2.5);
        ctx.fillText(lt, n.x + r + 2.7, n.y + 2.5);
        ctx.globalAlpha = 1;
      }
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  physicsFrame = function (now) {
    raf = 0;
    if (!N.length) { energy = 0; draw(); return; }
    stamp(now);
    if (!FLOW.on) return _physics(now);

    var dt = Math.min(2.2, Math.max(.45, (now - lastFrame) / 16.67));
    lastFrame = now;

    var a = Math.max(.012, energy);
    var roots = rootIdSet();
    var idle = energy <= FLOW.idle * 1.25;
    var i, n;

    if (!idle) {
      for (var ei = 0; ei < L.length; ei++) {
        var e = L[ei], ends = linkEnds(e), x = ends[0], y = ends[1];
        if (!x || !y) continue;
        var dx = y.x - x.x, dy = y.y - x.y, d = Math.hypot(dx, dy) || 1;
        var shared = e.bridge || x.owners.size > 1 || y.owners.size > 1;
        var want = shared ? 185 : 125 + Math.min(55, Math.max(x.depth || 0, y.depth || 0) * 4);
        var stiff = .0042 * (shared ? FLOW.slack : 1);
        var f = (d - want) * stiff * a, fx = dx / d * f, fy = dy / d * f;
        if (!x.pinned) { x.vx = (x.vx || 0) + fx; x.vy = (x.vy || 0) + fy; }
        if (!y.pinned) { y.vx = (y.vx || 0) - fx; y.vy = (y.vy || 0) - fy; }
      }

      for (i = 0; i < N.length; i++) {
        n = N[i];
        if (n.pinned) continue;
        var anc = ownerAnchor(n);
        var share = (n.owners && n.owners.size) || 1;
        var strength = (roots.has(n.id) ? .0018 : .00028) * (1 + FLOW.pull * (share - 1));
        n.vx = (n.vx || 0) + (anc.x - n.x) * strength * a;
        n.vy = (n.vy || 0) + (anc.y - n.y) * strength * a;
      }

      var repel = function (x2, y2) {
        var dx2 = y2.x - x2.x, dy2 = y2.y - x2.y, d2 = dx2 * dx2 + dy2 * dy2 + 12;
        if (d2 > 520 * 520) return;
        var dd = Math.sqrt(d2), min = 24;
        var ff = (dd < min ? (min - dd) * .055 : Math.min(.75, 1500 / d2)) * a;
        var fx2 = dx2 / dd * ff, fy2 = dy2 / dd * ff;
        if (!x2.pinned) { x2.vx -= fx2; x2.vy -= fy2; }
        if (!y2.pinned) { y2.vx += fx2; y2.vy += fy2; }
      };
      var cnt = N.length;
      if (cnt < 420) {
        for (i = 0; i < cnt; i++) for (var j = i + 1; j < cnt; j++) repel(N[i], N[j]);
      } else {
        var tries = Math.min(22000, cnt * 30);
        for (var t2 = 0; t2 < tries; t2++) {
          var ia = (Math.random() * cnt) | 0, ib = (Math.random() * cnt) | 0;
          if (ia !== ib) repel(N[ia], N[ib]);
        }
      }
    }

    var tt = now * .00035;
    var damp = Math.pow(idle ? .985 : .91, dt);
    for (i = 0; i < N.length; i++) {
      n = N[i];
      if (n.pinned) continue;
      var h = hash(n.id) % 1000;
      n.vx = (n.vx || 0) + (Math.sin(tt + h) * .0025) * a;
      n.vy = (n.vy || 0) + (Math.cos(tt * .87 + h * .37) * .0025) * a;
      n.vx *= damp; n.vy *= damp;
      n.x += n.vx * dt; n.y += n.vy * dt;
    }

    energy = Math.max(FLOW.idle, energy * Math.pow(auto ? 0.992 : 0.978, dt));
    draw();
    raf = requestAnimationFrame(physicsFrame);
  };

  var host = document.querySelector('.zoomBtns');
  if (host) {
    var b = document.createElement('button');
    b.className = 'btn on';
    b.id = 'flowToggle';
    b.textContent = '≈';
    b.setAttribute('aria-label', 'Toggle fluid motion');
    b.onclick = function () {
      FLOW.on = !FLOW.on;
      b.classList.toggle('on', FLOW.on);
      if (typeof toast === 'function') toast(FLOW.on ? 'Fluid motion: on' : 'Fluid motion: off — baseline');
      kick(1);
      draw();
    };
    host.appendChild(b);
  }

  kick(1);
  console.log('[flow] installed. window.FLOW to tune: pull, slack, idle, bloom, halo.');
})();
