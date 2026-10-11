/* NAYI Mini App · v5 extras (additive): in-app card top-up, tickets, rename/transfer, referral, IP */
(() => {
'use strict';
const tg = window.Telegram?.WebApp;
const DEMO = !tg?.initData;
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const N = () => window.NAYI || { S: {}, show() {} };
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = n => Number(n || 0).toLocaleString('en-US');
const fa2en = s => String(s ?? '').replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const when = ts => ts ? new Date(ts * 1000).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—';
const haptic = t => { try { t === 'ok' || t === 'err' ? tg?.HapticFeedback?.notificationOccurred(t === 'ok' ? 'success' : 'error') : tg?.HapticFeedback?.impactOccurred('light'); } catch (_) {} };
let toastT;
function toast(msg, type = 'ok') {
  const t = $('#toast'); if (!t) return;
  t.textContent = msg; t.className = 'toast show' + (type === 'err' ? ' err' : '');
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 3200);
}
async function api(url, opt = {}) {
  let r;
  try { r = await fetch(url, { ...opt, headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg?.initData || '', ...(opt.headers || {}) } }); }
  catch (_) { throw new Error('اتصال به سرور برقرار نشد'); }
  let j = {}; try { j = await r.json(); } catch (_) {}
  if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'خطای سرور (' + r.status + ')');
  return j;
}
async function copy(text) {
  if (!text) return;
  try { await navigator.clipboard.writeText(text); }
  catch (_) { const t = document.createElement('textarea'); t.value = text; t.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(t); t.select(); try { document.execCommand('copy'); } catch (__) {} t.remove(); }
  haptic('ok'); toast('کپی شد ✓');
}
function openTg(u) { try { tg?.openTelegramLink ? tg.openTelegramLink(u) : window.open(u, '_blank'); } catch (_) { window.open(u, '_blank'); } }

const X = { card: null, file: null, tickets: [], ticket: null, sheet: null };

/* ---------- card top-up inside the Mini App ---------- */
const PAY_ST = { pending: ['wait', 'در انتظار بررسی'], ok: ['ok', 'تأیید شد'], rejected: ['off', 'رد شد'], error: ['off', 'ناموفق'], processing: ['wait', 'در حال بررسی'] };
async function loadTopup() {
  const box = $('#xCard'); if (!box) return;
  if (DEMO) { X.card = { card: '6037-0000-0000-0000', owner: 'نمونه', min: 10000, gift_min: 500000, gift_percent: 10, payments: [] }; }
  else { try { X.card = await api('/api/x/topup'); } catch (e) { box.classList.add('hidden'); return; } }
  const c = X.card;
  if (!c.card) { box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  $('#xCardNo').textContent = c.card; $('#xCardOwner').textContent = c.owner || '—';
  $('#xGiftRow').classList.toggle('hidden', !(c.gift_percent > 0));
  $('#xGiftTxt').textContent = `شارژ ویژه: از ${num(c.gift_min)} تومان به بالا، ${c.gift_percent}% هدیه`;
  syncAmount();
  const list = $('#xPays');
  list.innerHTML = (c.payments || []).length ? c.payments.slice(0, 6).map(p => {
    const [cls, txt] = PAY_ST[p.status] || ['wait', p.status];
    return `<div class="x-pay"><span class="num">#${p.id}</span><b class="num">${num(p.amount)} تومان${p.bonus ? ` <small>+${num(p.bonus)}</small>` : ''}</b><span class="tag ${cls}">${txt}</span></div>`;
  }).join('') : '';
  list.classList.toggle('hidden', !(c.payments || []).length);
}
function syncAmount() {
  const inp = $('#xAmount'); if (!inp) return;
  if (!inp.dataset.touched) inp.value = num(N().S.topupAmount || 250000);
}
function amountValue() { return Number(fa2en($('#xAmount').value).replace(/[^\d]/g, '')) || 0; }
function compress(file) {
  return new Promise((res, rej) => {
    if (!/^image\//.test(file.type)) return rej(new Error('فقط عکس رسید قابل ارسال است'));
    const fr = new FileReader();
    fr.onerror = () => rej(new Error('خواندن عکس ناموفق بود'));
    fr.onload = () => {
      const img = new Image();
      img.onerror = () => file.size < 5.5e6 ? res(fr.result) : rej(new Error('عکس قابل خواندن نیست'));
      img.onload = () => {
        const max = 1600, k = Math.min(1, max / Math.max(img.width, img.height));
        const cv = document.createElement('canvas'); cv.width = Math.round(img.width * k); cv.height = Math.round(img.height * k);
        cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
        try { res(cv.toDataURL('image/jpeg', 0.84)); } catch (_) { res(fr.result); }
      };
      img.src = fr.result;
    };
    fr.readAsDataURL(file);
  });
}
async function sendReceipt() {
  const btn = $('#xSend'); if (btn.disabled) return;
  const amount = amountValue();
  if (amount < (X.card?.min || 10000)) return toast('حداقل مبلغ ۱۰,۰۰۰ تومان است', 'err');
  if (!X.file) return toast('اول عکس رسید را انتخاب کن', 'err');
  if (DEMO) return toast('پیش‌نمایشه؛ رسید واقعی ارسال نمی‌شود', 'err');
  btn.disabled = true; const label = btn.innerHTML; btn.innerHTML = '<span>در حال ارسال…</span>';
  try {
    const image = await compress(X.file);
    const d = await api('/api/x/topup', { method: 'POST', body: JSON.stringify({ amount, gift: $('#xGift').checked, image }) });
    toast(`رسید #${d.id} ارسال شد؛ بعد از تأیید، موجودی خودکار به‌روز می‌شود ✓`); haptic('ok');
    X.file = null; $('#xFile').value = ''; $('#xFileName').textContent = 'انتخاب عکس رسید';
    $('#xPick').classList.remove('on');
    loadTopup();
  } catch (e) { toast(e.message, 'err'); haptic('err'); }
  finally { btn.disabled = false; btn.innerHTML = label; }
}

/* ---------- tickets ---------- */
async function loadTickets() {
  const list = $('#xTicketList'); if (!list) return;
  list.innerHTML = '<div class="empty"><b>◌</b>در حال دریافت…</div>';
  if (DEMO) X.tickets = [{ id: 12, status: 'open', updated: Date.now() / 1000 - 3600, last: 'سلام، سرعت سرور کمه', last_admin: false }];
  else { try { X.tickets = (await api('/api/x/tickets')).items || []; } catch (e) { list.innerHTML = `<div class="empty"><b>!</b>${esc(e.message)}</div>`; return; } }
  list.innerHTML = X.tickets.length ? X.tickets.map(t => `<button type="button" class="x-tk" data-xticket="${t.id}">
      <span class="tag ${t.status === 'open' ? 'ok' : 'off'}">${t.status === 'open' ? 'باز' : 'بسته'}</span>
      <div><b>تیکت <span class="num">#${t.id}</span>${t.last_admin ? ' <em class="x-new">پاسخ جدید</em>' : ''}</b><small>${esc(t.last || '—')}</small></div>
      <i class="num">${when(t.updated)}</i></button>`).join('')
    : '<div class="empty"><b>🎫</b>هنوز تیکتی نداری.<br>سؤال یا مشکلت را پایین بنویس.</div>';
}
async function openTicket(id) {
  X.ticket = id; N().show('ticket');
  const box = $('#xThread'); box.innerHTML = '<div class="empty"><b>◌</b>در حال دریافت…</div>';
  let d;
  if (DEMO) d = { id, status: 'open', messages: [{ me: true, body: 'سلام، سرعت سرور کمه', created: Date.now() / 1000 - 3600 }, { me: false, body: 'سلام، بررسی شد و درست شد ✓', created: Date.now() / 1000 - 1200 }] };
  else { try { d = await api('/api/x/tickets/' + id); } catch (e) { box.innerHTML = `<div class="empty"><b>!</b>${esc(e.message)}</div>`; return; } }
  $('#xThreadTitle').textContent = `تیکت #${d.id}`;
  box.innerHTML = d.messages.map(m => `<div class="x-msg ${m.me ? 'me' : 'them'}"><p>${esc(m.body)}</p><small class="num">${m.me ? '' : 'پشتیبانی · '}${when(m.created)}</small></div>`).join('') || '<div class="empty">پیامی نیست.</div>';
  const open = d.status === 'open';
  $('#xReplyForm').classList.toggle('hidden', !open); $('#xCloseTk').classList.toggle('hidden', !open);
  $('#xClosedNote').classList.toggle('hidden', open);
  setTimeout(() => box.lastElementChild?.scrollIntoView({ block: 'end', behavior: 'smooth' }), 60);
}
async function submitTicket(e, reply) {
  e.preventDefault();
  const inp = reply ? $('#xReplyInput') : $('#xTicketInput'); const body = inp.value.trim();
  if (!body) return;
  if (DEMO) { inp.value = ''; return toast('پیش‌نمایشه؛ پیام ارسال نشد', 'err'); }
  const btn = e.target.querySelector('button'); btn.disabled = true;
  try {
    const d = reply ? await api(`/api/x/tickets/${X.ticket}/reply`, { method: 'POST', body: JSON.stringify({ body }) })
                    : await api('/api/x/tickets', { method: 'POST', body: JSON.stringify({ body }) });
    inp.value = ''; toast('پیام برای پشتیبانی ارسال شد ✓'); haptic('ok');
    openTicket(reply ? X.ticket : d.id);
  } catch (err) { toast(err.message, 'err'); }
  finally { btn.disabled = false; }
}
async function closeTicket() {
  if (!X.ticket || !confirm('این تیکت بسته شود؟')) return;
  try { if (!DEMO) await api(`/api/x/tickets/${X.ticket}/close`, { method: 'POST' }); toast('تیکت بسته شد'); openTicket(X.ticket); }
  catch (e) { toast(e.message, 'err'); }
}

/* ---------- rename / transfer sheet ---------- */
function svc(id) { return (N().S.services || []).find(s => s.id == id); }
function openX(mode, id) {
  const s = svc(id); if (!s) return;
  X.sheet = { mode, id };
  $('#xSheetSmall').textContent = mode === 'rename' ? 'RENAME' : 'TRANSFER';
  $('#xSheetTitle').textContent = mode === 'rename' ? 'تغییر نام سرویس' : 'انتقال سرویس';
  $('#xSheetText').textContent = mode === 'rename' ? `سرویس ${s.name} · یک نام دلخواه بنویس (حداکثر ۳۲ کاراکتر)` : `سرویس ${s.name} به آیدی عددی کاربر مقصد منتقل می‌شود. این کار قابل برگشت نیست.`;
  const inp = $('#xSheetInput');
  inp.value = mode === 'rename' ? (s.title || '') : ''; inp.maxLength = mode === 'rename' ? 32 : 20;
  inp.inputMode = mode === 'rename' ? 'text' : 'numeric'; inp.placeholder = mode === 'rename' ? 'مثلاً گوشی مامان' : 'آیدی عددی مقصد';
  const el = $('#xSheet'); el.classList.add('open'); el.setAttribute('aria-hidden', 'false'); haptic('light');
  setTimeout(() => inp.focus(), 250);
}
function closeX() { const el = $('#xSheet'); el.classList.remove('open'); el.setAttribute('aria-hidden', 'true'); }
async function submitX(e) {
  e.preventDefault(); if (!X.sheet) return;
  const { mode, id } = X.sheet; const v = $('#xSheetInput').value.trim(); if (!v) return;
  if (mode === 'transfer' && !confirm('مطمئنی؟ سرویس از حساب تو خارج می‌شود.')) return;
  if (DEMO) { closeX(); return toast('پیش‌نمایشه؛ تغییری ذخیره نشد', 'err'); }
  const btn = $('#xSheetGo'); btn.disabled = true;
  try {
    if (mode === 'rename') {
      const d = await api(`/api/x/service/${id}/rename`, { method: 'POST', body: JSON.stringify({ title: v }) });
      const s = svc(id); if (s) s.title = d.title; toast('نام سرویس عوض شد ✓');
    } else {
      await api(`/api/x/service/${id}/transfer`, { method: 'POST', body: JSON.stringify({ to: fa2en(v) }) });
      const S = N().S; S.services = S.services.filter(s => s.id != id); toast('سرویس منتقل شد ✓');
    }
    haptic('ok'); closeX(); N().show('services');
  } catch (err) { toast(err.message, 'err'); haptic('err'); }
  finally { btn.disabled = false; }
}

/* ---------- referral & IP ---------- */
async function loadRef() {
  let d;
  if (DEMO) d = { link: 'https://t.me/NayiBot?start=ref_1024', percent: 5, count: 3 };
  else { try { d = await api('/api/x/referral'); } catch (e) { return toast(e.message, 'err'); } }
  $('#xRefLink').textContent = d.link || '—'; $('#xRefLink').dataset.v = d.link || '';
  $('#xRefPct').textContent = num(d.percent) + '%'; $('#xRefCount').textContent = num(d.count);
}
async function loadIp() {
  const box = $('#xIpBox'); box.innerHTML = '<div class="empty"><b>◌</b>در حال بررسی اتصال…</div>';
  let d;
  if (DEMO) d = { ip: '203.0.113.7', version: 'IPv4', flag: '🇩🇪', country: 'Germany', region: 'Hesse', city: 'Frankfurt', isp: 'Demo ISP', asn: 64500, tz: 'Europe/Berlin' };
  else { try { d = await api('/api/x/ip'); } catch (e) { box.innerHTML = `<div class="empty"><b>!</b>${esc(e.message)}</div>`; return; } }
  const rows = [['آدرس IP', d.ip, 1], ['نسخه', d.version], ['کشور', `${d.flag} ${d.country}`], ['استان/منطقه', d.region], ['شهر', d.city], ['اپراتور', d.isp], ['ASN', d.asn, 1], ['منطقه زمانی', d.tz, 1]];
  box.innerHTML = `<div class="x-ip-hero"><span>${esc(d.flag)}</span><b class="latin">${esc(d.ip)}</b><button type="button" class="mini" data-xcopy="${esc(d.ip)}">کپی</button></div>
    <dl class="x-dl">${rows.map(([k, v, l]) => `<div><dt>${k}</dt><dd class="${l ? 'latin' : ''}">${esc(v)}</dd></div>`).join('')}</dl>
    <p class="topup-foot">موقعیت تقریبی است و ذخیره نمی‌شود. منبع: ${esc(d.provider || 'سرور اطلاعات IP')}</p>`;
}

/* ---------- hooks ---------- */
const VIEW_LOAD = { topup: loadTopup, tickets: loadTickets, referral: loadRef, ip: loadIp };
document.addEventListener('click', e => {
  const t = e.target.closest('button,[data-xcopy]'); if (!t) return;
  const d = t.dataset;
  const go = d.go || d.view;
  if (go && VIEW_LOAD[go]) setTimeout(VIEW_LOAD[go], 0);
  if (d.topup) { const i = $('#xAmount'); if (i) { delete i.dataset.touched; setTimeout(syncAmount, 0); } }
  if (d.xticket) return openTicket(+d.xticket);
  if (d.rename) return openX('rename', d.rename);
  if (d.transfer) return openX('transfer', d.transfer);
  if (d.xcopy) return copy(d.xcopy);
  if (d.xact === 'copy-no') return copy(fa2en(X.card?.card || '').replace(/[^\d]/g, ''));
  if (d.xact === 'copy-ref') return copy($('#xRefLink').dataset.v);
  if (d.xact === 'share-ref') { const l = $('#xRefLink').dataset.v; if (l) openTg('https://t.me/share/url?url=' + encodeURIComponent(l) + '&text=' + encodeURIComponent('با این لینک عضو شو 🚀')); return; }
  if (d.xact === 'ip-reload') return loadIp();
  if (d.xact === 'close-tk') return closeTicket();
  if (d.xact === 'tk-back') return N().show('tickets'), loadTickets();
  if (d.xact === 'x-close' || t.hasAttribute('data-xclose')) return closeX();
});
document.addEventListener('DOMContentLoaded', init);
if (document.readyState !== 'loading') init();
let inited = false;
function init() {
  if (inited) return; inited = true;
  $('#xFile')?.addEventListener('change', e => {
    X.file = e.target.files?.[0] || null;
    $('#xFileName').textContent = X.file ? X.file.name.slice(0, 32) : 'انتخاب عکس رسید';
    $('#xPick').classList.toggle('on', !!X.file);
  });
  $('#xAmount')?.addEventListener('input', e => {
    e.target.dataset.touched = '1';
    const v = Number(fa2en(e.target.value).replace(/[^\d]/g, '')); e.target.value = v ? num(v) : '';
  });
  $('#xSend')?.addEventListener('click', sendReceipt);
  $('#xTicketForm')?.addEventListener('submit', e => submitTicket(e, false));
  $('#xReplyForm')?.addEventListener('submit', e => submitTicket(e, true));
  $('#xSheetForm')?.addEventListener('submit', submitX);
  $('#xSheet')?.addEventListener('click', e => { if (e.target.id === 'xSheet') closeX(); });
}
window.NAYI_X = { loadTopup, loadTickets, openTicket, copyCard: () => X.card?.card ? copy(fa2en(X.card.card).replace(/[^\d]/g, '')) : toast('اطلاعات کارت در دسترس نیست', 'err') };
})();
