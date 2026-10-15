/* NAYI web admin panel · v8 */
(() => {
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = n => Number(n || 0).toLocaleString('en-US');
const fa2en = s => String(s ?? '').replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const intOf = v => { const n = parseInt(fa2en(v).replace(/[^\d]/g, ''), 10); return Number.isFinite(n) ? n : NaN; };
const when = ts => ts ? new Date(ts * 1000).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—';
let toastT;
function toast(m, err) { const t = $('#toast'); t.textContent = m; t.className = 'toast show' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 3200); }
async function api(url, body, method) {
  const opt = { method: method || (body !== undefined ? 'POST' : 'GET'), credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Panel': '1' } };
  if (body !== undefined) opt.body = JSON.stringify(body);
  let r; try { r = await fetch('/panel/api/' + url, opt); } catch (_) { throw new Error('اتصال برقرار نشد'); }
  let j = {}; try { j = await r.json(); } catch (_) {}
  if (r.status === 401 && url !== 'login') { showLogin(); throw new Error('دوباره وارد شو'); }
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'خطا (' + r.status + ')');
  return j;
}
async function act(btn, fn, okMsg) {
  if (btn) btn.disabled = true;
  try { const r = await fn(); if (okMsg) toast(okMsg); return r || true; } catch (e) { toast(e.message, true); return null; } finally { if (btn) btn.disabled = false; }
}
const ST = { active: ['ok', 'فعال'], pending: ['wait', 'در انتظار'], expired: ['off', 'منقضی'], disabled: ['off', 'غیرفعال'], limited: ['off', 'محدود'], ok: ['ok', 'تأیید'], rejected: ['off', 'رد'], open: ['ok', 'باز'], closed: ['off', 'بسته'], error: ['off', 'خطا'], processing: ['wait', 'در حال بررسی'] };
const tag = s => { const [c, t] = ST[s] || ['wait', s]; return `<span class="tag ${c}">${esc(t)}</span>`; };
const TITLES = { dash: 'داشبورد', pay: 'رسیدها', users: 'کاربران', svc: 'سرویس‌ها', tk: 'تیکت‌ها', plans: 'پلن‌ها', panels: 'پنل‌های سرور', dc: 'کد تخفیف', bc: 'پیام همگانی', look: 'تغییرات ظاهر', set: 'تنظیمات', admins: 'مدیریت ادمین‌ها', log: 'تراکنش و لاگ' };

/* ---------- fuzzy search (Persian-aware) ---------- */
const norm = s => String(s ?? '').replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[\u064B-\u0652]/g, '').replace(/[\s\u200c\u200e\u200f‌_\-()]+/g, '').toLowerCase();
function lev(a, b) {
  const m = a.length, n = b.length; if (!m) return n; if (!n) return m;
  let p = Array.from({ length: n + 1 }, (_, i) => i);
  for (let i = 1; i <= m; i++) { const c = [i]; for (let j = 1; j <= n; j++) c[j] = Math.min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); p = c; }
  return p[n];
}
function match(q, ...fields) {
  const nq = norm(q); if (!nq) return true;
  const hay = norm(fields.join(' '));
  if (hay.includes(nq)) return true;
  if (nq.length < 4) return false;
  const tol = nq.length >= 7 ? 2 : 1;
  for (let L = nq.length - 1; L <= nq.length + 1; L++)
    for (let i = 0; i + L <= hay.length; i++) if (lev(nq, hay.slice(i, i + L)) <= tol) return true;
  return false;
}

/* ---------- auth ---------- */
function showLogin() { $('#shell').classList.add('hidden'); $('#login').classList.remove('hidden'); }
function showShell() { $('#login').classList.add('hidden'); $('#shell').classList.remove('hidden'); go('dash'); }
$('#loginForm').addEventListener('submit', async e => {
  e.preventDefault(); $('#loginErr').textContent = '';
  try { await api('login', { username: $('#lu').value, password: $('#lp').value }); $('#lp').value = ''; showShell(); }
  catch (err) { $('#loginErr').textContent = err.message; }
});
$('#logout').addEventListener('click', async () => { try { await api('logout', {}); } catch (_) {} showLogin(); });

/* ---------- nav / menu ---------- */
const LOAD = { dash: loadDash, pay: loadPay, users: loadUsers, svc: () => loadSvc(false), tk: loadTk, plans: loadPlans, panels: loadPanels, dc: loadDc, bc: loadBc, look: loadLook, set: loadSet, admins: loadAdmins, log: loadLog };
let cur = 'dash';
const menu = open => $('#shell').classList.toggle('menu-open', open);
function go(t) {
  if (!LOAD[t]) t = 'dash';
  cur = t; menu(false);
  $$('#nav [data-tab]').forEach(b => b.classList.toggle('on', b.dataset.tab === t));
  $$('.tab').forEach(s => s.classList.toggle('on', s.id === 't-' + t));
  $('#pageTitle').textContent = TITLES[t] || '';
  closeSheet();
  LOAD[t]();
  scrollTo({ top: 0, behavior: 'smooth' });
}
$('#nav').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.hasAttribute('data-group')) { b.parentElement.classList.toggle('open'); return; }
  if (b.dataset.tab) go(b.dataset.tab);
});
$('#menuBtn').addEventListener('click', () => menu(true));
$('#sideClose').addEventListener('click', () => menu(false));
$('#shade').addEventListener('click', () => menu(false));
$('#refreshBtn').addEventListener('click', () => LOAD[cur]?.());

/* global search: live-filters the menu; submit searches all bot buttons & messages */
$('#gq').addEventListener('input', () => {
  const q = $('#gq').value.trim();
  const items = $$('#nav [data-tab]'); const hits = items.filter(b => match(q, b.textContent));
  items.forEach(b => b.classList.toggle('hidden', !!q && hits.length > 0 && !hits.includes(b)));
});
$('#gSearch').addEventListener('submit', e => {
  e.preventDefault();
  const q = $('#gq').value.trim();
  const hit = q && $$('#nav [data-tab]').find(b => norm(b.textContent).includes(norm(q)));
  $('#gq').value = ''; $$('#nav [data-tab]').forEach(b => b.classList.remove('hidden'));
  if (hit && !LOOK.btns.some(x => norm(x.name) === norm(q))) return go(hit.dataset.tab);
  $('#lq').value = q; if (cur !== 'look') go('look'); else loadLook();
});

/* ---------- sheet (editor) ---------- */
function openSheet(html) { $('#sheetIn').innerHTML = html; const s = $('#sheet'); s.classList.add('open'); s.setAttribute('aria-hidden', 'false'); }
function closeSheet() { const s = $('#sheet'); s.classList.remove('open'); s.setAttribute('aria-hidden', 'true'); }
$('#sheet').addEventListener('click', e => { if (e.target.id === 'sheet' || e.target.closest('[data-sclose]')) closeSheet(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeSheet(); $('#drawer').classList.remove('open'); menu(false); } });

/* ---------- dashboard ---------- */
async function loadDash() {
  const d = await act(null, () => api('stats')); if (!d || d === true) return;
  const k = [['کاربران', d.users, `+${num(d.users_day)} امروز`, '👥'], ['سرویس فعال', d.active, `از ${num(d.services)} سرویس`, '📦'], ['فروش ۲۴ ساعت', d.sales_day, 'تومان', '💰'], ['فروش کل', d.sales_all, 'تومان', '📈'],
    ['شارژ ۲۴ ساعت', d.topup_day, 'تومان', '💳'], ['شارژ کل', d.topup_all, 'تومان', '🏦'], ['رسید در انتظار', d.pending, 'برای بررسی', '🧾', d.pending > 0, 'pay'], ['تیکت باز', d.tickets, 'پاسخ بده', '🎫', d.tickets > 0, 'tk'], ['موجودی کل کاربران', d.balance_total, 'تومان', '👛']];
  $('#kpis').innerHTML = k.map(([t, v, s, ic, hot, link]) => `<div class="kpi ${hot ? 'hot' : ''} ${link ? 'click' : ''}" ${link ? `data-go="${link}"` : ''}><span class="kpi-ic">${ic}</span><small>${t}</small><b class="num">${num(v)}</b><small>${s}</small></div>`).join('');
  const max = Math.max(1, ...d.days.map(x => Math.max(x.sales, x.topup)));
  $('#chart').innerHTML = d.days.map(x => `<div class="d" title="${new Date(x.t * 1000).toLocaleDateString('en-GB')} · فروش ${num(x.sales)} · شارژ ${num(x.topup)}"><i class="a" style="height:${x.sales / max * 100}%"></i><i class="b" style="height:${x.topup / max * 100}%"></i><small class="num">${new Date(x.t * 1000).getDate()}</small></div>`).join('');
  badge('#badgePay', d.pending); badge('#badgeTk', d.tickets);
}
$('#kpis').addEventListener('click', e => { const k = e.target.closest('[data-go]'); if (k) go(k.dataset.go); });
function badge(sel, n) { const b = $(sel); b.textContent = n; b.classList.toggle('hidden', !n); }

/* ---------- payments ---------- */
let paySt = 'pending';
$('#paySeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; paySt = b.dataset.st; $$('#paySeg button').forEach(x => x.classList.toggle('on', x === b)); loadPay(); });
function payActs(p) {
  if (p.status === 'pending') return `<div class="acts"><button type="button" class="btn ok" data-pa="${p.id}">✅ تأیید</button><button type="button" class="btn bad" data-pr="${p.id}">✖ رد</button></div>`;
  if (p.status === 'rejected' || p.status === 'error') return `<div class="acts" data-racts="${p.id}"><button type="button" class="btn" data-rr="${p.id}">🔁 بررسی دوباره</button></div>`;
  return '';
}
async function loadPay() {
  const d = await act(null, () => api('payments?status=' + paySt)); if (!d || d === true) return;
  $('#payList').innerHTML = d.items.length ? d.items.map(p => `<div class="item" data-pid="${p.id}">
    ${p.online ? '<span class="tag ok">آنلاین</span>' : `<img class="receipt" loading="lazy" alt="رسید" src="/panel/api/payments/${p.id}/photo" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'receipt none',textContent:'بدون تصویر'}))">`}
    <div class="grow"><b class="num">#${p.id} · ${num(p.amount)} تومان${p.bonus ? ` <small>+ هدیه ${num(p.bonus)}</small>` : ''}</b>
      <small>کاربر <a href="#" data-user="${p.user_id}" class="num">${p.user_id}</a> ${esc(p.name || '')} ${p.username ? '@' + esc(p.username) : ''} · ${p.order_id ? 'خرید مستقیم پلن' : 'شارژ کیف پول'} · ${when(p.created)}</small></div>
    ${tag(p.status)}${payActs(p)}</div>`).join('')
    : '<p class="empty">موردی نیست.</p>';
}
$('#payList').addEventListener('click', async e => {
  const t = e.target.closest('button,.receipt'); if (!t) return;
  if (t.matches('img.receipt')) { const z = document.createElement('div'); z.className = 'zoom'; z.innerHTML = `<img src="${t.src}" alt="">`; z.onclick = () => z.remove(); document.body.appendChild(z); return; }
  const d = t.dataset;
  if (d.pa) { if (!confirm(`رسید #${d.pa} تأیید شود؟`)) return; if (await act(t, () => api(`payments/${d.pa}/approve`, {}), 'تأیید شد ✓')) loadPay(); }
  if (d.pr) { if (!confirm(`رسید #${d.pr} رد شود؟`)) return; if (await act(t, () => api(`payments/${d.pr}/reject`, {}), 'رد شد')) loadPay(); }
  if (d.rr) { const box = $(`[data-racts="${d.rr}"]`); box.innerHTML = `<span class="muted">بررسی دوباره:</span><button type="button" class="btn ok" data-ry="${d.rr}">✅ تأیید</button><button type="button" class="btn ghost" data-rn="${d.rr}">✖ لغو</button>`; }
  if (d.rn) { $(`[data-racts="${d.rn}"]`).innerHTML = `<button type="button" class="btn" data-rr="${d.rn}">🔁 بررسی دوباره</button>`; }
  if (d.ry) { if (!confirm(`رسید #${d.ry} بعد از بررسی دوباره تأیید شود؟ موجودی/سرویس کاربر اعمال می‌شود.`)) return; if (await act(t, () => api(`payments/${d.ry}/reapprove`, {}), 'رسید تأیید شد ✓')) loadPay(); }
});

/* ---------- users ---------- */
$('#userSearch').addEventListener('submit', e => { e.preventDefault(); loadUsers(); });
async function loadUsers() {
  const d = await act(null, () => api('users?q=' + encodeURIComponent($('#uq').value.trim()))); if (!d || d === true) return;
  $('#userList').innerHTML = d.items.length ? d.items.map(u => `<div class="item click" data-user="${u.id}">
    <span class="avatar">${esc((u.name || '?').trim()[0] || '?')}</span>
    <div class="grow"><b>${esc(u.name || '—')} ${u.username ? `<small class="latin">@${esc(u.username)}</small>` : ''}</b><small class="num">${u.id} · آخرین بازدید ${when(u.last_seen)}</small></div>
    <b class="num">${num(u.balance)} تومان</b>${u.banned ? '<span class="tag off">مسدود</span>' : ''}</div>`).join('') : '<p class="empty">کاربری پیدا نشد.</p>';
}
document.addEventListener('click', e => { const t = e.target.closest('[data-user]'); if (t && !e.target.closest('.drawer')) { e.preventDefault(); openUser(+t.dataset.user); } });
async function openUser(id) {
  const d = await act(null, () => api('users/' + id)); if (!d || d === true) return;
  const u = d.user;
  $('#drawerIn').innerHTML = `<div class="bar"><h2>${esc(u.name || 'کاربر')}</h2><button type="button" class="btn ghost" data-close>بستن ×</button></div>
    <div class="kv"><div><small>آیدی</small><b class="num">${u.id}</b></div><div><small>یوزرنیم</small><b class="latin">${u.username ? '@' + esc(u.username) : '—'}</b></div>
    <div><small>موجودی</small><b class="num" id="dBal">${num(u.balance)}</b></div><div><small>شماره</small><b class="num">${esc(u.phone || '—')}</b></div>
    <div><small>عضویت</small><b class="num">${when(u.created)}</b></div><div><small>زیرمجموعه</small><b class="num">${num(d.refs)}</b></div></div>
    <form class="card inline" id="balForm"><input type="number" min="1" id="balAmt" placeholder="مبلغ (تومان)" required><button class="btn ok" data-op="add">افزایش</button><button class="btn bad" data-op="sub">کسر</button></form>
    <form class="card" id="msgForm"><textarea id="msgTxt" rows="3" placeholder="پیام مستقیم به کاربر"></textarea><button class="btn">ارسال پیام</button></form>
    <div class="acts"><button type="button" class="btn ${u.banned ? 'ok' : 'bad'}" id="banBtn">${u.banned ? 'رفع مسدودی' : 'مسدود کردن'}</button><button type="button" class="btn" id="userSvcBtn">📦 همه سرویس‌های این کاربر</button></div>
    <h3 style="margin-top:18px">سرویس‌ها</h3><div class="list">${d.services.map(s => `<div class="item"><div class="grow"><b class="latin">${esc(s.title || s.username)}</b><small class="num">${num(s.gb)}GB · انقضا ${when(s.expire)}</small></div>${tag(s.status)}</div>`).join('') || '<p class="muted">ندارد.</p>'}</div>
    <h3 style="margin-top:18px">پرداخت‌ها</h3><div class="list">${d.payments.map(p => `<div class="item"><div class="grow"><b class="num">#${p.id} · ${num(p.amount)}</b><small class="num">${when(p.created)}</small></div>${tag(p.status)}</div>`).join('') || '<p class="muted">ندارد.</p>'}</div>`;
  $('#drawer').classList.add('open');
  let op = 'add';
  $$('#balForm button').forEach(b => b.addEventListener('click', () => { op = b.dataset.op; }));
  $('#balForm').addEventListener('submit', async e => {
    e.preventDefault(); const amount = +$('#balAmt').value; if (!amount) return;
    if (!confirm(`${num(amount)} تومان ${op === 'add' ? 'اضافه' : 'کسر'} شود؟`)) return;
    const r = await act(e.submitter, () => api(`users/${id}/balance`, { op, amount }), 'انجام شد ✓'); if (r && r !== true) { $('#dBal').textContent = num(r.balance); $('#balAmt').value = ''; }
  });
  $('#msgForm').addEventListener('submit', async e => { e.preventDefault(); const text = $('#msgTxt').value.trim(); if (!text) return; if (await act(e.submitter, () => api(`users/${id}/message`, { text }), 'ارسال شد ✓')) $('#msgTxt').value = ''; });
  $('#banBtn').addEventListener('click', async e => { if (!confirm('مطمئنی؟')) return; if (await act(e.target, () => api(`users/${id}/ban`, { banned: !u.banned }), 'ذخیره شد')) openUser(id); });
  $('#userSvcBtn').addEventListener('click', () => { $('#drawer').classList.remove('open'); $('#sq').value = String(id); $('#sst').value = ''; go('svc'); });
}
$('#drawer').addEventListener('click', e => { if (e.target.id === 'drawer' || e.target.closest('[data-close]')) $('#drawer').classList.remove('open'); });

/* ---------- services ---------- */
const SV = { items: [], total: 0, offset: 0 };
$('#svcSearch').addEventListener('submit', e => { e.preventDefault(); loadSvc(false); });
$('#sst').addEventListener('change', () => loadSvc(false));
$('#svcMore').addEventListener('click', () => loadSvc(true));
async function loadSvc(more) {
  const off = more ? SV.items.length : 0;
  const q = fa2en($('#sq').value.trim());
  const d = await act(more ? $('#svcMore') : null, () => api(`services?q=${encodeURIComponent(q)}&status=${$('#sst').value}&offset=${off}&limit=50`)); if (!d || d === true) return;
  SV.items = more ? SV.items.concat(d.items) : d.items; SV.total = d.total;
  $('#svcCount').textContent = `${num(SV.total)} سرویس${/^\d+$/.test(q) ? ' · کاربر/سرویس ' + q : ''}`;
  renderSvc();
}
function renderSvc() {
  $('#svcList').innerHTML = SV.items.length ? SV.items.map(s => {
    const off = s.status === 'disabled';
    return `<div class="item svc ${off ? 'is-off' : ''}"><div class="grow svc-copy"><div class="svc-title"><b class="latin">${esc(s.username)}</b>${tag(s.status)}</div>
    <div class="svc-meta"><span>👤 <a href="#" data-user="${s.user_id}">${s.user_id}</a>${s.uname ? ' · ' + esc(s.uname) : ''}${s.uuser ? ' · @' + esc(s.uuser) : ''}</span><span>🧩 ${esc(s.panel || '—')}</span></div>
    <div class="svc-specs"><span>📦 حجم <b class="num">${num(s.gb)}GB</b></span><span>⏱ ${num(s.days)} روز</span><span>💰 ${num(s.price)} تومان</span><span>⌛ انقضا ${when(s.expire)}</span></div></div>
    ${s.is_test ? '<span class="tag wait">تست</span>' : ''}
    <div class="acts">${s.sub || s.link ? `<button type="button" class="btn" data-copy="${esc(s.sub || s.link)}">⧉ کپی لینک</button>` : ''}
      ${s.status === 'pending' ? '' : `<button type="button" class="btn ${off ? 'ok' : 'warn'}" data-stog="${s.id}">${off ? '▶ فعال کردن' : '⏸ غیرفعال کردن'}</button>`}
      <button type="button" class="btn bad" data-sdel="${s.id}">🗑 حذف</button></div></div>`;
  }).join('') : '<p class="empty">سرویسی پیدا نشد.</p>';
  $('#svcMore').classList.toggle('hidden', SV.items.length >= SV.total);
  $('#svcMore').textContent = `نمایش بیشتر (${num(SV.total - SV.items.length)})`;
}
$('#svcList').addEventListener('click', async e => {
  const t = e.target.closest('button'); if (!t) return;
  if (t.dataset.copy) { try { await navigator.clipboard.writeText(t.dataset.copy); toast('کپی شد'); } catch (_) { toast('کپی نشد', true); } }
  if (t.dataset.stog) {
    const s = SV.items.find(x => x.id == t.dataset.stog); const enable = s && s.status === 'disabled';
    if (!confirm(enable ? 'سرویس روی پنل و ربات فعال شود؟' : 'سرویس روی پنل و ربات غیرفعال شود؟')) return;
    const r = await act(t, () => api(`services/${t.dataset.stog}/toggle`, {}), enable ? 'سرویس فعال شد ✓' : 'سرویس غیرفعال شد');
    if (r && r !== true && s) { s.status = r.status; renderSvc(); }
  }
  if (t.dataset.sdel) { if (!confirm('سرویس از پنل و ربات حذف شود؟ قابل برگشت نیست.')) return; if (await act(t, () => api(`services/${t.dataset.sdel}/delete`, {}), 'حذف شد')) { SV.items = SV.items.filter(x => x.id != t.dataset.sdel); SV.total--; renderSvc(); } }
});

/* ---------- tickets ---------- */
let tkSt = 'open', tkId = null;
$('#tkSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; tkSt = b.dataset.st; $$('#tkSeg button').forEach(x => x.classList.toggle('on', x === b)); loadTk(); });
async function loadTk() {
  const d = await act(null, () => api('tickets?status=' + tkSt)); if (!d || d === true) return;
  $('#tkList').innerHTML = d.items.length ? d.items.map(t => `<div class="item click ${t.id === tkId ? 'sel' : ''}" data-tk="${t.id}"><div class="grow"><b class="num">#${t.id} · ${esc(t.name || t.user_id)}</b><small class="num">${when(t.updated)}</small></div>${t.admin_id ? '' : '<span class="tag wait">منتظر پاسخ</span>'}</div>`).join('') : '<p class="empty">تیکتی نیست.</p>';
}
$('#tkList').addEventListener('click', e => { const t = e.target.closest('[data-tk]'); if (t) openTk(+t.dataset.tk); });
async function openTk(id) {
  tkId = id; $$('#tkList .item').forEach(x => x.classList.toggle('sel', +x.dataset.tk === id));
  const d = await act(null, () => api('tickets/' + id)); if (!d || d === true) return;
  const open = d.ticket.status === 'open';
  $('#tkView').innerHTML = `<div class="bar"><h3>تیکت #${id} · کاربر <a href="#" data-user="${d.ticket.user_id}" class="num">${d.ticket.user_id}</a></h3>${open ? '<button type="button" class="btn bad" id="tkClose">بستن تیکت</button>' : tag('closed')}</div>
    <div class="msgs">${d.messages.map(m => `<div class="msg ${m.admin ? 'admin' : 'user'}">${esc(m.body)}<small class="num">${when(m.created)}</small></div>`).join('')}</div>
    ${open ? '<form id="tkReply"><textarea id="tkTxt" rows="3" placeholder="پاسخ به کاربر"></textarea><button class="btn primary" style="margin-top:8px">ارسال پاسخ</button></form>' : ''}`;
  const m = $('#tkView .msgs'); m.scrollTop = m.scrollHeight;
  $('#tkReply')?.addEventListener('submit', async e => { e.preventDefault(); const text = $('#tkTxt').value.trim(); if (!text) return; if (await act(e.submitter, () => api(`tickets/${id}/reply`, { text }), 'پاسخ ارسال شد ✓')) { openTk(id); loadTk(); } });
  $('#tkClose')?.addEventListener('click', async e => { if (!confirm('بسته شود؟')) return; if (await act(e.target, () => api(`tickets/${id}/close`, {}), 'بسته شد')) { openTk(id); loadTk(); } });
}

/* ---------- plans: month → plans → editor ---------- */
const PL = { items: [], month: null };
const monthName = m => ({ 1: 'یک ماهه', 2: 'دو ماهه', 3: 'سه ماهه', 6: 'شش ماهه', 12: 'یک ساله' }[m] || `${m} ماهه`);
async function loadPlans() {
  const d = await act(null, () => api('plans')); if (!d || d === true) return;
  PL.items = d.items; renderPlans();
}
function renderPlans() {
  const months = [...new Set([1, 3, 6, ...PL.items.map(p => +p.months)])].filter(Boolean).sort((a, b) => a - b);
  $('#monthCards').innerHTML = months.map(m => {
    const list = PL.items.filter(p => +p.months === m), on = list.filter(p => p.active).length;
    return `<button type="button" class="month-card ${PL.month === m ? 'on' : ''}" data-month="${m}"><b class="num">${m}</b><span>${monthName(m)}</span><small class="num">${num(list.length)} پلن · ${num(on)} فعال</small></button>`;
  }).join('');
  const has = PL.month != null;
  $('#planHead').classList.toggle('hidden', !has);
  if (!has) { $('#planList').innerHTML = '<p class="empty">یک مدت را انتخاب کن تا پلن‌هایش بیاید.</p>'; return; }
  $('#planTitle').textContent = `پلن‌های ${monthName(PL.month)}`;
  const list = PL.items.filter(p => +p.months === PL.month).sort((a, b) => a.gb - b.gb || a.price - b.price);
  $('#planList').innerHTML = list.length ? list.map(p => `<button type="button" class="plan-card ${p.active ? '' : 'off'}" data-plan="${p.id}">
      <span class="plan-gb num">${num(p.gb)}<small>GB</small></span>
      <span class="plan-meta num">${num(p.days)} روز · #${p.id}</span>
      <span class="plan-price num">${num(p.price)} <small>تومان</small></span>
      ${p.active ? '<span class="tag ok">فعال</span>' : '<span class="tag off">غیرفعال</span>'}</button>`).join('')
    : '<p class="empty">برای این مدت پلنی تعریف نشده. از فرم بالا اضافه کن.</p>';
}
$('#monthCards').addEventListener('click', e => { const b = e.target.closest('[data-month]'); if (!b) return; PL.month = +b.dataset.month; renderPlans(); });
$('#planBack').addEventListener('click', () => { PL.month = null; renderPlans(); });
$('#planList').addEventListener('click', e => { const b = e.target.closest('[data-plan]'); if (b) openPlan(+b.dataset.plan); });
function openPlan(id) {
  const p = PL.items.find(x => x.id === id); if (!p) return;
  openSheet(`<div class="sheet-head"><div><small>PLAN #${p.id}</small><h3>${monthName(+p.months)} · ${num(p.gb)} گیگ</h3></div><button type="button" class="icon-btn" data-sclose>×</button></div>
    <form id="planEdit" class="form-grid">
      <label>تغییر حجم (گیگ)<input id="peGb" inputmode="numeric" value="${p.gb}" required></label>
      <label>تغییر قیمت (تومان)<input id="pePrice" inputmode="numeric" value="${p.price}" required></label>
      <label>مدت (روز)<input id="peDays" inputmode="numeric" value="${p.days}" required></label>
      <button class="btn primary wide">💾 ذخیره</button>
    </form>
    <div class="acts sheet-acts"><button type="button" class="btn ${p.active ? 'warn' : 'ok'}" id="peTog">${p.active ? '⏸ غیرفعال کن' : '▶ فعال کن'}</button><button type="button" class="btn bad" id="peDel">🗑 حذف پلن</button></div>`);
  $('#planEdit').addEventListener('submit', async e => {
    e.preventDefault();
    const gb = intOf($('#peGb').value), price = intOf($('#pePrice').value), days = intOf($('#peDays').value);
    if (!(gb > 0) || !(price >= 0) || !(days > 0)) return toast('حجم، قیمت و روز را درست وارد کن', true);
    if (await act(e.submitter, () => api('plans/' + id, { gb, price, days }), 'پلن ذخیره شد ✓')) { Object.assign(p, { gb, price, days }); closeSheet(); renderPlans(); }
  });
  $('#peTog').addEventListener('click', async e => { if (await act(e.target, () => api('plans/' + id, { active: !p.active }), 'وضعیت پلن عوض شد')) { p.active = p.active ? 0 : 1; closeSheet(); renderPlans(); } });
  $('#peDel').addEventListener('click', async e => { if (!confirm('پلن حذف شود؟')) return; if (await act(e.target, () => api(`plans/${id}/delete`, {}), 'حذف شد')) { PL.items = PL.items.filter(x => x.id !== id); closeSheet(); renderPlans(); } });
}
$('#planAdd').addEventListener('submit', async e => {
  e.preventDefault(); const f = new FormData(e.target); const body = Object.fromEntries([...f].map(([k, v]) => [k, +v]));
  if (await act(e.submitter, () => api('plans', body), 'پلن اضافه شد ✓')) { e.target.reset(); PL.month = body.months; loadPlans(); }
});
$('#planBulkBtn').addEventListener('click', () => { openSheet(`<div class="sheet-head"><div><small>BULK PLANS</small><h3>افزودن چند پلن</h3></div><button type="button" class="icon-btn" data-sclose>×</button></div><form id="bulkPlanForm" class="form-grid"><label>مدت مشترک (ماه)<input id="bpMonths" type="number" min="1" value="1" required></label><label>روز مشترک<input id="bpDays" type="number" min="1" value="30" required></label><label>پلن‌ها، هر خط به شکل <code>حجم,قیمت</code><textarea id="bpItems" rows="7" placeholder="20,20000\n40,35000\n60,45000" required></textarea></label><p class="hint">بعد از ثبت، همه پلن‌ها در لیست می‌آیند و از بخش ویرایش می‌توانی دستی اصلاحشان کنی.</p><button class="btn primary wide">ثبت همه پلن‌ها</button></form>`); $('#bulkPlanForm').addEventListener('submit', async e => { e.preventDefault(); const items = $('#bpItems').value.split('\n').map(x => x.trim()).filter(Boolean).map(x => { const [gb, price] = x.split(',').map(v => intOf(v)); return { gb, price }; }); if (!items.length || items.some(x => !(x.gb > 0) || x.price < 0 || !Number.isFinite(x.price))) return toast('فرمت پلن‌ها باید حجم,قیمت باشد', true); const body = { months: +$('#bpMonths').value, days: +$('#bpDays').value, items }; if (await act(e.submitter, () => api('plans/bulk', body), 'پلن‌ها اضافه شدند ✓')) { closeSheet(); loadPlans(); } }); });

/* ---------- panels ---------- */
async function loadPanels() {
  const d = await act(null, () => api('panels')); if (!d || d === true) return;
  $('#panelList').innerHTML = d.items.map(p => `<div class="item"><div class="grow"><b>${esc(p.name)} <small class="latin">${esc(p.ptype)}</small></b><small class="latin">${esc(p.url || '—')} · ${num(p.services)} سرویس فعال</small></div>
    ${p.active ? '<span class="tag ok">فعال</span>' : '<span class="tag off">غیرفعال</span>'}<span class="muted" data-res="${p.id}"></span>
    <div class="acts"><button type="button" class="btn" data-ntest="${p.id}">تست اتصال</button><button type="button" class="btn" data-ntog="${p.id}">${p.active ? 'غیرفعال کن' : 'فعال کن'}</button><button type="button" class="btn bad" data-ndel="${p.id}" data-nname="${esc(p.name)}" data-nsvc="${num(p.services)}">🗑 حذف پنل</button></div></div>`).join('') || '<p class="empty">پنلی ثبت نشده.</p>';
}
$('#panelList').addEventListener('click', async e => {
  const t = e.target.closest('button'); if (!t) return;
  if (t.dataset.ntest) { const r = await act(t, () => api(`panels/${t.dataset.ntest}/test`, {})); if (r && r !== true) { const s = $(`[data-res="${t.dataset.ntest}"]`); s.textContent = r.message; s.style.color = r.success ? 'var(--ok)' : 'var(--bad)'; } }
  if (t.dataset.ntog) { if (await act(t, () => api(`panels/${t.dataset.ntog}/toggle`, {}))) loadPanels(); }
  if (t.dataset.ndel) {
    const warn = +String(t.dataset.nsvc).replace(/,/g, '') ? `\nاین پنل ${t.dataset.nsvc} سرویس فعال دارد.` : '';
    if (!confirm(`پنل «${t.dataset.nname}» حذف شود؟ از ربات هم حذف می‌شود.${warn}`)) return;
    if (await act(t, () => api(`panels/${t.dataset.ndel}/delete`, {}), 'پنل حذف شد ✓')) loadPanels();
  }
});
/* ➕ add panel (same DB as bot) */
let PTYPES = null;
const PF = {
  manual: { url: 0, user: 0, pass: 0, extra: 0 },
  hiddify: { urlL: 'لینک ادمین هیدیفای', urlP: 'https://domain.com/ADMIN_PATH/ADMIN_UUID/admin/', user: 0, passL: 'API Key (UUID ادمین، اگر داخل لینک هست خالی بگذار)', passReq: false },
};
$('#panelAddBtn').addEventListener('click', async e => {
  if (!PTYPES) { const d = await act(e.target, () => api('panel-types')); if (!d || d === true) return; PTYPES = d; }
  const opts = PTYPES.items.map(t => `<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('');
  openSheet(`<div class="sheet-head"><div><small>NEW PANEL</small><h3>افزودن پنل</h3></div><button type="button" class="icon-btn" data-sclose>×</button></div>
    <form id="pnAdd" class="form-grid" autocomplete="off">
      <label>نوع پنل<select id="pnType">${opts}</select></label>
      <label>اسم پنل / لوکیشن<input id="pnName" placeholder="مثلاً 🇩🇪 آلمان" required maxlength="60"></label>
      <label id="pnUrlL"><span>لینک پنل</span><input id="pnUrl" class="latin" dir="ltr" inputmode="url" placeholder="https://panel.site.com:8000"></label>
      <label id="pnUserL">یوزرنیم ادمین<input id="pnUser" class="latin" dir="ltr" autocomplete="off"></label>
      <label id="pnPassL"><span>پسورد ادمین</span><input id="pnPass" class="latin" dir="ltr" type="password" autocomplete="new-password"></label>
      <label id="pnExtraL">تنظیمات اضافه (اختیاری)<input id="pnExtra" class="latin" dir="ltr"><small id="pnHint"></small></label>
      <p class="muted" id="pnRes"></p>
      <button class="btn primary wide">➕ افزودن</button>
    </form>`);
  const sync = () => {
    const t = $('#pnType').value, f = PF[t] || {}, h = PTYPES.items.find(x => x.id === t);
    $('#pnUrlL').classList.toggle('hidden', f.url === 0); $('#pnUserL').classList.toggle('hidden', f.user === 0);
    $('#pnPassL').classList.toggle('hidden', f.pass === 0); $('#pnExtraL').classList.toggle('hidden', f.extra === 0);
    $('#pnUrlL span').textContent = f.urlL || 'لینک پنل (با پورت)'; $('#pnUrl').placeholder = f.urlP || 'https://panel.site.com:8000';
    $('#pnPassL span').textContent = f.passL || 'پسورد ادمین'; $('#pnHint').textContent = (h && h.hint) || '';
  };
  $('#pnType').addEventListener('change', sync); sync();
  $('#pnAdd').addEventListener('submit', async ev => {
    ev.preventDefault();
    const t = $('#pnType').value, f = PF[t] || {};
    const body = { ptype: t, name: $('#pnName').value.trim(), url: $('#pnUrl').value.trim(), user: $('#pnUser').value.trim(), password: $('#pnPass').value, extra: $('#pnExtra').value.trim() };
    if (!body.name) return toast('اسم پنل را وارد کن', true);
    if (f.url !== 0 && !body.url) return toast('لینک پنل را وارد کن', true);
    if (f.user !== 0 && !body.user) return toast('یوزرنیم را وارد کن', true);
    if (f.pass !== 0 && f.passReq !== false && !body.password) return toast('پسورد را وارد کن', true);
    $('#pnRes').textContent = '⏳ در حال تست اتصال و ذخیره...';
    const r = await act(ev.submitter, () => api('panels', body));
    if (!r || r === true) { $('#pnRes').textContent = ''; return; }
    toast(r.success ? 'پنل اضافه شد و اتصال موفق بود ✓' : 'پنل اضافه شد، ولی تست اتصال ناموفق بود: ' + r.message, !r.success);
    closeSheet(); loadPanels();
  });
});

/* ---------- discounts ---------- */
async function loadDc() {
  const d = await act(null, () => api('discounts')); if (!d || d === true) return;
  loadUserDiscounts();
  $('#dcList').innerHTML = d.items.map(c => `<div class="item"><div class="grow"><b class="latin">${esc(c.code)}</b><small class="num">${c.percent}% · استفاده ${num(c.used)}${c.max_uses ? ' از ' + num(c.max_uses) : ''}</small></div>
    ${c.active ? '<span class="tag ok">فعال</span>' : '<span class="tag off">غیرفعال</span>'}<div class="acts"><button type="button" class="btn" data-dtog="${esc(c.code)}">${c.active ? 'غیرفعال' : 'فعال'}</button><button type="button" class="btn bad" data-ddel="${esc(c.code)}">حذف</button></div></div>`).join('') || '<p class="empty">کدی نیست.</p>';
}
$('#dcAdd').addEventListener('submit', async e => {
  e.preventDefault(); const f = new FormData(e.target);
  if (await act(e.submitter, () => api('discounts', { code: f.get('code'), percent: +f.get('percent'), max_uses: +(f.get('max_uses') || 0) }), 'کد ساخته شد ✓')) { e.target.reset(); loadDc(); }
});
$('#dcList').addEventListener('click', async e => {
  const t = e.target.closest('button'); if (!t) return;
  if (t.dataset.dtog) { if (await act(t, () => api(`discounts/${encodeURIComponent(t.dataset.dtog)}/toggle`, {}))) loadDc(); }
  if (t.dataset.ddel) { if (!confirm('حذف شود؟')) return; if (await act(t, () => api(`discounts/${encodeURIComponent(t.dataset.ddel)}/delete`, {}), 'حذف شد')) loadDc(); }
});

async function loadUserDiscounts() {
  const d = await act(null, () => api('user-discounts')); if (!d || d === true) return;
  $('#udList').innerHTML = d.items.map(x => `<div class="item"><div class="grow"><b>${esc(x.name || 'کاربر')} <small class="latin num">${x.user_id}</small></b><small>${x.username ? '@' + esc(x.username) + ' · ' : ''}${num(x.percent)}٪ تخفیف اختصاصی</small></div><span class="tag ok">فعال</span><div class="acts"><button type="button" class="btn bad" data-udel="${x.user_id}">حذف تخفیف</button></div></div>`).join('') || '<p class="empty">تخفیف اختصاصی ثبت نشده.</p>';
}
$('#udSave').addEventListener('click', async e => { const user_id = intOf($('#udUser').value), percent = intOf($('#udPercent').value); if (!(user_id > 0) || !(percent > 0 && percent <= 100)) return toast('آیدی و درصد را درست وارد کن', true); if (await act(e.target, () => api('user-discounts', { user_id, percent }), 'تخفیف اختصاصی ثبت شد ✓')) { $('#udUser').value = ''; $('#udPercent').value = ''; loadUserDiscounts(); } });
$('#udList').addEventListener('click', async e => { const t = e.target.closest('[data-udel]'); if (!t) return; if (await act(t, () => api('user-discounts/' + t.dataset.udel + '/delete', {}), 'تخفیف حذف شد')) loadUserDiscounts(); });

/* ---------- admins ---------- */
async function loadAdmins() {
  const d = await act(null, () => api('admins')); if (!d || d === true) return;
  const row = (x, type, removable) => `<div class="item admin-row"><div class="avatar">${type === 'main' ? '👑' : type === 'temp' ? '⏳' : '🛡️'}</div><div class="grow"><b>${esc(x.name || 'کاربر بدون نام')} <small class="latin num">${x.id}</small></b><small>${x.username ? '@' + esc(x.username) : 'بدون یوزرنیم'}${type === 'temp' ? ' · تا ' + when(x.expires) : type === 'env' ? ' · از تنظیمات سرور' : ' · دائمی'}</small></div>${removable ? `<button type="button" class="btn bad" data-adel="${x.id}">حذف</button>` : '<span class="tag ok">فعال</span>'}</div>`;
  $('#adminList').innerHTML = [row(d.main, 'main', false), ...(d.env || []).map(x => row(x, 'env', false)), ...(d.permanent || []).map(x => row(x, 'permanent', true)), ...(d.temporary || []).map(x => row(x, 'temp', true))].join('');
}
$('#adminAdd').addEventListener('submit', async e => { e.preventDefault(); const f = new FormData(e.target); const body = { user_id: intOf(f.get('user_id')), days: +(f.get('days') || 0), hours: +(f.get('hours') || 0) }; if (!(body.user_id > 0)) return toast('آیدی کاربر را درست وارد کن', true); if (await act(e.submitter, () => api('admins', body), 'ادمین اضافه شد ✓')) { e.target.reset(); loadAdmins(); } });
$('#adminList').addEventListener('click', async e => { const t = e.target.closest('[data-adel]'); if (!t) return; if (await act(t, () => api('admins/' + t.dataset.adel + '/delete', {}), 'ادمین حذف شد')) loadAdmins(); });

/* ---------- broadcast ---------- */
let bcTimer;
async function loadBc() {
  const d = await act(null, () => api('broadcast')); if (!d || d === true) return;
  $('#bcState').textContent = d.total ? `${d.running ? 'در حال ارسال' : 'آخرین ارسال'}: ${num(d.sent)} موفق · ${num(d.failed)} ناموفق از ${num(d.total)}` : '';
  clearTimeout(bcTimer); if (d.running && cur === 'bc') bcTimer = setTimeout(loadBc, 2000);
}
$('#bcForm').addEventListener('submit', async e => {
  e.preventDefault(); const text = $('#bcText').value.trim(); if (!text) return;
  if (!confirm('پیام برای همه کاربران ارسال شود؟')) return;
  const button_text = $('#bcBtnText').value.trim(), button_start = $('#bcStart').value.trim() || 'start'; if (await act(e.submitter, () => api('broadcast', { text, button_text, button_start }), 'ارسال شروع شد')) { $('#bcText').value = ''; $('#bcBtnText').value = ''; $('#bcStart').value = ''; setTimeout(loadBc, 800); }
});

/* ---------- appearance: تغییرات ظاهر ---------- */
const LOOK = { btns: [], texts: [], emojis: [], premium: true, kind: 'btn', loaded: false };
const COLORS = [['orig', 'رنگ اورجینال'], ['green', 'سبز'], ['red', 'قرمز'], ['blue', 'آبی'], ['none', 'بی‌رنگ']];
const colorName = c => (COLORS.find(x => x[0] === c) || COLORS[0])[1];
async function loadLook(force) {
  if (!LOOK.loaded || force !== false) {
    const d = await act(null, () => api('appearance')); if (!d || d === true) return;
    LOOK.btns = d.buttons; LOOK.texts = d.texts; LOOK.emojis = d.emojis || []; LOOK.premium = d.premium; LOOK.loaded = true;
  }
  renderLook();
}
function renderLook() {
  const q = $('#lq').value.trim();
  const bs = LOOK.btns.map((b, i) => ({ ...b, i })).filter(b => match(q, b.name, b.label));
  const ts = LOOK.texts.filter(t => match(q, t.title, t.key, t.value));
  const es = LOOK.emojis.filter(t => match(q, t.key, t.fallback, t.id));
  $('#lookBtnN').textContent = num(bs.length); $('#lookTxtN').textContent = num(ts.length); $('#lookEmojiN').textContent = num(es.length);
  $$('#lookSeg button').forEach(b => b.classList.toggle('on', b.dataset.k === LOOK.kind));
  if (LOOK.kind === 'emoji') {
    $('#lookList').innerHTML = es.length ? es.map(e => `<button type="button" class="look-btn emoji-row" data-le="${esc(e.key)}"><span class="swatch">${esc(e.fallback || '⭐️')}</span><span class="lb-txt"><b>${esc(e.key)}</b><small>${e.id ? 'آیدی پریمیوم ثبت شده' : 'بدون آیدی پریمیوم'}</small></span><i>‹</i></button>`).join('') : `<p class="empty">ایموجی‌ای پیدا نشد.</p>`;
  } else if (LOOK.kind === 'btn') {
    $('#lookList').innerHTML = bs.length ? bs.map(b => `<button type="button" class="look-btn c-${esc(b.color)}" data-lb="${b.i}">
        <span class="swatch"></span><span class="lb-txt"><b>${esc(b.label || b.name)}</b><small>${b.group ? 'گروه دکمه‌ها' : (b.label ? 'اصلی: ' + esc(b.name) : colorName(b.color))}${b.emoji ? ' · ⭐ پریمیوم' : ''}</small></span><i>‹</i></button>`).join('')
      : `<p class="empty">دکمه‌ای با «${esc(q)}» پیدا نشد.${ts.length ? ' در پیام‌ها ' + num(ts.length) + ' مورد هست.' : ''}</p>`;
  } else {
    $('#lookList').innerHTML = ts.length ? ts.map(t => `<button type="button" class="look-btn txt" data-lt="${esc(t.key)}"><span class="swatch">💬</span><span class="lb-txt"><b>${esc(t.title)}</b><small>${esc(t.value.replace(/<[^>]+>/g, '').slice(0, 70))}${t.custom ? ' · ویرایش‌شده' : ''}</small></span><i>‹</i></button>`).join('')
      : `<p class="empty">پیامی با «${esc(q)}» پیدا نشد.</p>`;
  }
}
$('#lookSearch').addEventListener('submit', e => { e.preventDefault(); renderLook(); const q = $('#lq').value.trim(); if (q && LOOK.kind === 'btn' && !$('#lookList [data-lb]') && $('#lookTxtN').textContent !== '0') { LOOK.kind = 'txt'; renderLook(); } });
$('#lq').addEventListener('input', renderLook);
$('#lookClear').addEventListener('click', () => { $('#lq').value = ''; renderLook(); $('#lq').focus(); });
$('#lookSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; LOOK.kind = b.dataset.k; renderLook(); });
$('#lookList').addEventListener('click', e => {
  const b = e.target.closest('[data-lb],[data-lt],[data-le]'); if (!b) return;
  if (b.dataset.le != null) openEmoji(b.dataset.le); else if (b.dataset.lb != null) openBtn(+b.dataset.lb); else openText(b.dataset.lt);
});

function btnPreview(b) { return `<span class="tg-btn c-${esc(b.color)}">${esc(b.label || b.name)}</span>`; }
function openBtn(i, pane) {
  const b = LOOK.btns[i]; if (!b) return;
  openSheet(`<div class="sheet-head"><div><small>BUTTON</small><h3>${esc(b.name)}</h3></div><button type="button" class="icon-btn" data-sclose>×</button></div>
    <div class="preview"><small>پیش‌نمایش در ربات</small>${btnPreview(b)}</div>
    <div class="act-grid">
      <button type="button" class="act-card ${pane === 'color' ? 'on' : ''}" data-pane="color"><span>🎨</span>تغییر رنگ</button>
      <button type="button" class="act-card ${pane === 'name' ? 'on' : ''}" data-pane="name" ${b.group ? 'disabled' : ''}><span>✏️</span>تغییر نام</button>
      <button type="button" class="act-card ${pane === 'msg' ? 'on' : ''}" data-pane="msg" ${b.group ? 'disabled' : ''}><span>💬</span>تغییر پیغام</button>
      <button type="button" class="act-card ${pane === 'emoji' ? 'on' : ''}" data-pane="emoji" ${b.group ? 'disabled' : ''}><span>⭐</span>ایموجی پریمیوم</button>
    </div>
    ${b.group ? '<p class="muted">این یک گروه دکمه است (مثل لیست پلن‌ها)؛ فقط رنگش قابل تغییر است.</p>' : ''}
    <div id="pane" class="pane"></div>`);
  $$('#sheetIn [data-pane]').forEach(x => x.addEventListener('click', () => { $$('#sheetIn [data-pane]').forEach(y => y.classList.toggle('on', y === x)); showPane(i, x.dataset.pane); }));
  if (pane) showPane(i, pane);
}
async function saveBtn(i, body, el, msg) {
  const b = LOOK.btns[i];
  const r = await act(el, () => api('appearance/button', { name: b.name, ...body }), msg);
  if (!r) return false;
  if (body.color != null) b.color = body.color;
  if (body.label != null) b.label = body.label.trim() === b.name ? '' : body.label.trim();
  if (body.emoji != null) b.emoji = fa2en(body.emoji).replace(/\D/g, '');
  const pv = $('#sheetIn .preview .tg-btn'); if (pv) pv.outerHTML = btnPreview(b);
  renderLook(); return true;
}
function showPane(i, pane) {
  const b = LOOK.btns[i], P = $('#pane');
  if (pane === 'color') {
    P.innerHTML = `<div class="colors">${COLORS.map(([k, n]) => `<button type="button" class="color-opt c-${k} ${b.color === k ? 'on' : ''}" data-c="${k}"><span class="swatch"></span>${n}</button>`).join('')}</div>`;
    P.querySelectorAll('[data-c]').forEach(x => x.addEventListener('click', async () => { if (await saveBtn(i, { color: x.dataset.c }, x, 'رنگ ذخیره شد ✓')) showPane(i, 'color'); }));
  }
  if (pane === 'name') {
    P.innerHTML = `<form id="nameForm" class="form-grid"><label>نام جدید دکمه<input id="nmIn" maxlength="60" value="${esc(b.label || b.name)}" required></label>
      <div class="acts"><button class="btn primary">💾 ذخیره نام</button><button type="button" class="btn ghost" id="nmReset">↺ برگرداندن به «${esc(b.name)}»</button></div></form>`;
    $('#nameForm').addEventListener('submit', async e => { e.preventDefault(); const v = $('#nmIn').value.trim(); if (!v) return; await saveBtn(i, { label: v }, e.submitter, 'نام دکمه عوض شد ✓'); });
    $('#nmReset').addEventListener('click', async e => { if (await saveBtn(i, { label: '' }, e.target, 'نام اصلی برگشت')) $('#nmIn').value = b.name; });
  }
  if (pane === 'emoji') {
    P.innerHTML = `<form id="emForm" class="form-grid"><label>آیدی ایموجی پریمیوم (custom_emoji_id)<input id="emIn" inputmode="numeric" dir="ltr" value="${esc(b.emoji)}" placeholder="5368324170671202286"></label>
      ${LOOK.premium ? '' : '<p class="warn-note">ایموجی پریمیوم در تنظیمات ربات خاموش است (premium_on)؛ بعد از روشن کردن نمایش داده می‌شود.</p>'}
      <div class="acts"><button class="btn primary">💾 ذخیره ایموجی</button><button type="button" class="btn ghost" id="emClear">حذف ایموجی</button></div></form>`;
    $('#emForm').addEventListener('submit', async e => { e.preventDefault(); const v = $('#emIn').value.trim(); if (!v) return toast('آیدی را وارد کن', true); await saveBtn(i, { emoji: v }, e.submitter, 'ایموجی ذخیره شد ✓'); });
    $('#emClear').addEventListener('click', async e => { if (await saveBtn(i, { emoji: '' }, e.target, 'ایموجی حذف شد')) $('#emIn').value = ''; });
  }
  if (pane === 'msg') {
    const guess = b.text || '';
    P.innerHTML = `<label class="lbl">پیغامی که با این دکمه نمایش داده می‌شود
      <select id="msgKey">${guess ? '' : '<option value="">— یک پیام انتخاب کن —</option>'}${LOOK.texts.map(t => `<option value="${esc(t.key)}" ${t.key === guess ? 'selected' : ''}>${esc(t.title)}</option>`).join('')}</select></label>
      <div id="msgBox"></div>`;
    const draw = () => { const k = $('#msgKey').value; $('#msgBox').innerHTML = k ? textForm(k) : '<p class="muted">از لیست بالا پیام مربوط به این دکمه را انتخاب کن.</p>'; if (k) bindText(k); };
    $('#msgKey').addEventListener('change', draw); draw();
  }
}
function textForm(k) {
  const t = LOOK.texts.find(x => x.key === k); if (!t) return '';
  return `<form id="txForm" class="form-grid"><label>متن پیام «${esc(t.title)}» <small class="latin">${esc(t.key)}</small><textarea id="txIn" rows="9" required>${esc(t.value)}</textarea></label>
    <p class="hint">متغیرها مثل <code>{USER}</code> <code>{BALANCE}</code> و ایموجی‌ها مثل <code>{E:bot}</code> را نگه دار. تگ‌های HTML تلگرام مجازند.</p>
    <div class="acts"><button class="btn primary">💾 ذخیره پیغام</button><button type="button" class="btn ghost" id="txReset">↺ متن پیش‌فرض</button></div></form>`;
}
function bindText(k) {
  const t = LOOK.texts.find(x => x.key === k);
  $('#txForm').addEventListener('submit', async e => { e.preventDefault(); const v = $('#txIn').value; if (!v.trim()) return; const r = await act(e.submitter, () => api('appearance/text', { key: k, value: v }), 'پیغام ذخیره شد ✓'); if (r && r !== true) { t.value = r.value; t.custom = true; renderLook(); } });
  $('#txReset').addEventListener('click', async e => { if (!confirm('متن به حالت پیش‌فرض برگردد؟')) return; const r = await act(e.target, () => api('appearance/text', { key: k, reset: true }), 'متن پیش‌فرض برگشت'); if (r && r !== true) { t.value = r.value; t.custom = false; $('#txIn').value = r.value; renderLook(); } });
}
function openEmoji(k) {
  const e = LOOK.emojis.find(x => x.key === k); if (!e) return;
  openSheet(`<div class="sheet-head"><div><small>PREMIUM EMOJI</small><h3>ایموجی ${esc(e.key)}</h3></div><button type="button" class="icon-btn" data-sclose>×</button></div><div class="preview"><span class="emoji-big">${esc(e.fallback || '⭐️')}</span><small>پیش‌نمایش جایگزین در صورت خاموش بودن پریمیوم</small></div><form id="emojiForm" class="form-grid"><label>آیدی custom emoji تلگرام<input id="emojiIdIn" inputmode="numeric" dir="ltr" value="${esc(e.id)}" placeholder="5368324170671202286"></label><label>ایموجی جایگزین<input id="emojiFbIn" value="${esc(e.fallback || '⭐️')}" maxlength="8"></label><p class="hint">آیدی را از یک ایموجی پریمیوم در تلگرام کپی کن. اگر خالی باشد، ایموجی معمولی نمایش داده می‌شود.</p><div class="acts"><button class="btn primary">💾 ذخیره ایموجی</button><button type="button" class="btn ghost" id="emojiClear">پاک کردن آیدی</button></div></form>`);
  $('#emojiForm').addEventListener('submit', async ev => { ev.preventDefault(); const id = $('#emojiIdIn').value.trim(); const fallback = $('#emojiFbIn').value.trim() || '⭐️'; const r = await act(ev.submitter, () => api('appearance/emoji', { key: k, emoji_id: id, fallback }), 'ایموجی ذخیره شد ✓'); if (r && r !== true) { e.id = r.id; e.fallback = r.fallback; closeSheet(); renderLook(); } });
  $('#emojiClear').addEventListener('click', async ev => { const r = await act(ev.target, () => api('appearance/emoji', { key: k, emoji_id: '', fallback: $('#emojiFbIn').value.trim() || '⭐️' }), 'آیدی ایموجی پاک شد'); if (r && r !== true) { e.id = ''; closeSheet(); renderLook(); } });
}

function openText(k) {
  const t = LOOK.texts.find(x => x.key === k); if (!t) return;
  openSheet(`<div class="sheet-head"><div><small>MESSAGE</small><h3>${esc(t.title)}</h3></div><button type="button" class="icon-btn" data-sclose>×</button></div>${textForm(k)}`);
  bindText(k);
}

/* ---------- settings ---------- */
async function loadSet() {
  const d = await act(null, () => api('settings')); if (!d || d === true) return;
  $('#setList').innerHTML = d.items.map(s => s.toggle
    ? `<div class="set-row"><label>${esc(s.title)}<small>${esc(s.k)}</small></label><span>${s.v === '1' ? '<span class="tag ok">روشن</span>' : '<span class="tag off">خاموش</span>'}</span><button type="button" class="btn" data-stog="${esc(s.k)}" data-v="${esc(s.v)}">${s.v === '1' ? 'خاموش کن' : 'روشن کن'}</button></div>`
    : `<div class="set-row"><label>${esc(s.title)}<small>${esc(s.k)}</small></label><input value="${esc(s.v)}" data-sk="${esc(s.k)}"><button type="button" class="btn" data-ssave="${esc(s.k)}">ذخیره</button></div>`).join('');
}
$('#setList').addEventListener('click', async e => {
  const t = e.target.closest('button'); if (!t) return;
  if (t.dataset.ssave) { const v = $(`[data-sk="${CSS.escape(t.dataset.ssave)}"]`).value; await act(t, () => api('settings', { k: t.dataset.ssave, v: v || '-' }), 'ذخیره شد ✓'); }
  if (t.dataset.stog) { if (await act(t, () => api('settings', { k: t.dataset.stog, v: t.dataset.v === '1' ? '0' : '1' }))) loadSet(); }
});

/* ---------- logs ---------- */
let logK = 'transactions';
$('#logSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; logK = b.dataset.k; $$('#logSeg button').forEach(x => x.classList.toggle('on', x === b)); loadLog(); });
async function loadLog() {
  const d = await act(null, () => api(logK)); if (!d || d === true) return;
  $('#logList').innerHTML = d.items.map(r => logK === 'transactions'
    ? `<div class="item"><div class="grow"><b>${esc(r.kind)} · <span class="num">${num(r.amount)} تومان</span></b><small class="num">کاربر <a href="#" data-user="${r.user_id}">${r.user_id}</a> · سرویس #${r.service_id ?? '—'}${r.code ? ' · کد ' + esc(r.code) : ''} · ${when(r.created)}</small></div></div>`
    : `<div class="item"><div class="grow"><b>${esc(r.action)}</b><small class="num">${r.actor_id === -1 ? 'پنل وب' : 'ادمین ' + r.actor_id} · ${esc(r.target)} ${esc(String(r.details || '').slice(0, 120))} · ${when(r.created)}</small></div></div>`).join('') || '<p class="empty">موردی نیست.</p>';
}

/* ---------- boot ---------- */
setInterval(() => { if (!$('#shell').classList.contains('hidden') && !$('#sheet').classList.contains('open') && (cur === 'dash' || cur === 'pay')) LOAD[cur](); }, 30000);
(async () => { try { await api('me'); showShell(); api('appearance').then(d => { LOOK.btns = d.buttons; LOOK.texts = d.texts; LOOK.emojis = d.emojis || []; LOOK.premium = d.premium; LOOK.loaded = true; }).catch(() => {}); } catch (e) { showLogin(); if (!/وارد/.test(e.message)) $('#loginErr').textContent = e.message; } })();
})();
