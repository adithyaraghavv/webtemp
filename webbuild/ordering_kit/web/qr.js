/* Minimal QR code encoder (byte mode, error correction level M, versions 1 to 10). Our own code, no dependencies.
   QR.matrix(text) -> array of rows of 0/1.   QR.svg(text, {scale, margin, dark, light}) -> SVG string. */
(function (root) {
  'use strict';
  // [total codewords, ec codewords per block, [[blocks, data codewords per block], ...]] for level M
  var VER = {
    1: [26, 10, [[1, 16]]], 2: [44, 16, [[1, 28]]], 3: [70, 26, [[1, 44]]], 4: [100, 18, [[2, 32]]],
    5: [134, 24, [[2, 43]]], 6: [172, 16, [[4, 27]]], 7: [196, 18, [[4, 31]]], 8: [242, 22, [[2, 38], [2, 39]]],
    9: [292, 22, [[3, 36], [2, 37]]], 10: [346, 26, [[4, 43], [1, 44]]]
  };
  var ALIGN = { 1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50] };

  var EXP = new Array(512), LOG = new Array(256);
  (function () { var x = 1; for (var i = 0; i < 255; i++) { EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 256) x ^= 0x11d; } for (var j = 255; j < 512; j++) EXP[j] = EXP[j - 255]; })();
  function gmul(a, b) { return a && b ? EXP[LOG[a] + LOG[b]] : 0; }
  function rsGen(n) { var g = [1]; for (var i = 0; i < n; i++) { var ng = new Array(g.length + 1).fill(0); for (var j = 0; j < g.length; j++) { ng[j] ^= g[j]; ng[j + 1] ^= gmul(g[j], EXP[i]); } g = ng; } return g; }
  function rsEncode(data, n) {
    var gen = rsGen(n), res = new Array(n).fill(0);
    for (var i = 0; i < data.length; i++) {
      var f = data[i] ^ res[0]; res.shift(); res.push(0);
      for (var j = 0; j < n; j++) res[j] ^= gmul(gen[j + 1], f);
    }
    return res;
  }
  function utf8(s) { return Array.prototype.slice.call(unescape(encodeURIComponent(s))).map(function (c) { return c.charCodeAt(0); }); }

  function pickVersion(len) {
    for (var v = 1; v <= 10; v++) {
      var cap = VER[v][2].reduce(function (a, b) { return a + b[0] * b[1]; }, 0);
      var bits = 4 + (v < 10 ? 8 : 16) + len * 8;
      if (bits <= cap * 8) return v;
    }
    throw new Error('text too long for this QR encoder (max about 210 bytes)');
  }

  function codewords(bytes, v) {
    var info = VER[v], cap = info[2].reduce(function (a, b) { return a + b[0] * b[1]; }, 0), bits = [];
    function put(val, n) { for (var i = n - 1; i >= 0; i--) bits.push((val >> i) & 1); }
    put(4, 4); put(bytes.length, v < 10 ? 8 : 16); bytes.forEach(function (b) { put(b, 8); });
    put(0, Math.min(4, cap * 8 - bits.length));
    while (bits.length % 8) bits.push(0);
    var data = []; for (var i = 0; i < bits.length; i += 8) { var x = 0; for (var k = 0; k < 8; k++) x = (x << 1) | bits[i + k]; data.push(x); }
    for (var pad = 0; data.length < cap; pad++) data.push(pad % 2 ? 0x11 : 0xec);
    var blocks = [], pos = 0;
    info[2].forEach(function (g) { for (var b = 0; b < g[0]; b++) { var d = data.slice(pos, pos + g[1]); pos += g[1]; blocks.push({ d: d, e: rsEncode(d, info[1]) }); } });
    var out = [], maxd = Math.max.apply(null, blocks.map(function (b) { return b.d.length; }));
    for (var c = 0; c < maxd; c++) blocks.forEach(function (b) { if (c < b.d.length) out.push(b.d[c]); });
    for (var c2 = 0; c2 < info[1]; c2++) blocks.forEach(function (b) { out.push(b.e[c2]); });
    return out;
  }

  function bch(val, poly, bitsLen) { var d = val << bitsLen; var plen = poly.toString(2).length; while (d.toString(2).length >= plen) d ^= poly << (d.toString(2).length - plen); return d; }
  function formatBits(mask) { var data = (0 << 3) | mask; /* level M = 00 */ return ((data << 10) | bch(data, 0x537, 10)) ^ 0x5412; }
  function versionBits(v) { return (v << 12) | bch(v, 0x1f25, 12); }

  function build(v, cw, mask) {
    var n = 17 + 4 * v, m = [], fn = [];
    for (var i = 0; i < n; i++) { m.push(new Array(n).fill(0)); fn.push(new Array(n).fill(false)); }
    function set(r, c, val) { m[r][c] = val ? 1 : 0; fn[r][c] = true; }
    function finder(r, c) { for (var dr = -1; dr <= 7; dr++) for (var dc = -1; dc <= 7; dc++) { var rr = r + dr, cc = c + dc; if (rr < 0 || cc < 0 || rr >= n || cc >= n) continue; var on = (dr >= 0 && dr <= 6 && (dc === 0 || dc === 6)) || (dc >= 0 && dc <= 6 && (dr === 0 || dr === 6)) || (dr >= 2 && dr <= 4 && dc >= 2 && dc <= 4); set(rr, cc, on); } }
    finder(0, 0); finder(0, n - 7); finder(n - 7, 0);
    for (var k = 8; k < n - 8; k++) { set(6, k, k % 2 === 0); set(k, 6, k % 2 === 0); }
    var ap = ALIGN[v];
    ap.forEach(function (r) { ap.forEach(function (c) {
      if ((r === 6 && c === 6) || (r === 6 && c === ap[ap.length - 1]) || (r === ap[ap.length - 1] && c === 6)) return;
      for (var dr = -2; dr <= 2; dr++) for (var dc = -2; dc <= 2; dc++) set(r + dr, c + dc, Math.max(Math.abs(dr), Math.abs(dc)) !== 1);
    }); });
    set(n - 8, 8, 1); // dark module
    // reserve format areas
    for (var a = 0; a < 9; a++) { if (!fn[8][a]) { fn[8][a] = true; } if (!fn[a][8]) { fn[a][8] = true; } }
    for (var b = 0; b < 8; b++) { fn[8][n - 1 - b] = true; fn[n - 1 - b][8] = true; }
    if (v >= 7) { var vb = versionBits(v); for (var q = 0; q < 18; q++) { var bit = (vb >> q) & 1, r1 = Math.floor(q / 3), c1 = n - 11 + (q % 3); set(r1, c1, bit); set(c1, r1, bit); } }
    // data
    var bits = []; cw.forEach(function (x) { for (var i2 = 7; i2 >= 0; i2--) bits.push((x >> i2) & 1); });
    var bi = 0, up = true;
    for (var col = n - 1; col > 0; col -= 2) {
      if (col === 6) col--;
      for (var t = 0; t < n; t++) {
        var row = up ? n - 1 - t : t;
        for (var d = 0; d < 2; d++) {
          var cc = col - d;
          if (fn[row][cc]) continue;
          var bit2 = bi < bits.length ? bits[bi++] : 0;
          var inv = [ (row + cc) % 2 === 0, row % 2 === 0, cc % 3 === 0, (row + cc) % 3 === 0, (Math.floor(row / 2) + Math.floor(cc / 3)) % 2 === 0,
            (row * cc) % 2 + (row * cc) % 3 === 0, ((row * cc) % 2 + (row * cc) % 3) % 2 === 0, ((row + cc) % 2 + (row * cc) % 3) % 2 === 0 ][mask];
          m[row][cc] = bit2 ^ (inv ? 1 : 0);
        }
      }
      up = !up;
    }
    // format bits
    var fb = formatBits(mask);
    for (var i3 = 0; i3 < 15; i3++) {
      var bt = (fb >> i3) & 1;
      if (i3 < 6) m[i3][8] = bt; else if (i3 < 8) m[i3 + 1][8] = bt; else m[n - 15 + i3][8] = bt;
      if (i3 < 8) m[8][n - 1 - i3] = bt; else if (i3 === 8) m[8][7] = bt; else m[8][14 - i3] = bt;
    }
    m[n - 8][8] = 1;
    return m;
  }

  function penalty(m) {
    var n = m.length, p = 0, r, c, run, i;
    for (r = 0; r < n; r++) { run = 1; for (c = 1; c < n; c++) { if (m[r][c] === m[r][c - 1]) { run++; if (c === n - 1 && run >= 5) p += run - 2; } else { if (run >= 5) p += run - 2; run = 1; } } }
    for (c = 0; c < n; c++) { run = 1; for (r = 1; r < n; r++) { if (m[r][c] === m[r - 1][c]) { run++; if (r === n - 1 && run >= 5) p += run - 2; } else { if (run >= 5) p += run - 2; run = 1; } } }
    for (r = 0; r < n - 1; r++) for (c = 0; c < n - 1; c++) { var s = m[r][c] + m[r][c + 1] + m[r + 1][c] + m[r + 1][c + 1]; if (s === 0 || s === 4) p += 3; }
    var pat = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0], pat2 = pat.slice().reverse();
    function chk(get) { for (var a = 0; a < n; a++) for (var b = 0; b <= n - 11; b++) { var ok1 = true, ok2 = true; for (var k = 0; k < 11; k++) { var v = get(a, b + k); if (v !== pat[k]) ok1 = false; if (v !== pat2[k]) ok2 = false; } if (ok1 || ok2) p += 40; } }
    chk(function (a, b) { return m[a][b]; }); chk(function (a, b) { return m[b][a]; });
    var dark = 0; for (i = 0; i < n; i++) for (var j = 0; j < n; j++) dark += m[i][j];
    p += Math.floor(Math.abs(dark * 100 / (n * n) - 50) / 5) * 10;
    return p;
  }

  function matrix(text) {
    var bytes = utf8(String(text)), v = pickVersion(bytes.length), cw = codewords(bytes, v), best = null, bp = Infinity;
    for (var mask = 0; mask < 8; mask++) { var m = build(v, cw, mask), p = penalty(m); if (p < bp) { bp = p; best = m; } }
    return best;
  }
  function svg(text, o) {
    o = o || {}; var m = matrix(text), n = m.length, mg = o.margin == null ? 4 : o.margin, sc = o.scale || 6, dark = o.dark || '#000000', light = o.light || '#ffffff';
    var size = (n + 2 * mg) * sc, d = '';
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) if (m[r][c]) d += 'M' + ((c + mg) * sc) + ' ' + ((r + mg) * sc) + 'h' + sc + 'v' + sc + 'h-' + sc + 'z';
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + size + ' ' + size + '" width="' + size + '" height="' + size + '" role="img" aria-label="QR code" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="' + light + '"/><path d="' + d + '" fill="' + dark + '"/></svg>';
  }
  var api = { matrix: matrix, svg: svg };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.QR = api;
})(this);
