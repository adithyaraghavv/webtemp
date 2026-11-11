/* Owner dashboard: orders, kitchen, analytics, menu management, tables, settings. No libraries. */
(function () {
  'use strict';
  var app = document.getElementById('app');
  var TABS = [['orders', 'Orders'], ['kitchen', 'Kitchen'], ['analytics', 'Analytics'], ['menu', 'Menu'], ['tables', 'Tables'], ['settings', 'Settings']];
  var cfg = { currency: 'Rs ', cafe_name: '' };
  var tab = 'orders', timer = null, view = null, banner = null, signedOut = false;
  var S = { active: [], done: [], bills: [], an: null, range: 'day', cats: [], items: [], tables: [], settings: null };

  function cur() { return cfg.currency; }
  function imgSrc(u) { return /^(https?:)?\/\//.test(u) ? u : '../' + u; }
  function mins(t) { return Math.max(0, Math.round((Date.now() - new Date(t)) / 60000)); }
  function ago(t) { var m = mins(t); return m < 1 ? 'just now' : m < 60 ? m + ' min ago' : Math.floor(m / 60) + ' h ' + (m % 60) + ' min ago'; }
  function clock(t) { return new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function paise(v) { var n = parseFloat(String(v).replace(/,/g, '')); return isFinite(n) ? Math.round(n * 100) : NaN; }
  function say(msg, bad) { if (banner) { banner.textContent = msg || ''; banner.className = msg ? 'msg' + (bad ? ' err' : '') : ''; if (msg) banner.setAttribute('role', bad ? 'alert' : 'status'); } }
  function oops(e, fallback) {
    var m = (e && e.message) || '';
    if (/foreign key/.test(m)) return 'That is still in use. Move or remove what depends on it first.';
    if (/duplicate key/.test(m)) return 'That name already exists.';
    if (/invalid status/.test(m)) return 'That order was already changed by someone else.';
    return fallback || 'Something went wrong. Please try again.';
  }
  function guard(e) { if (e && (e.status === 401 || (e.status === 403 && /JWT|expired|not allowed/i.test(e.message)))) { signOut(); return true; } return false; }

  // simple confirm dialog (no browser pop-ups)
  function ask(text, yes) {
    return new Promise(function (res) {
      var d = el('dialog', {}, [el('h2', { text: text }), el('div', { class: 'acts' }, [
        el('button', { class: 'btn ghost', type: 'button', text: 'No', onclick: function () { d.close(); res(false); } }),
        el('button', { class: 'btn', type: 'button', text: yes || 'Yes', onclick: function () { d.close(); res(true); } })])]);
      d.addEventListener('close', function () { d.remove(); res(false); });
      document.body.appendChild(d); d.showModal();
    });
  }

  /* ---------- sign in ---------- */
  function login(err) {
    clearInterval(timer); app.textContent = '';
    app.appendChild(el('header', { class: 'top' }, [el('h1', { text: 'Owner sign in' })]));
    if (err) app.appendChild(el('div', { class: 'msg err', role: 'alert', text: err }));
    var em = el('input', { id: 'em', type: 'email', autocomplete: 'username', required: 'required' });
    var pw = el('input', { id: 'pw', type: 'password', autocomplete: 'current-password', required: 'required' });
    var f = el('form', {}, [el('label', { for: 'em', text: 'Email' }), em, el('label', { for: 'pw', text: 'Password' }), pw,
      el('p', {}, [el('button', { class: 'btn', type: 'submit', text: 'Sign in' })])]);
    f.addEventListener('submit', async function (e) {
      e.preventDefault();
      try { await API.login(em.value, pw.value); start(); } catch (x) { login('Sign in failed. Check the email and password.'); }
    });
    app.appendChild(f);
  }
  function signOut() { API.logout(); signedOut = true; login(); }

  /* ---------- shell ---------- */
  function shell() {
    app.textContent = '';
    app.appendChild(el('header', { class: 'top' }, [el('h1', { text: cfg.cafe_name || 'Dashboard' }),
      el('button', { class: 'btn ghost', text: 'Sign out', onclick: signOut })]));
    var nav = el('nav', { class: 'tabs', 'aria-label': 'Sections' });
    TABS.forEach(function (t) {
      nav.appendChild(el('a', { href: '#' + t[0], 'aria-current': t[0] === tab ? 'page' : 'false', text: t[1] + (t[0] === 'orders' && S.active.length ? ' (' + S.active.filter(function (o) { return o.status === 'new'; }).length + ')' : '') }));
    });
    app.appendChild(nav);
    banner = el('div', {}); app.appendChild(banner);
    view = el('div', { id: 'view' }); app.appendChild(view);
  }
  function go() {
    var h = (location.hash || '#orders').slice(1);
    tab = TABS.some(function (t) { return t[0] === h; }) ? h : 'orders';
    shell(); loadTab();
  }
  window.addEventListener('hashchange', function () { if (API.signedIn()) go(); });

  async function loadTab() {
    try {
      if (tab === 'orders' || tab === 'kitchen') await loadOrders();
      else if (tab === 'analytics') await loadAnalytics();
      else if (tab === 'menu') await loadMenu();
      else if (tab === 'tables') await loadTables();
      else if (tab === 'settings') await loadSettings();
    } catch (e) { if (!guard(e)) say('Connection problem. Retrying…', true); }
  }
  async function start() {
    signedOut = false;
    try { var s = await API.get('settings?select=*'); if (s && s[0]) { S.settings = s[0]; cfg.currency = s[0].currency; cfg.cafe_name = s[0].cafe_name; } } catch (e) { if (guard(e)) return; }
    go(); clearInterval(timer);
    timer = setInterval(function () { if (!signedOut && (tab === 'orders' || tab === 'kitchen') && !document.querySelector('dialog[open]')) loadOrders().catch(function (e) { if (!guard(e)) say('Connection problem. Retrying…', true); }); }, 4000);
  }

  /* ---------- orders and kitchen ---------- */
  var NEXT = { new: ['preparing', 'Start preparing'], preparing: ['ready', 'Mark ready'], ready: ['completed', 'Complete'] };
  async function loadOrders() {
    S.active = await API.get('staff_orders?select=*&status=in.(new,preparing,ready)&order=created_at.asc');
    S.bills = await API.get('staff_bills?select=*&status=eq.requested&order=requested_at.asc');
    if (tab === 'orders') S.done = await API.get('staff_orders?select=*&status=eq.completed&order=updated_at.desc&limit=10');
    var n = S.active.filter(function (o) { return o.status === 'new'; }).length;
    document.title = (n ? '(' + n + ') ' : '') + 'Owner dashboard';
    say('');
    if (tab === 'orders') drawOrders(); else if (tab === 'kitchen') drawKitchen();
    var a = document.querySelector('.tabs a[href="#orders"]'); if (a) a.textContent = 'Orders' + (n ? ' (' + n + ')' : '');
  }
  async function move(o, to) {
    try { await API.patch('orders?id=eq.' + encodeURIComponent(o.id), { status: to }); } catch (e) { if (!guard(e)) say(oops(e, 'Could not update that order.'), true); }
    loadOrders();
  }
  function itemLines(o, big) {
    var box = el('div', {});
    (o.items || []).forEach(function (i) {
      box.appendChild(el('div', { class: big ? 'line' : '' , text: i.qty + ' × ' + i.name }));
      var chips = (i.options || []).map(function (x) { return el('span', { class: 'chip', text: x.group + ': ' + x.choice }); });
      if (chips.length) box.appendChild(el('div', { class: 'chips' }, chips));
      if (i.note) box.appendChild(el('div', { class: 'noteline', text: 'Note: ' + i.note }));
    });
    if (o.note) box.appendChild(el('div', { class: 'noteline', text: 'Order note: ' + o.note }));
    return box;
  }
  function who(o) {
    var kids = [];
    if (o.customer_name) kids.push(o.customer_name);
    if (o.customer_phone) kids.push(el('a', { href: 'tel:' + o.customer_phone.replace(/[^0-9+]/g, ''), text: ' ' + o.customer_phone }));
    return kids.length ? el('div', { class: 'muted' }, kids) : null;
  }
  function orderCard(o, big) {
    var age = mins(o.created_at);
    var c = el('div', { class: 'panel ord ' + o.status }, [
      el('div', { class: 'row' }, [el('strong', { text: 'Table ' + o.table_label }),
        el('span', { class: 'pill ' + o.status + (big && age >= 20 ? ' age-late' : big && age >= 10 ? ' age-warn' : ''), text: o.status + ' · ' + clock(o.created_at) + ' · ' + ago(o.created_at) })]),
      who(o), itemLines(o, big)]);
    var a = el('div', { class: 'acts' }), nx = NEXT[o.status];
    if (nx) a.appendChild(el('button', { class: 'btn', text: nx[1], onclick: function () { move(o, nx[0]); } }));
    if (!big) a.appendChild(el('button', { class: 'btn ghost', text: 'Cancel', onclick: async function () { if (await ask('Cancel this order?', 'Cancel order')) move(o, 'cancelled'); } }));
    c.appendChild(a); return c;
  }
  function billsBlock() {
    var box = el('div', {}, [el('h2', { class: 'sec', text: 'Bills waiting for payment' })]);
    if (!S.bills.length) { box.appendChild(el('p', { class: 'muted', text: 'None.' })); return box; }
    var g = el('div', { class: 'cols' });
    S.bills.forEach(function (b) {
      g.appendChild(el('div', { class: 'panel' }, [el('div', { class: 'row' }, [el('strong', { text: 'Table ' + b.table_label }), el('strong', { text: money(b.total_paise, cur()) })]),
        el('p', { class: 'muted', text: 'Asked ' + ago(b.requested_at) + (b.rating ? ' · rated ' + b.rating + '/5' : '') }),
        el('div', { class: 'acts' }, [el('button', { class: 'btn', text: 'Payment received', onclick: async function () {
          if (!(await ask('Mark Table ' + b.table_label + ' as paid?', 'Payment received'))) return;
          try { await API.rpc('mark_paid', { p_bill: b.id }); } catch (e) { if (!guard(e)) say('Could not mark as paid.', true); } loadOrders(); } })])]));
    });
    box.appendChild(g); return box;
  }
  function drawOrders() {
    view.textContent = '';
    var cols = el('div', { class: 'cols' });
    [['new', 'New'], ['preparing', 'Preparing'], ['ready', 'Ready']].forEach(function (s) {
      var list = S.active.filter(function (o) { return o.status === s[0]; });
      var col = el('div', {}, [el('h2', { text: s[1] + ' (' + list.length + ')' })]);
      if (!list.length) col.appendChild(el('p', { class: 'muted', text: 'Nothing here.' }));
      list.forEach(function (o) { col.appendChild(orderCard(o, false)); });
      cols.appendChild(col);
    });
    view.appendChild(cols); view.appendChild(billsBlock());
    view.appendChild(el('h2', { class: 'sec', text: 'Completed recently' }));
    if (!S.done.length) view.appendChild(el('p', { class: 'muted', text: 'None yet.' }));
    S.done.forEach(function (o) { view.appendChild(el('div', { class: 'row' }, [el('span', { text: 'Table ' + o.table_label + ' · ' + (o.items || []).map(function (i) { return i.qty + ' × ' + i.name; }).join(', ') }), el('span', { class: 'muted', text: clock(o.updated_at) })])); });
  }
  function drawKitchen() {
    view.textContent = '';
    var list = S.active.filter(function (o) { return o.status === 'new' || o.status === 'preparing'; });
    view.appendChild(el('h2', { text: list.length ? 'Prepare next (' + list.length + ')' : 'Nothing to prepare' }));
    var box = el('div', { class: 'kitchen' });
    list.forEach(function (o) { box.appendChild(orderCard(o, true)); });
    view.appendChild(box);
  }

  /* ---------- analytics ---------- */
  var RANGES = { day: { label: 'Daily', days: 14 }, week: { label: 'Weekly', days: 84 }, month: { label: 'Monthly', days: 366 } };
  async function loadAnalytics() {
    var r = RANGES[S.range], from = new Date(Date.now() - r.days * 864e5).toISOString(), to = new Date(Date.now() + 60000).toISOString();
    S.an = await API.rpc('analytics', { p_from: from, p_to: to, p_bucket: S.range });
    say(''); drawAnalytics();
  }
  function barChart(title, pts, o) {
    o = o || {}; var W = 640, H = 150, L = 8, B = 22, T = 8, max = Math.max.apply(null, pts.map(function (p) { return p.v; }).concat([1]));
    var ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', title + ': ' + pts.map(function (p) { return p.label + ' ' + (o.fmt ? o.fmt(p.v) : p.v); }).join(', '));
    var bw = (W - L * 2) / pts.length, every = Math.ceil(pts.length / (o.labels || 8));
    pts.forEach(function (p, i) {
      var h = Math.round((H - B - T) * p.v / max), x = L + i * bw + bw * 0.12;
      var r = document.createElementNS(ns, 'rect'); r.setAttribute('class', 'bar-rect'); r.setAttribute('x', x); r.setAttribute('y', H - B - h); r.setAttribute('width', Math.max(1, bw * 0.76)); r.setAttribute('height', h);
      var t = document.createElementNS(ns, 'title'); t.textContent = p.label + ': ' + (o.fmt ? o.fmt(p.v) : p.v); r.appendChild(t); svg.appendChild(r);
      if (i % every === 0) { var tx = document.createElementNS(ns, 'text'); tx.setAttribute('class', 'axis-label'); tx.setAttribute('x', x); tx.setAttribute('y', H - 6); tx.textContent = p.label; svg.appendChild(tx); }
    });
    var ax = document.createElementNS(ns, 'line'); ax.setAttribute('class', 'axis'); ax.setAttribute('x1', L); ax.setAttribute('x2', W - L); ax.setAttribute('y1', H - B); ax.setAttribute('y2', H - B); svg.appendChild(ax);
    return el('div', { class: 'chart' }, [el('h3', { text: title + (o.max ? ' (highest ' + o.max + ')' : '') }), svg]);
  }
  function hbars(title, rows, empty) {
    var max = Math.max.apply(null, rows.map(function (r) { return r.qty; }).concat([1])), box = el('div', { class: 'chart' }, [el('h3', { text: title })]);
    if (!rows.length) box.appendChild(el('p', { class: 'muted', text: empty }));
    rows.forEach(function (r) { box.appendChild(el('div', { class: 'hbar' }, [el('span', { text: r.name }), el('span', {}, [el('i', { style: 'width:' + Math.round(100 * r.qty / max) + '%' })]), el('span', { class: 'muted', text: r.qty + ' sold · ' + money(r.revenue_paise, cur()) })])); });
    return box;
  }
  function drawAnalytics() {
    view.textContent = ''; var a = S.an; if (!a) return;
    var seg = el('div', { class: 'seg', role: 'group', 'aria-label': 'Period' });
    Object.keys(RANGES).forEach(function (k) { seg.appendChild(el('button', { type: 'button', 'aria-pressed': k === S.range ? 'true' : 'false', text: RANGES[k].label, onclick: function () { S.range = k; loadAnalytics().catch(function (e) { if (!guard(e)) say('Could not load analytics.', true); }); } })); });
    view.appendChild(seg);
    var o = a.overview;
    view.appendChild(el('div', { class: 'kpis' }, [
      el('div', { class: 'kpi' }, ['Revenue', el('b', { text: money(o.revenue_paise, cur()) })]), el('div', { class: 'kpi' }, ['Orders', el('b', { text: String(o.orders) })]),
      el('div', { class: 'kpi' }, ['Average order', el('b', { text: money(o.avg_order_paise, cur()) })]), el('div', { class: 'kpi' }, ['Paid so far', el('b', { text: money(o.paid_paise, cur()) })])]));
    var label = function (b) { var d = new Date(b + 'T00:00:00'); return S.range === 'month' ? d.toLocaleDateString([], { month: 'short' }) : d.toLocaleDateString([], { day: 'numeric', month: 'short' }); };
    view.appendChild(barChart('Revenue by ' + S.range, a.series.map(function (s) { return { label: label(s.bucket), v: s.revenue_paise / 100 }; }), { fmt: function (v) { return cur() + v.toFixed(0); } }));
    view.appendChild(barChart('Orders by ' + S.range, a.series.map(function (s) { return { label: label(s.bucket), v: s.orders }; })));
    view.appendChild(barChart('Busiest hours (orders by hour of day)', a.hours.map(function (h) { return { label: String(h.hour).padStart(2, '0'), v: h.orders }; }), { labels: 12 }));
    view.appendChild(el('div', { class: 'cols' }, [hbars('Top sellers', a.top, 'No sales in this period.'), hbars('Least sold (available items)', a.least, 'No items.')]));
    view.appendChild(el('p', { class: 'muted', text: 'Revenue counts every order that was not cancelled. "Paid so far" counts bills you marked as paid.' }));
  }

  /* ---------- menu management ---------- */
  async function loadMenu() {
    S.cats = await API.get('menu_categories?select=*&order=sort.asc,name.asc');
    S.items = await API.get('menu_items?select=*&order=sort.asc,name.asc');
    say(''); drawMenu();
  }
  function drawMenu() {
    view.textContent = '';
    view.appendChild(el('div', { class: 'acts' }, [el('button', { class: 'btn', text: 'Add item', onclick: function () { itemDialog(null); } }), el('button', { class: 'btn ghost', text: 'Add category', onclick: function () { catDialog(null); } })]));
    if (!S.cats.length) view.appendChild(el('p', { class: 'muted', text: 'No categories yet. Add one first.' }));
    S.cats.forEach(function (c, ci) {
      var items = S.items.filter(function (i) { return i.category_id === c.id; });
      view.appendChild(el('div', { class: 'catbar' }, [el('h2', { text: c.name }), el('div', { class: 'row-actions' }, [
        el('button', { class: 'btn ghost small', text: 'Up', 'aria-label': 'Move ' + c.name + ' up', onclick: function () { swapCat(ci, -1); } }),
        el('button', { class: 'btn ghost small', text: 'Down', 'aria-label': 'Move ' + c.name + ' down', onclick: function () { swapCat(ci, 1); } }),
        el('button', { class: 'btn ghost small', text: 'Rename', onclick: function () { catDialog(c); } }),
        el('button', { class: 'btn ghost small', text: 'Delete', onclick: async function () {
          if (!(await ask('Delete the category "' + c.name + '"?', 'Delete'))) return;
          try { await API.remove('menu_categories?id=eq.' + c.id); } catch (e) { if (!guard(e)) say(/foreign key/.test(e.message) ? 'This category still has items. Move or delete them first.' : oops(e), true); } loadMenu(); } })])]));
      if (!items.length) view.appendChild(el('p', { class: 'muted', text: 'No items in this category.' }));
      items.forEach(function (i) {
        var img = i.image_url ? el('img', { src: imgSrc(i.image_url), alt: '', loading: 'lazy' }) : el('div', { class: 'thumb', 'aria-hidden': 'true' });
        var av = el('input', { type: 'checkbox', id: 'av-' + i.id }); av.checked = i.available;
        av.addEventListener('change', async function () { try { await API.patch('menu_items?id=eq.' + i.id, { available: av.checked }); say(i.name + (av.checked ? ' is available.' : ' is marked sold out.')); } catch (e) { av.checked = !av.checked; if (!guard(e)) say(oops(e), true); } });
        view.appendChild(el('div', { class: 'mrowx' }, [img, el('div', {}, [el('strong', { text: i.name }), el('div', { class: 'muted', text: money(i.price_paise, cur()) + (i.options && i.options.length ? ' · ' + i.options.length + ' option group' + (i.options.length > 1 ? 's' : '') : '') + (i.description ? ' · ' + i.description : '') })]),
          el('div', { class: 'row-actions' }, [el('span', { class: 'inline' }, [av, el('label', { for: 'av-' + i.id, text: 'Available' })]),
            el('button', { class: 'btn ghost small', text: 'Edit', 'aria-label': 'Edit ' + i.name, onclick: function () { itemDialog(i); } }),
            el('button', { class: 'btn ghost small', text: 'Delete', 'aria-label': 'Delete ' + i.name, onclick: async function () {
              if (!(await ask('Delete "' + i.name + '"? Past orders keep their record.', 'Delete'))) return;
              try { await API.remove('menu_items?id=eq.' + i.id); dropImage(i.image_url); } catch (e) { if (!guard(e)) say(oops(e), true); } loadMenu(); } })])]));
      });
    });
  }
  async function swapCat(i, d) {
    var j = i + d; if (j < 0 || j >= S.cats.length) return;
    var a = S.cats[i], b = S.cats[j];
    try { await API.patch('menu_categories?id=eq.' + a.id, { sort: j }); await API.patch('menu_categories?id=eq.' + b.id, { sort: i }); } catch (e) { if (!guard(e)) say(oops(e), true); }
    loadMenu();
  }
  function dlg(title, build) {
    var d = el('dialog', {}, [el('h2', { text: title })]);
    d.addEventListener('close', function () { d.remove(); });
    build(d); document.body.appendChild(d); d.showModal(); return d;
  }
  function catDialog(c) {
    dlg(c ? 'Rename category' : 'New category', function (d) {
      var inp = el('input', { id: 'cn', maxlength: '40', required: 'required', value: c ? c.name : '' }), err = el('div', {});
      var f = el('form', { method: 'dialog' }, [el('label', { for: 'cn', text: 'Name' }), inp, err, el('div', { class: 'acts' }, [
        el('button', { class: 'btn ghost', type: 'button', text: 'Cancel', onclick: function () { d.close(); } }), el('button', { class: 'btn', type: 'submit', text: 'Save' })])]);
      f.addEventListener('submit', async function (e) {
        e.preventDefault(); var name = inp.value.trim(); if (!name) return;
        try { if (c) await API.patch('menu_categories?id=eq.' + c.id, { name: name }); else await API.insert('menu_categories', { name: name, sort: S.cats.length }); d.close(); loadMenu(); }
        catch (x) { err.className = 'msg err'; err.textContent = oops(x); }
      });
      d.appendChild(f);
    });
  }

  // downscale a chosen photo to at most 900px wide JPEG so uploads stay small
  function shrink(file) {
    return new Promise(function (res, rej) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () { var s = Math.min(1, 900 / img.width), c = document.createElement('canvas'); c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); URL.revokeObjectURL(url); c.toBlob(function (b) { b ? res(b) : rej(new Error('Could not read that image.')); }, 'image/jpeg', 0.82); };
      img.onerror = function () { URL.revokeObjectURL(url); rej(new Error('That file is not an image.')); }; img.src = url;
    });
  }
  function dropImage(u) { var m = u && /\/storage\/v1\/object\/public\/menu\/([A-Za-z0-9._-]+)$/.exec(u); if (m) API.unstore(m[1]); }

  function itemDialog(it) {
    dlg(it ? 'Edit item' : 'New item', function (d) {
      var groups = JSON.parse(JSON.stringify((it && it.options) || [])), photo = it ? it.image_url : null, newFile = null;
      var name = el('input', { id: 'in', maxlength: '80', required: 'required', value: it ? it.name : '' });
      var price = el('input', { id: 'ip', inputmode: 'decimal', required: 'required', value: it ? String(it.price_paise / 100) : '' });
      var desc = el('textarea', { id: 'id', rows: '2', maxlength: '240' }); desc.value = it ? it.description : '';
      var cat = el('select', { id: 'ic', required: 'required' }); S.cats.forEach(function (c) { var o = el('option', { value: c.id, text: c.name }); if (it && it.category_id === c.id) o.selected = true; cat.appendChild(o); });
      var av = el('input', { type: 'checkbox', id: 'ia' }); av.checked = it ? it.available : true;
      var prev = el('div', {}), file = el('input', { type: 'file', id: 'if', accept: 'image/jpeg,image/png,image/webp' }), err = el('div', {}), optBox = el('div', {});
      function drawPrev() { prev.textContent = ''; if (photo || newFile) { prev.appendChild(el('img', { class: 'thumb', alt: 'Item photo', src: newFile ? URL.createObjectURL(newFile) : imgSrc(photo) })); prev.appendChild(el('button', { class: 'btn ghost small', type: 'button', text: 'Remove photo', onclick: function () { photo = null; newFile = null; file.value = ''; drawPrev(); } })); } }
      file.addEventListener('change', async function () { if (!file.files[0]) return; try { newFile = await shrink(file.files[0]); drawPrev(); err.textContent = ''; err.className = ''; } catch (x) { err.className = 'msg err'; err.textContent = x.message; } });
      function drawOpts() {
        optBox.textContent = '';
        groups.forEach(function (g, gi) {
          var gn = el('input', { 'aria-label': 'Option group name', placeholder: 'Group name, e.g. Size', maxlength: '30', value: g.name || '' }); gn.addEventListener('input', function () { g.name = gn.value; });
          var rq = el('input', { type: 'checkbox', id: 'rq' + gi }); rq.checked = !!g.required; rq.addEventListener('change', function () { g.required = rq.checked; });
          var box = el('div', { class: 'grp' }, [el('div', { class: 'two' }, [gn, el('span', { class: 'inline' }, [rq, el('label', { for: 'rq' + gi, text: 'Customer must choose' })])])]);
          (g.choices || []).forEach(function (c, ci) {
            var cl = el('input', { 'aria-label': 'Choice name', placeholder: 'Choice, e.g. Large', maxlength: '30', value: c.label || '' }); cl.addEventListener('input', function () { c.label = cl.value; });
            var cd = el('input', { 'aria-label': 'Price change', inputmode: 'decimal', placeholder: 'Price change, e.g. 20', value: c.delta_paise ? String(c.delta_paise / 100) : '' }); cd.addEventListener('input', function () { c.delta_raw = cd.value; });
            box.appendChild(el('div', { class: 'two', style: 'margin-top:8px' }, [cl, el('span', { class: 'inline' }, [cd, el('button', { class: 'btn ghost small', type: 'button', text: 'Remove', onclick: function () { g.choices.splice(ci, 1); drawOpts(); } })])]));
          });
          box.appendChild(el('div', { class: 'acts' }, [el('button', { class: 'btn ghost small', type: 'button', text: 'Add choice', onclick: function () { if ((g.choices || []).length < 10) { (g.choices = g.choices || []).push({ label: '', delta_paise: 0 }); drawOpts(); } } }),
            el('button', { class: 'btn ghost small', type: 'button', text: 'Remove group', onclick: function () { groups.splice(gi, 1); drawOpts(); } })]));
          optBox.appendChild(box);
        });
        if (groups.length < 6) optBox.appendChild(el('button', { class: 'btn ghost small', type: 'button', text: 'Add option group (size, sugar…)', onclick: function () { groups.push({ name: '', required: false, choices: [{ label: '', delta_paise: 0 }] }); drawOpts(); } }));
      }
      drawPrev(); drawOpts();
      var f = el('form', { method: 'dialog' }, [el('label', { for: 'in', text: 'Name' }), name, el('div', { class: 'two' }, [el('div', {}, [el('label', { for: 'ip', text: 'Price (' + cur().trim() + ')' }), price]), el('div', {}, [el('label', { for: 'ic', text: 'Category' }), cat])]),
        el('label', { for: 'id', text: 'Description' }), desc, el('label', { for: 'if', text: 'Photo' }), file, prev, el('p', { class: 'inline' }, [av, el('label', { for: 'ia', text: 'Available to order' })]),
        el('h2', { text: 'Options' }), el('p', { class: 'muted', text: 'Let customers choose a size, sugar level and so on. A price change adds to or takes from the base price.' }), optBox, err,
        el('div', { class: 'acts' }, [el('button', { class: 'btn ghost', type: 'button', text: 'Cancel', onclick: function () { d.close(); } }), el('button', { class: 'btn', type: 'submit', text: 'Save' })])]);
      f.addEventListener('submit', async function (e) {
        e.preventDefault(); err.className = ''; err.textContent = '';
        var p = paise(price.value); if (!(p >= 0 && p <= 10000000)) { err.className = 'msg err'; err.textContent = 'Enter a price like 90 or 90.50.'; return; }
        var opts = [];
        for (var gi = 0; gi < groups.length; gi++) {
          var g = groups[gi]; if (!(g.name || '').trim()) continue;
          var ch = [];
          for (var ci = 0; ci < (g.choices || []).length; ci++) {
            var c = g.choices[ci]; if (!(c.label || '').trim()) continue;
            var dp = c.delta_raw !== undefined ? paise(c.delta_raw || '0') : (c.delta_paise || 0);
            if (!isFinite(dp) || Math.abs(dp) > 100000) { err.className = 'msg err'; err.textContent = 'A price change must be a number like 20 or -10.'; return; }
            ch.push({ label: c.label.trim(), delta_paise: dp });
          }
          if (!ch.length) { err.className = 'msg err'; err.textContent = 'Each option group needs at least one choice.'; return; }
          opts.push({ name: g.name.trim(), required: !!g.required, choices: ch });
        }
        try {
          var url = photo;
          if (newFile) { var fn = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2)) + '.jpg'; await API.upload(fn, newFile); url = API.imageUrl(fn); }
          var row = { name: name.value.trim(), category_id: cat.value, price_paise: p, description: desc.value.trim(), image_url: url, options: opts, available: av.checked };
          if (it) { await API.patch('menu_items?id=eq.' + it.id, row); if (it.image_url && it.image_url !== url) dropImage(it.image_url); }
          else { row.sort = S.items.length; await API.insert('menu_items', row); }
          d.close(); loadMenu();
        } catch (x) { err.className = 'msg err'; err.textContent = /JWT|expired/.test(x.message) ? 'Please sign in again.' : oops(x, x.message || 'Could not save.'); }
      });
      d.appendChild(f);
    });
  }

  /* ---------- tables and QR ---------- */
  async function loadTables() { S.tables = await API.get('cafe_tables?select=*&order=label.asc'); say(''); drawTables(); }
  function secret() { var a = new Uint8Array(12); crypto.getRandomValues(a); return Array.prototype.map.call(a, function (b) { return b.toString(16).padStart(2, '0'); }).join(''); }
  function drawTables() {
    view.textContent = '';
    var root = API.site();
    view.appendChild(el('div', { class: 'noprint' }, [el('p', { class: 'muted', text: 'Each code opens your website for that table so customers can order. Print them and keep them on the tables. Rotating a code makes the old printed one stop working.' }),
      el('div', { class: 'acts' }, [el('button', { class: 'btn', text: 'Add table', onclick: addTable }), el('button', { class: 'btn ghost', text: 'Print codes', onclick: function () { print(); } })])]));
    var g = el('div', { class: 'tbl' });
    S.tables.forEach(function (t) {
      var url = root + '?t=' + encodeURIComponent(t.label) + '&k=' + encodeURIComponent(t.secret), box = el('div', { class: 'qr', role: 'img', 'aria-label': 'QR code for table ' + t.label });
      box.innerHTML = QR.svg(url, { scale: 5, margin: 1, dark: '#150c0b', light: '#fff7f1' });
      g.appendChild(el('div', { class: 'panel' }, [el('h2', { text: 'Table ' + t.label }), t.active ? box : el('p', { class: 'muted', text: 'Switched off' }), el('p', { class: 'muted', text: t.active ? 'Scan to order' : '' }),
        el('div', { class: 'acts noprint' }, [
          el('button', { class: 'btn ghost small', text: t.active ? 'Switch off' : 'Switch on', onclick: async function () { try { await API.patch('cafe_tables?id=eq.' + t.id, { active: !t.active }); } catch (e) { if (!guard(e)) say(oops(e), true); } loadTables(); } }),
          el('button', { class: 'btn ghost small', text: 'New code', onclick: async function () { if (!(await ask('Make a new code for Table ' + t.label + '? The old printed code will stop working.', 'New code'))) return; try { await API.patch('cafe_tables?id=eq.' + t.id, { secret: secret() }); } catch (e) { if (!guard(e)) say(oops(e), true); } loadTables(); } }),
          el('button', { class: 'btn ghost small', text: 'Remove', onclick: async function () { if (!(await ask('Remove Table ' + t.label + '?', 'Remove'))) return; try { await API.remove('cafe_tables?id=eq.' + t.id); } catch (e) { if (!guard(e)) say(/foreign key/.test(e.message) ? 'This table has past orders, so it cannot be removed. Switch it off instead.' : oops(e), true); } loadTables(); } })])]));
    });
    view.appendChild(g);
  }
  function addTable() {
    dlg('New table', function (d) {
      var inp = el('input', { id: 'tl', maxlength: '20', required: 'required' }), err = el('div', {});
      var f = el('form', { method: 'dialog' }, [el('label', { for: 'tl', text: 'Table name or number' }), inp, err, el('div', { class: 'acts' }, [el('button', { class: 'btn ghost', type: 'button', text: 'Cancel', onclick: function () { d.close(); } }), el('button', { class: 'btn', type: 'submit', text: 'Add' })])]);
      f.addEventListener('submit', async function (e) { e.preventDefault(); try { await API.insert('cafe_tables', { label: inp.value.trim(), secret: secret() }); d.close(); loadTables(); } catch (x) { err.className = 'msg err'; err.textContent = oops(x); } });
      d.appendChild(f);
    });
  }

  /* ---------- settings ---------- */
  async function loadSettings() { var s = await API.get('settings?select=*'); S.settings = s && s[0] ? s[0] : null; say(''); drawSettings(); }
  function drawSettings() {
    view.textContent = ''; var s = S.settings || { cafe_name: '', currency: 'Rs ', upi_id: '', upi_name: '', google_place_id: '', timezone: 'Asia/Kolkata' };
    var F = {}; function field(key, label, hint) { F[key] = el('input', { id: 's-' + key, value: s[key] || '' }); return [el('label', { for: 's-' + key, text: label }), F[key], hint ? el('div', { class: 'muted', text: hint }) : null]; }
    var err = el('div', {});
    var f = el('form', {}, [].concat(field('cafe_name', 'Cafe name'), field('currency', 'Currency symbol', 'Shown before prices, e.g. Rs or ₹'), field('upi_id', 'UPI id for payments', 'Customers pay to this id. Example: mycafe@okbank'),
      field('upi_name', 'Name shown in the UPI app'), field('google_place_id', 'Google place id (optional)', 'Used for the "Leave a Google review" button after payment. Everyone gets the same button.'), field('timezone', 'Time zone', 'Used for daily, weekly and monthly numbers. Example: Asia/Kolkata'),
      [err, el('p', {}, [el('button', { class: 'btn', type: 'submit', text: 'Save settings' })])]));
    f.addEventListener('submit', async function (e) {
      e.preventDefault(); err.className = '';
      var row = { cafe_name: F.cafe_name.value.trim(), currency: F.currency.value || 'Rs ', upi_id: F.upi_id.value.trim() || null, upi_name: F.upi_name.value.trim() || null, google_place_id: F.google_place_id.value.trim() || null, timezone: F.timezone.value.trim() || 'Asia/Kolkata' };
      if (!row.cafe_name) { err.className = 'msg err'; err.textContent = 'Enter the cafe name.'; return; }
      if (row.upi_id && !/^[A-Za-z0-9._-]{2,}@[A-Za-z0-9]{2,}$/.test(row.upi_id)) { err.className = 'msg err'; err.textContent = 'The UPI id should look like name@bank.'; return; }
      try { if (S.settings) await API.patch('settings?id=eq.1', row); else { row.id = 1; await API.insert('settings', row); } cfg.currency = row.currency; cfg.cafe_name = row.cafe_name; say('Settings saved.'); loadSettings(); }
      catch (x) { err.className = 'msg err'; err.textContent = oops(x, 'Could not save. Check the time zone name.'); }
    });
    view.appendChild(f);
  }

  if (API.signedIn()) start(); else login();
})();
