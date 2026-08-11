/**
 * SchemaLock Recorder bridge — runs in the isolated world at document_start.
 *
 * Forwards the MAIN-world hook's `schemalock:record` window events to the
 * background service worker in batches, and pushes the current recording state
 * (from background / storage) back to the hook.
 */
(function () {
  const BUFFER_LIMIT = 64;
  const FLUSH_MS = 250;

  let buffer = [];
  let flushTimer = null;

  function flush() {
    if (!buffer.length) return;
    const batch = buffer;
    buffer = [];
    try {
      chrome.runtime.sendMessage({ type: "record", entries: batch });
    } catch (e) {
      /* ignore */
    }
  }

  function pushState(detail) {
    window.dispatchEvent(new CustomEvent("schemalock:state", { detail }));
  }

  window.addEventListener("schemalock:record", (e) => {
    if (!e.detail) return;
    buffer.push(e.detail);
    if (!flushTimer) {
      flushTimer = setTimeout(() => {
        flushTimer = null;
        flush();
      }, FLUSH_MS);
    }
    if (buffer.length >= BUFFER_LIMIT) flush();
  });

  function applyState(state) {
    pushState({
      enabled: !!state.enabled,
      captureSuccessBodies: !!state.captureSuccessBodies,
    });
  }

  try {
    chrome.runtime.sendMessage({ type: "state:get" }, (res) => {
      if (res) applyState(res);
    });
  } catch (e) {
    /* ignore */
  }

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== "local" || !changes.sl_state) return;
    applyState(changes.sl_state.newValue);
  });
})();
