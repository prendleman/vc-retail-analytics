async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function money(n) {
  return (Number(n) || 0).toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

function num(n, d = 0) {
  const x = Number(n);
  if (!Number.isFinite(x)) return '—';
  return x.toLocaleString(undefined, { maximumFractionDigits: d });
}

function pct(n) {
  const x = Number(n);
  if (!Number.isFinite(x)) return '—';
  return `${x.toFixed(1)}%`;
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function fmtCell(key, val) {
  const k = key.toLowerCase();
  if (val == null) return '—';
  if (/net_sales|margin$|quarterly_quota/.test(k) && typeof val === 'number') return money(val);
  if (/pct|realization|index|vs_peer|attainment|composite|capacity_pct|otif|score|yoy/.test(k) && typeof val === 'number') {
    if (k.includes('realization') || k.includes('index') || k.includes('vs_peer') || k.includes('peak_index')) return num(val, 2);
    return pct(val);
  }
  if (typeof val === 'number' && !Number.isInteger(val)) return num(val, 1);
  return esc(val);
}

function htmlTable(rows, limit = 25) {
  if (!rows || !rows.length) return '<p class="fine">(empty)</p>';
  const slice = rows.slice(0, limit);
  const keys = Object.keys(slice[0]);
  const head = keys.map(k => `<th>${esc(k)}</th>`).join('');
  const body = slice.map(r => {
    const cells = keys.map(k => {
      let cls = '';
      const v = r[k];
      if (k === 'grade') cls = ` class="badge-grade g-${esc(v)}"`;
      if (k === 'tier') cls = ` class="badge-tier t-${esc(String(v).toLowerCase())}"`;
      if (k === 'risk_flag' || k === 'plan_action') cls = ` class="flag ${String(v).includes('Ok') || v === 'Monitor' ? 'ok' : 'warn'}"`;
      return `<td${cls}>${fmtCell(k, v)}</td>`;
    }).join('');
    return `<tr>${cells}</tr>`;
  }).join('');
  const more = rows.length > limit ? `<p class="fine">Showing ${limit} of ${rows.length}</p>` : '';
  return `<div class="data-wrap"><table class="data"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>${more}`;
}

function barChart(rows, labelKey, valueKey, opts = {}) {
  if (!rows || !rows.length) return '';
  const max = Math.max(...rows.map(r => Math.abs(Number(r[valueKey]) || 0)), 0.0001);
  const bars = rows.slice(0, opts.limit || 12).map(r => {
    const v = Number(r[valueKey]) || 0;
    const w = Math.min(100, (Math.abs(v) / max) * 100);
    const neg = v < 0 ? ' neg' : '';
    const label = esc(r[labelKey]);
    const display = opts.money ? money(v) : (opts.pct ? pct(v) : num(v, opts.digits ?? 0));
    return `<div class="bar-row"><span class="bar-label" title="${label}">${label}</span>`
      + `<div class="bar-track"><div class="bar-fill${neg}" style="width:${w}%"></div></div>`
      + `<span class="bar-val">${display}</span></div>`;
  }).join('');
  return `<div class="bar-chart">${bars}</div>`;
}

function seasonHeatmap(rows) {
  if (!rows || !rows.length) return '';
  const families = [...new Set(rows.map(r => r.family))];
  const months = ['01','02','03','04','05','06','07','08','09','10','11','12'];
  const map = {};
  rows.forEach(r => {
    map[`${r.family}|${String(r.month_num).padStart(2, '0')}`] = Number(r.seasonal_index) || 0;
  });
  const head = `<tr><th>Family</th>${months.map(m => `<th>${m}</th>`).join('')}</tr>`;
  const body = families.map(f => {
    const cells = months.map(m => {
      const v = map[`${f}|${m}`] || 0;
      // 0.6..1.9 -> heat
      const t = Math.max(0, Math.min(1, (v - 0.6) / 1.3));
      const bg = `rgba(138,106,59,${(0.12 + t * 0.85).toFixed(2)})`;
      const color = t > 0.55 ? '#fff' : '#1c1914';
      return `<td style="background:${bg};color:${color}" title="${esc(f)} ${m}: ${v}">${v ? v.toFixed(2) : '—'}</td>`;
    }).join('');
    return `<tr><th>${esc(f)}</th>${cells}</tr>`;
  }).join('');
  return `<div class="data-wrap heat-wrap"><table class="heat">${head}${body}</table></div>`;
}

function sparklineByFamily(rows) {
  // aggregate units by month across selected families for last 12 months
  if (!rows || !rows.length) return '';
  const byMonth = {};
  rows.forEach(r => {
    byMonth[r.month] = (byMonth[r.month] || 0) + (Number(r.units_sold) || 0);
  });
  const months = Object.keys(byMonth).sort().slice(-12);
  const vals = months.map(m => byMonth[m]);
  const max = Math.max(...vals, 1);
  const w = 320, h = 56, pad = 2;
  const step = (w - pad * 2) / Math.max(months.length - 1, 1);
  const pts = vals.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - (v / max) * (h - pad * 2);
    return `${x},${y}`;
  }).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" role="img" aria-label="Units trend">`
    + `<polyline fill="none" stroke="#8a6a3b" stroke-width="2" points="${pts}" />`
    + `</svg><div class="spark-labels"><span>${esc(months[0] || '')}</span><span>${esc(months[months.length - 1] || '')}</span></div>`;
}

function insightCards(items) {
  if (!items.length) return '';
  return `<div class="insights">${items.map(i =>
    `<aside class="insight ${i.tone || ''}"><strong>${esc(i.title)}</strong><p>${esc(i.body)}</p></aside>`
  ).join('')}</div>`;
}

function buildInsights(section, a) {
  const items = [];
  if (section === 'core' || section === 'margin') {
    const ch = [...(a.margin_pct || [])].sort((x, y) => (x.margin_pct || 0) - (y.margin_pct || 0));
    if (ch[0]) items.push({ title: 'Thinnest channel', body: `${ch[0].channel} at ${pct(ch[0].margin_pct)} margin — volume may be subsidizing mix.`, tone: 'warn' });
    const wf = a.margin_waterfall || [];
    const drag = wf.filter(r => (r.mix_contribution || 0) < 0).slice(0, 1)[0];
    if (drag) items.push({ title: 'Mix drag', body: `${drag.family} pulls portfolio margin (${num(drag.mix_contribution, 2)} contribution pts).`, tone: 'warn' });
    const pr = [...(a.price_realization || [])].sort((x, y) => (x.realization || 1) - (y.realization || 1))[0];
    if (pr) items.push({ title: 'Deepest discount', body: `${pr.family} realizes ${num(pr.realization, 2)} of list — check Trade vs Consumer deal depth.`, tone: '' });
  }
  if (section === 'season') {
    const peaks = a.lead_vs_peak || [];
    peaks.filter(r => r.risk_flag === 'Buy ahead').slice(0, 2).forEach(r => {
      items.push({ title: `${r.family} peak risk`, body: `Peak month ${r.peak_month} (index ${num(r.peak_index, 2)}) with ${r.long_lead_skus}/${r.skus} long-lead SKUs — buy ahead.`, tone: 'warn' });
    });
    const yoy = (a.yoy_family || []).filter(r => r.yoy_pct != null).sort((x, y) => Math.abs(y.yoy_pct) - Math.abs(x.yoy_pct))[0];
    if (yoy) items.push({ title: 'Largest YoY swing', body: `${yoy.family} month ${yoy.month_num}: ${pct(yoy.yoy_pct)} vs prior year.`, tone: Number(yoy.yoy_pct) < 0 ? 'warn' : 'good' });
  }
  if (section === 'field') {
    const grades = a.rep_grade || [];
    const top = grades[0];
    const bottom = [...grades].reverse()[0];
    if (top) items.push({ title: `Top rep · ${top.grade}`, body: `${top.rep}: composite ${num(top.composite, 1)} · attainment ${pct(top.attainment_pct)} · mix ${pct(top.mix_pct)}.`, tone: 'good' });
    if (bottom && bottom !== top) items.push({ title: `Needs coaching · ${bottom.grade}`, body: `${bottom.rep}: margin ${pct(bottom.margin_pct)} vs peers — grade on discipline, not vanity volume.`, tone: 'warn' });
    const ws = a.whitespace || [];
    if (ws[0]) items.push({ title: 'Whitespace', body: `${ws[0].name} at ${num(ws[0].vs_peer, 2)}× region peer — coverage gap, not product gap.`, tone: 'warn' });
  }
  if (section === 'supply') {
    const vendors = a.vendor_scorecard || [];
    const exit = vendors.filter(v => v.tier === 'Exit');
    const prefer = vendors.filter(v => v.tier === 'Prefer');
    if (exit[0]) items.push({ title: 'Exit candidate', body: `${exit[0].name}: score ${num(exit[0].score, 1)} · OTIF ${pct(exit[0].otif_pct)} · quality ${pct(exit[0].quality_pct)}.`, tone: 'warn' });
    if (prefer[0]) items.push({ title: 'Prefer supplier', body: `${prefer[0].name}: score ${num(prefer[0].score, 1)} — protect allocation.`, tone: 'good' });
    const plan = (a.plan_vs_season || []).filter(r => r.plan_action === 'Pull forward')[0];
    if (plan) items.push({ title: 'Pull forward', body: `${plan.family}: ${plan.reorder_skus} reorder SKUs before peak month ${plan.peak_month}.`, tone: 'warn' });
  }
  if (section === 'core') {
    const risk = a.stock_risk || [];
    if (risk.length) items.push({ title: 'Stock risk', body: `${risk.length} SKUs with sell-through ≥ 2× on-hand — open Supply for reorder + lead.`, tone: 'warn' });
  }
  return items.slice(0, 4);
}

const SECTIONS = {
  core: {
    blurb: 'Channel · family · region · stock risk',
    panels: [
      { title: 'Sales by channel', key: 'by_channel', chart: { label: 'channel', value: 'net_sales', money: true } },
      { title: 'Sales by family', key: 'by_family', chart: { label: 'family', value: 'net_sales', money: true } },
      { title: 'Sales by region', key: 'by_region', chart: { label: 'region', value: 'net_sales', money: true } },
      { title: 'Stock risk SKUs', key: 'stock_risk' },
    ],
  },
  margin: {
    blurb: 'Where margin leaks — mix, realization, SKU exceptions',
    panels: [
      { title: 'Margin % by channel', key: 'margin_pct', chart: { label: 'channel', value: 'margin_pct', pct: true } },
      { title: 'Margin waterfall (mix contribution)', key: 'margin_waterfall', chart: { label: 'family', value: 'mix_contribution', digits: 2 } },
      { title: 'Price realization vs list', key: 'price_realization', chart: { label: 'family', value: 'realization', digits: 3 } },
      { title: 'Low-margin SKUs', key: 'low_margin_skus' },
    ],
  },
  season: {
    blurb: 'Seasonal index heat · YoY · lead vs peak',
    panels: [
      { title: 'Seasonal index heatmap', key: 'seasonal_index', heat: true },
      { title: 'Units trend (24 mo)', key: 'units_by_month', spark: true },
      { title: 'YoY by family-month', key: 'yoy_family' },
      { title: 'Lead time vs seasonal peak', key: 'lead_vs_peak' },
    ],
  },
  field: {
    blurb: 'Territories · whitespace · rep grades (not vanity volume)',
    panels: [
      { title: 'Territory performance', key: 'territory_perf', chart: { label: 'territory', value: 'net_sales', money: true } },
      { title: 'Territory coverage vs capacity', key: 'territory_coverage', chart: { label: 'territory', value: 'capacity_pct', pct: true } },
      { title: 'Whitespace dealers', key: 'whitespace' },
      { title: 'Rep grades (A–D)', key: 'rep_grade' },
      { title: 'Rep leaderboard', key: 'rep_leaderboard' },
    ],
  },
  supply: {
    blurb: 'Days of cover · reorder · plan vs season · vendor Prefer/Watch/Exit',
    panels: [
      { title: 'Days of cover by family', key: 'days_of_cover', chart: { label: 'family', value: 'days_of_cover', digits: 1 } },
      { title: 'Plan vs season', key: 'plan_vs_season' },
      { title: 'Reorder candidates', key: 'reorder_candidates' },
      { title: 'Vendor scorecard', key: 'vendor_scorecard', chart: { label: 'name', value: 'score', digits: 1 } },
      { title: 'Vendor OTIF', key: 'vendor_otif', chart: { label: 'name', value: 'otif_pct', pct: true } },
    ],
  },
};

let analyticsCache = null;
let analyticsSection = 'core';

function showTab(name) {
  document.querySelectorAll('.tab').forEach(el => { el.hidden = el.id !== name; });
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
}

function renderAnalyticsSection() {
  if (!analyticsCache) return;
  const a = analyticsCache;
  const spec = SECTIONS[analyticsSection] || SECTIONS.core;
  const insights = insightCards(buildInsights(analyticsSection, a));
  const head = `<div class="analytics-head">`
    + `<div><p class="fine">${esc(spec.blurb)}</p>`
    + `<p class="fine">Scope <strong>${esc(a.dealer_scope)}</strong> · net ${money(a.summary?.net_sales)} · margin ${money(a.summary?.margin)}`
    + (a.summary?.margin_pct != null ? ` (${pct(a.summary.margin_pct)})` : '')
    + ` · ${num(a.elapsed_ms)} ms</p></div></div>`;

  const panels = spec.panels.map(p => {
    let rows = a[p.key] || [];
    if (p.key === 'units_by_month' && rows.length > 200) rows = rows.slice(-200);
    let viz = '';
    if (p.heat) viz = seasonHeatmap(rows);
    else if (p.spark) viz = sparklineByFamily(rows);
    else if (p.chart) viz = barChart(rows, p.chart.label, p.chart.value, p.chart);
    const table = p.heat ? '' : htmlTable(rows, p.key === 'units_by_month' ? 36 : 20);
    return `<article class="panel-rich"><h3>${esc(p.title)}</h3>${viz}${table}</article>`;
  }).join('');

  document.getElementById('analytics-panels').innerHTML = head + insights + `<div class="panels-rich">${panels}</div>`;
}

async function loadOverview() {
  const [health, summary, portfolio, analytics] = await Promise.all([
    api('/api/health'),
    api('/api/summary'),
    api('/api/metric?name=portfolio'),
    api('/api/analytics').catch(() => null),
  ]);
  if (analytics) analyticsCache = analytics;
  document.getElementById('backend').textContent = health.backend.toUpperCase();
  const marginPct = analytics?.summary?.margin_pct;
  document.getElementById('summary').innerHTML = [
    ['Dealers', summary.dealers],
    ['Active SKUs', summary.skus],
    ['Units sold', num(summary.units_sold)],
    ['Net sales', money(summary.net_sales)],
    ['Margin', money(summary.margin)],
    ['Margin %', marginPct != null ? pct(marginPct) : '—'],
    ['On hand', num(summary.on_hand)],
    ['Quarantined', summary.quarantined],
  ].map(([k, v]) => `<div><span>${k}</span><strong>${v}</strong></div>`).join('');

  const ch = analytics?.by_channel || [];
  const preview = document.getElementById('portfolio');
  preview.innerHTML = `<div class="overview-grid">`
    + `<div><h3>Channel mix</h3>${barChart(ch, 'channel', 'net_sales', { money: true })}</div>`
    + `<div><h3>Dealer portfolio</h3>${htmlTable(portfolio.rows, 15)}</div>`
    + `</div>`;
}

async function loadAnalytics() {
  document.getElementById('analytics-panels').innerHTML = '<p class="fine">Loading governed metrics…</p>';
  if (!analyticsCache) analyticsCache = await api('/api/analytics');
  else {
    // refresh in background for freshness
    api('/api/analytics').then(a => { analyticsCache = a; renderAnalyticsSection(); }).catch(() => {});
  }
  renderAnalyticsSection();
}

async function ask(mode) {
  const qEl = document.getElementById(mode === 'today' ? 'q-today' : 'q-proposed');
  const out = document.getElementById(mode === 'today' ? 'out-today' : 'out-proposed');
  out.classList.remove('out-rich');
  out.textContent = '…';
  try {
    const data = await api('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: qEl.value, mode }),
    });
    out.innerHTML = renderAsk(data);
    out.classList.add('out-rich');
  } catch (e) {
    out.textContent = JSON.stringify({ error: e.message }, null, 2);
  }
}

function metricInsight(name, rows) {
  if (!rows || !rows.length) return 'Governed metric returned no rows for this scope.';
  const r0 = rows[0];
  if (name === 'margin_pct' && r0.channel != null) {
    return `Thinnest channel in result set: ${r0.channel} at ${pct(r0.margin_pct)} margin.`;
  }
  if (name === 'vendor_scorecard' && r0.tier) {
    return `Top of list: ${r0.name} → ${r0.tier} (score ${num(r0.score, 1)}).`;
  }
  if (name === 'rep_grade' && r0.grade) {
    return `Highest composite: ${r0.rep} grade ${r0.grade} (attainment ${pct(r0.attainment_pct)}).`;
  }
  if (name === 'reorder_candidates') {
    return `${rows.length} SKUs need reorder attention (safety stock or days-of-cover vs lead).`;
  }
  if (name === 'seasonal_index' || name === 'lead_vs_peak') {
    return `Seasonality grounded in silver_monthly — peak/lead conflicts flagged as Buy ahead.`;
  }
  if (name === 'by_channel' || name === 'by_family' || name === 'by_region') {
    return `Top slice: ${Object.values(r0)[0]} · ${money(r0.net_sales)} net.`;
  }
  return `Returned ${rows.length} rows from governed metric \`${name}\`.`;
}

function renderAsk(data) {
  const kind = data.kind || 'unknown';
  const mode = esc(data.mode || '');
  if (kind === 'metric') {
    const insight = metricInsight(data.metric, data.rows);
    const chartKeys = {
      by_channel: ['channel', 'net_sales'],
      by_family: ['family', 'net_sales'],
      margin_pct: ['channel', 'margin_pct'],
      vendor_scorecard: ['name', 'score'],
      rep_grade: ['rep', 'composite'],
      territory_perf: ['territory', 'net_sales'],
    };
    const ck = chartKeys[data.metric];
    let viz = '';
    if (ck) {
      const opts = ck[1].includes('pct') || ck[1] === 'score' || ck[1] === 'composite'
        ? (ck[1].includes('pct') ? { pct: true } : { digits: 1 })
        : { money: true };
      viz = barChart(data.rows, ck[0], ck[1], opts);
    }
    return `<div class="ask-card">`
      + `<p class="ask-meta">${mode} · <strong>${esc(data.metric)}</strong></p>`
      + `<p class="ask-insight">${esc(insight)}</p>`
      + `<p class="fine">${esc(data.description || '')}</p>`
      + viz
      + htmlTable(data.rows, 12)
      + `<details><summary>SQL + tool trace</summary><pre class="out">${esc(data.sql || '')}\n\nparams: ${esc(JSON.stringify(data.parameters))}\n\n${esc((data.trace || []).join(' → '))}</pre></details>`
      + `</div>`;
  }
  if (kind === 'faq') {
    return `<div class="ask-card">`
      + `<p class="ask-meta">${mode} · FAQ <code>${esc(data.source || '')}</code></p>`
      + `<p class="ask-insight">${esc(data.answer)}</p>`
      + (data.improvement_gap ? `<p class="fine warn-text">${esc(data.improvement_gap)}</p>` : '')
      + `<p class="fine">${esc((data.trace || []).join(' → '))}</p>`
      + `</div>`;
  }
  if (kind === 'escalate') {
    return `<div class="ask-card">`
      + `<p class="ask-meta">${mode} · escalate</p>`
      + `<p class="ask-insight">${esc(data.answer)}</p>`
      + (data.improvement_gap ? `<p class="fine warn-text">${esc(data.improvement_gap)}</p>` : '')
      + `</div>`;
  }
  if (kind === 'catalog') {
    return `<div class="ask-card">`
      + `<p class="ask-meta">${mode} · catalog</p>`
      + `<p class="ask-insight">${esc(data.answer)}</p>`
      + htmlTable(data.rows, 8)
      + `</div>`;
  }
  if (kind === 'clarify') {
    return `<div class="ask-card">`
      + `<p class="ask-meta">${mode} · clarify</p>`
      + `<p class="ask-insight">${esc(data.answer)}</p>`
      + `</div>`;
  }
  return `<pre class="out">${esc(JSON.stringify(data, null, 2))}</pre>`;
}

async function escalate() {
  const out = document.getElementById('out-proposed');
  out.classList.add('out-rich');
  const data = await api('/api/escalate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: document.getElementById('q-proposed').value,
      lane: 'Consumer|Trade',
      reason: 'demo_handoff',
    }),
  });
  out.innerHTML = `<div class="ask-card">`
    + `<p class="ask-meta">escalation packet</p>`
    + `<p class="ask-insight">${esc(data.note || 'Structured handoff')}</p>`
    + `<pre class="out">${esc(JSON.stringify(data.escalation, null, 2))}</pre>`
    + `</div>`;
}

async function loadCatalog() {
  const q = document.getElementById('catalog-q').value.trim();
  const rows = await api('/api/products' + (q ? `?q=${encodeURIComponent(q)}` : ''));
  document.getElementById('catalog-out').innerHTML = htmlTable(rows, 40);
}

async function boot() {
  const sess = await api('/api/session');
  if (!sess.authenticated) { location.href = '/login'; return; }
  document.getElementById('who').textContent = sess.session.label || sess.session.username;
  document.querySelectorAll('nav button').forEach(b => b.addEventListener('click', () => {
    showTab(b.dataset.tab);
    if (b.dataset.tab === 'analytics') loadAnalytics();
    if (b.dataset.tab === 'catalog') loadCatalog();
  }));
  document.querySelectorAll('#analytics-subnav button').forEach(b => {
    b.addEventListener('click', () => {
      analyticsSection = b.dataset.section;
      document.querySelectorAll('#analytics-subnav button').forEach(x => x.classList.toggle('active', x === b));
      renderAnalyticsSection();
    });
  });
  document.getElementById('ask-today').onclick = () => ask('today');
  document.getElementById('ask-proposed').onclick = () => ask('proposed');
  document.getElementById('escalate').onclick = escalate;
  document.getElementById('catalog-q').addEventListener('change', loadCatalog);
  document.getElementById('logout').onclick = async () => {
    await api('/api/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    location.href = '/';
  };
  await loadOverview();
}

boot().catch(err => {
  document.body.insertAdjacentHTML('beforeend', `<p class="err">${err.message}</p>`);
});
