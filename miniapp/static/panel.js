/* NAYI web admin panel */
(() => {
'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = n => Number(n || 0).toLocaleString('en-US');
const when = ts => ts ? new Date(ts * 1000).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—';
let toastT;
function toast(m, err) { const t = $('#toast'); t.textContent = m; t.className = 'toast show' + (err ? ' err' : ''); clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 3000); }
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
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; } catch (e) { toast(e.message, true); } finally { if (btn) btn.disabled = false; }
}
const ST = { active: ['ok', 'فعال'], pending: ['wait', 'در انتظار'], expired: ['off', 'منقضی'], disabled: ['off', 'غیرفعال'], limited: ['off', 'محدود'], ok: ['ok', 'تأیید'], rejected: ['off', 'رد'], open: ['ok', 'باز'], closed: ['off', 'بسته'], error: ['off', 'خطا'], processing: ['wait', 'در حال بررسی'] };
const tag = s => { const [c, t] = ST[s] || ['wait', s]; return `<span class="tag ${c}">${esc(t)}</span>`; };

/* ---------- auth ---------- */
function showLogin() { $('#shell').classList.add('hidden'); $('#login').classList.remove('hidden'); }
function showShell() { $('#login').classList.add('hidden'); $('#shell').classList.remove('hidden'); go('dash'); }
$('#loginForm').addEventListener('submit', async e => {
  e.preventDefault(); $('#loginErr').textContent = '';
  try { await api('login', { username: $('#lu').value, password: $('#lp').value }); $('#lp').value = ''; showShell(); }
  catch (err) { $('#loginErr').textContent = err.message; }
});
$('#menuToggle')?.addEventListener('click', () => $('#shell').classList.toggle('menu-open'));
$('#mobileShade')?.addEventListener('click', () => $('#shell').classList.remove('menu-open'));
$('#quickRefresh')?.addEventListener('click', () => LOAD[cur]?.());
$('#logout').addEventListener('click', async () => { try { await api('logout', {}); } catch (_) {} showLogin(); });

/* ---------- nav ---------- */
const LOAD = { dash: loadDash, pay: loadPay, users: loadUsers, svc: loadSvc, tk: loadTk, plans: loadPlans, panels: loadPanels, dc: loadDc, bc: loadBc, set: loadSet, log: loadLog };
let cur = 'dash';
function go(t) {
  cur = t;
  $('#shell').classList.remove('menu-open');
  $$('#nav button').forEach(b => b.classList.toggle('on', b.dataset.tab === t));
  $$('.tab').forEach(s => s.classList.toggle('on', s.id === 't-' + t));
  LOAD[t]?.();
}
$('#nav').addEventListener('click', e => { const b = e.target.closest('button'); if (b) go(b.dataset.tab); });

/* ---------- dashboard ---------- */
async function loadDash() {
  const d = await act(null, () => api('stats')); if (!d) return;
  const k = [['کاربران', d.users, `+${num(d.users_day)} امروز`], ['سرویس فعال', d.active, `از ${num(d.services)} سرویس`], ['فروش ۲۴ ساعت', d.sales_day, 'تومان'], ['فروش کل', d.sales_all, 'تومان'],
    ['شارژ ۲۴ ساعت', d.topup_day, 'تومان'], ['شارژ کل', d.topup_all, 'تومان'], ['رسید در انتظار', d.pending, 'برای بررسی', d.pending > 0], ['تیکت باز', d.tickets, 'پاسخ بده', d.tickets > 0], ['موجودی کل کاربران', d.balance_total, 'تومان']];
  $('#kpis').innerHTML = k.map(([t, v, s, hot]) => `<div class="kpi ${hot ? 'hot' : ''}"><small>${t}</small><b class="num">${num(v)}</b><small>${s}</small></div>`).join('');
  const max = Math.max(1, ...d.days.map(x => Math.max(x.sales, x.topup)));
  $('#chart').innerHTML = d.days.map(x => `<div class="d" title="${new Date(x.t * 1000).toLocaleDateString('en-GB')} · فروش ${num(x.sales)} · شارژ ${num(x.topup)}"><i class="a" style="height:${x.sales / max * 100}%"></i><i class="b" style="height:${x.topup / max * 100}%"></i><small class="num">${new Date(x.t * 1000).getDate()}</small></div>`).join('');
  badge('#badgePay', d.pending); badge('#badgeTk', d.tickets);
}
function badge(sel, n) { const b = $(sel); b.textContent = n; b.classList.toggle('hidden', !n); }

/* ---------- payments ---------- */
let paySt = 'pending';
$('#paySeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; paySt = b.dataset.st; $$('#paySeg button').forEach(x => x.classList.toggle('on', x === b)); loadPay(); });
async function loadPay() {
  const d = await act(null, () => api('payments?status=' + paySt)); if (!d) return;
  const L = $('#payList');
  L.innerHTML = d.items.length ? d.items.map(p => `<div class="item" data-pid="${p.id}">
    ${p.online ? '<span class="tag ok">آنلاین</span>' : `<img class="receipt" loading="lazy" alt="رسید" src="/panel/api/payments/${p.id}/photo" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'muted',textContent:'بدون تصویر'}))">`}
    <div class="grow"><b class="num">#${p.id} · ${num(p.amount)} تومان${p.bonus ? ` <small>+ هدیه ${num(p.bonus)}</small>` : ''}</b>
      <small>کاربر <a href="#" data-user="${p.user_id}" class="num">${p.user_id}</a> ${esc(p.name || '')} ${p.username ? '@' + esc(p.username) : ''} · ${p.order_id ? 'خرید مستقیم پلن' : 'شارژ کیف پول'} · ${when(p.created)}</small></div>
    ${tag(p.status)}
    ${p.status === 'pending' ? `<div class="acts"><button class="btn ok" data-pa="${p.id}">تأیید</button><button class="btn bad" data-pr="${p.id}">رد</button></div>` : ''}</div>`).join('')
    : '<p class="muted">موردی نیست.</p>';
}
$('#payList').addEventListener('click', async e => {
  const t = e.target;
  if (t.matches('.receipt')) { const z = document.createElement('div'); z.className = 'zoom'; z.innerHTML = `<img src="${t.src}" alt="">`; z.onclick = () => z.remove(); document.body.appendChild(z); return; }
  if (t.dataset.pa) { if (!confirm(`رسید #${t.dataset.pa} تأیید شود؟`)) return; await act(t, () => api(`payments/${t.dataset.pa}/approve`, {}), 'تأیید شد ✓'); loadPay(); }
  if (t.dataset.pr) { if (!confirm(`رسید #${t.dataset.pr} رد شود؟`)) return; await act(t, () => api(`payments/${t.dataset.pr}/reject`, {}), 'رد شد'); loadPay(); }
});

/* ---------- users ---------- */
$('#userSearch').addEventListener('submit', e => { e.preventDefault(); loadUsers(); });
async function loadUsers() {
  const d = await act(null, () => api('users?q=' + encodeURIComponent($('#uq').value.trim()))); if (!d) return;
  $('#userList').innerHTML = d.items.length ? d.items.map(u => `<div class="item click" data-user="${u.id}">
    <div class="grow"><b>${esc(u.name || '—')} ${u.username ? `<small class="latin">@${esc(u.username)}</small>` : ''}</b><small class="num">${u.id} · آخرین بازدید ${when(u.last_seen)}</small></div>
    <b class="num">${num(u.balance)} تومان</b>${u.banned ? '<span class="tag off">مسدود</span>' : ''}</div>`).join('') : '<p class="muted">کاربری پیدا نشد.</p>';
}
document.addEventListener('click', e => { const t = e.target.closest('[data-user]'); if (t && !e.target.closest('.drawer')) { e.preventDefault(); openUser(+t.dataset.user); } });
async function openUser(id) {
  const d = await act(null, () => api('users/' + id)); if (!d) return;
  const u = d.user;
  $('#drawerIn').innerHTML = `<div class="bar"><h2>${esc(u.name || 'کاربر')}</h2><button class="btn ghost" data-close>بستن ×</button></div>
    <div class="kv"><div><small>آیدی</small><b class="num">${u.id}</b></div><div><small>یوزرنیم</small><b class="latin">${u.username ? '@' + esc(u.username) : '—'}</b></div>
    <div><small>موجودی</small><b class="num" id="dBal">${num(u.balance)}</b></div><div><small>شماره</small><b class="num">${esc(u.phone || '—')}</b></div>
    <div><small>عضویت</small><b class="num">${when(u.created)}</b></div><div><small>زیرمجموعه</small><b class="num">${num(d.refs)}</b></div></div>
    <form class="card inline" id="balForm"><input type="number" min="1" id="balAmt" placeholder="مبلغ (تومان)" required><button class="btn ok" data-op="add">افزایش</button><button class="btn bad" data-op="sub">کسر</button></form>
    <form class="card" id="msgForm"><textarea id="msgTxt" rows="3" placeholder="پیام مستقیم به کاربر"></textarea><button class="btn">ارسال پیام</button></form>
    <button class="btn ${u.banned ? 'ok' : 'bad'}" id="banBtn">${u.banned ? 'رفع مسدودی' : 'مسدود کردن'}</button>
    <h3 style="margin-top:18px">سرویس‌ها</h3><div class="list">${d.services.map(s => `<div class="item"><div class="grow"><b class="latin">${esc(s.title || s.username)}</b><small class="num">${num(s.gb)}GB · انقضا ${when(s.expire)}</small></div>${tag(s.status)}</div>`).join('') || '<p class="muted">ندارد.</p>'}</div>
    <h3 style="margin-top:18px">پرداخت‌ها</h3><div class="list">${d.payments.map(p => `<div class="item"><div class="grow"><b class="num">#${p.id} · ${num(p.amount)}</b><small class="num">${when(p.created)}</small></div>${tag(p.status)}</div>`).join('') || '<p class="muted">ندارد.</p>'}</div>`;
  $('#drawer').classList.add('open');
  let op = 'add';
  $$('#balForm button').forEach(b => b.addEventListener('click', () => { op = b.dataset.op; }));
  $('#balForm').addEventListener('submit', async e => {
    e.preventDefault(); const amount = +$('#balAmt').value; if (!amount) return;
    if (!confirm(`${num(amount)} تومان ${op === 'add' ? 'اضافه' : 'کسر'} شود؟`)) return;
    const r = await act(e.submitter, () => api(`users/${id}/balance`, { op, amount }), 'انجام شد ✓'); if (r) { $('#dBal').textContent = num(r.balance); $('#balAmt').value = ''; }
  });
  $('#msgForm').addEventListener('submit', async e => { e.preventDefault(); const text = $('#msgTxt').value.trim(); if (!text) return; if (await act(e.submitter, () => api(`users/${id}/message`, { text }), 'ارسال شد ✓')) $('#msgTxt').value = ''; });
  $('#banBtn').addEventListener('click', async e => { if (!confirm('مطمئنی؟')) return; if (await act(e.target, () => api(`users/${id}/ban`, { banned: !u.banned }), 'ذخیره شد')) openUser(id); });
}
$('#drawer').addEventListener('click', e => { if (e.target.id === 'drawer' || e.target.closest('[data-close]')) $('#drawer').classList.remove('open'); });

/* ---------- services ---------- */
$('#svcSearch').addEventListener('submit', e => { e.preventDefault(); loadSvc(); });
async function loadSvc() {
  const d = await act(null, () => api(`services?q=${encodeURIComponent($('#sq').value.trim())}&status=${$('#sst').value}`)); if (!d) return;
  $('#svcList').innerHTML = d.items.length ? d.items.map(s => `<div class="item"><div class="grow"><b class="latin">${esc(s.username)}</b>
    <small class="num">#${s.id} · کاربر <a href="#" data-user="${s.user_id}">${s.user_id}</a> · ${esc(s.panel || '—')} · ${num(s.gb)}GB / ${num(s.days)} روز · ${num(s.price)} تومان · انقضا ${when(s.expire)}</small></div>
    ${s.is_test ? '<span class="tag wait">تست</span>' : ''}${tag(s.status)}<div class="acts">${s.sub || s.link ? `<button class="btn" data-copy="${esc(s.sub || s.link)}">کپی لینک</button>` : ''}<button class="btn bad" data-sdel="${s.id}">حذف</button></div></div>`).join('') : '<p class="muted">سرویسی پیدا نشد.</p>';
}
$('#svcList').addEventListener('click', async e => {
  const t = e.target;
  if (t.dataset.copy) { try { await navigator.clipboard.writeText(t.dataset.copy); toast('کپی شد'); } catch (_) { toast('کپی نشد', true); } }
  if (t.dataset.sdel) { if (!confirm('سرویس از پنل و ربات حذف شود؟ قابل برگشت نیست.')) return; await act(t, () => api(`services/${t.dataset.sdel}/delete`, {}), 'حذف شد'); loadSvc(); }
});

/* ---------- tickets ---------- */
let tkSt = 'open', tkId = null;
$('#tkSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; tkSt = b.dataset.st; $$('#tkSeg button').forEach(x => x.classList.toggle('on', x === b)); loadTk(); });
async function loadTk() {
  const d = await act(null, () => api('tickets?status=' + tkSt)); if (!d) return;
  $('#tkList').innerHTML = d.items.length ? d.items.map(t => `<div class="item click ${t.id === tkId ? 'sel' : ''}" data-tk="${t.id}"><div class="grow"><b class="num">#${t.id} · ${esc(t.name || t.user_id)}</b><small class="num">${when(t.updated)}</small></div>${t.admin_id ? '' : '<span class="tag wait">منتظر پاسخ</span>'}</div>`).join('') : '<p class="muted">تیکتی نیست.</p>';
}
$('#tkList').addEventListener('click', e => { const t = e.target.closest('[data-tk]'); if (t) openTk(+t.dataset.tk); });
async function openTk(id) {
  tkId = id; $$('#tkList .item').forEach(x => x.classList.toggle('sel', +x.dataset.tk === id));
  const d = await act(null, () => api('tickets/' + id)); if (!d) return;
  const open = d.ticket.status === 'open';
  $('#tkView').innerHTML = `<div class="bar"><h3>تیکت #${id} · کاربر <a href="#" data-user="${d.ticket.user_id}" class="num">${d.ticket.user_id}</a></h3>${open ? '<button class="btn bad" id="tkClose">بستن تیکت</button>' : tag('closed')}</div>
    <div class="msgs">${d.messages.map(m => `<div class="msg ${m.admin ? 'admin' : 'user'}">${esc(m.body)}<small class="num">${when(m.created)}</small></div>`).join('')}</div>
    ${open ? '<form id="tkReply"><textarea id="tkTxt" rows="3" placeholder="پاسخ به کاربر"></textarea><button class="btn primary" style="margin-top:8px">ارسال پاسخ</button></form>' : ''}`;
  const m = $('#tkView .msgs'); m.scrollTop = m.scrollHeight;
  $('#tkReply')?.addEventListener('submit', async e => { e.preventDefault(); const text = $('#tkTxt').value.trim(); if (!text) return; if (await act(e.submitter, () => api(`tickets/${id}/reply`, { text }), 'پاسخ ارسال شد ✓')) { openTk(id); loadTk(); } });
  $('#tkClose')?.addEventListener('click', async e => { if (!confirm('بسته شود؟')) return; if (await act(e.target, () => api(`tickets/${id}/close`, {}), 'بسته شد')) { openTk(id); loadTk(); } });
}

/* ---------- plans ---------- */
async function loadPlans() {
  const d = await act(null, () => api('plans')); if (!d) return;
  $('#planList').innerHTML = d.items.map(p => `<div class="item"><div class="grow"><b class="num">${p.months} ماهه · ${num(p.gb)} گیگ · ${num(p.days)} روز</b><small class="num">#${p.id}</small></div>
    <input type="number" min="0" value="${p.price}" data-price="${p.id}" style="width:140px"><button class="btn" data-psave="${p.id}">ذخیره قیمت</button>
    <button class="btn ${p.active ? 'bad' : 'ok'}" data-ptog="${p.id}" data-on="${p.active}">${p.active ? 'غیرفعال کن' : 'فعال کن'}</button><button class="btn bad" data-pdel="${p.id}">حذف</button></div>`).join('') || '<p class="muted">پلنی نیست.</p>';
}
$('#planAdd').addEventListener('submit', async e => {
  e.preventDefault(); const f = new FormData(e.target); const body = Object.fromEntries([...f].map(([k, v]) => [k, +v]));
  if (await act(e.submitter, () => api('plans', body), 'پلن اضافه شد ✓')) { e.target.reset(); loadPlans(); }
});
$('#planList').addEventListener('click', async e => {
  const t = e.target;
  if (t.dataset.psave) { const price = +$(`[data-price="${t.dataset.psave}"]`).value; await act(t, () => api('plans/' + t.dataset.psave, { price }), 'قیمت ذخیره شد ✓'); }
  if (t.dataset.ptog) { await act(t, () => api('plans/' + t.dataset.ptog, { active: t.dataset.on !== '1' })); loadPlans(); }
  if (t.dataset.pdel) { if (!confirm('پلن حذف شود؟')) return; await act(t, () => api(`plans/${t.dataset.pdel}/delete`, {}), 'حذف شد'); loadPlans(); }
});

/* ---------- panels ---------- */
async function loadPanels() {
  const d = await act(null, () => api('panels')); if (!d) return;
  $('#panelList').innerHTML = d.items.map(p => `<div class="item"><div class="grow"><b>${esc(p.name)} <small class="latin">${esc(p.ptype)}</small></b><small class="latin">${esc(p.url || '—')} · ${num(p.services)} سرویس فعال</small></div>
    ${p.active ? '<span class="tag ok">فعال</span>' : '<span class="tag off">غیرفعال</span>'}<span class="muted" data-res="${p.id}"></span>
    <div class="acts"><button class="btn" data-ntest="${p.id}">تست اتصال</button><button class="btn" data-ntog="${p.id}">${p.active ? 'غیرفعال کن' : 'فعال کن'}</button></div></div>`).join('') || '<p class="muted">پنلی ثبت نشده.</p>';
}
$('#panelList').addEventListener('click', async e => {
  const t = e.target;
  if (t.dataset.ntest) { const r = await act(t, () => api(`panels/${t.dataset.ntest}/test`, {})); if (r) { const s = $(`[data-res="${t.dataset.ntest}"]`); s.textContent = r.message; s.style.color = r.success ? 'var(--ok)' : 'var(--bad)'; } }
  if (t.dataset.ntog) { await act(t, () => api(`panels/${t.dataset.ntog}/toggle`, {})); loadPanels(); }
});

/* ---------- discounts ---------- */
async function loadDc() {
  const d = await act(null, () => api('discounts')); if (!d) return;
  $('#dcList').innerHTML = d.items.map(c => `<div class="item"><div class="grow"><b class="latin">${esc(c.code)}</b><small class="num">${c.percent}% · استفاده ${num(c.used)}${c.max_uses ? ' از ' + num(c.max_uses) : ''}</small></div>
    ${c.active ? '<span class="tag ok">فعال</span>' : '<span class="tag off">غیرفعال</span>'}<div class="acts"><button class="btn" data-dtog="${esc(c.code)}">${c.active ? 'غیرفعال' : 'فعال'}</button><button class="btn bad" data-ddel="${esc(c.code)}">حذف</button></div></div>`).join('') || '<p class="muted">کدی نیست.</p>';
}
$('#dcAdd').addEventListener('submit', async e => {
  e.preventDefault(); const f = new FormData(e.target);
  if (await act(e.submitter, () => api('discounts', { code: f.get('code'), percent: +f.get('percent'), max_uses: +(f.get('max_uses') || 0) }), 'کد ساخته شد ✓')) { e.target.reset(); loadDc(); }
});
$('#dcList').addEventListener('click', async e => {
  const t = e.target;
  if (t.dataset.dtog) { await act(t, () => api(`discounts/${encodeURIComponent(t.dataset.dtog)}/toggle`, {})); loadDc(); }
  if (t.dataset.ddel) { if (!confirm('حذف شود؟')) return; await act(t, () => api(`discounts/${encodeURIComponent(t.dataset.ddel)}/delete`, {}), 'حذف شد'); loadDc(); }
});

/* ---------- broadcast ---------- */
let bcTimer;
async function loadBc() {
  const d = await act(null, () => api('broadcast')); if (!d) return;
  $('#bcState').textContent = d.total ? `${d.running ? 'در حال ارسال' : 'آخرین ارسال'}: ${num(d.sent)} موفق · ${num(d.failed)} ناموفق از ${num(d.total)}` : '';
  clearTimeout(bcTimer); if (d.running && cur === 'bc') bcTimer = setTimeout(loadBc, 2000);
}
$('#bcForm').addEventListener('submit', async e => {
  e.preventDefault(); const text = $('#bcText').value.trim(); if (!text) return;
  if (!confirm('پیام برای همه کاربران ارسال شود؟')) return;
  if (await act(e.submitter, () => api('broadcast', { text }), 'ارسال شروع شد')) { $('#bcText').value = ''; setTimeout(loadBc, 800); }
});

/* ---------- settings ---------- */
async function loadSet() {
  const d = await act(null, () => api('settings')); if (!d) return;
  $('#setList').innerHTML = d.items.map(s => s.toggle
    ? `<div class="set-row"><label>${esc(s.title)}<small>${esc(s.k)}</small></label><span>${s.v === '1' ? '<span class="tag ok">روشن</span>' : '<span class="tag off">خاموش</span>'}</span><button class="btn" data-stog="${esc(s.k)}" data-v="${esc(s.v)}">${s.v === '1' ? 'خاموش کن' : 'روشن کن'}</button></div>`
    : `<div class="set-row"><label>${esc(s.title)}<small>${esc(s.k)}</small></label><input value="${esc(s.v)}" data-sk="${esc(s.k)}"><button class="btn" data-ssave="${esc(s.k)}">ذخیره</button></div>`).join('');
}
$('#setList').addEventListener('click', async e => {
  const t = e.target;
  if (t.dataset.ssave) { const v = $(`[data-sk="${t.dataset.ssave}"]`).value; await act(t, () => api('settings', { k: t.dataset.ssave, v: v || '-' }), 'ذخیره شد ✓'); }
  if (t.dataset.stog) { await act(t, () => api('settings', { k: t.dataset.stog, v: t.dataset.v === '1' ? '0' : '1' })); loadSet(); }
});

/* ---------- logs ---------- */
let logK = 'transactions';
$('#logSeg').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; logK = b.dataset.k; $$('#logSeg button').forEach(x => x.classList.toggle('on', x === b)); loadLog(); });
async function loadLog() {
  const d = await act(null, () => api(logK)); if (!d) return;
  $('#logList').innerHTML = d.items.map(r => logK === 'transactions'
    ? `<div class="item"><div class="grow"><b>${esc(r.kind)} · <span class="num">${num(r.amount)} تومان</span></b><small class="num">کاربر <a href="#" data-user="${r.user_id}">${r.user_id}</a> · سرویس #${r.service_id ?? '—'}${r.code ? ' · کد ' + esc(r.code) : ''} · ${when(r.created)}</small></div></div>`
    : `<div class="item"><div class="grow"><b>${esc(r.action)}</b><small class="num">${r.actor_id === -1 ? 'پنل وب' : 'ادمین ' + r.actor_id} · ${esc(r.target)} ${esc(String(r.details || '').slice(0, 120))} · ${when(r.created)}</small></div></div>`).join('') || '<p class="muted">موردی نیست.</p>';
}

/* ---------- boot ---------- */
setInterval(() => { if (!$('#shell').classList.contains('hidden') && (cur === 'dash' || cur === 'pay')) LOAD[cur](); }, 30000);
(async () => { try { await api('me'); showShell(); } catch (e) { showLogin(); if (!/وارد/.test(e.message)) $('#loginErr').textContent = e.message; } })();
})();
