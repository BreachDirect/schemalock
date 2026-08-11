# SchemaLock Recorder (browser extension)

A Chrome (Manifest V3) extension that watches a frontend's live API traffic and
exports a `capture.json` from which `schemalock scaffold` generates a
runnable `schemalock.yaml` — without hand-writing a single endpoint entry.

Instead of starting from an empty YAML, you:

1. Install the extension, open your app, and flip **Recording** on.
2. Drive the flows you care about (happy path, missing resources, expired
   tokens, invalid input, etc.).
3. Optionally **Probe** endpoints — the extension replays each captured
   request *without credentials* and records whether the route rejects it.
4. **Export capture.json**, then:

```bash
schemalock scaffold schemalock-capture.json --output schemalock.yaml
```

What gets inferred from the recording:

- **Endpoints** — method + path pattern, with variable segments normalized to
  `{placeholders}` (e.g. `/escrows/esc_123` and `/escrows/esc_999` both become
  `/escrows/{id}`) and sample `path_params` preserved.
- **Expected statuses** — the set of statuses observed per endpoint.
- **Error envelopes** — 4xx/5xx response bodies are clustered by top-level key
  shape into `standard` / `error_vN` envelopes with `required_fields` and
  `field_types`.
- **`auth_required`** — true when a 401/403 was observed, or when an auth probe
  (replay without credentials) was rejected with 401/403.
- **Request bodies** — the first JSON request body per endpoint is kept so the
  generated config can actually run.

## Install (Chrome / Edge / Chromium)

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top-right).
3. Click **Load unpacked** and select this `browser-extension/` directory.
4. Pin the **SchemaLock Recorder** icon (puzzle icon → pushpin).

Requires Chrome 111+ (the capture hook runs in the page's MAIN world).

## Record

1. Open the popup.
2. Flip **Recording** on. The hook is injected into every page at
   `document_start`; it intercepts `fetch` and `XMLHttpRequest`.
3. Optionally set a **URL filter** (regex) so only traffic matching
   `127\.0\.0\.1`, `myapi`, etc. is kept.
4. Drive your app. Error responses (4xx/5xx) are always captured; 2xx bodies are
   captured only when **Capture 2xx response bodies** is enabled.

Privacy notes: only a boolean "was this request authenticated?" flag is stored —
token values are never recorded. Response bodies are capped at 256 KB.

## Probe auth boundaries

An endpoint observed with credentials isn't proof it *requires* auth — the
backend could ignore the token. **Probe GETs** replays each captured
GET/HEAD request without credentials (extension host permissions bypass CORS)
and records the resulting status. A 401/403 means the route enforces auth;
a 2xx is flagged in `schemalock scaffold`'s notes as a likely auth-boundary gap.

Per-endpoint **probe** buttons work for any method, but replaying POST/PUT/DELETE
can create or mutate resources — use with care.

## Export & scaffold

**Export capture.json** downloads `schemalock-capture.json` containing only the
endpoints left checked. Then:

```bash
schemalock scaffold schemalock-capture.json --output schemalock.yaml
# review the generated contract, then run it:
schemalock test --config schemalock.yaml --base-url http://127.0.0.1:8000
    --auth-header "Authorization: Bearer <real-token>"
```

`scaffold` prints notes to stderr when the recording is ambiguous — e.g.
multiple origins, or a probe that came back 2xx (auth not enforced).

## Demo

The repo bundles a demo frontend against `examples/mock_server.py`:

```bash
uvicorn examples.mock_server:app --port 8000
```

Open `http://127.0.0.1:8000/demo`, turn Recording on, click the buttons (get /
404 / create / settle / delete-409 / GraphQL-422 / health), then export and
scaffold. Toggle the auth checkbox to also capture 401s.

## Capture format

`capture.json` is a small versioned JSON document (`version: 1`) that the
Python `schemalock scaffold` command parses. See `schemalock/scaffold.py` for
the exact schema (`method`, `path`, `origin`, `request_body`, `path_params`,
`observations[]`, `auth_probe`).
