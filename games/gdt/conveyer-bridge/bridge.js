// Conveyer bridge for Game Dev Tycoon. No network and no code execution.
// Every 300 ms it writes what is on screen to ~/Library/Application Support/conveyer-gdt/state.json and runs at most one command from cmd.json there.
// Commands are a fixed list (click, clickAt, slider, text, key, inspect). Anything else is refused. inspect only reads properties, it never calls anything.
(function () {
	var fs = require('fs'), path = require('path');
	var DIR = path.join(process.env.HOME, 'Library/Application Support/conveyer-gdt');   // not under Documents: macOS would ask for folder access
	try { fs.mkdirSync(DIR); } catch (e) { }
	var STATE = path.join(DIR, 'state.json'), CMD = path.join(DIR, 'cmd.json');
	var lastId = null, lastResult = null, els = [], gen = 0, lastSig = '', lastWrite = 0;
	var TAGS = { BUTTON: 1, A: 1, INPUT: 1, SELECT: 1, TEXTAREA: 1 };

	function hasClick(el) {
		var ev = null;
		try { ev = window.jQuery && jQuery._data ? jQuery._data(el, 'events') : null; } catch (e) { }
		return !!(ev && (ev.click || ev.mousedown || ev.mouseup)) || el.onclick != null;
	}

	function label(el) {
		return String(el.innerText || el.value || el.title || el.alt || '').replace(/\s+/g, ' ').trim().slice(0, 80);
	}

	// Everything the player could press right now: buttons, inputs, sliders, and anything with a click handler or a pointer cursor.
	function scan() {
		var out = [], found = [], all = document.body.getElementsByTagName('*');
		for (var i = 0; i < all.length && found.length < 300; i++) {
			var el = all[i];
			if (el.offsetWidth < 2 || el.offsetHeight < 2) continue;
			var r = el.getBoundingClientRect();
			if (r.right <= 0 || r.left >= innerWidth) continue;
			var off = r.bottom <= 0 || r.top >= innerHeight;   // scrolled out of view (a long platform list): still listed, flagged, and pressable
			var cs = getComputedStyle(el);
			if (cs.visibility === 'hidden' || parseFloat(cs.opacity) < 0.05) continue;
			var cls = typeof el.className === 'string' ? el.className : '';
			var slider = cls.indexOf('ui-slider') > -1 && cls.indexOf('ui-slider-') === -1;
			var own = TAGS[el.tagName] || slider || hasClick(el);
			if (!own) {
				if (cs.cursor !== 'pointer') continue;
				var p = el.parentElement;
				if (p && getComputedStyle(p).cursor === 'pointer') continue;   // the cursor is inherited: keep only the outermost one
			}
			var kind = slider ? 'slider' : (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') ? 'input' : el.tagName === 'CANVAS' ? 'canvas' : 'button';
			var item = { i: found.length, kind: kind, text: label(el), id: el.id || '', cls: cls.slice(0, 60), x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), w: Math.round(r.width), h: Math.round(r.height) };
			if (off) item.off = true;
			if (slider) { try { item.value = jQuery(el).slider('value'); item.min = jQuery(el).slider('option', 'min'); item.max = jQuery(el).slider('option', 'max'); } catch (e) { } }
			if (kind === 'input') item.value = String(el.value || '').slice(0, 80);
			found.push(el); out.push(item);
		}
		els = found;
		return out;
	}

	function mouse(el, x, y) {
		['mousedown', 'mouseup', 'click'].forEach(function (t) {
			el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y, button: 0 }));
		});
	}

	// Read-only look at a dotted path from window, for example "GameManager.company". Property reads only.
	function inspect(p, max) {
		var cur = window, parts = String(p || '').split('.').filter(function (s) { return s; });
		for (var i = 0; i < parts.length; i++) { if (cur == null) return { missing: parts.slice(0, i + 1).join('.') }; cur = cur[parts[i]]; }
		function brief(v) {
			var t = typeof v;
			if (v === null || t === 'undefined' || t === 'number' || t === 'boolean') return v === undefined ? 'undefined' : v;
			if (t === 'string') return v.slice(0, 160);
			if (t === 'function') return 'function(' + v.length + ')';
			if (Array.isArray(v)) return 'array(' + v.length + ')';
			return 'object';
		}
		if (cur === null || typeof cur !== 'object') return { value: brief(cur) };
		var out = {}, n = 0, lim = max || 120;
		if (Array.isArray(cur)) { out.length = cur.length; for (var k = 0; k < cur.length && k < lim; k++) out[k] = brief(cur[k]); return out; }
		for (var key in cur) { if (n++ >= lim) { out['...'] = 'more'; break; } try { out[key] = brief(cur[key]); } catch (e) { out[key] = 'unreadable'; } }
		return out;
	}

	function run(c) {
		var el = typeof c.i === 'number' ? els[c.i] : null;
		if ((c.type === 'click' || c.type === 'slider' || c.type === 'text') && (!el || c.gen !== gen)) return { ok: false, error: 'stale or missing element, read state again' };
		if (c.type === 'click') { var r = el.getBoundingClientRect(); mouse(el, r.left + r.width / 2, r.top + r.height / 2); return { ok: true }; }
		if (c.type === 'clickAt') { var t = document.elementFromPoint(c.x, c.y); if (!t) return { ok: false, error: 'nothing there' }; mouse(t, c.x, c.y); return { ok: true, tag: t.tagName, id: t.id || '' }; }
		if (c.type === 'slider') {
			var $s = jQuery(el), v = Number(c.value);
			$s.slider('value', v);
			['slide', 'change'].forEach(function (n) { var cb = $s.slider('option', n); if (typeof cb === 'function') cb.call(el, {}, { value: v, handle: el.firstChild }); });
			return { ok: true, value: $s.slider('value') };
		}
		if (c.type === 'text') {
			el.value = String(c.value);
			['input', 'change', 'keyup'].forEach(function (n) { el.dispatchEvent(new Event(n, { bubbles: true })); });
			return { ok: true };
		}
		if (c.type === 'key') {
			['keydown', 'keyup'].forEach(function (n) { document.dispatchEvent(new KeyboardEvent(n, { key: String(c.key), bubbles: true })); });
			return { ok: true };
		}
		if (c.type === 'inspect') return { ok: true, data: inspect(c.path, c.max) };
		return { ok: false, error: 'unknown command' };
	}

	function tick() {
		try {
			if (fs.existsSync(CMD)) {
				var c = null;
				try { c = JSON.parse(fs.readFileSync(CMD, 'utf8')); } catch (e) { }
				if (c && c.id !== lastId) {
					lastId = c.id;
					try { lastResult = run(c); } catch (e) { lastResult = { ok: false, error: String(e) }; }
					lastResult.id = c.id;
				}
				if (c) { try { fs.unlinkSync(CMD); } catch (e) { } }
			}
			var items = scan();
			var text = String(document.body.innerText || '').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').slice(0, 4000);
			var sig = JSON.stringify(items) + text;
			if (sig !== lastSig) { gen++; lastSig = sig; }
			var now = Date.now();
			var state = JSON.stringify({ t: now, gen: gen, w: innerWidth, h: innerHeight, last: lastResult, text: text, items: items });
			if (now - lastWrite > 250) { fs.writeFileSync(STATE + '.tmp', state); fs.renameSync(STATE + '.tmp', STATE); lastWrite = now; }
		} catch (e) {
			try { fs.writeFileSync(path.join(DIR, 'error.txt'), String(e && e.stack || e)); } catch (e2) { }
		}
	}
	setInterval(tick, 300);
})();
