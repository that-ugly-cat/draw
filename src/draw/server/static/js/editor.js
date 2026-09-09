/*
 * The bridge between this app and the draw.io iframe.
 *
 * The whole integration is here, and it is small on purpose: the editor is a
 * component that receives XML and returns XML, and everything that decides
 * anything — who holds the lock, what becomes a version, what happens to a save
 * that arrives too late — lives on the server.
 *
 * The session id is generated per page load rather than stored in a cookie, and
 * that is the point: the lock is keyed on a session, so the same person in two
 * tabs is two holders and sees the conflict.
 */
(function () {
  const cfg = window.DRAW;
  const frame = document.getElementById("editor-frame");
  const statusEl = document.getElementById("save-status");
  const lockEl = document.getElementById("lock-status");
  const takeoverBtn = document.getElementById("take-over");

  const session = (crypto.randomUUID && crypto.randomUUID()) ||
    String(Date.now()) + Math.random().toString(36).slice(2);

  let ready = false;
  let dirty = false;
  let lastSent = null;

  // The revision we believe the server holds. Every answer that carries one --
  // a lock refresh, a save -- is a chance to notice the document moved under
  // us, which is what happens when the same person edits it from a script.
  let revision = cfg.revision || 0;
  // How many saves of ours are in flight. Non-zero means the revision on the
  // server is ahead of what we know for a reason we caused.
  let pendingSaves = 0;
  let banner = document.getElementById("moved-banner");

  function say(el, text, cls) {
    if (!el) return;
    el.textContent = text;
    el.className = "badge" + (cls ? " " + cls : "");
  }

  function post(msg) {
    frame.contentWindow.postMessage(JSON.stringify(msg), "*");
  }

  async function api(path, body) {
    const res = await fetch(cfg.apiBase + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ session: session }, body || {})),
    });
    if (!res.ok && res.status !== 413) throw new Error(String(res.status));
    return res.json();
  }

  function paintLock(state) {
    if (!lockEl) return;
    if (state.held) {
      say(lockEl, cfg.strings.lockYours, "ok");
      if (takeoverBtn) takeoverBtn.hidden = true;
    } else if (state.held_by_other) {
      say(lockEl, cfg.strings.lockOther.replace("{who}", state.label || "?"), "warn");
      if (takeoverBtn) takeoverBtn.hidden = false;
    } else {
      say(lockEl, cfg.strings.lockFree, "");
      if (takeoverBtn) takeoverBtn.hidden = true;
    }
  }

  async function adopt() {
    // Replace what the editor is showing with what the server now holds.
    const res = await fetch(cfg.xmlUrl, { headers: { Accept: "application/json" } });
    const doc = await res.json();
    revision = doc.revision;
    lastSent = doc.xml;   // adopting is not an edit: do not save it straight back
    dirty = false;
    post({ action: "load", xml: doc.xml, autosave: cfg.mode === "rw" ? 1 : 0 });
    if (banner) banner.hidden = true;
    say(statusEl, cfg.strings.reloaded, "");
  }

  function noticed(serverRevision) {
    if (typeof serverRevision !== "number" || serverRevision <= revision) return;
    // A save of our own that has not come back yet has already moved the
    // revision on the server, so any other answer arriving in the meantime
    // reports a change we caused. Without this guard the page announces its own
    // writing as somebody else's: opening a fresh diagram was enough, because
    // the editor autosaves right after loading and the lock refresh overtook
    // the save it raced.
    if (pendingSaves > 0) return;
    // Somebody else wrote. With nothing unsaved this is not a decision worth
    // interrupting anyone for -- take theirs. With unsaved work it is, so ask.
    if (!dirty) {
      adopt().catch(function () {});
    } else if (banner) {
      banner.hidden = false;
    }
  }

  async function takeLock(steal) {
    try {
      const state = await api("/lock", { steal: !!steal });
      paintLock(state);
      noticed(state.revision);
    } catch (e) {
      /* A failed refresh is not worth interrupting anyone over: the save path
         reports the truth, and an orphan version is not a lost one. */
    }
  }

  async function save(xml) {
    if (xml === lastSent) return; // the editor re-emits identical states often
    lastSent = xml;
    say(statusEl, cfg.strings.saving, "");
    pendingSaves++;
    try {
      const out = await api("/save", { xml: xml });
      if (out.error === "diagram_too_large") {
        say(statusEl, out.message, "danger");
        lastSent = null; // let the next attempt through once it shrinks
        return;
      }
      if (out.ok === false && out.reason === "lock_held") {
        say(
          statusEl,
          cfg.strings.saveOrphan
            .replace("{who}", out.holder || "?")
            .replace("{n}", out.version),
          "warn"
        );
        paintLock({ held: false, held_by_other: true, label: out.holder });
        // Refused, but the revision the server reports is still news to us.
        if (typeof out.revision === "number") {
          revision = Math.max(revision, out.revision);
        }
        return;
      }
      dirty = false;
      // Highest wins: two saves can be in flight at once, and their answers do
      // not have to arrive in the order they were sent.
      if (typeof out.revision === "number") {
        revision = Math.max(revision, out.revision);
      }
      say(statusEl, cfg.strings.saved, "ok");
      post({ action: "export", format: "png", spinKey: "export" });
    } catch (e) {
      say(statusEl, "…", "warn");
      lastSent = null;
    } finally {
      pendingSaves--;
    }
  }

  window.addEventListener("message", function (evt) {
    if (evt.source !== frame.contentWindow) return;
    let msg;
    try {
      msg = JSON.parse(evt.data);
    } catch (e) {
      return;
    }

    if (msg.event === "init") {
      ready = true;
      post({ action: "load", xml: cfg.xml, autosave: cfg.mode === "rw" ? 1 : 0 });
      if (cfg.mode === "rw") takeLock(false);
      return;
    }

    if (msg.event === "autosave" || msg.event === "save") {
      if (cfg.mode !== "rw") return;
      dirty = true;
      save(msg.xml);
      return;
    }

    if (msg.event === "export" && msg.data) {
      fetch(cfg.thumbUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ png: msg.data }),
      }).catch(function () {});
    }
  });

  if (cfg.mode === "rw") {
    setInterval(function () {
      if (ready) takeLock(false);
    }, cfg.lockRefresh * 1000);

    window.addEventListener("beforeunload", function () {
      // Best effort; if it does not land the lock expires on its own in 90s.
      navigator.sendBeacon &&
        navigator.sendBeacon(
          cfg.apiBase + "/unlock",
          new Blob([JSON.stringify({ session: session })], {
            type: "application/json",
          })
        );
    });
  }

  if (banner) {
    document.getElementById("moved-reload").addEventListener("click", function () {
      adopt().catch(function () {});
    });
    document.getElementById("moved-dismiss").addEventListener("click", function () {
      // Keeping yours is allowed and costs nothing: whatever it overwrites is
      // already a version, so the other side is recoverable either way.
      banner.hidden = true;
      revision = Infinity;
    });
  }

  if (takeoverBtn) {
    takeoverBtn.addEventListener("click", function () {
      if (confirm(cfg.strings.takeOverWarn)) takeLock(true);
    });
  }

  paintLock(cfg.lock);
})();
