const $ = (id) => document.getElementById(id);

const elements = {
  recording: $("recording-toggle"),
  filter: $("filter-input"),
  successBodies: $("success-bodies"),
  summary: $("summary"),
  probeAll: $("probe-all"),
  clear: $("clear"),
  export: $("export"),
  endpoints: $("endpoints"),
};

let view = [];

function send(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (res) => resolve(res || {}));
  });
}

function chipClass(status) {
  if (status >= 500) return "err";
  if (status >= 400) return status === 401 || status === 403 ? "auth" : "err";
  return "ok";
}

function methodClass(method) {
  switch (method) {
    case "GET":
    case "HEAD":
      return "ok";
    case "POST":
    case "PUT":
    case "PATCH":
      return "auth";
    case "DELETE":
      return "err";
    default:
      return "";
  }
}

function render() {
  const included = view.filter((ep) => ep.included).length;
  elements.summary.textContent = `${included}/${view.length} endpoints${view.entryCount ? ` · ${view.entryCount} requests` : ""}`;

  if (!view.length) {
    elements.endpoints.innerHTML = `<div class="empty">No traffic captured yet.<br/>Flip on Recording, then drive your app.</div>`;
    elements.export.disabled = true;
    return;
  }
  elements.export.disabled = included === 0;

  const rows = view.map((ep) => {
    const chips = ep.observations
      .map(
        (o) =>
          `<span class="chip ${chipClass(o.status)}" title="${o.authed ? "authenticated" : "unauthenticated"}">${o.status}${o.authed ? "🔑" : ""}×${o.count}</span>`
      )
      .join("");

    let probeChip = "";
    if (ep.probe) {
      const probeStatus = ep.probe.status || ep.probe;
      probeChip = `<span class="chip probe" title="replayed without credentials">no-auth → ${probeStatus}</span>`;
    }

    return `<div class="endpoint">
      <input type="checkbox" class="include" data-id="${escapeHtml(ep.id)}" ${ep.included ? "checked" : ""} />
      <div>
        <div class="path-line">
          <span class="method ${methodClass(ep.method)}">${ep.method}</span>
          <span class="path">${escapeHtml(ep.path)}</span>
        </div>
        <div class="origin">${escapeHtml(ep.origin)}${ep.hasRequestBody ? " · has body" : ""}</div>
        <div class="obs-row">${chips}${probeChip}</div>
      </div>
      <div class="actions">
        <button class="probe" data-id="${escapeHtml(ep.id)}" title="Replay without credentials (may have side effects)">probe</button>
      </div>
    </div>`;
  }).join("");

  elements.endpoints.innerHTML = rows;

  document.querySelectorAll(".include").forEach((el) => {
    el.addEventListener("change", () => {
      send({ type: "capture:setIncluded", id: el.dataset.id, included: el.checked });
    });
  });
  document.querySelectorAll(".probe").forEach((el) => {
    el.addEventListener("click", async () => {
      const res = await send({ type: "auth:probe", id: el.dataset.id });
      if (res.status) await refresh();
    });
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

async function refresh() {
  const [state, data] = await Promise.all([send({ type: "state:get" }), send({ type: "capture:view" })]);
  elements.recording.checked = !!state.enabled;
  elements.successBodies.checked = !!state.captureSuccessBodies;
  if (document.activeElement !== elements.filter) {
    elements.filter.value = state.filterPattern || "";
  }
  view = data.endpoints || [];
  view.entryCount = data.entryCount || 0;
  render();
}

elements.recording.addEventListener("change", () => {
  send({ type: "state:set", enabled: elements.recording.checked });
});

elements.successBodies.addEventListener("change", () => {
  send({ type: "state:set", captureSuccessBodies: elements.successBodies.checked });
});

let filterTimer = null;
elements.filter.addEventListener("input", () => {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(() => {
    send({ type: "state:set", filterPattern: elements.filter.value });
  }, 250);
});

elements.probeAll.addEventListener("click", async () => {
  elements.probeAll.disabled = true;
  elements.probeAll.textContent = "Probing…";
  await send({ type: "auth:probeAll", unsafe: false });
  await refresh();
  elements.probeAll.disabled = false;
  elements.probeAll.textContent = "Probe GETs";
});

elements.clear.addEventListener("click", async () => {
  if (confirm("Clear all captured traffic?")) {
    await send({ type: "capture:clear" });
    await refresh();
  }
});

elements.export.addEventListener("click", async () => {
  const capture = await send({ type: "capture:export" });
  const blob = new Blob([JSON.stringify(capture, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "schemalock-capture.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

refresh();
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local" || !(changes.sl_state || changes.sl_capture)) return;
  refresh();
});
