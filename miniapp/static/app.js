/* NAYI Mini App · v3 */
(() => {
'use strict';
const tg = window.Telegram?.WebApp;
const DEMO = !tg?.initData;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const app = $('#app');

const state = { plans: [], panels: [], services: [], balance: 0, month: null, selected: null, panelId: null, view: 'shop', busy: false, loaded: false };

/* ---------- helpers ---------- */
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = n => Number(n || 0).toLocaleString('en-US');
const money = n => num(n) + ' تومان';
const monthName = m => ({ 1: 'یک ماهه', 2: 'دو ماهه', 3: 'سه ماهه', 6: 'شش ماهه', 12: 'یک ساله' }[m] || `${m} ماهه`);
const haptic = (t = 'light') => { try { t === 'ok' || t === 'err' ? tg?.HapticFeedback?.notificationOccurred(t === 'ok' ? 'success' : 'error') : tg?.HapticFeedback?.impactOccurred(t); } catch (_) {} };
const store = { get: k => { try { return localStorage.getItem(k); } catch (_) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} } };

let toastTimer;
function toast(msg, type = 'ok') {
  const t = $('#toast');
  t.textContent = msg; t.className = 'toast show' + (type === 'err' ? ' err' : '');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
}

async function api(url, opt = {}) {
  let r;
  try {
    r = await fetch(url, { ...opt, headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg?.initData || '', ...(opt.headers || {}) } });
  } catch (_) { throw new Error('اتصال به سرور برقرار نشد'); }
  let j = {};
  try { j = await r.json(); } catch (_) {}
  if (!r.ok) {
    const d = j.detail;
    throw Object.assign(new Error(typeof d === 'string' ? d : 'خطای سرور (' + r.status + ')'), { status: r.status });
  }
  return j;
}

/* ---------- demo data (browser preview only) ---------- */
const demoData = () => ({
  balance: 450000,
  panels: [{ id: 1, name: 'آلمان', ptype: 'marzban' }, { id: 2, name: 'هلند', ptype: 'marzban' }],
  plans: [
    { id: 1, months: 1, gb: 20, days: 30, price: 89000 }, { id: 2, months: 1, gb: 50, days: 30, price: 149000 }, { id: 3, months: 1, gb: 100, days: 30, price: 229000 },
    { id: 4, months: 3, gb: 100, days: 90, price: 349000 }, { id: 5, months: 3, gb: 200, days: 90, price: 529000 },
    { id: 6, months: 6, gb: 300, days: 180, price: 899000 }
  ],
  services: [{ id: 7, name: 'nayi_1024_a3f1', gb: 50, days: 30, expire: Math.floor(Date.now() / 1000) + 19 * 86400, status: 'active', link: 'vless://demo-config@de.nayi.example:443?security=reality#NAYI', sub: 'https://sub.nayi.example/s/demo', qr: '' }]
});

/* ---------- theme ---------- */
const HERO = {
  space: { t: 'سفرت را<br><em>شروع کن.</em>', p: 'اتصال سریع و بی‌مرز، برای مدار دیجیتال تو.', sub: 'NAYI · DEEP SPACE', c: '#060b1a' },
  ocean: { t: 'آرامش را<br><em>انتخاب کن.</em>', p: 'اتصالی نرم و پیوسته، مثل موجی که به ساحل می‌رسد.', sub: 'NAYI · OPEN SEA', c: '#04222f' }
};
function setTheme(name, quiet) {
  if (!HERO[name]) name = 'space';
  app.classList.remove('theme-space', 'theme-ocean'); app.classList.add('theme-' + name);
  $$('.theme-switch button').forEach(b => b.setAttribute('aria-checked', b.dataset.theme === name));
  const h = HERO[name];
  $('#heroTitle').innerHTML = h.t; $('#heroText').textContent = h.p; $('#brandSub').textContent = h.sub;
  document.querySelector('meta[name=theme-color]').content = h.c;
  try { tg?.setHeaderColor?.(h.c); tg?.setBackgroundColor?.(h.c); } catch (_) {}
  store.set('nayi-theme', name);
  if (!quiet) haptic('light');
}

/* ---------- starfield ---------- */
function sky() {
  const c = $('#sky'), x = c.getContext('2d'); let stars = [], w, h, dpr;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  function size() {
    dpr = Math.min(devicePixelRatio || 1, 2); w = c.offsetWidth; h = c.offsetHeight;
    c.width = w * dpr; c.height = h * dpr; x.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = Array.from({ length: Math.round(w * h / 5000) }, () => ({ x: Math.random() * w, y: Math.random() * h, r: Math.random() * 1.3 + .2, a: Math.random() * Math.PI * 2, s: Math.random() * .015 + .004, v: Math.random() * .08 + .02 }));
  }
  function frame() {
    x.clearRect(0, 0, w, h);
    for (const s of stars) {
      s.a += s.s; s.y += s.v; if (s.y > h) s.y = 0;
      x.globalAlpha = .35 + Math.sin(s.a) * .35; x.fillStyle = '#d6f6ff';
      x.beginPath(); x.arc(s.x, s.y, s.r, 0, 6.283); x.fill();
    }
    if (!reduce) requestAnimationFrame(frame);
  }
  size(); frame(); addEventListener('resize', () => { size(); if (reduce) frame(); });
}

/* ---------- shop ---------- */
function usablePanels() { return state.panels.filter(p => p.ptype !== 'manual'); }
function months() {
  const ms = [...new Set(state.plans.map(p => Number(p.months)))].filter(Boolean).sort((a, b) => a - b);
  return ms.length ? ms : [1, 3, 6];
}

function renderShop() {
  const step = state.selected ? 3 : state.month ? 2 : 1;
  $$('#steps li').forEach(li => { const n = +li.dataset.step; li.classList.toggle('on', n === step); li.classList.toggle('done', n < step); });
  $('#stepTitle').textContent = state.month ? 'پلن ' + monthName(state.month) + ' را انتخاب کن' : 'مدت اشتراک را انتخاب کن';
  $('#back').classList.toggle('hidden', !state.month);
  $('#skeleton').classList.toggle('hidden', state.loaded);
  $('#months').classList.toggle('hidden', !state.loaded || !!state.month);
  $('#plans').classList.toggle('hidden', !state.month);

  if (!state.loaded) return syncChrome();

  if (!state.month) {
    const ms = months();
    // best value: lowest price per day across plans
    let best = null, bestRate = Infinity;
    ms.forEach(m => state.plans.filter(p => +p.months === m).forEach(p => { const r = p.price / Math.max(p.days, 1); if (r < bestRate) { bestRate = r; best = m; } }));
    $('#months').innerHTML = ms.map(m => {
      const list = state.plans.filter(p => +p.months === m);
      const min = list.length ? Math.min(...list.map(p => p.price)) : 0;
      return `<button type="button" class="month ${m === best && ms.length > 1 ? 'best' : ''}" data-month="${m}" ${list.length ? '' : 'disabled'}>
        <span class="m-num">${m}</span><strong>${monthName(m)}</strong><small>${list.length ? list.length + ' پلن' : 'به‌زودی'}</small>
        <span class="from">${list.length ? 'از <span class="num">' + num(min) + '</span>' : '—'}</span><i class="ring"></i></button>`;
    }).join('');
  }

  // panels
  const panels = usablePanels();
  $('#panels').classList.toggle('hidden', !state.month || panels.length < 2);
  if (panels.length && !panels.some(p => p.id === state.panelId)) state.panelId = panels[0].id;
  $('#panels').innerHTML = panels.map(p => `<button type="button" class="chip ${p.id === state.panelId ? 'on' : ''}" data-panel="${p.id}">${esc(p.name || 'سرور ' + p.id)}</button>`).join('');

  if (state.month) {
    const list = state.plans.filter(p => +p.months === state.month).sort((a, b) => a.price - b.price);
    $('#plans').innerHTML = list.length ? list.map(p => `
      <button type="button" class="plan ${state.selected?.id === p.id ? 'picked' : ''}" data-id="${p.id}" aria-pressed="${state.selected?.id === p.id}">
        <span class="gb"><b class="num">${num(p.gb)}</b><small>GB</small></span>
        <span class="meta"><b>${num(p.gb)} گیگ · ${num(p.days)} روز</b><small>حدود ${num(Math.round(p.gb / Math.max(p.days, 1) * 10) / 10)} گیگ در روز</small></span>
        <span class="price"><b class="num">${num(p.price)}</b><small>تومان</small></span>
      </button>`).join('')
      : `<div class="empty"><b>✧</b>برای این مدت هنوز پلنی تعریف نشده.<button type="button" class="ghost" data-act="back">انتخاب مدت دیگر</button></div>`;
  }

  // checkout bar
  const co = $('#checkout');
  co.classList.toggle('show', state.view === 'shop' && !!state.selected);
  if (state.selected) {
    $('#choice').textContent = `${num(state.selected.gb)} گیگ · ${num(state.selected.days)} روز`;
    $('#choicePrice').textContent = num(state.selected.price);
  }
  const noPanel = !panels.length;
  $('#buy').disabled = noPanel;
  $('#buy').textContent = noPanel ? 'سرور در دسترس نیست' : 'خرید';
  syncChrome();
}

/* ---------- services ---------- */
function statusTag(s, left) {
  if (s.status === 'active' && left !== 0) return '<span class="tag ok">فعال</span>';
  if (s.status === 'active' && left === 0) return '<span class="tag off">منقضی</span>';
  if (['expired', 'disabled', 'limited'].includes(s.status)) return '<span class="tag off">غیرفعال</span>';
  return '<span class="tag wait">در انتظار فعال‌سازی</span>';
}
function renderServices() {
  const list = $('#serviceList');
  const active = state.services.filter(s => s.status === 'active').length;
  $('#svcBadge').textContent = active; $('#svcBadge').classList.toggle('hidden', !active);
  if (!state.services.length) {
    list.innerHTML = `<div class="empty"><b>◈</b>هنوز سرویسی نداری.<br>اولین مدارت رو بساز.<button type="button" class="ghost" data-go="shop">رفتن به خرید</button></div>`;
    return;
  }
  const now = Date.now() / 1000;
  list.innerHTML = state.services.map(s => {
    const left = s.expire ? Math.max(0, Math.ceil((s.expire - now) / 86400)) : null;
    const pct = left != null && s.days ? Math.min(100, Math.round(left / s.days * 100)) : 0;
    const exp = s.expire ? new Date(s.expire * 1000).toLocaleDateString('en-GB') : '—';
    const cfg = [s.link && ['کانفیگ', s.link], s.sub && ['لینک ساب', s.sub]].filter(Boolean);
    return `<article class="svc">
      <div class="svc-top"><b class="latin">${esc(s.name || 'NAYI')}</b>${statusTag(s, left)}</div>
      ${left != null ? `<div class="meter"><i style="width:${pct}%"></i></div><div class="meter-l"><span><span class="num">${num(left)}</span> روز باقی‌مانده</span><span class="num">${pct}%</span></div>` : ''}
      <div class="svc-stats">
        <span><b class="num">${num(s.gb)}</b><small>گیگابایت</small></span>
        <span><b class="num">${num(s.days)}</b><small>روز</small></span>
        <span><b class="num">${exp}</b><small>انقضا</small></span>
      </div>
      ${cfg.length ? cfg.map(([label, v]) => `<div class="cfg"><code title="${esc(label)}">${esc(v)}</code><button type="button" class="mini" data-copy="${esc(v)}">کپی ${label}</button></div>`).join('')
        : '<div class="cfg"><code>کانفیگ هنوز تحویل نشده</code></div>'}
      ${s.qr ? `<div class="cfg" style="margin-top:8px"><code>QR Code</code><button type="button" class="mini alt" data-qr="${s.id}">نمایش QR</button></div><div class="qr-box" id="qr-${s.id}"><img alt="QR" src="${esc(s.qr)}" loading="lazy"></div>` : ''}
    </article>`;
  }).join('');
}

/* ---------- profile ---------- */
async function loadProfile() {
  if (DEMO) return fillProfile({ id: 1024, name: 'کاربر نمایشی', username: 'nayi_demo', balance: state.balance, services: state.services.length });
  try { fillProfile(await api('/api/profile')); } catch (e) { toast(e.message, 'err'); }
}
function fillProfile(p) {
  const name = p.name || tg?.initDataUnsafe?.user?.first_name || 'کاربر نایی';
  $('#profileName').textContent = name;
  $('#avatar').textContent = (name.trim()[0] || 'N').toUpperCase();
  $('#profileUser').textContent = p.username ? '@' + p.username : 'حساب تلگرام';
  $('#profileId').textContent = p.id ?? '—';
  $('#profileBalance').textContent = money(p.balance);
  $('#profileServices').textContent = num(p.services);
  $('#profileActive').textContent = num(p.active ?? state.services.filter(s => s.status === 'active').length);
  if (typeof p.balance === 'number') { state.balance = p.balance; paintWallet(); }
}

/* ---------- navigation & chrome ---------- */
function show(v) {
  state.view = v;
  $$('.view').forEach(x => x.classList.toggle('active', x.id === 'view-' + v));
  const idx = ['shop', 'services', 'profile'].indexOf(v);
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $('.tab-ink').style.transform = `translateX(${-idx * 100}%)`;
  if (v === 'services') renderServices();
  if (v === 'profile') loadProfile();
  renderShop(); haptic('light');
  scrollTo({ top: 0, behavior: 'smooth' });
}
function goBack() {
  if (isOpen()) return closeModal();
  if (state.view !== 'shop') return show('shop');
  if (state.month) { state.month = null; state.selected = null; renderShop(); }
}
function syncChrome() {
  if (!tg?.BackButton) return;
  (state.view !== 'shop' || state.month || isOpen()) ? tg.BackButton.show() : tg.BackButton.hide();
}
function paintWallet() { $('#walletAmount').textContent = state.loaded ? num(state.balance) : '—'; }

/* ---------- checkout modal ---------- */
const isOpen = () => $('#modal').classList.contains('open');
function openModal() {
  if (!state.selected) return;
  if (!usablePanels().length) return toast('در حال حاضر سروری برای ساخت سرویس متصل نیست', 'err');
  const p = state.selected, after = state.balance - p.price, short = after < 0;
  $('#modalChoice').textContent = `${monthName(p.months)} · ${num(p.gb)} گیگ`;
  $('#billPrice').textContent = money(p.price);
  $('#billBalance').textContent = money(state.balance);
  $('#billAfter').textContent = short ? 'ناکافی' : money(after);
  $('#billAfter').classList.toggle('neg', short);
  $('#billWarn').classList.toggle('hidden', !short);
  $('#approve').disabled = short;
  $('#modal').classList.add('open'); $('#modal').setAttribute('aria-hidden', 'false');
  haptic('medium'); syncChrome();
}
function closeModal() { $('#modal').classList.remove('open'); $('#modal').setAttribute('aria-hidden', 'true'); syncChrome(); }

async function approve() {
  if (state.busy || !state.selected) return;
  if (DEMO) { closeModal(); return toast('در پیش‌نمایش خرید غیرفعاله؛ از داخل ربات امتحان کن', 'err'); }
  state.busy = true; const btn = $('#approve'); btn.disabled = true; btn.classList.add('loading');
  try {
    const d = await api('/api/buy', { method: 'POST', body: JSON.stringify({ plan_id: state.selected.id, panel_id: state.panelId }) });
    state.balance = d.balance; state.services = [d.service, ...state.services.filter(s => s.id !== d.service.id)];
    state.month = null; state.selected = null; paintWallet(); closeModal(); show('services');
    haptic('ok'); toast('سرویس با موفقیت ساخته شد ✓');
    load(true);
  } catch (e) {
    haptic('err'); toast(e.message || 'خرید انجام نشد و موجودی کم نشد', 'err');
    if (e.status === 402 || e.status === 409) load(true);
    closeModal();
  } finally { state.busy = false; btn.classList.remove('loading'); btn.disabled = false; }
}

/* ---------- data ---------- */
async function load(silent) {
  try {
    const d = DEMO ? demoData() : await api('/api/catalog');
    state.plans = (d.plans || []).map(p => ({ ...p, months: +p.months, price: +p.price, gb: +p.gb, days: +p.days }));
    state.panels = d.panels || []; state.services = d.services || []; state.balance = +d.balance || 0;
    if (state.selected) state.selected = state.plans.find(p => p.id === state.selected.id) || null;
    state.loaded = true;
  } catch (e) {
    state.loaded = true;
    if (!silent) {
      $('#months').innerHTML = '';
      toast(e.status === 401 ? 'نشست تلگرام نامعتبره؛ مینی‌اپ رو دوباره باز کن' : e.message, 'err');
    }
  }
  paintWallet(); renderShop(); renderServices();
  if (state.loaded && !state.plans.length) $('#months').innerHTML = `<div class="empty" style="grid-column:1/-1"><b>✧</b>فعلاً پلنی برای فروش فعال نیست.<button type="button" class="ghost" data-act="reload">تلاش دوباره</button></div>`;
}

/* ---------- copy ---------- */
async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch (_) { const t = document.createElement('textarea'); t.value = text; t.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(t); t.select(); document.execCommand('copy'); t.remove(); }
  haptic('ok'); toast('کپی شد ✓');
}

/* ---------- events (delegated, bound once) ---------- */
document.addEventListener('click', e => {
  const t = e.target.closest('button'); if (!t) return;
  if (t.dataset.month) { state.month = +t.dataset.month; state.selected = null; renderShop(); haptic('light'); return; }
  if (t.dataset.id) { const p = state.plans.find(x => x.id == t.dataset.id); state.selected = state.selected?.id === p?.id ? null : p; renderShop(); haptic('light'); return; }
  if (t.dataset.panel) { state.panelId = +t.dataset.panel; renderShop(); haptic('light'); return; }
  if (t.dataset.view) return show(t.dataset.view);
  if (t.dataset.go) return show(t.dataset.go);
  if (t.dataset.theme) return setTheme(t.dataset.theme);
  if (t.dataset.copy) return copy(t.dataset.copy);
  if (t.dataset.qr) { const b = $('#qr-' + t.dataset.qr); const o = b.classList.toggle('open'); t.textContent = o ? 'بستن QR' : 'نمایش QR'; return; }
  if (t.dataset.act === 'back') return goBack();
  if (t.dataset.act === 'reload') return load();
});
$('#back').addEventListener('click', goBack);
$('#buy').addEventListener('click', openModal);
$('#close').addEventListener('click', closeModal);
$('#approve').addEventListener('click', approve);
$('#walletChip').addEventListener('click', () => show('profile'));
$('#refresh').addEventListener('click', async () => { await load(); toast('به‌روز شد ✓'); });
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') goBack(); });
tg?.BackButton?.onClick(goBack);

/* ---------- boot ---------- */
if (tg) { tg.ready(); tg.expand(); try { tg.disableVerticalSwipes?.(); } catch (_) {} }
if (DEMO) $('#demoBar').classList.remove('hidden');
setTheme(store.get('nayi-theme') || 'space', true);
sky(); renderShop(); load();
})();
