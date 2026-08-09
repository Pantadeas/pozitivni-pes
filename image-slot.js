// @ds-adherence-ignore -- omelette starter scaffold (raw elements/hex/px by design)
(() => {
  const STATE_FILE = '.image-slots.state.json';
  const UNSPLASH_HOMEPAGE_HREF = 'https://unsplash.com/?utm_source=claude_design&utm_medium=referral';
  const isUnsplashHost = (u) => {
    try { return /(^|\.)unsplash\.com$/.test(new URL(u, document.baseURI).hostname.replace(/\.$/, '')); } catch { return false; }
  };
  const withReferral = (href) => {
    try {
      const u = new URL(href);
      if (!/(^|\.)unsplash\.com$/.test(u.hostname.replace(/\.$/, ''))) return href;
      if (!u.searchParams.has('utm_source')) u.searchParams.set('utm_source', 'claude_design');
      if (!u.searchParams.has('utm_medium')) u.searchParams.set('utm_medium', 'referral');
      return u.toString();
    } catch (e) { return href; }
  };
  const MAX_DIM = 1200;
  const ACCEPT = ['image/png', 'image/jpeg', 'image/webp', 'image/avif'];

  const subs = new Set();
  let slots = {};
  const tombstones = new Set();
  let loaded = false;
  let loadP = null;

  function load() {
    if (loadP) return loadP;
    loadP = fetch(STATE_FILE)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (j && typeof j === 'object') {
          const merged = Object.assign({}, j, slots);
          for (const k in slots) {
            if (merged[k] && !merged[k].u && j[k]) {
              merged[k].u = typeof j[k] === 'string' ? j[k] : j[k].u;
            }
          }
          for (const id of tombstones) delete merged[id];
          slots = merged;
        }
        tombstones.clear();
      })
      .catch(() => {})
      .then(() => { loaded = true; subs.forEach((fn) => fn()); });
    return loadP;
  }

  let saving = false;
  let saveDirty = false;
  function flushNow() {
    if (!loaded) return;
    const w = window.omelette && window.omelette.writeFile;
    if (!w) return;
    try { Promise.resolve(w(STATE_FILE, JSON.stringify(slots))).catch(() => {}); } catch (e) {}
  }
  function save() {
    if (saving) { saveDirty = true; return; }
    const w = window.omelette && window.omelette.writeFile;
    if (!w) return;
    saving = true;
    Promise.resolve(w(STATE_FILE, JSON.stringify(slots)))
      .catch(() => {})
      .then(() => { saving = false; if (saveDirty) { saveDirty = false; save(); } });
  }

  const S_MAX = 5;
  const clampS = (s) => Math.max(1, Math.min(S_MAX, s));

  function getSlot(id) {
    const v = slots[id];
    if (!v) return null;
    return typeof v === 'string' ? { u: v, s: 1, x: 0, y: 0 } : v;
  }

  function setSlot(id, val) {
    if (!id) return;
    if (val) { slots[id] = val; tombstones.delete(id); }
    else { delete slots[id]; if (!loaded) tombstones.add(id); }
    subs.forEach((fn) => fn());
    if (loaded) save(); else load().then(save);
  }

  async function toDataUrl(file, targetW) {
    const bitmap = await createImageBitmap(file);
    try {
      const cap = Math.min(MAX_DIM, Math.max(1, Math.round(targetW * 2)) || MAX_DIM);
      const scale = Math.min(1, cap / Math.max(bitmap.width, bitmap.height));
      const w = Math.max(1, Math.round(bitmap.width * scale));
      const h = Math.max(1, Math.round(bitmap.height * scale));
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d').drawImage(bitmap, 0, 0, w, h);
      return canvas.toDataURL('image/webp', 0.85);
    } finally { bitmap.close && bitmap.close(); }
  }

  const stylesheet =
    ':host{display:block;position:relative;font:13px/1.3 system-ui,-apple-system,sans-serif;width:100%;height:100%;aspect-ratio:3/2}' +
    '.empty .cap,.empty .sub{opacity:.75}' +
    '.frame{position:absolute;inset:0;overflow:hidden;background:rgba(127,127,127,.08)}' +
    '.frame img{position:absolute;max-width:none;transform:translate(-50%,-50%);-webkit-user-drag:none;user-select:none;touch-action:none}' +
    '.spill{position:fixed;margin:0;inset:auto;border:0;padding:0;background:transparent;overflow:visible;transform:translate(-50%,-50%);z-index:1;cursor:grab;touch-action:none}' +
    ':host([data-panning]) .spill{cursor:grabbing}' +
    '.spill .ghost{position:absolute;inset:0;width:100%;height:100%;opacity:.35;pointer-events:none;-webkit-user-drag:none;user-select:none;box-shadow:0 0 0 1px rgba(0,0,0,.2),0 12px 32px rgba(0,0,0,.2)}' +
    '.spill .handle{position:absolute;width:12px;height:12px;border-radius:50%;background:#fff;box-shadow:0 0 0 1.5px #c96442,0 1px 3px rgba(0,0,0,.3);transform:translate(-50%,-50%)}' +
    '.spill .handle[data-c=nw]{left:0;top:0;cursor:nwse-resize}' +
    '.spill .handle[data-c=ne]{left:100%;top:0;cursor:nesw-resize}' +
    '.spill .handle[data-c=sw]{left:0;top:100%;cursor:nesw-resize}' +
    '.spill .handle[data-c=se]{left:100%;top:100%;cursor:nwse-resize}' +
    ':host([data-reframe]){z-index:10}' +
    ':host([data-reframe]) .frame{box-shadow:0 0 0 2px #c96442}' +
    '.empty{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;text-align:center;padding:12px;box-sizing:border-box;cursor:pointer;user-select:none}' +
    '.empty svg{opacity:.45}' +
    '.empty .cap{max-width:90%;font-weight:500;letter-spacing:.01em}' +
    '.empty .sub{font-size:11px}' +
    '.empty .sub u{text-underline-offset:2px}' +
    '.empty:hover .sub{opacity:1}' +
    ':host([data-over]) .frame{outline:2px solid #c96442;outline-offset:-2px;background:rgba(201,100,66,.10)}' +
    '.ring{position:absolute;inset:0;pointer-events:none;border:1.5px dashed currentColor;opacity:.35;transition:border-color .12s,opacity .12s}' +
    ':host([data-over]) .ring{border-color:#c96442;opacity:1}' +
    ':host([data-filled]) .ring{display:none}' +
    '.ctl{position:absolute;inset:auto;top:8px;right:8px;margin:0;border:0;padding:0;background:transparent;overflow:visible;display:flex;gap:6px;opacity:0;pointer-events:none;transition:opacity .12s;z-index:2;white-space:nowrap}' +
    '.ctl:popover-open{position:fixed;inset:auto;transform:translateX(-100%)}' +
    ':host([data-filled][data-editable]:hover) .ctl,:host([data-reframe]) .ctl{opacity:1;pointer-events:auto}' +
    '.ctl button{appearance:none;border:0;border-radius:6px;padding:5px 10px;cursor:pointer;background:rgba(0,0,0,.65);color:#fff;font:11px/1 system-ui,-apple-system,sans-serif;backdrop-filter:blur(6px)}' +
    '.ctl button:hover{background:rgba(0,0,0,.8)}' +
    '.err{position:absolute;left:8px;bottom:8px;right:8px;color:#b3261e;font-size:11px;background:rgba(255,255,255,.85);padding:4px 6px;border-radius:5px;pointer-events:none}' +
    ':host([data-swapping]) .frame img{visibility:hidden}' +
    '.loading{position:absolute;inset:0;display:none;align-items:center;justify-content:center;pointer-events:none}' +
    ':host([data-swapping]) .loading{display:flex}' +
    '.loading::after{content:"";width:22px;height:22px;border-radius:50%;border:2px solid rgba(127,127,127,.25);border-top-color:currentColor;animation:om-slot-spin .7s linear infinite}' +
    '@keyframes om-slot-spin{to{transform:rotate(360deg)}}' +
    '@media (prefers-reduced-motion:reduce){.loading::after{animation:none}}' +
    '.credit{position:absolute;left:6px;bottom:6px;max-width:calc(100% - 12px);display:none;padding:3px 7px;border-radius:5px;background:rgba(0,0,0,.55);color:#fff;font:10px/1.2 system-ui,-apple-system,sans-serif;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;backdrop-filter:blur(6px)}' +
    '.credit a{color:inherit;text-decoration:none}' +
    '.credit a:hover,.credit a:focus-visible{text-decoration:underline}' +
    ':host([data-filled][data-credit]) .credit{display:block}' +
    ':host-context([data-om-exporting]) .ctl,:host-context([data-om-exporting]) .credit{display:none !important}' +
    '@media print{.ctl,.credit{display:none !important}}' +
    '.attr-error{position:absolute;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center;gap:6px;text-align:center;padding:12px;box-sizing:border-box;background:#f2f1ef;color:#6e6c66;user-select:none;font:13px/1.45 system-ui,-apple-system,sans-serif}' +
    '.attr-error svg{opacity:.55}' +
    '.attr-error .cap{max-width:92%;font-weight:500;letter-spacing:.01em}' +
    ':host([data-attribution-error]) .attr-error{display:flex}' +
    ':host([data-attribution-error]) .ring{display:none}';

  const icon =
    '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>' +
    '<path d="m21 15-5-5L5 21"/></svg>';

  const warnIcon =
    '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/>' +
    '<path d="M12 9v4"/><path d="M12 17h.01"/></svg>';

  class ImageSlot extends HTMLElement {
    static get observedAttributes() {
      return ['shape', 'radius', 'mask', 'fit', 'placeholder', 'src', 'id', 'credit', 'credit-href'];
    }

    static cloneSlot(fromId, isFree) {
      if (typeof fromId !== 'string' || !fromId) return null;
      if (!loaded) return null;
      const stem = fromId.replace(/-\d+$/, '') || fromId;
      for (let n = 2; n < 100; n++) {
        const toId = stem + '-' + n;
        if (toId === fromId) continue;
        if (slots[toId] !== undefined) {
          const prev = getSlot(toId);
          const cur = getSlot(fromId);
          if (!(prev && cur && prev.u && prev.u === cur.u &&
                prev.s === cur.s && prev.x === cur.x && prev.y === cur.y &&
                (typeof isFree !== 'function' || isFree(toId)))) continue;
          return toId;
        }
        if (typeof isFree === 'function' && !isFree(toId)) continue;
        const v = getSlot(fromId);
        if (v) setSlot(toId, Object.assign({}, v));
        return toId;
      }
      return null;
    }

    constructor() {
      super();
      const root = this.shadowRoot || this.attachShadow({ mode: 'open', clonable: true });
      root.innerHTML =
        '<style>' + stylesheet + '</style>' +
        '<div class="frame" part="frame">' +
        '  <img part="image" alt="" draggable="false" style="display:none">' +
        '  <div class="empty" part="empty">' + icon +
        '    <div class="cap"></div>' +
        '    <div class="sub">or <u>browse files</u></div></div>' +
        '  <div class="attr-error" part="attribution-error">' + warnIcon +
        '    <div class="cap">This photo needs attribution</div></div>' +
        '  <div class="loading" part="loading"></div>' +
        '  <div class="ring" part="ring"></div>' +
        '</div>' +
        '<span class="credit" part="credit"></span>' +
        '<div class="spill" popover="manual" data-dc-edit-transparent>' +
        '  <img class="ghost" alt="" draggable="false">' +
        '  <div class="handle" data-c="nw"></div><div class="handle" data-c="ne"></div>' +
        '  <div class="handle" data-c="sw"></div><div class="handle" data-c="se"></div>' +
        '</div>' +
        '<div class="ctl" popover="manual" data-dc-edit-transparent><button data-act="replace" title="Replace image">Replace</button>' +
        '  <button data-act="edit" title="Reframe image">Edit</button></div>' +
        '<input type="file" accept="' + ACCEPT.join(',') + '" hidden>';
      this._frame = root.querySelector('.frame');
      this._ring = root.querySelector('.ring');
      this._img = root.querySelector('.frame img');
      this._empty = root.querySelector('.empty');
      this._cap = root.querySelector('.cap');
      this._sub = root.querySelector('.sub');
      this._spill = root.querySelector('.spill');
      this._ctl = root.querySelector('.ctl');
      this._credit = root.querySelector('.credit');
      this._attrError = root.querySelector('.attr-error');
      this._credit.addEventListener('click', (e) => e.stopPropagation());
      this._credit.addEventListener('dblclick', (e) => e.stopPropagation());
      this._ghost = root.querySelector('.ghost');
      this._err = null;
      this._input = root.querySelector('input');
      this._depth = 0;
      this._gen = 0;
      this._swapGen = 0;
      this._loadPending = false;
      this._hidShowing = false;
      this._view = { s: 1, x: 0, y: 0 };
      this._subFn = () => this._render();
      this._empty.addEventListener('click', () => this._input.click());
      root.addEventListener('click', (e) => {
        const act = e.target && e.target.getAttribute && e.target.getAttribute('data-act');
        if (!act) return;
        if (!this.hasAttribute('data-editable')) return;
        if (act === 'replace') {
          this._exitReframe(true);
          this.dispatchEvent(new CustomEvent('image-slot:pick', { bubbles: true, composed: true, detail: { id: this.id || null } }));
        }
        if (act === 'edit') {
          if (!this._reframes()) return;
          if (this.hasAttribute('data-reframe')) this._exitReframe(true);
          else this._enterReframe();
        }
      });
      this._input.addEventListener('change', () => {
        const f = this._input.files && this._input.files[0];
        if (f) this._ingest(f);
        this._input.value = '';
      });
      this._img.addEventListener('load', () => { this._loadPending = false; this._releaseMask(true); this._applyView(); });
      this._img.addEventListener('error', () => { this._loadPending = false; this._releaseMask(true); });
      this.addEventListener('dblclick', (e) => {
        if (!this.hasAttribute('data-editable') || !this._reframes()) return;
        e.preventDefault();
        if (this.hasAttribute('data-reframe')) this._exitReframe(true);
        else this._enterReframe();
      });
      this._spill.addEventListener('pointerdown', (e) => {
        if (e.button !== 0 || !this.hasAttribute('data-reframe')) return;
        e.preventDefault(); e.stopPropagation();
        this._spill.setPointerCapture(e.pointerId);
        const rect = this.getBoundingClientRect();
        const fw = rect.width || 1, fh = rect.height || 1;
        const corner = e.target.getAttribute && e.target.getAttribute('data-c');
        let move;
        if (corner) {
          const iw = this._img.naturalWidth || 1, ih = this._img.naturalHeight || 1;
          const contain = (this.getAttribute('fit') || 'cover').toLowerCase() === 'contain';
          const base = contain ? Math.min(fw / iw, fh / ih) : Math.max(fw / iw, fh / ih);
          const sx = corner.includes('e') ? 1 : -1;
          const sy = corner.includes('s') ? 1 : -1;
          const s0 = this._view.s;
          const w0 = iw * base * s0, h0 = ih * base * s0;
          const cx0 = (50 + this._view.x) / 100 * fw;
          const cy0 = (50 + this._view.y) / 100 * fh;
          const ox = cx0 - sx * w0 / 2, oy = cy0 - sy * h0 / 2;
          const diag0 = Math.hypot(w0, h0);
          const ux = sx * w0 / diag0, uy = sy * h0 / diag0;
          move = (ev) => {
            const proj = (ev.clientX - rect.left - ox) * ux + (ev.clientY - rect.top - oy) * uy;
            const s = clampS(s0 * proj / diag0);
            const d = diag0 * s / s0;
            this._view.s = s;
            this._view.x = (ox + ux * d / 2) / fw * 100 - 50;
            this._view.y = (oy + uy * d / 2) / fh * 100 - 50;
            this._clampView(); this._applyView();
          };
        } else {
          this.setAttribute('data-panning', '');
          const start = { px: e.clientX, py: e.clientY, x: this._view.x, y: this._view.y };
          move = (ev) => {
            this._view.x = start.x + (ev.clientX - start.px) / fw * 100;
            this._view.y = start.y + (ev.clientY - start.py) / fh * 100;
            this._clampView(); this._applyView();
          };
        }
        const up = () => {
          try { this._spill.releasePointerCapture(e.pointerId); } catch {}
          this._spill.removeEventListener('pointermove', move);
          this._spill.removeEventListener('pointerup', up);
          this._spill.removeEventListener('pointercancel', up);
          this.removeAttribute('data-panning');
          this._dragUp = null;
        };
        this._dragUp = up;
        this._spill.addEventListener('pointermove', move);
        this._spill.addEventListener('pointerup', up);
        this._spill.addEventListener('pointercancel', up);
      });
      this.addEventListener('wheel', (e) => {
        if (!this.hasAttribute('data-reframe')) return;
        e.preventDefault();
        const r = this.getBoundingClientRect();
        const cx = (e.clientX - r.left) / r.width * 100 - 50;
        const cy = (e.clientY - r.top) / r.height * 100 - 50;
        const prev = this._view.s;
        const next = clampS(prev * Math.pow(1.0015, -e.deltaY));
        if (next === prev) return;
        const k = next / prev;
        this._view.s = next;
        this._view.x = cx * (1 - k) + this._view.x * k;
        this._view.y = cy * (1 - k) + this._view.y * k;
        this._clampView(); this._applyView();
      }, { passive: false });
    }

    connectedCallback() {
      if (!this.id && !ImageSlot._warned) { ImageSlot._warned = true; console.warn('<image-slot> without an id will not persist its dropped image.'); }
      this.addEventListener('dragenter', this);
      this.addEventListener('dragover', this);
      this.addEventListener('dragleave', this);
      this.addEventListener('drop', this);
      subs.add(this._subFn);
      this.addEventListener('pointerenter', this._subFn);
      this._ro = new ResizeObserver(() => this._render());
      this._ro.observe(this);
      load();
      this._render();
    }

    disconnectedCallback() {
      subs.delete(this._subFn);
      this.removeEventListener('pointerenter', this._subFn);
      this.removeEventListener('dragenter', this);
      this.removeEventListener('dragover', this);
      this.removeEventListener('dragleave', this);
      this.removeEventListener('drop', this);
      if (this._ro) { this._ro.disconnect(); this._ro = null; }
      this._exitReframe(false);
    }

    _enterReframe() {
      if (this.hasAttribute('data-reframe')) return;
      this.setAttribute('data-reframe', '');
      this._signalReframe(true);
      this._pagehide = () => { this._exitReframe(true); flushNow(); };
      window.addEventListener('pagehide', this._pagehide);
      try { this._spill.showPopover(); } catch {}
      try { this._ctl.showPopover(); } catch {}
      this._reposition = () => { if (this.hasAttribute('data-reframe')) this._applyView(); };
      window.addEventListener('scroll', this._reposition, true);
      window.addEventListener('resize', this._reposition);
      this._lastRect = '';
      this._watch = () => {
        if (!this.hasAttribute('data-reframe')) return;
        const r = this.getBoundingClientRect();
        const key = r.left + ',' + r.top + ',' + r.width + ',' + r.height;
        if (key !== this._lastRect) { this._lastRect = key; this._applyView(); }
        this._watchId = requestAnimationFrame(this._watch);
      };
      this._watchId = requestAnimationFrame(this._watch);
      this._applyView();
      this._outside = (e) => { if (e.composedPath && e.composedPath().includes(this)) return; this._exitReframe(true); };
      this._esc = (e) => { if (e.key === 'Escape') this._exitReframe(true); };
      document.addEventListener('pointerdown', this._outside, true);
      document.addEventListener('keydown', this._esc, true);
    }

    _exitReframe(commit) {
      if (!this.hasAttribute('data-reframe')) return;
      if (this._dragUp) this._dragUp();
      this.removeAttribute('data-reframe');
      this.removeAttribute('data-panning');
      if (this._outside) document.removeEventListener('pointerdown', this._outside, true);
      if (this._esc) document.removeEventListener('keydown', this._esc, true);
      this._outside = this._esc = null;
      if (this._reposition) { window.removeEventListener('scroll', this._reposition, true); window.removeEventListener('resize', this._reposition); this._reposition = null; }
      if (this._watchId) { cancelAnimationFrame(this._watchId); this._watchId = 0; }
      if (this._pagehide) { window.removeEventListener('pagehide', this._pagehide); this._pagehide = null; }
      try { this._spill.hidePopover(); } catch {}
      try { this._ctl.hidePopover(); } catch {}
      this._ctl.style.left = ''; this._ctl.style.top = '';
      if (commit) this._commitView();
      this._signalReframe(false);
    }

    _signalReframe(active) {
      const target = this.isConnected ? this : document;
      target.dispatchEvent(new CustomEvent('image-slot:reframe', { bubbles: true, composed: true, detail: { active: active, id: this.id || null } }));
    }

    openFilePicker() { this._exitReframe(true); this._input.click(); }

    attributeChangedCallback(name, oldVal, newVal) {
      if (name === 'src' && oldVal !== newVal) { this._gen++; this._swapGen = 0; }
      if (this.shadowRoot) this._render();
    }

    handleEvent(e) {
      if (e.type === 'dragenter' || e.type === 'dragover') {
        e.preventDefault(); e.stopPropagation();
        if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
        if (e.type === 'dragenter') this._depth++;
        this.setAttribute('data-over', '');
      } else if (e.type === 'dragleave') {
        if (--this._depth <= 0) { this._depth = 0; this.removeAttribute('data-over'); }
      } else if (e.type === 'drop') {
        e.preventDefault(); e.stopPropagation();
        this._depth = 0; this.removeAttribute('data-over');
        const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) this._ingest(f);
      }
    }

    async _ingest(file) {
      this._setError(null);
      if (!file || ACCEPT.indexOf(file.type) < 0) { this._setError('Drop a PNG, JPEG, WebP, or AVIF image.'); return; }
      const gen = ++this._gen;
      if (this.hasAttribute('data-filled')) { this.setAttribute('data-swapping', ''); this._swapGen = gen; }
      try {
        const w = this.clientWidth || this.offsetWidth || MAX_DIM;
        const url = await toDataUrl(file, w);
        if (gen !== this._gen) return;
        this._exitReframe(false);
        this._swapGen = 0;
        const val = { u: url, s: 1, x: 0, y: 0 };
        setSlot(this.id || '', val);
        if (!this.id) { this._local = val; this._render(); }
      } catch (err) {
        if (gen !== this._gen) return;
        this._swapGen = 0;
        this._releaseMask();
        this._setError('Could not read that image.');
        console.warn('<image-slot> ingest failed:', err);
      }
    }

    _setError(msg) {
      if (this._err) { this._err.remove(); this._err = null; }
      if (!msg) return;
      const d = document.createElement('div');
      d.className = 'err'; d.textContent = msg;
      this.shadowRoot.appendChild(d);
      this._err = d;
      setTimeout(() => { if (this._err === d) { d.remove(); this._err = null; } }, 3000);
    }

    _reframes() { return this.hasAttribute('data-filled'); }

    _releaseMask(settled) {
      if (!this._swapGen && !this._loadPending && (settled || this._img.complete)) {
        this.removeAttribute('data-swapping');
      }
    }

    _geom() {
      const iw = this._img.naturalWidth, ih = this._img.naturalHeight;
      const fw = this.clientWidth, fh = this.clientHeight;
      if (!iw || !ih || !fw || !fh) return null;
      const contain = (this.getAttribute('fit') || 'cover').toLowerCase() === 'contain';
      const base = contain ? Math.min(fw / iw, fh / ih) : Math.max(fw / iw, fh / ih);
      return { iw, ih, fw, fh, base };
    }

    _clampView() {
      const g = this._geom();
      if (!g) return;
      const mx = Math.max(0, (g.iw * g.base * this._view.s / g.fw - 1) * 50);
      const my = Math.max(0, (g.ih * g.base * this._view.s / g.fh - 1) * 50);
      this._view.x = Math.max(-mx, Math.min(mx, this._view.x));
      this._view.y = Math.max(-my, Math.min(my, this._view.y));
    }

    _applyView() {
      const g = this._geom();
      if (this.hasAttribute('data-reframe')) {
        let onTop = false;
        try { onTop = this._ctl.matches(':popover-open'); } catch {}
        if (onTop) {
          const r = this.getBoundingClientRect();
          this._ctl.style.left = (r.right - 8) + 'px';
          this._ctl.style.top = (r.top + 8) + 'px';
        }
      }
      if (!g) {
        const contain = (this.getAttribute('fit') || 'cover').toLowerCase() === 'contain';
        this._img.style.width = '100%'; this._img.style.height = '100%';
        this._img.style.left = '50%'; this._img.style.top = '50%';
        this._img.style.objectFit = contain ? 'contain' : 'cover';
        return;
      }
      const k = g.base * this._view.s;
      const w = (g.iw * k / g.fw * 100) + '%';
      const h = (g.ih * k / g.fh * 100) + '%';
      const l = (50 + this._view.x) + '%';
      const t = (50 + this._view.y) + '%';
      this._img.style.width = w; this._img.style.height = h;
      this._img.style.left = l; this._img.style.top = t;
      this._img.style.objectFit = '';
      if (this.hasAttribute('data-reframe')) {
        const r = this.getBoundingClientRect();
        const sx = g.fw ? r.width / g.fw : 1;
        const sy = g.fh ? r.height / g.fh : 1;
        this._spill.style.width = (g.iw * k * sx) + 'px';
        this._spill.style.height = (g.ih * k * sy) + 'px';
        this._spill.style.left = (r.left + (50 + this._view.x) / 100 * r.width) + 'px';
        this._spill.style.top = (r.top + (50 + this._view.y) / 100 * r.height) + 'px';
      }
    }

    _commitView() {
      const v = { s: this._view.s, x: this._view.x, y: this._view.y };
      if (this._userUrl) v.u = this._userUrl;
      if (this.id) setSlot(this.id, v);
      else { this._local = v; }
    }

    _render() {
      const mask = this.getAttribute('mask');
      const shape = (this.getAttribute('shape') || 'rounded').toLowerCase();
      let radius = '';
      if (shape === 'circle') radius = '50%';
      else if (shape === 'pill') radius = '9999px';
      else if (shape === 'rounded') { const n = parseFloat(this.getAttribute('radius')); radius = (Number.isFinite(n) ? n : 12) + 'px'; }
      this._frame.style.borderRadius = mask ? '' : radius;
      this._frame.style.clipPath = mask || '';
      this._ring.style.borderRadius = mask ? '' : radius;
      this._ring.style.display = mask ? 'none' : '';
      const editable = !!(window.omelette && window.omelette.writeFile);
      this.toggleAttribute('data-editable', editable);
      this._sub.style.display = editable ? '' : 'none';
      let stored = this.id ? getSlot(this.id) : this._local;
      if (stored && stored.u && !/^data:image\//i.test(stored.u)) stored = null;
      const srcAttr = this.getAttribute('src') || '';
      this._userUrl = (stored && stored.u) || null;
      const url = this._userUrl || srcAttr;
      if (!this.hasAttribute('data-reframe')) {
        this._view = {
          s: stored && Number.isFinite(stored.s) ? clampS(stored.s) : 1,
          x: stored && Number.isFinite(stored.x) ? stored.x : 0,
          y: stored && Number.isFinite(stored.y) ? stored.y : 0,
        };
      }
      this._cap.textContent = this.getAttribute('placeholder') || 'Drop an image';
      const credit = (this.getAttribute('credit') || '').trim();
      const attrError = !!(!credit && !this._userUrl && srcAttr && isUnsplashHost(srcAttr));
      this.toggleAttribute('data-attribution-error', attrError);
      if (url && !attrError) {
        const prev = this._img.getAttribute('src');
        if (prev !== url) {
          if (prev || this._hidShowing) this.setAttribute('data-swapping', '');
          this._loadPending = true;
          this._img.src = url;
          this._ghost.src = url;
        } else { this._releaseMask(); }
        this._hidShowing = false;
        this._img.style.display = 'block';
        this._empty.style.display = 'none';
        this.setAttribute('data-filled', '');
        this._clampView(); this._applyView();
      } else {
        this.removeAttribute('data-swapping');
        this._loadPending = false;
        this._hidShowing = attrError && !!this._img.getAttribute('src');
        this._img.style.display = 'none';
        this._img.removeAttribute('src');
        this._ghost.removeAttribute('src');
        this._empty.style.display = attrError ? 'none' : 'flex';
        this.removeAttribute('data-filled');
      }
      const showCredit = !!(url && credit && !this._userUrl && !attrError);
      this._credit.textContent = '';
      if (showCredit) {
        let href = '';
        const rawHref = this.getAttribute('credit-href') || '';
        if (rawHref) {
          try {
            const u = new URL(rawHref, document.baseURI);
            if (u.protocol === 'http:' || u.protocol === 'https:') href = withReferral(u.href);
          } catch {}
        }
        const mkLink = (text, linkHref) => {
          const a = document.createElement('a');
          a.setAttribute('target', '_blank');
          a.setAttribute('rel', 'noopener noreferrer');
          a.setAttribute('href', linkHref);
          a.textContent = text;
          return a;
        };
        const m = /^Photo by (.+) on Unsplash$/.exec(credit);
        if (m) {
          this._credit.appendChild(document.createTextNode('Photo by '));
          this._credit.appendChild(href ? mkLink(m[1], href) : document.createTextNode(m[1]));
          this._credit.appendChild(document.createTextNode(' on '));
          this._credit.appendChild(mkLink('Unsplash', UNSPLASH_HOMEPAGE_HREF));
        } else if (href) {
          this._credit.appendChild(mkLink(credit, href));
        } else {
          this._credit.textContent = credit;
        }
      }
      this.toggleAttribute('data-credit', showCredit);
    }
  }

  if (!customElements.get('image-slot')) {
    customElements.define('image-slot', ImageSlot);
  }
})();
