/* Thin client for the cafe's Supabase project, using only fetch. No libraries. */
(function () {
  'use strict';
  var C = window.CAFE || { url: '', key: '' };
  var token = null;
  try { token = sessionStorage.getItem('staff_token'); } catch (e) {}
  function headers(extra) {
    var h = { apikey: C.key, 'Content-Type': 'application/json', Authorization: 'Bearer ' + (token || C.key) };
    for (var k in (extra || {})) h[k] = extra[k];
    return h;
  }
  function fail(res, body) {
    var msg = (body && (body.message || body.msg || body.error_description)) || 'Something went wrong';
    var e = new Error(msg); e.status = res.status; throw e;
  }
  async function call(method, path, body, extra) {
    var res = await fetch(C.url + path, { method: method, headers: headers(extra), body: body === undefined ? undefined : JSON.stringify(body) });
    var text = await res.text(), json = null;
    try { json = text ? JSON.parse(text) : null; } catch (e) {}
    if (!res.ok) fail(res, json);
    return json;
  }
  window.API = {
    rpc: function (fn, args) { return call('POST', '/rest/v1/rpc/' + fn, args || {}); },
    get: function (path) { return call('GET', '/rest/v1/' + path); },
    patch: function (path, body) { return call('PATCH', '/rest/v1/' + path, body, { Prefer: 'return=minimal' }); },
    insert: function (table, row) { return call('POST', '/rest/v1/' + table, row, { Prefer: 'return=representation' }); },
    remove: function (path) { return call('DELETE', '/rest/v1/' + path); },
    upload: async function (name, blob) {
      var res = await fetch(C.url + '/storage/v1/object/menu/' + name, { method: 'POST', body: blob,
        headers: { apikey: C.key, Authorization: 'Bearer ' + (token || C.key), 'Content-Type': blob.type, 'x-upsert': 'true' } });
      if (!res.ok) { var j = null; try { j = await res.json(); } catch (e) {} fail(res, j); }
    },
    unstore: function (name) { return fetch(C.url + '/storage/v1/object/menu/' + name, { method: 'DELETE', headers: { apikey: C.key, Authorization: 'Bearer ' + (token || C.key) } }); },
    imageUrl: function (name) { return C.url + '/storage/v1/object/public/menu/' + name; },
    site: function () { return C.site || location.href.split('#')[0].split('?')[0].replace(/order\/[^\/]*$/, '').replace(/[^\/]*$/, ''); },
    login: async function (email, password) {
      var r = await call('POST', '/auth/v1/token?grant_type=password', { email: email, password: password });
      token = r.access_token; try { sessionStorage.setItem('staff_token', token); } catch (e) {}
    },
    logout: function () { token = null; try { sessionStorage.removeItem('staff_token'); } catch (e) {} },
    signedIn: function () { return !!token; }
  };
  window.el = function (tag, props, kids) {
    var n = document.createElement(tag);
    for (var k in (props || {})) { if (k === 'class') n.className = props[k]; else if (k === 'text') n.textContent = props[k]; else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), props[k]); else n.setAttribute(k, props[k]); }
    (kids || []).forEach(function (c) { if (c != null) n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  };
  window.money = function (paise, cur) { var n = Math.abs(paise); return (paise < 0 ? '-' : '') + (cur == null ? 'Rs ' : cur) + (n / 100).toFixed(n % 100 ? 2 : 0); };
})();
