/* Landing page data layer: shows the live menu from the database and, for table QR visitors only, the ordering flow.
   A plain visit (no ?t=&k=) is read-only. Prices and totals are always recomputed on the server. */
(function () {
  'use strict';
  var Q = new URLSearchParams(location.search), TABLE = Q.get('t') || '', KEY = Q.get('k') || '';
  var CAN = !!(TABLE && KEY), host = document.getElementById('menu-live');
  if (!host || !window.CAFE || !CAFE.url) return;
  var cur = host.getAttribute('data-currency') || 'Rs ', placeId = '', cats = [], items = [], sig = '', cart = [], bill = null, poll = null;
  var K = 'bill:' + TABLE, token = ''; try { token = localStorage.getItem(K) || ''; } catch (e) {}
  var cname = '', cphone = '', cnote = '';
  var LABEL = { new: 'Received', preparing: 'Being prepared', ready: 'Ready', completed: 'Served', cancelled: 'Cancelled' };
  function safeSrc(u) { return u && /^(https?:\/\/|[\w][\w./-]*$)/.test(u) ? u : ''; }
  function m(p) { return money(p, cur); }
  function modal(title, build) {
    var d = el('dialog', { class: 'o-dlg', 'aria-label': title }); d.appendChild(el('h2', { text: title }));
    d.addEventListener('close', function () { d.remove(); }); build(d);
    document.body.appendChild(d); d.showModal(); return d;
  }
  function openDlg() { return document.querySelector('dialog.o-dlg[open]'); }

  /* ---------- menu ---------- */
  function renderMenu() {
    var box = el('div', {});
    if (!CAN) box.appendChild(el('p', { class: 'o-note', text: 'To order, scan the QR code on your table.' }));
    cats.forEach(function (c, n) {
      var its = items.filter(function (i) { return i.category_id === c.id; }); if (!its.length) return;
      var feat = its.filter(function (i) { return safeSrc(i.image_url) && i.available; })[0] || its.filter(function (i) { return safeSrc(i.image_url); })[0];
      var rows = el('div', {}, [el('h3', { text: c.name })]);
      its.forEach(function (i) {
        var r = el('div', { class: 'mrow o-row' + (i.available ? '' : ' sold') + (safeSrc(i.image_url) && i !== feat ? ' has-thumb' : '') }, [el('h4', { text: i.name }), el('span', { class: 'price', text: m(i.price_paise) })]);
        if (safeSrc(i.image_url) && i !== feat) r.insertBefore(el('img', { class: 'o-thumb', src: safeSrc(i.image_url), alt: '', loading: 'lazy' }), r.firstChild);
        if (i.description) r.appendChild(el('p', { text: i.description }));
        if (!i.available) r.appendChild(el('span', { class: 'o-sold', text: 'Sold out' }));
        else if (CAN) r.appendChild(el('button', { class: 'o-btn o-add', type: 'button', 'aria-label': 'Add ' + i.name, text: 'Add', onclick: function () { pick(i); } }));
        rows.appendChild(r);
      });
      var kids = [];
      if (feat) kids.push(el('div', { class: 'mfeat' }, [el('img', { src: safeSrc(feat.image_url), alt: feat.name, loading: 'lazy' })]));
      kids.push(rows);
      box.appendChild(el('div', { class: 'mcat in' + (n % 2 ? ' flip' : '') + (feat ? '' : ' nofeat') }, kids));
    });
    host.textContent = ''; host.appendChild(box);
  }
  async function loadMenu(first) {
    try {
      var r = await Promise.all([API.get('menu_categories?select=*&order=sort.asc,name.asc'), API.get('menu_items?select=*&order=sort.asc,name.asc')]);
      var s = JSON.stringify(r); if (s === sig) return; sig = s; cats = r[0]; items = r[1];
      if (cats.length) renderMenu();
    } catch (e) { if (first) return; }
  }

  /* ---------- picking an item ---------- */
  function unitPrice(i, ch) {
    var p = i.price_paise; (i.options || []).forEach(function (g) { var c = (g.choices || []).filter(function (x) { return x.label === ch[g.name]; })[0]; if (c) p += c.delta_paise || 0; }); return p;
  }
  function pick(i) {
    var ch = {}, qty = 1;
    modal(i.name, function (d) {
      if (i.description) d.appendChild(el('p', { class: 'muted', text: i.description }));
      var price = el('strong', {}), err = el('div', {});
      (i.options || []).forEach(function (g, gi) {
        var fs = el('fieldset', { class: 'o-grp' }, [el('legend', { text: g.name + (g.required ? '' : ' (optional)') })]);
        function opt(label, delta, val) {
          var id = 'o' + gi + '-' + val.replace(/\W/g, '_'), inp = el('input', { type: 'radio', name: 'g' + gi, id: id });
          inp.addEventListener('change', function () { if (val === '') delete ch[g.name]; else ch[g.name] = val; upd(); });
          if (!g.required && val === '') inp.checked = true;
          fs.appendChild(el('label', { class: 'o-opt', for: id }, [el('span', {}, [inp, label]), el('span', { class: 'muted', text: delta ? (delta > 0 ? '+' : '') + m(delta) : '' })]));
        }
        if (!g.required) opt('No preference', 0, '');
        (g.choices || []).forEach(function (c) { opt(c.label, c.delta_paise, c.label); });
        d.appendChild(fs);
      });
      var note = el('textarea', { id: 'on', rows: '2', maxlength: '120', placeholder: 'e.g. less sugar, no ice' });
      d.appendChild(el('label', { for: 'on', text: 'Anything we should know? (optional)' })); d.appendChild(note);
      var q = el('span', { text: '1', 'aria-live': 'polite' });
      var qb = el('div', { class: 'o-qty' }, [el('button', { type: 'button', 'aria-label': 'Fewer', text: '−', onclick: function () { if (qty > 1) { qty--; upd(); } } }), q,
        el('button', { type: 'button', 'aria-label': 'More', text: '+', onclick: function () { if (qty < 20) { qty++; upd(); } } })]);
      var add = el('button', { class: 'o-btn', type: 'button', onclick: function () {
        for (var gi = 0; gi < (i.options || []).length; gi++) { var g = i.options[gi]; if (g.required && !ch[g.name]) { err.className = 'o-msg err'; err.setAttribute('role', 'alert'); err.textContent = 'Please choose ' + g.name.toLowerCase() + '.'; return; } }
        var line = { id: i.id, name: i.name, qty: qty, options: JSON.parse(JSON.stringify(ch)), note: note.value.trim(), unit: unitPrice(i, ch) };
        var key = JSON.stringify([line.id, line.options, line.note]), same = cart.filter(function (c) { return JSON.stringify([c.id, c.options, c.note]) === key; })[0];
        if (same) same.qty = Math.min(20, same.qty + qty); else cart.push(line);
        d.close(); drawBar();
      } });
      function upd() { q.textContent = String(qty); add.textContent = 'Add ' + qty + ' · ' + m(unitPrice(i, ch) * qty); price.textContent = m(unitPrice(i, ch)); }
      d.appendChild(err);
      d.appendChild(el('div', { class: 'o-acts' }, [qb, el('button', { class: 'o-btn ghost', type: 'button', text: 'Cancel', onclick: function () { d.close(); } }), add])); upd();
    });
  }

  /* ---------- bottom bar and cart ---------- */
  var bar = null;
  function count() { return cart.reduce(function (a, c) { return a + c.qty; }, 0); }
  function total() { return cart.reduce(function (a, c) { return a + c.qty * c.unit; }, 0); }
  function drawBar() {
    if (!CAN) return;
    if (!bar) { bar = el('div', { class: 'o-bar' }); document.body.appendChild(bar); document.body.classList.add('has-bar'); }
    bar.textContent = '';
    var left = el('span', {}, [el('span', { class: 'o-chip', text: 'Table ' + TABLE }), count() ? el('strong', { text: ' ' + count() + ' item' + (count() > 1 ? 's' : '') + ' · ' + m(total()) }) : el('span', { text: ' Browse the menu and tap Add' })]);
    var acts = el('div', { class: 'acts' });
    if (token) acts.appendChild(el('button', { class: 'o-btn ghost', type: 'button', text: 'My bill', onclick: showBill }));
    if (count()) acts.appendChild(el('button', { class: 'o-btn', type: 'button', text: 'View order', onclick: showCart }));
    bar.appendChild(el('div', { class: 'in' }, [left, acts]));
  }
  function showCart() {
    modal('Your order', function (d) {
      var err = el('div', {}), list = el('div', {}), tot = el('div', { class: 'o-total' });
      function draw() {
        list.textContent = ''; if (!cart.length) { d.close(); drawBar(); return; }
        cart.forEach(function (c, n) {
          var opts = Object.keys(c.options).map(function (k) { return k + ': ' + c.options[k]; }).join(' · ');
          list.appendChild(el('div', { class: 'o-line' }, [el('strong', { text: c.name }), el('span', { text: m(c.unit * c.qty) }),
            el('small', { text: [opts, c.note ? 'Note: ' + c.note : ''].filter(Boolean).join(' · ') }),
            el('div', { class: 'o-qty' }, [el('button', { type: 'button', 'aria-label': 'Fewer ' + c.name, text: '−', onclick: function () { c.qty--; if (c.qty < 1) cart.splice(n, 1); draw(); } }), el('span', { text: String(c.qty) }),
              el('button', { type: 'button', 'aria-label': 'More ' + c.name, text: '+', onclick: function () { if (c.qty < 20) { c.qty++; draw(); } } })])]));
        });
        tot.textContent = ''; tot.appendChild(el('span', { text: 'Total' })); tot.appendChild(el('span', { text: m(total()) })); drawBar();
      }
      var nm = el('input', { type: 'text', id: 'cn', maxlength: '40', autocomplete: 'name', value: cname }), ph = el('input', { type: 'tel', id: 'cp', maxlength: '20', autocomplete: 'tel', value: cphone }), nt = el('textarea', { id: 'co', rows: '2', maxlength: '200' }); nt.value = cnote;
      var send = el('button', { class: 'o-btn', type: 'button', text: 'Send order', onclick: async function () {
        cname = nm.value.trim(); cphone = ph.value.trim(); cnote = nt.value.trim(); err.className = ''; err.textContent = '';
        if (!cname) { err.className = 'o-msg err'; err.setAttribute('role', 'alert'); err.textContent = 'Please tell us your name so we can find you.'; nm.focus(); return; }
        send.disabled = true;
        try {
          var r = await API.rpc('place_order', { p_table: TABLE, p_secret: KEY, p_items: cart.map(function (c) { return { id: c.id, qty: c.qty, options: c.options, note: c.note || null }; }), p_note: cnote || null, p_name: cname, p_phone: cphone || null });
          token = r.bill_token; try { localStorage.setItem(K, token); } catch (e) {}
          cart = []; cnote = ''; d.close(); drawBar(); showBill(true);
        } catch (e) {
          send.disabled = false; err.className = 'o-msg err'; err.setAttribute('role', 'alert');
          err.textContent = /table|secret|invalid/i.test(e.message) ? 'This table code is not valid. Please ask a member of staff.' : /too many|slow/i.test(e.message) ? 'Too many orders just now. Please ask a member of staff.' : /unavailable|sold/i.test(e.message) ? 'One of the items just sold out. Please remove it and try again.' : 'We could not send the order. Please try again.';
          loadMenu();
        }
      } });
      d.appendChild(list); d.appendChild(tot);
      d.appendChild(el('label', { for: 'cn', text: 'Your name' })); d.appendChild(nm);
      d.appendChild(el('label', { for: 'cp', text: 'Phone (optional)' })); d.appendChild(ph);
      d.appendChild(el('label', { for: 'co', text: 'Note for the whole order (optional)' })); d.appendChild(nt); d.appendChild(err);
      d.appendChild(el('div', { class: 'o-acts' }, [el('button', { class: 'o-btn ghost', type: 'button', text: 'Keep browsing', onclick: function () { d.close(); } }), send])); draw();
    });
  }

  /* ---------- bill, payment, rating ---------- */
  var pay = null;
  function showBill(fresh) {
    modal(fresh === true ? 'Order sent' : 'Your bill', function (d) {
      var body = el('div', {}); d.appendChild(body);
      var closing = false; d.addEventListener('close', function () { closing = true; clearInterval(poll); });
      async function refresh() {
        try { bill = await API.rpc('get_bill', { p_token: token }); } catch (e) { body.textContent = ''; body.appendChild(el('p', { class: 'o-msg err', text: 'Could not load your bill. Please try again.' })); return; }
        if (closing) return; draw();
      }
      function draw() {
        body.textContent = ''; if (!bill) return;
        if (!bill.lines.length) body.appendChild(el('p', { class: 'muted', text: 'No orders yet.' }));
        bill.lines.forEach(function (l) {
          var opts = (l.options || []).map(function (o) { return o.group + ': ' + o.choice; }).join(' · ');
          body.appendChild(el('div', { class: 'o-line' }, [el('strong', { text: l.qty + ' × ' + l.name }), el('span', { class: 'o-st ' + l.order_status, text: LABEL[l.order_status] || l.order_status }),
            el('small', { text: [opts, l.note ? 'Note: ' + l.note : '', m(l.price_paise * l.qty)].filter(Boolean).join(' · ') })]));
        });
        body.appendChild(el('div', { class: 'o-total' }, [el('span', { text: 'Total so far' }), el('span', { text: m(bill.total_paise) })]));
        if (bill.status === 'paid') return thanks(body);
        var acts = el('div', { class: 'o-acts' });
        acts.appendChild(el('button', { class: 'o-btn ghost', type: 'button', text: 'Order more', onclick: function () { d.close(); } }));
        if (bill.status === 'open' && bill.total_paise > 0) acts.appendChild(el('button', { class: 'o-btn', type: 'button', text: 'Ask for the bill', onclick: askBill }));
        body.appendChild(acts);
        if (bill.status === 'requested') { if (pay) payPanel(body); else askBill(); }
      }
      async function askBill() {
        try { pay = await API.rpc('request_bill', { p_token: token }); } catch (e) { body.appendChild(el('p', { class: 'o-msg err', role: 'alert', text: 'Could not get the bill. Please ask a member of staff.' })); return; }
        if (pay.google_place_id) placeId = pay.google_place_id; draw();
      }
      refresh(); poll = setInterval(refresh, 5000);
    });
  }
  function payPanel(body) {
    var box = el('div', { class: 'o-pay' });
    box.appendChild(el('h3', { text: 'Pay your bill' }));
    box.appendChild(el('div', { class: 'amt', text: m(bill.total_paise) }));
    if (pay.upi_id) {
      var link = 'upi://pay?pa=' + encodeURIComponent(pay.upi_id) + '&pn=' + encodeURIComponent(pay.upi_name || pay.cafe_name || '') + '&am=' + (bill.total_paise / 100).toFixed(2) + '&cu=INR&tn=' + encodeURIComponent('Table ' + TABLE + ' ' + (pay.bill_ref || ''));
      var q = el('div', { class: 'o-qr', role: 'img', 'aria-label': 'UPI payment QR code' }); q.innerHTML = QR.svg(link, { scale: 6, margin: 0, dark: '#111', light: '#fff' });
      box.appendChild(q); box.appendChild(el('p', {}, [el('a', { class: 'o-btn', href: link, text: 'Open UPI app' })]));
      box.appendChild(el('p', { class: 'muted', text: 'Scan with any UPI app, or tap the button on your phone. A member of staff will confirm your payment.' }));
    } else box.appendChild(el('p', { class: 'muted', text: 'Please pay at the counter. A member of staff will confirm your payment.' }));
    body.appendChild(box);
    if (!bill.rated) body.appendChild(rating(body));
  }
  function rating(body) {
    var box = el('div', { class: 'o-rate' }, [el('h3', { text: 'How was it? (optional)' })]), stars = el('div', { class: 'o-stars', role: 'group', 'aria-label': 'Rating' }), val = 0;
    function paint() { Array.prototype.forEach.call(stars.children, function (b, n) { b.className = n < val ? 'on' : ''; b.setAttribute('aria-pressed', n + 1 === val ? 'true' : 'false'); }); }
    for (var s = 1; s <= 5; s++) (function (n) { stars.appendChild(el('button', { type: 'button', 'aria-label': n + ' star' + (n > 1 ? 's' : ''), text: '★', onclick: function () { val = n; paint(); } })); })(s);
    var cm = el('textarea', { rows: '2', maxlength: '300', 'aria-label': 'Comment (optional)', placeholder: 'Anything to add?' });
    var done = el('div', {});
    box.appendChild(stars); box.appendChild(cm);
    box.appendChild(el('div', { class: 'o-acts' }, [el('button', { class: 'o-btn ghost', type: 'button', text: 'Skip', onclick: function () { box.remove(); } }),
      el('button', { class: 'o-btn', type: 'button', text: 'Send rating', onclick: async function () {
        if (!val) { done.textContent = 'Tap a star first, or choose Skip.'; return; }
        try { await API.rpc('submit_rating', { p_token: token, p_stars: val, p_comment: cm.value.trim() || null }); box.textContent = 'Thank you for the feedback.'; bill.rated = true; } catch (e) { done.textContent = 'Could not send. You can skip this.'; }
      } })]));
    box.appendChild(done); return box;
  }
  function thanks(body) {
    clearInterval(poll); try { localStorage.removeItem(K); } catch (e) {}
    var box = el('div', { class: 'o-pay' }, [el('h3', { text: 'Payment received. Thank you!' }), el('p', { class: 'muted', text: 'We hope to see you again.' })]);
    if (placeId) box.appendChild(el('p', {}, [el('a', { class: 'o-btn', rel: 'noopener', target: '_blank', href: 'https://search.google.com/local/writereview?placeid=' + encodeURIComponent(placeId), text: 'Leave a Google review' })]));
    body.appendChild(box); token = ''; drawBar();
  }

  loadMenu(true).then(function () { drawBar(); });
  if (token && CAN) API.rpc('get_bill', { p_token: token }).then(function (b) { if (!b || b.status === 'paid') { token = ''; try { localStorage.removeItem(K); } catch (e) {} drawBar(); } }).catch(function () {});
  API.rpc('get_cafe').then(function (c) { if (c && c.google_place_id) placeId = c.google_place_id; }).catch(function () {});
  setInterval(function () { if (!openDlg() && !document.hidden) loadMenu(); }, 20000);
  document.addEventListener('visibilitychange', function () { if (!document.hidden && !openDlg()) loadMenu(); });
})();
