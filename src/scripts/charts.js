// Small, dependency-free line charts. Each line is indexed to 100 at the first
// available value in the selected period; hovering shows actual prices.
const DAYS = { '1M': 31, '6M': 183, '1Y': 366, All: Infinity };
const NS = 'http://www.w3.org/2000/svg';
const fmtNum = (v) => v >= 1000 ? Math.round(v).toLocaleString('en-IN') : v.toFixed(2);
const fmtDate = (d) => new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const fmtShort = (d) => new Date(d + 'T00:00:00').toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

function niceTicks(min, max, count) {
  const span = max - min || 1;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(+v.toFixed(6));
  return ticks;
}

function setup(fig) {
  const data = JSON.parse(fig.querySelector('.chart-data').textContent);
  const plot = fig.querySelector('.plot');
  const legend = fig.querySelector('.legend');
  const compact = fig.classList.contains('compact');
  let range = fig.dataset.range || '1Y';
  const hidden = new Set();
  if (data.dates.length < 2) return;

  const colors = () => ['--c1', '--c2', '--c3', '--c4', '--c5', '--c6'].map(css);

  function windowIdx() {
    const last = new Date(data.dates[data.dates.length - 1] + 'T00:00:00');
    const cutoff = DAYS[range] === Infinity ? -Infinity : last.getTime() - DAYS[range] * 864e5;
    const i0 = data.dates.findIndex((d) => new Date(d + 'T00:00:00').getTime() >= cutoff);
    return Math.max(0, i0);
  }

  function renderLegend() {
    const cs = colors();
    legend.innerHTML = '';
    data.series.forEach((s, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'lg';
      b.setAttribute('aria-pressed', hidden.has(s.key) ? 'false' : 'true');
      b.innerHTML = `<span class="sw" style="background:${cs[i % cs.length]}"></span>${s.name}`;
      b.addEventListener('click', () => {
        hidden.has(s.key) ? hidden.delete(s.key) : hidden.add(s.key);
        renderLegend(); render();
      });
      legend.appendChild(b);
    });
  }

  function render() {
    const cs = colors();
    const line = css('--line'), muted = css('--muted'), fg = css('--fg'), bg = css('--bg');
    plot.innerHTML = '';
    const W = plot.clientWidth || 300, H = plot.clientHeight || 200;
    const padL = compact ? 30 : 38, padR = 8, padT = 8, padB = 22;
    const i0 = windowIdx();
    const dates = data.dates.slice(i0);
    const n = dates.length;
    const vis = [];
    data.series.forEach((s, si) => {
      if (hidden.has(s.key)) return;
      const vals = s.values.slice(i0);
      const base = vals.find((v) => v !== null && v > 0);
      if (!base) return;
      vis.push({ s, si, vals, idx: vals.map((v) => (v === null ? null : (v / base) * 100)) });
    });
    let lo = Infinity, hi = -Infinity;
    vis.forEach((v) => v.idx.forEach((x) => { if (x !== null) { lo = Math.min(lo, x); hi = Math.max(hi, x); } }));
    if (!Number.isFinite(lo)) { lo = 95; hi = 105; }
    lo = Math.min(lo, 100); hi = Math.max(hi, 100);
    const pad = (hi - lo) * 0.08 || 2; lo -= pad; hi += pad;
    const x = (i) => padL + (n <= 1 ? 0 : (i / (n - 1)) * (W - padL - padR));
    const y = (v) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);

    const svg = el('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, 'aria-hidden': 'true' }, plot);
    niceTicks(lo, hi, compact ? 3 : 4).forEach((t) => {
      el('line', { x1: padL, x2: W - padR, y1: y(t), y2: y(t), stroke: line, 'stroke-dasharray': t === 100 ? '' : '2 4' }, svg);
      const lab = el('text', { x: padL - 6, y: y(t) + 4, 'text-anchor': 'end', 'font-size': 11, fill: muted }, svg);
      lab.textContent = t;
    });
    const xt = compact ? [0, n - 1] : [0, Math.floor((n - 1) / 2), n - 1];
    [...new Set(xt)].forEach((i, k, arr) => {
      const t = el('text', { x: x(i), y: H - 5, 'font-size': 11, fill: muted, 'text-anchor': k === 0 ? 'start' : k === arr.length - 1 ? 'end' : 'middle' }, svg);
      t.textContent = fmtShort(dates[i]);
    });
    vis.forEach((v) => {
      let d = '', pen = false;
      v.idx.forEach((val, i) => {
        if (val === null) { pen = false; return; }
        d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(val).toFixed(1)}`; pen = true;
      });
      el('path', { d, fill: 'none', stroke: cs[v.si % cs.length], 'stroke-width': compact ? 1.6 : 1.9, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, svg);
    });

    // hover
    const guide = el('line', { y1: padT, y2: H - padB, stroke: muted, 'stroke-width': 1, opacity: 0 }, svg);
    const tip = document.createElement('div');
    tip.className = 'tip';
    tip.style.cssText = `position:absolute;pointer-events:none;opacity:0;background:${bg};border:1px solid ${line};color:${fg};font-size:12px;line-height:1.5;padding:8px 10px;border-radius:6px;white-space:nowrap;z-index:2;box-shadow:0 4px 18px rgba(0,0,0,.18)`;
    plot.appendChild(tip);
    function move(clientX) {
      const r = svg.getBoundingClientRect();
      const px = clientX - r.left;
      const i = Math.max(0, Math.min(n - 1, Math.round(((px - padL) / (W - padL - padR)) * (n - 1))));
      guide.setAttribute('x1', x(i)); guide.setAttribute('x2', x(i)); guide.setAttribute('opacity', 0.5);
      const rows = vis.map((v) => {
        const a = v.vals[i];
        if (a === null) return '';
        const ch = v.idx[i] - 100;
        return `<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${cs[v.si % cs.length]};margin-right:6px"></span>${v.s.name}: <b>${fmtNum(a)}</b> <span style="color:${muted}">(${ch >= 0 ? '+' : ''}${ch.toFixed(1)}%)</span></div>`;
      }).join('');
      tip.innerHTML = `<div style="color:${muted};margin-bottom:2px">${fmtDate(dates[i])}</div>${rows}`;
      tip.style.opacity = 1;
      const tw = tip.offsetWidth;
      tip.style.left = Math.min(Math.max(0, x(i) + 12), W - tw) + 'px';
      tip.style.top = '4px';
      if (x(i) + 12 + tw > W) tip.style.left = Math.max(0, x(i) - tw - 12) + 'px';
    }
    svg.style.touchAction = 'pan-y';
    svg.addEventListener('pointermove', (e) => move(e.clientX));
    svg.addEventListener('pointerleave', () => { tip.style.opacity = 0; guide.setAttribute('opacity', 0); });
  }

  fig.querySelectorAll('.ranges button').forEach((b) => {
    b.addEventListener('click', () => {
      range = b.dataset.r;
      fig.querySelectorAll('.ranges button').forEach((o) => o.setAttribute('aria-pressed', o === b ? 'true' : 'false'));
      render();
    });
  });
  renderLegend();
  render();
  new ResizeObserver(() => render()).observe(plot);
  document.addEventListener('themechange', () => { renderLegend(); render(); });
}

document.querySelectorAll('figure.chart').forEach(setup);
