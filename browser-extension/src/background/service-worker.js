/**
 * SchemaLock Recorder background service worker.
 *
 * Collects recorded entries, aggregates them into normalized endpoints
 * (method + origin + path pattern with {placeholders}), replays requests
 * without credentials to probe auth boundaries, and exports a capture.json
 * that `schemalock scaffold` turns into a contract.
 */
const STORAGE_STATE = "sl_state";
const STORAGE_CAPTURE = "sl_capture";

const DEFAULT_STATE = {
  enabled: false,
  filterPattern: "",
  captureSuccessBodies: false,
};

const MAX_ENTRIES = 5000;
const MAX_CAPTURE_BYTES = 32 * 1024 * 1024; // evict oldest entries past this

let state = null;
let capture = null;

function endpointId(method, origin, path) {
  return `${encodeURIComponent(method)}|${encodeURIComponent(origin)}|${encodeURIComponent(path)}`;
}

function entryBytes(entry) {
  return (
    64 +
    (entry.url ? entry.url.length : 0) +
    (entry.requestBodyText ? entry.requestBodyText.length : 0) +
    (entry.responseBodyText ? entry.responseBodyText.length : 0)
  );
}

function isJsonObject(text) {
  if (!text) return false;
  try {
    const v = JSON.parse(text);
    return v !== null && typeof v === "object" && !Array.isArray(v);
  } catch (e) {
    return false;
  }
}

function parseJsonObject(text) {
  try {
    const v = JSON.parse(text);
    return v !== null && typeof v === "object" && !Array.isArray(v) ? v : null;
  } catch (e) {
    return null;
  }
}

async function saveState() {
  await chrome.storage.local.set({ [STORAGE_STATE]: state });
}

async function saveCapture() {
  await chrome.storage.local.set({ [STORAGE_CAPTURE]: capture });
}

/**
 * Aggregate raw entries into normalized endpoints. A path segment is treated
 * as a variable {placeholder} when it has multiple distinct observed values or
 * looks like an id/hex/digit token. Placeholders reuse {id}, {id_2}, ...
 * sample values (most common) are kept in pathParams.
 */
function buildView() {
  const groups = new Map();

  for (const entry of capture.entries) {
    let url;
    try {
      url = new URL(entry.url);
    } catch (e) {
      continue;
    }
    if (!/^https?:/.test(url.protocol)) continue;
    const key = `${entry.method}|${url.origin}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ pathname: url.pathname, entry });
  }

  const endpoints = new Map();

  for (const items of groups.values()) {
    const method = items[0].entry.method;
    const origin = new URL(items[0].entry.url).origin;
    const segLists = items.map((it) => it.pathname.split("/").filter((s) => s.length > 0));
    const maxSegs = Math.max(...segLists.map((s) => s.length));

    const varPositions = [];
    for (let i = 0; i < maxSegs; i++) {
      const values = segLists.map((s) => s[i]).filter((v) => v !== undefined);
      const distinct = new Set(values);
      const looksVariable =
        distinct.size > 1 ||
        values.some(
          (v) =>
            /^\d+$/.test(v) ||
            /^[0-9a-fA-F]{8,}$/.test(v) ||
            /^[a-zA-Z0-9]+\d+$/.test(v)
        );
      varPositions.push(looksVariable);
    }

    for (const { pathname, entry } of items) {
      const segs = pathname.split("/").filter((s) => s.length > 0);
      const patternSegs = [];
      const segParams = {};
      let placeholderIdx = 0;
      const width = Math.max(segs.length, varPositions.length);

      for (let i = 0; i < width; i++) {
        if (varPositions[i]) {
          const placeholder = placeholderIdx === 0 ? "id" : `id_${placeholderIdx + 1}`;
          placeholderIdx++;
          patternSegs.push(`{${placeholder}}`);
          segParams[placeholder] = segs[i] || null;
        } else {
          patternSegs.push(segs[i] || "");
        }
      }

      const path = "/" + patternSegs.join("/");
      const id = endpointId(method, origin, path);

      if (!endpoints.has(id)) {
        endpoints.set(id, {
          id,
          method,
          origin,
          path,
          pathParams: {},
          requestBody: null,
          observations: new Map(),
          authedSeen: false,
          firstTs: entry.ts || 0,
        });
      }
      const ep = endpoints.get(id);

      for (const [placeholder, value] of Object.entries(segParams)) {
        if (!value) continue;
        const tally = ep.pathParams[placeholder];
        if (!tally) {
          ep.pathParams[placeholder] = { [value]: 1 };
        } else {
          tally[value] = (tally[value] || 0) + 1;
        }
      }

      const obsKey = `${entry.status}|${entry.hadAuth ? 1 : 0}`;
      if (!ep.observations.has(obsKey)) {
        ep.observations.set(obsKey, {
          status: entry.status,
          authed: !!entry.hadAuth,
          count: 0,
          body: null,
        });
      }
      const obs = ep.observations.get(obsKey);
      obs.count += 1;
      if (obs.body === null && isJsonObject(entry.responseBodyText)) {
        obs.body = parseJsonObject(entry.responseBodyText);
      }

      if (ep.requestBody === null && isJsonObject(entry.requestBodyText)) {
        ep.requestBody = parseJsonObject(entry.requestBodyText);
      }
      if (entry.hadAuth) ep.authedSeen = true;
    }
  }

  const view = [];
  for (const ep of endpoints.values()) {
    const params = {};
    for (const [placeholder, tally] of Object.entries(ep.pathParams)) {
      params[placeholder] = Object.entries(tally).sort((a, b) => b[1] - a[1])[0][0];
    }
    ep.pathParams = params;
    ep.observations = [...ep.observations.values()].sort(
      (a, b) => a.status - b.status || Number(b.authed) - Number(a.authed)
    );
    view.push(ep);
  }
  view.sort((a, b) => a.firstTs - b.firstTs);
  return view;
}

function viewForPopup() {
  return buildView().map((ep) => ({
    id: ep.id,
    method: ep.method,
    origin: ep.origin,
    path: ep.path,
    pathParams: ep.pathParams,
    authedSeen: ep.authedSeen,
    hasRequestBody: !!ep.requestBody,
    observations: ep.observations,
    probe: capture.probes[ep.id] || null,
    included: !capture.excluded[ep.id],
  }));
}

function findEndpoint(id) {
  return buildView().find((ep) => ep.id === id) || null;
}

async function probeEndpoint(ep) {
  let path = ep.path.replace(/\{([^}]+)\}/g, (m, k) => ep.pathParams[k] || "probe");
  const init = {
    method: ep.method,
    credentials: "omit",
    cache: "no-store",
    redirect: "manual",
  };
  if (ep.requestBody) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(ep.requestBody);
  }
  try {
    const res = await fetch(ep.origin + path, init);
    return res.status;
  } catch (e) {
    return null;
  }
}

function buildExport() {
  const endpoints = buildView()
    .filter((ep) => !capture.excluded[ep.id])
    .map((ep) => {
      const out = {
        method: ep.method,
        path: ep.path,
        origin: ep.origin,
        request_body: ep.requestBody,
        path_params: ep.pathParams,
        observations: ep.observations.map((o) => ({
          status: o.status,
          authed: o.authed,
          count: o.count,
          body: o.body,
        })),
      };
      const probe = capture.probes[ep.id];
      if (probe) out.auth_probe = { status: probe };
      return out;
    });

  return {
    version: 1,
    recorder: "schemalock-recorder/0.1.0",
    recorded_at: capture.recordedAt,
    endpoints,
  };
}

async function handleRecord(entries) {
  if (!state.enabled || !Array.isArray(entries)) return { ok: true };

  let re = null;
  const pattern = (state.filterPattern || "").trim();
  if (pattern) {
    try {
      re = new RegExp(pattern, "i");
    } catch (e) {
      re = null;
    }
  }

  if (!capture.recordedAt && entries.length) {
    capture.recordedAt = new Date().toISOString();
  }

  for (const entry of entries) {
    if (!entry || typeof entry.url !== "string" || !entry.status) continue;
    if (re && !re.test(entry.url)) continue;
    if (capture.entries.length >= MAX_ENTRIES) break;
    const stored = {
      method: String(entry.method || "GET").toUpperCase(),
      url: entry.url,
      status: entry.status,
      hadAuth: !!entry.hadAuth,
      requestBodyText: entry.requestBodyText || null,
      responseBodyText: entry.responseBodyText || null,
      contentType: entry.contentType || null,
      ts: Date.now(),
    };
    capture.entries.push(stored);
    capture.bytes += entryBytes(stored);
  }

  // Bound total recorded bytes so a long recording session (or a chatty page)
  // cannot exhaust the extension's storage.
  while (capture.bytes > MAX_CAPTURE_BYTES && capture.entries.length > 1) {
    const dropped = capture.entries.shift();
    capture.bytes -= entryBytes(dropped);
  }

  await saveCapture();
  return { ok: true };
}

async function handle(message, sender) {
  switch (message.type) {
    case "record":
      return handleRecord(message.entries);

    case "state:get":
      return {
        enabled: state.enabled,
        captureSuccessBodies: state.captureSuccessBodies,
        filterPattern: state.filterPattern,
      };

    case "state:set": {
      if (typeof message.enabled === "boolean") state.enabled = message.enabled;
      if (typeof message.captureSuccessBodies === "boolean") {
        state.captureSuccessBodies = message.captureSuccessBodies;
      }
      if (typeof message.filterPattern === "string") state.filterPattern = message.filterPattern;
      await saveState();
      return {
        enabled: state.enabled,
        captureSuccessBodies: state.captureSuccessBodies,
        filterPattern: state.filterPattern,
      };
    }

    case "capture:view":
      return { endpoints: viewForPopup(), entryCount: capture.entries.length };

    case "capture:clear":
      capture = { entries: [], recordedAt: null, excluded: {}, probes: {}, bytes: 0 };
      await saveCapture();
      return { ok: true };

    case "capture:setIncluded":
      if (message.included) delete capture.excluded[message.id];
      else capture.excluded[message.id] = true;
      await saveCapture();
      return { ok: true };

    case "capture:export":
      return buildExport();

    case "auth:probe": {
      const ep = findEndpoint(message.id);
      if (!ep) return { status: null };
      const status = await probeEndpoint(ep);
      if (status) {
        capture.probes[ep.id] = status;
        await saveCapture();
      }
      return { status };
    }

    case "auth:probeAll": {
      const results = {};
      const endpoints = buildView().filter((ep) => {
        if (message.unsafe) return true;
        return ep.method === "GET" || ep.method === "HEAD";
      });
      for (const ep of endpoints) {
        const status = await probeEndpoint(ep);
        if (status) {
          capture.probes[ep.id] = status;
          results[ep.id] = status;
        }
      }
      await saveCapture();
      return { results };
    }

    default:
      return { error: `unknown message type: ${message.type}` };
  }
}

(async function main() {
  const data = await chrome.storage.local.get([STORAGE_STATE, STORAGE_CAPTURE]);
  state = { ...DEFAULT_STATE, ...(data[STORAGE_STATE] || {}) };
  capture = data[STORAGE_CAPTURE] || { entries: [], recordedAt: null, excluded: {}, probes: {}, bytes: 0 };
  if (typeof capture.bytes !== "number") {
    capture.bytes = capture.entries.reduce((sum, e) => sum + entryBytes(e), 0);
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    handle(message, sender)
      .then(sendResponse)
      .catch((e) => sendResponse({ error: String(e) }));
    return true;
  });
})();
