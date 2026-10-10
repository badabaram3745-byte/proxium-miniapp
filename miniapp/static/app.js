/* NAYI Mini App · v4 */
(() => {
'use strict';
const tg = window.Telegram?.WebApp;
const DEMO = !tg?.initData;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const app = $('#app');
const PAGE = 6;

const S = { plans: [], panels: [], services: [], balance: 0, month: null, selected: null, panelId: null, view: 'shop',
  busy: false, loaded: false, features: {}, hasTest: false, filter: 'all', shown: PAGE, guideOs: null, renewSvc: null, renewPlan: null,
  discount: null, me: null, bot: '', support: '', tx: [], topupAmount: 250000, awaitingWallet: false };

/* ---------- helpers ---------- */
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = n => Number(n || 0).toLocaleString('en-US');
const money = n => num(n) + ' تومان';
const monthName = m => ({ 1: 'یک ماهه', 2: 'دو ماهه', 3: 'سه ماهه', 6: 'شش ماهه', 12: 'یک ساله' }[m] || `${m} ماهه`);
const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleDateString('en-GB') : '—';
const nowS = () => Date.now() / 1000;
const daysLeft = s => s.expire ? Math.max(0, Math.ceil((s.expire - nowS()) / 86400)) : null;
const haptic = t => { try { if (t === 'ok' || t === 'err') tg?.HapticFeedback?.notificationOccurred(t === 'ok' ? 'success' : 'error'); else tg?.HapticFeedback?.impactOccurred(t || 'light'); } catch (_) {} };
const lsGet = k => { try { return localStorage.getItem(k); } catch (_) { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} };
const sleep = ms => new Promise(r => setTimeout(r, ms));

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
  } catch (_) { throw Object.assign(new Error('اتصال به سرور برقرار نشد'), { status: 0 }); }
  let j = {};
  try { j = await r.json(); } catch (_) {}
  if (!r.ok) {
    const d = j.detail;
    throw Object.assign(new Error(typeof d === 'string' ? d : 'خطای سرور (' + r.status + ')'), { status: r.status });
  }
  return j;
}

/* ---------- demo data (preview only) ---------- */
const demo = () => ({
  balance: 450000,
  panels: [{ id: 1, name: 'آلمان', ptype: 'marzban' }, { id: 2, name: 'هلند', ptype: 'marzban' }, { id: 3, name: 'فرانسه', ptype: 'marzban' }],
  plans: [
    { id: 1, months: 1, gb: 20, days: 30, price: 89000, orig: 89000 }, { id: 2, months: 1, gb: 50, days: 30, price: 149000, orig: 149000 }, { id: 3, months: 1, gb: 100, days: 30, price: 229000, orig: 229000 },
    { id: 4, months: 3, gb: 100, days: 90, price: 349000, orig: 399000 }, { id: 5, months: 3, gb: 200, days: 90, price: 529000, orig: 529000 },
    { id: 6, months: 6, gb: 300, days: 180, price: 899000, orig: 999000 }
  ],
  services: [
    { id: 7, name: 'nayi_1024_a3f1', gb: 50, days: 30, expire: nowS() + 19 * 86400, status: 'active', link: 'vless://demo@de.nayi.example:443?security=reality#NAYI-DE', sub: 'https://sub.nayi.example/s/demo1', panel: 'آلمان', panel_id: 1, is_test: 0, price: 149000, created: nowS() - 11 * 86400 },
    { id: 8, name: 'nayi_1024_t7c2', gb: 2, days: 1, expire: nowS() + 1 * 86400, status: 'active', link: 'vless://demo@nl.nayi.example:443#NAYI-NL-TEST', sub: '', panel: 'هلند', panel_id: 2, is_test: 1, price: 0, created: nowS() - 86400 * 0.5 },
    { id: 9, name: 'nayi_1024_b9d8', gb: 20, days: 30, expire: nowS() - 4 * 86400, status: 'expired', link: '', sub: '', panel: 'آلمان', panel_id: 1, is_test: 0, price: 89000, created: nowS() - 40 * 86400 }
  ],
  features: { renew: true, usage: true, discount: true, test: true, test_gb: 2, test_days: 1 },
  has_test: true, bot: 'NayiBot', support: 'nayi_support'
});

/* ---------- theme ---------- */
const THEMES = {
  space: { t: 'سفرت را<br><em>شروع کن.</em>', p: 'اتصال سریع و بی‌مرز، برای مدار دیجیتال تو.', sub: 'NAYI · DEEP SPACE', c: '#060b1a' },
  ocean: { t: 'آرامش را<br><em>انتخاب کن.</em>', p: 'اتصالی نرم و پیوسته، مثل موجی که به ساحل می‌رسد.', sub: 'NAYI · OPEN SEA', c: '#04222f' },
  dawn:  { t: 'روشن شروع کن<br><em>نفس بکش.</em>', p: 'همان اتصال، با نوری که چشمت رو اذیت نمی‌کنه.', sub: 'NAYI · DAYLIGHT', c: '#eef3fb' }
};
function setTheme(name, quiet) {
  if (!THEMES[name]) name = 'space';
  app.classList.remove('theme-space', 'theme-ocean', 'theme-dawn'); app.classList.add('theme-' + name);
  $$('.theme-switch button').forEach(b => b.setAttribute('aria-checked', String(b.dataset.theme === name)));
  const th = THEMES[name];
  $('#heroTitle').innerHTML = th.t; $('#heroText').textContent = th.p; $('#brandSub').textContent = th.sub;
  document.querySelector('meta[name=theme-color]').content = th.c;
  try { tg?.setHeaderColor?.(th.c); tg?.setBackgroundColor?.(th.c); } catch (_) {}
  lsSet('nayi-theme', name);
  if (!quiet) haptic('light');
}

/* ---------- starfield ---------- */
function sky() {
  const c = $('#sky'), x = c.getContext('2d'); let stars = [], w = 0, h = 0;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  function size() {
    const dpr = Math.min(devicePixelRatio || 1, 2); w = c.offsetWidth; h = c.offsetHeight;
    c.width = w * dpr; c.height = h * dpr; x.setTransform(dpr, 0, 0, dpr, 0, 0);
    stars = Array.from({ length: Math.round(w * h / 5000) }, () => ({ x: Math.random() * w, y: Math.random() * h, r: Math.random() * 1.3 + .2, a: Math.random() * 6.28, s: Math.random() * .015 + .004, v: Math.random() * .08 + .02 }));
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
  size(); frame(); addEventListener('resize', size);
}

/* ---------- 3D tilt + shine ---------- */
function tiltify(root = document) {
  root.querySelectorAll('.tilt').forEach(el => {
    if (el.dataset.tilt) return; el.dataset.tilt = '1';
    const move = e => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
      el.style.setProperty('--ry', ((px - .5) * 14).toFixed(2) + 'deg');
      el.style.setProperty('--rx', ((.5 - py) * 12).toFixed(2) + 'deg');
      el.style.setProperty('--mx', (px * 100).toFixed(1) + '%'); el.style.setProperty('--my', (py * 100).toFixed(1) + '%');
      el.classList.add('moving');
    };
    const out = () => { el.classList.remove('moving'); el.style.setProperty('--rx', '0deg'); el.style.setProperty('--ry', '0deg'); };
    el.addEventListener('pointermove', move); el.addEventListener('pointerleave', out); el.addEventListener('pointerup', out);
  });
}
function parallax() {
  const scene = $('#scene'); if (!scene || matchMedia('(pointer:coarse)').matches === false) return;
  addEventListener('deviceorientation', e => {
    if (e.gamma == null) return;
    const world = scene.querySelector('.world');
    world.style.setProperty('--gx', Math.max(-15, Math.min(15, e.gamma / 2)).toFixed(1));
    world.style.setProperty('--gy', Math.max(-15, Math.min(15, (e.beta - 45) / 2)).toFixed(1));
  });
  scene.addEventListener('pointermove', e => {
    const r = scene.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width - .5, py = (e.clientY - r.top) / r.height - .5;
    const world = scene.querySelector('.world'); world.style.setProperty('--gx', (px * 26).toFixed(1)); world.style.setProperty('--gy', (-py * 22).toFixed(1));
  });
  scene.addEventListener('pointerleave', () => { const w = scene.querySelector('.world'); w.style.setProperty('--gx', 0); w.style.setProperty('--gy', 0); });
}

/* ---------- shop ---------- */
const usablePanels = () => S.panels.filter(p => p.ptype !== 'manual');
const planList = () => S.plans.filter(p => +p.months === S.month).sort((a, b) => a.price - b.price);
const curPanel = () => usablePanels().find(p => p.id === S.panelId);
function monthsList() {
  const ms = [...new Set(S.plans.map(p => Number(p.months)))].filter(Boolean).sort((a, b) => a - b);
  return ms;
}
function stepOf() { return S.selected ? 4 : S.month ? (usablePanels().length > 1 ? 3 : 2) : 1; }

function renderShop() {
  const panels = usablePanels();
  if (panels.length && !panels.some(p => p.id === S.panelId)) S.panelId = panels[0].id;
  const step = stepOf();
  $$('#steps li').forEach(li => { const n = +li.dataset.step; li.classList.toggle('on', n === step); li.classList.toggle('done', n < step); });

  $('#skeleton').classList.toggle('hidden', S.loaded);
  $('#testCard').classList.toggle('hidden', !(S.features.test && !S.hasTest && S.loaded && !S.month));
  $('#testInfo').textContent = `${num(S.features.test_gb)} گیگ · ${num(S.features.test_days)} روز · رایگان، فقط یک بار`;

  // step 1: months
  const showMonths = S.loaded && !S.month;
  $('#months').classList.toggle('hidden', !showMonths);
  if (showMonths) {
    const ms = monthsList();
    let best = null, bestRate = Infinity;
    S.plans.forEach(p => { const r = p.price / Math.max(p.days, 1); if (r < bestRate) { bestRate = r; best = p.months; } });
    $('#months').innerHTML = ms.length ? ms.map(m => {
      const list = S.plans.filter(p => +p.months === m), min = list.length ? Math.min(...list.map(p => p.price)) : 0;
      return `<button type="button" class="month tilt ${m === best && ms.length > 1 ? 'best' : ''}" data-month="${m}" ${list.length ? '' : 'disabled'}>
        <span class="m-num">${m}</span><strong>${monthName(m)}</strong><small>${list.length ? num(list.length) + ' پلن' : 'به‌زودی'}</small>
        <span class="from">${list.length ? 'از <span class="num">' + num(min) + '</span>' : '—'}</span><i class="orbit-deco"></i></button>`;
    }).join('') : `<div class="empty"><b>✧</b>فعلاً پلنی برای فروش فعال نیست.<button type="button" class="ghost" data-act="reload">تلاش دوباره</button></div>`;
    tiltify($('#months'));
  }

  // step 2: server (only when there is more than one server)
  const multi = S.loaded && panels.length > 1;
  $('#panels').classList.toggle('hidden', !(multi && S.month));
  $('#panels').innerHTML = multi ? panels.map(p => `
    <button type="button" class="srv tilt ${p.id === S.panelId ? 'on' : ''}" data-panel="${p.id}" aria-pressed="${p.id === S.panelId}">
      <span class="live">آنلاین</span><span class="globe">${flag(p.name)}</span><b>${esc(p.name || 'سرور ' + p.id)}</b><small class="latin">${esc((p.ptype || 'panel').toUpperCase())}</small>
    </button>`).join('') : '';
  if (multi) tiltify($('#panels'));
  $('#serverChip').classList.toggle('hidden', !(S.month && panels.length === 1 && S.loaded));
  $('#serverChip').innerHTML = panels.length === 1 ? `<span>سرور: <b>${esc(panels[0].name || 'اصلی')}</b></span>` : '';

  $('#back').classList.toggle('hidden', !S.month);
  $('#stepEyebrow').textContent = S.month && curPanel() ? 'SERVER · ' + (curPanel().name || '') : 'MISSION CONTROL';
  $('#stepTitle').textContent = S.month ? (multi ? 'سرور و پلن را' : 'پلن ' + monthName(S.month)) + ' انتخاب کن' : 'مدت اشتراک را انتخاب کن';

  // step 3: plans
  $('#plans').classList.toggle('hidden', !S.month);
  if (S.month) {
    const list = planList();
    $('#plans').innerHTML = list.length ? list.map(p => {
      const disc = p.orig && p.orig > p.price;
      return `<button type="button" class="plan tilt ${S.selected?.id === p.id ? 'picked' : ''}" data-id="${p.id}" aria-pressed="${S.selected?.id === p.id}">
        <span class="gb"><b class="num">${num(p.gb)}</b><small>GB</small></span>
        <span class="meta"><b>${num(p.gb)} گیگ · ${num(p.days)} روز</b><small>${num(Math.round(p.gb / Math.max(p.days, 1) * 10) / 10)} گیگ در روز</small></span>
        <span class="price">${disc ? `<s class="num">${num(p.orig)}</s>` : ''}<b class="num">${num(p.price)}</b><small>تومان</small></span>
      </button>`;
    }).join('') : `<div class="empty"><b>✧</b>برای این مدت هنوز پلنی تعریف نشده.<button type="button" class="ghost" data-act="back">انتخاب مدت دیگر</button></div>`;
    tiltify($('#plans'));
  }

  // checkout bar
  const co = $('#checkout');
  co.classList.toggle('show', S.view === 'shop' && !!S.selected);
  if (S.selected) {
    const p = S.selected;
    $('#coServer').textContent = (curPanel()?.name ? 'سرور ' + curPanel().name + ' · ' : '') + 'انتخاب تو';
    $('#choice').textContent = `${num(p.gb)} گیگ · ${num(p.days)} روز`;
    const price = discounted(p.price);
    $('#choicePrice').textContent = num(price);
    const o = $('#choiceOrig'); o.classList.toggle('hidden', !(p.orig > price)); o.textContent = num(p.orig);
  }
  $('#buy').disabled = !panels.length;
  $('#buy').textContent = panels.length ? 'خرید' : 'بدون سرور';
}

function flag(name = '') {
  const n = name.toLowerCase();
  if (/آلمان|german|de\b/.test(n)) return '🇩🇪';
  if (/هلند|nether|nl\b/.test(n)) return '🇳🇱';
  if (/فرانس|french|fr\b/.test(n)) return '🇫🇷';
  if (/ترکیه|turk|tr\b/.test(n)) return '🇹🇷';
  if (/امارات|emirat|uae|ae\b/.test(n)) return '🇦🇪';
  if (/انگلیس|\buk\b|britain/.test(n)) return '🇬🇧';
  if (/امریکا|آمریکا|usa|us\b/.test(n)) return '🇺🇸';
  return '🛰️';
}
const discounted = price => S.discount?.price != null ? Number(S.discount.price) : (S.discount?.demo ? Math.round(price * .8) : price);

/* ---------- services ---------- */
function statusOf(s) {
  const left = daysLeft(s);
  if (s.status === 'active' && left === 0) return { cls: 'off', txt: 'منقضی' };
  if (s.status === 'active') return { cls: 'ok', txt: 'فعال' };
  if (['expired', 'disabled', 'limited'].includes(s.status)) return { cls: 'off', txt: 'غیرفعال' };
  return { cls: 'wait', txt: 'در انتظار' };
}
function renderServices() {
  const act = S.services.filter(s => s.status === 'active' && daysLeft(s) !== 0), ended = S.services.length - act.length;
  $('#cAll').textContent = S.services.length; $('#cActive').textContent = act.length; $('#cEnded').textContent = ended;
  $('#svcBadge').textContent = act.length; $('#svcBadge').classList.toggle('hidden', !act.length);
  $$('#svcFilter button').forEach(b => b.classList.toggle('on', b.dataset.filter === S.filter));
  const list = $('#serviceList');
  if (!S.services.length) {
    list.innerHTML = `<div class="empty"><b>◈</b>هنوز سرویسی نداری.<br>اولین مدارت رو بساز.<button type="button" class="ghost" data-go="shop">رفتن به خرید</button></div>`;
    $('#more').classList.add('hidden'); return;
  }
  let items = S.services.filter(s => S.filter === 'all' || (S.filter === 'active' ? act.includes(s) : !act.includes(s)));
  if (!items.length) { list.innerHTML = `<div class="empty"><b>◌</b>موردی توی این فیلتر نیست.</div>`; $('#more').classList.add('hidden'); return; }
  const shown = items.slice(0, S.shown);
  list.innerHTML = shown.map(s => {
    const st = statusOf(s), left = daysLeft(s), pct = left != null && s.days ? Math.min(100, Math.round(left / s.days * 100)) : 0;
    const used = s.usage?.total ? Math.min(100, Math.round(s.usage.used / s.usage.total * 100)) : null;
    const cfg = [s.link && ['کانفیگ', s.link], s.sub && ['لینک ساب', s.sub]].filter(Boolean);
    return `<article class="svc" data-sid="${s.id}">
      <div class="svc-top"><span class="svc-flag">${flag(s.panel)}</span>
        <div class="svc-id"><b class="latin">${esc(s.name || 'NAYI')}</b><small>${esc(s.panel || '')}${s.is_test ? ' · تست' : ''}</small></div>
        <span class="tag ${s.is_test ? 'test' : st.cls}">${s.is_test ? 'تست' : st.txt}</span></div>
      ${left != null ? `<div class="meter ${pct < 20 ? 'low' : ''}"><i style="width:${pct}%"></i></div>
        <div class="meter-l"><span><span class="num">${num(left)}</span> روز باقی‌مانده</span><span class="num">${pct}%</span></div>` : ''}
      <div class="svc-stats">
        <span><b class="num">${num(s.gb)}</b><small>گیگابایت</small></span>
        <span><b class="num">${used != null ? used + '%' : num(s.days)}</b><small>${used != null ? 'مصرف' : 'روز'}</small></span>
        <span><b class="num">${fmtDate(s.expire)}</b><small>انقضا</small></span>
      </div>
      ${cfg.length ? cfg.map(([label, v]) => `<div class="cfg"><code>${esc(v)}</code><button type="button" class="mini" data-copy="${esc(v)}">کپی</button></div>`).join('') : '<div class="cfg"><code>کانفیگ هنوز تحویل نشده</code></div>'}
      <div class="acts">
        <button type="button" data-qr="${s.id}"><span>▦</span>QR</button>
        <button type="button" data-usage="${s.id}"><span>📊</span>مصرف</button>
        ${S.features.renew && !s.is_test ? `<button type="button" data-renew="${s.id}"><span>↻</span>تمدید</button>` : `<button type="button" data-go="guide"><span>📖</span>راهنما</button>`}
        <button type="button" data-delete="${s.id}"><span>⌫</span>حذف</button>
      </div>
      <div class="qr-box" id="qr-${s.id}"></div>
    </article>`;
  }).join('');
  $('#more').classList.toggle('hidden', items.length <= S.shown);
  $('#more').textContent = `نمایش بیشتر (${num(items.length - S.shown)})`;
  tiltify(list);
}

function renderTransactions() {
  const list = $('#transactionList');
  if (!S.tx.length) { list.innerHTML = '<div class="empty"><b>🧾</b>تراکنشی ثبت نشده.</div>'; return; }
  list.innerHTML = S.tx.map(x => `<article class="svc"><div class="svc-top"><span class="svc-flag">${x.kind === 'renew' ? '↻' : '✦'}</span><div class="svc-id"><b>${x.kind === 'renew' ? 'تمدید سرویس' : 'خرید سرویس'}</b><small>${new Date((x.created || 0) * 1000).toLocaleString('en-GB')}</small></div><span class="tag ok num">${num(x.amount)} تومان</span></div></article>`).join('');
}

function renderTopup() {
  $$('.amount').forEach(b => b.classList.toggle('on', Number(b.dataset.topup) === S.topupAmount));
}

/* ---------- guide ---------- */
const APPS = {
  android: [{ n: 'v2rayNG', d: 'رایگان · متن‌باز', rec: 1, u: 'https://play.google.com/store/apps/details?id=com.v2ray.ang' }, { n: 'Hiddify', d: 'ساده و سریع', u: 'https://play.google.com/store/apps/details?id=app.hiddify.com' }],
  ios: [{ n: 'Streisand', d: 'پیشنهادی آیفون', rec: 1, u: 'https://apps.apple.com/app/streisand/id6450534064' }, { n: 'V2Box', d: 'جایگزین', u: 'https://apps.apple.com/app/v2box-v2ray-client/id6446814690' }],
  windows: [{ n: 'Hiddify', d: 'ویندوز و مک', rec: 1, u: 'https://github.com/hiddify/hiddify-app/releases' }, { n: 'v2rayN', d: 'متن‌باز', u: 'https://github.com/2dust/v2rayN/releases' }],
  mac: [{ n: 'Hiddify', d: 'ویندوز و مک', rec: 1, u: 'https://github.com/hiddify/hiddify-app/releases' }, { n: 'V2Box', d: 'جایگزین', u: 'https://apps.apple.com/app/v2box-v2ray-client/id6446814690' }]
};
function renderGuide() {
  const os = S.guideOs || 'android';
  $$('#osSeg button').forEach(b => b.classList.toggle('on', b.dataset.os === os));
  $('#apps').innerHTML = APPS[os].map(a => `<div class="appc"><span class="ic">${esc(a.n[0])}</span><div><b>${esc(a.n)}${a.rec ? '<span class="rec">پیشنهادی</span>' : ''}</b><small>${esc(a.d)}</small></div><div class="btns"><button type="button" class="mini alt" data-open="${esc(a.u)}">دانلود</button></div></div>`).join('');
  const s = S.services.find(x => x.status === 'active' && (x.link || x.sub));
  $('#guideSvc').innerHTML = s ? `<div class="cfg"><code>${esc(s.sub || s.link)}</code><button type="button" class="mini" data-copy="${esc(s.sub || s.link)}">کپی لینک ساب</button></div>` : '<div class="empty"><b>◌</b>هنوز سرویس فعالی نداری.</div>';
}

/* ---------- profile ---------- */
function fillMe(p) {
  S.me = p;
  const name = p.name || tg?.initDataUnsafe?.user?.first_name || 'کاربر نایی';
  const init = (name.trim()[0] || 'N').toUpperCase();
  const photo = p.photo || tg?.initDataUnsafe?.user?.photo_url || '';
  $('#meName').textContent = name; $('#meInit').textContent = init; $('#avatarInit').textContent = init;
  $('#profileName').textContent = name;
  $('#profileUser').textContent = p.username ? '@' + p.username : 'حساب تلگرام';
  $('#profileId').textContent = p.id ?? '—'; $('#cardId').textContent = '•••• ' + String(p.id ?? '').slice(-4);
  $('#profileBalance').textContent = money(p.balance);
  $('#profileServices').textContent = num(p.services ?? S.services.length);
  $('#profileActive').textContent = num(p.active ?? S.services.filter(s => s.status === 'active').length);
  $('#profileSpent').textContent = num(p.spent ?? 0);
  if (photo) { for (const [img, ini] of [['#meImg', '#meInit'], ['#avatarImg', '#avatarInit']]) { const i = $(img); i.src = photo; i.hidden = false; i.onerror = () => { i.hidden = true; }; } }
  if (typeof p.balance === 'number') { S.balance = p.balance; paintWallet(); }
}
async function loadProfile() {
  if (DEMO) return fillMe({ id: 1024, name: 'کاربر نمایشی', username: 'nayi_demo', balance: S.balance, services: S.services.length, active: 2, spent: 238000 });
  try { fillMe(await api('/api/profile')); } catch (e) { toast(e.message, 'err'); }
}
function paintWallet() { $('#walletAmount').textContent = S.loaded ? num(S.balance) : '—'; }

/* ---------- navigation & chrome ---------- */
function show(v) {
  if (v === 'bot') return openBot();
  S.view = v;
  $$('.view').forEach(x => x.classList.toggle('active', x.id === 'view-' + v));
  const idx = ['shop', 'services', 'guide', 'profile'].indexOf(v);
  $$('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $('.tab-ink').style.transform = idx >= 0 ? `translateX(${-idx * 100}%)` : 'translateX(0)';
  if (v === 'services') renderServices();
  if (v === 'transactions') { loadTransactions().then(renderTransactions); }
  if (v === 'topup') renderTopup();
  if (v === 'guide') renderGuide();
  if (v === 'profile') loadProfile();
  renderShop(); haptic('light');
  scrollTo({ top: 0, behavior: 'smooth' });
  syncChrome();
}
async function loadTransactions() {
  if (DEMO) { S.tx = [{kind:'buy',amount:149000,created:Date.now()/1000-86400}]; return; }
  try { S.tx = (await api('/api/transactions')).items || []; } catch (e) { toast(e.message, 'err'); }
}

async function removeService(id) {
  if (!confirm('این سرویس از پنل و ربات حذف شود؟')) return;
  if (DEMO) { S.services = S.services.filter(x => x.id != id); renderServices(); return toast('در پیش‌نمایش حذف شد'); }
  try { await api('/api/service/' + id, { method: 'DELETE' }); S.services = S.services.filter(x => x.id != id); renderServices(); toast('سرویس از پنل و ربات حذف شد ✓'); }
  catch (e) { toast(e.message, 'err'); }
}

function topupBot() {
  if (DEMO) return toast('پیش‌نمایشه؛ شارژ واقعی داخل ربات انجام می‌شود', 'err');
  const u = S.bot ? `https://t.me/${S.bot}?start=topup_${encodeURIComponent(S.topupAmount)}` : '';
  if (!u) return toast('لینک ربات پیدا نشد', 'err');
  S.awaitingWallet = true;
  try { tg?.openTelegramLink ? tg.openTelegramLink(u) : window.open(u, '_blank'); } catch (_) { window.open(u, '_blank'); }
}
function goBack() {
  if (sheetOpen()) return closeSheets();
  if (S.view !== 'shop') return show('shop');
  if (S.selected) { S.selected = null; renderShop(); return; }
  if (S.month) { S.month = null; renderShop(); }
}
const sheetOpen = () => $$('.sheet-wrap.open').length > 0;
function syncChrome() {
  if (!tg?.BackButton) return;
  (S.view !== 'shop' || S.month || sheetOpen()) ? tg.BackButton.show() : tg.BackButton.hide();
}
function openBot() {
  const u = S.bot ? `https://t.me/${S.bot}` : '';
  if (!u) return toast('لینک ربات پیدا نشد', 'err');
  try { tg?.openTelegramLink ? tg.openTelegramLink(u) : window.open(u, '_blank'); } catch (_) { window.open(u, '_blank'); }
}
function openLink(u) { try { tg?.openLink ? tg.openLink(u) : window.open(u, '_blank', 'noopener'); } catch (_) { window.open(u, '_blank'); } }

/* ---------- sheets ---------- */
function openSheet(id) { const el = $('#' + id); el.classList.add('open'); el.setAttribute('aria-hidden', 'false'); syncChrome(); haptic('medium'); }
function closeSheets() { $$('.sheet-wrap.open').forEach(el => { el.classList.remove('open'); el.setAttribute('aria-hidden', 'true'); }); syncChrome(); }

function openCheckout() {
  if (!S.selected) return;
  if (!usablePanels().length) return toast('سروری برای ساخت سرویس متصل نیست', 'err');
  renderBill();
  openSheet('modal');
}
function renderBill() {
  const p = S.selected; if (!p) return;
  const price = discounted(p.price), after = S.balance - price, short = after < 0;
  $('#modalChoice').textContent = `${monthName(p.months)} · ${num(p.gb)} گیگ`;
  $('#billServer').textContent = curPanel()?.name || '—';
  $('#billPrice').textContent = money(p.price);
  $('#billDiscRow').classList.toggle('hidden', !S.discount);
  if (S.discount) $('#billDisc').textContent = `−${num(p.price - price)} تومان`;
  $('#billBalance').textContent = money(S.balance);
  $('#billAfter').textContent = short ? 'ناکافی' : money(after);
  $('#billAfter').classList.toggle('neg', short);
  $('#billWarn').classList.toggle('hidden', !short);
  $('#approve').disabled = short; $('#approve span').textContent = short ? 'موجودی کافی نیست' : 'تأیید و پرداخت از کیف پول';
  $('#dcForm').classList.toggle('hidden', !S.features.discount || !!S.discount);
}

function showSuccess(svc) {
  $('#sucText').textContent = svc.is_test ? `اکانت تست ${num(svc.gb)} گیگی ساخته شد. از بخش سرویس‌ها کانفیگ رو بردار.` : `${num(svc.gb)} گیگ · ${num(svc.days)} روز روی ${svc.panel || 'سرور'} فعال شد.`;
  $('#sucCopy').classList.toggle('hidden', !(svc.link || svc.sub));
  $('#sucCopy').onclick = () => copy(svc.sub || svc.link);
  const b = $('#burst'); b.innerHTML = '';
  const cols = ['#68e8ff', '#9b8cff', '#f4d39b', '#5ff0b5', '#ff7ab6'];
  for (let i = 0; i < 46; i++) {
    const d = document.createElement('i'); const a = Math.random() * 6.28, r = 90 + Math.random() * 150;
    d.style.cssText = `background:${cols[i % cols.length]};--tx:${Math.cos(a) * r}px;--ty:${Math.sin(a) * r + 60}px;--tr:${Math.random() * 720}deg;animation-delay:${Math.random() * .15}s`;
    b.appendChild(d);
  }
  $('#success').classList.add('open'); haptic('ok');
  setTimeout(() => $('#success').classList.remove('open'), 4200);
  $('#sucGo').onclick = () => { $('#success').classList.remove('open'); show('services'); };
  $('#success').onclick = e => { if (e.target.id === 'success') $('#success').classList.remove('open'); };
}

async function approve() {
  if (S.busy || !S.selected) return;
  if (DEMO) { closeSheets(); return toast('پیش‌نمایشه؛ خرید واقعی از داخل ربات انجام می‌شه', 'err'); }
  S.busy = true; const btn = $('#approve'); btn.disabled = true; btn.classList.add('loading');
  try {
    const d = await api('/api/buy', { method: 'POST', body: JSON.stringify({ plan_id: S.selected.id, panel_id: S.panelId, discount_code: S.discount?.code || null }) });
    S.balance = d.balance; S.services = [d.service, ...S.services.filter(s => s.id !== d.service.id)];
    S.month = null; S.selected = null; S.discount = null; paintWallet();
    closeSheets(); show('services'); showSuccess(d.service);
    load(true);
  } catch (e) {
    haptic('err'); toast(e.message || 'خرید انجام نشد و موجودی کم نشد', 'err');
    closeSheets();
    if (e.status === 402 || e.status === 409) load(true);
  } finally { S.busy = false; btn.classList.remove('loading'); btn.disabled = false; }
}

/* ---------- test account ---------- */
async function getTest() {
  if (DEMO) return toast('پیش‌نمایشه؛ اکانت تست از داخل ربات گرفته می‌شه', 'err');
  const btn = $('#testBtn'); btn.disabled = true; btn.classList.add('loading');
  try {
    const d = await api('/api/test', { method: 'POST', body: JSON.stringify({ panel_id: S.panelId }) });
    S.hasTest = true; S.services = [d.service, ...S.services]; $('#testCard').classList.add('hidden');
    showSuccess(d.service); show('services');
  } catch (e) { toast(e.message, 'err'); if (e.status === 409) { S.hasTest = true; renderShop(); } }
  finally { btn.disabled = false; btn.classList.remove('loading'); }
}

/* ---------- renew ---------- */
function openRenew(sid) {
  const s = S.services.find(x => x.id == sid); if (!s) return;
  S.renewSvc = s; S.renewPlan = null;
  $('#renewTitle').innerHTML = `تمدید <span class="latin">${esc(s.name)}</span>`;
  const list = S.plans.slice().sort((a, b) => a.price - b.price);
  $('#renewPlans').innerHTML = list.map(p => `<button type="button" class="plan tilt" data-rplan="${p.id}"><span class="gb"><b class="num">${num(p.gb)}</b><small>GB</small></span><span class="meta"><b>${num(p.gb)} گیگ · ${num(p.days)} روز</b></span><span class="price"><b class="num">${num(discounted(p.price))}</b><small>تومان</small></span></button>`).join('');
  $('#renewGo').disabled = true;
  tiltify($('#renewPlans')); openSheet('renewSheet');
}
async function doRenew() {
  if (!S.renewPlan || !S.renewSvc) return;
  const p = S.renewPlan;
  if (S.balance < discounted(p.price)) return toast('موجودی کیف پول کافی نیست', 'err');
  if (DEMO) { closeSheets(); return toast('پیش‌نمایشه؛ تمدید واقعی از داخل ربات انجام می‌شه', 'err'); }
  const btn = $('#renewGo'); btn.disabled = true; btn.classList.add('loading');
  try {
    const d = await api('/api/renew', { method: 'POST', body: JSON.stringify({ service_id: S.renewSvc.id, plan_id: p.id }) });
    S.balance = d.balance; const s = S.services.find(x => x.id === S.renewSvc.id); if (s) { s.expire = d.expire; s.status = 'active'; s.gb = p.gb; s.days = p.days; }
    paintWallet(); closeSheets(); renderServices(); toast('تمدید شد ✓'); haptic('ok');
  } catch (e) { toast(e.message, 'err'); }
  finally { btn.classList.remove('loading'); }
}

/* ---------- usage / qr ---------- */
async function toggleUsage(sid, btn) {
  const box = $('#qr-' + sid);
  if (box.classList.contains('open') && box.dataset.mode === 'usage') { box.classList.remove('open'); return; }
  box.dataset.mode = 'usage'; box.innerHTML = '<div class="qr-wait">در حال گرفتن اطلاعات…</div>'; box.classList.add('open');
  let u = null;
  if (DEMO) { u = { used: 31.4, total: 50 }; }
  else if (S.features.usage) { try { const d = await api('/api/service/' + sid); u = d.usage; const s = S.services.find(x => x.id == sid); if (s && u) s.usage = u; } catch (_) {} }
  if (!u || !u.total) { box.innerHTML = '<div class="qr-wait">اطلاعات مصرف الان در دسترس نیست.</div>'; return; }
  const pct = Math.min(100, Math.round(u.used / u.total * 100));
  box.innerHTML = `<div class="meter ${pct > 85 ? 'low' : ''}" style="width:100%"><i style="width:${pct}%"></i></div><div class="meter-l" style="width:100%"><span><span class="num">${num(u.used)}</span> از <span class="num">${num(u.total)}</span> گیگ</span><span class="num">${pct}%</span></div>`;
}
async function toggleQr(sid) {
  const box = $('#qr-' + sid);
  if (box.classList.contains('open') && box.dataset.mode === 'qr') { box.classList.remove('open'); return; }
  box.dataset.mode = 'qr'; box.classList.add('open');
  const s = S.services.find(x => x.id == sid);
  if (s?.qr) { box.innerHTML = `<img alt="QR" src="${esc(s.qr)}">`; return; }
  box.innerHTML = '<div class="qr-wait">در حال ساخت QR…</div>';
  if (DEMO) { box.innerHTML = '<div class="qr-wait">QR در نسخه واقعی نمایش داده می‌شه.</div>'; return; }
  try { const d = await api('/api/service/' + sid); if (s) s.qr = d.qr; box.innerHTML = d.qr ? `<img alt="QR" src="${esc(d.qr)}">` : '<div class="qr-wait">QR ساخته نشد</div>'; }
  catch (e) { box.innerHTML = `<div class="qr-wait">${esc(e.message)}</div>`; }
}

/* ---------- discount ---------- */
async function applyDiscount(e) {
  e.preventDefault();
  const code = $('#dcInput').value.trim(); if (!code) return;
  if (DEMO) { S.discount = { code, demo: true }; renderBill(); renderShop(); return toast('کد اعمال شد (نمونه)'); }
  try {
    const d = await api('/api/discount', { method: 'POST', body: JSON.stringify({ code, plan_id: S.selected?.id || null }) });
    S.discount = { code: d.code || code, price: d.price, plan_id: S.selected?.id };
    renderBill(); renderShop(); toast('کد اعمال شد ✓');
  }
  catch (err) { toast(err.message, 'err'); }
}

/* ---------- copy ---------- */
async function copy(text) {
  try { await navigator.clipboard.writeText(text); }
  catch (_) { const t = document.createElement('textarea'); t.value = text; t.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(t); t.select(); try { document.execCommand('copy'); } catch (__) {} t.remove(); }
  haptic('ok'); toast('کپی شد ✓');
}

/* ---------- data ---------- */
async function load(silent) {
  try {
    const d = DEMO ? demo() : await api('/api/catalog');
    S.plans = (d.plans || []).map(p => ({ ...p, months: +p.months, price: +p.price, orig: +(p.orig || p.price), gb: +p.gb, days: +p.days }));
    S.panels = d.panels || []; S.services = d.services || []; S.balance = +d.balance || 0;
    S.features = d.features || {}; S.hasTest = !!d.has_test; S.bot = d.bot || S.bot; S.support = d.support || S.support;
    if (S.selected) S.selected = S.plans.find(p => p.id === S.selected.id) || null;
    S.loaded = true;
  } catch (e) {
    S.loaded = true;
    if (!silent) toast(e.status === 401 ? 'نشست تلگرام نامعتبره؛ مینی‌اپ رو دوباره باز کن' : e.message, 'err');
  }
  if (!S.bot && !DEMO) { try { const c = await api('/api/config'); S.bot = c.bot || ''; S.support = c.support || S.support; } catch (_) {} }
  $('#supportRow').classList.toggle('hidden', !S.support);
  paintWallet(); renderShop(); if (S.view === 'services') renderServices(); if (S.view === 'guide') renderGuide();
  loadProfile();
}

async function refreshWallet() {
  if (DEMO) return;
  try {
    const d = await api('/api/wallet');
    if (Number.isFinite(Number(d.balance))) {
      S.balance = Number(d.balance);
      if (S.me) S.me.balance = S.balance;
      paintWallet();
      if (S.view === 'profile') $('#profileBalance').textContent = money(S.balance);
      if (S.view === 'shop') renderShop();
    }
  } catch (_) {}
}

/* ---------- events (delegated) ---------- */
document.addEventListener('click', e => {
  const t = e.target.closest('button,[data-open]'); if (!t) return;
  const d = t.dataset;
  if (d.open) return openLink(d.open);
  if (d.month) { S.month = +d.month; S.selected = null; S.discount = null; renderShop(); haptic('light'); return; }
  if (d.id) { const p = S.plans.find(x => x.id == d.id); S.selected = S.selected?.id === p?.id ? null : p; S.discount = null; renderShop(); haptic('light'); return; }
  if (d.panel) { S.panelId = +d.panel; S.selected = null; S.discount = null; renderShop(); haptic('light'); return; }
  if (d.rplan) { S.renewPlan = S.plans.find(p => p.id == d.rplan); $$('#renewPlans .plan').forEach(x => x.classList.toggle('picked', x.dataset.rplan == d.rplan)); $('#renewGo').disabled = false; return; }
  if (d.view) return show(d.view);
  if (d.go) return show(d.go);
  if (d.theme) return setTheme(d.theme);
  if (d.copy) return copy(d.copy);
  if (d.qr) return toggleQr(d.qr);
  if (d.usage) return toggleUsage(d.usage, t);
  if (d.renew) return openRenew(d.renew);
  if (d.delete) return removeService(d.delete);
  if (d.os) { S.guideOs = d.os; return renderGuide(); }
  if (d.filter) { S.filter = d.filter; S.shown = PAGE; return renderServices(); }
  if (d.act === 'back') return goBack();
  if (d.act === 'reload') return load();
  if (d.act === 'topup' || d.act === 'bot') return openBot();
  if (d.act === 'topup-bot') return topupBot();
  if (d.act === 'copy-card') return toast('اطلاعات کارت را از داخل ربات بردار', 'err');
  if (d.topup) { S.topupAmount = Number(d.topup); renderTopup(); haptic('light'); return; }
  if (d.act === 'support') return S.support ? openLink(S.support.startsWith('http') ? S.support : 'https://t.me/' + S.support.replace('@', '')) : toast('پشتیبانی فعلاً در دسترس نیست', 'err');
  if (t.hasAttribute('data-close')) return closeSheets();
});
$('#back').addEventListener('click', goBack);
$('#buy').addEventListener('click', openCheckout);
$('#approve').addEventListener('click', approve);
$('#testBtn').addEventListener('click', getTest);
$('#renewGo').addEventListener('click', doRenew);
$('#dcForm').addEventListener('submit', applyDiscount);
$('#walletChip').addEventListener('click', () => show('profile'));
$('#me').addEventListener('click', () => show('profile'));
$('#more').addEventListener('click', () => { S.shown += PAGE; renderServices(); });
$('#refresh').addEventListener('click', async () => { await load(); toast('به‌روز شد ✓'); });
$('#copyId').addEventListener('click', () => copy(String(S.me?.id ?? '')));
$('#modal').addEventListener('click', e => { if (e.target.id === 'modal') closeSheets(); });
$('#renewSheet').addEventListener('click', e => { if (e.target.id === 'renewSheet') closeSheets(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') goBack(); });
$$('.theme-switch button').forEach(b => b.addEventListener('click', () => setTheme(b.dataset.theme)));
tg?.BackButton?.onClick(goBack);
// The bot and Mini App use the same wallet balance. Refresh it when Telegram
// brings the Mini App back to the foreground after a top-up is approved.
let refreshOnReturn = false;
document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'hidden') {
    refreshOnReturn = true;
    return;
  }
  if (refreshOnReturn && !DEMO) {
    refreshOnReturn = false;
    await refreshWallet();
    await loadProfile();
  }
});
window.addEventListener('focus', async () => {
  if (!DEMO && S.loaded) {
    await refreshWallet();
    await loadProfile();
  }
});
tg?.onEvent?.('activated', async () => {
  await refreshWallet();
  await loadProfile();
});
setInterval(() => {
  if (!DEMO && S.awaitingWallet) refreshWallet();
}, 5000);

/* ---------- boot ---------- */
if (tg) { tg.ready(); tg.expand(); try { tg.disableVerticalSwipes?.(); } catch (_) {} }
if (DEMO) $('#demoBar').classList.remove('hidden');
setTheme(lsGet('nayi-theme') || 'space', true);
sky(); tiltify(); parallax(); renderShop(); show('shop'); load();
window.NAYI = { S, show };
})();
