/**
 * SchemaLock Recorder hook — runs in the MAIN world at document_start.
 *
 * Patches window.fetch and XMLHttpRequest so it can observe the page's own API
 * traffic (status codes, error envelopes, and whether the request carried auth
 * headers). It never stores token values — only a boolean "hadAuth" flag.
 *
 * The hook is passive: it only records while the extension's "recording" state
 * is on, which the isolated-world content script (recorder.js) forwards to us
 * as a window CustomEvent.
 */
(function () {
  if (window.__schemalockHookInstalled) return;
  window.__schemalockHookInstalled = true;

  const state = { enabled: false, captureSuccessBodies: false };

  window.addEventListener("schemalock:state", (e) => {
    if (!e.detail) return;
    state.enabled = !!e.detail.enabled;
    state.captureSuccessBodies = !!e.detail.captureSuccessBodies;
  });

  const MAX_BODY = 256 * 1024;
  const MAX_REQUEST_BODY = 64 * 1024;
  const AUTH_HEADERS = ["authorization", "x-api-key", "x-auth-token"];
  const BODY_METHODS = ["POST", "PUT", "PATCH"];

  function dispatch(entry) {
    if (!state.enabled) return;
    if (!/^https?:/.test(entry.url)) return;
    try {
      window.dispatchEvent(new CustomEvent("schemalock:record", { detail: entry }));
    } catch (e) {
      /* ignore */
    }
  }

  function hasAuthHeaders(headerMap, initHeaders) {
    if (headerMap) {
      for (const name of AUTH_HEADERS) {
        if (headerMap.get ? headerMap.get(name) : headerMap[name]) return true;
      }
    }
    if (initHeaders) {
      try {
        const h = initHeaders instanceof Headers ? initHeaders : new Headers(initHeaders);
        for (const name of AUTH_HEADERS) {
          if (h.get(name)) return true;
        }
      } catch (e) {
        /* ignore */
      }
    }
    return false;
  }

  /* ------------------------------ fetch ------------------------------ */

  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    let request;
    try {
      request = input instanceof Request ? input : new Request(input, init);
    } catch (e) {
      return origFetch.apply(this, arguments);
    }

    const method = (request.method || "GET").toUpperCase();
    const auth = hasAuthHeaders(request.headers, init && init.headers);

    const requestBodyPromise = BODY_METHODS.includes(method)
      ? request.clone().text().catch(() => null)
      : Promise.resolve(null);

    const responsePromise = origFetch.apply(this, arguments);

    responsePromise.then((response) => {
      if (response.status === 0) return response; // opaque (no-cors) response
      const wantResponse = response.status >= 400 || state.captureSuccessBodies;
      const responseBodyPromise = wantResponse
        ? response.clone().text().catch(() => null)
        : Promise.resolve(null);

      Promise.all([requestBodyPromise, responseBodyPromise]).then(
        ([requestBodyText, responseBodyText]) => {
          dispatch({
            method,
            url: request.url,
            status: response.status,
            hadAuth: auth,
            requestBodyText:
              requestBodyText && requestBodyText.length < MAX_REQUEST_BODY
                ? requestBodyText
                : null,
            responseBodyText:
              responseBodyText && responseBodyText.length < MAX_BODY ? responseBodyText : null,
            contentType: response.headers.get("content-type") || null,
          });
        }
      );
      return response;
    });

    return responsePromise;
  };

  /* ----------------------------- XHR ----------------------------- */

  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  const origSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;

  XMLHttpRequest.prototype.open = function (method, url) {
    this.__schemalock = {
      method: (method || "GET").toUpperCase(),
      url: String(url),
      reqHeaders: {},
    };
    return origOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
    if (this.__schemalock) {
      this.__schemalock.reqHeaders[String(name).toLowerCase()] = String(value);
    }
    return origSetRequestHeader.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function (body) {
    const meta = this.__schemalock;

    let requestBodyText = null;
    if (meta && typeof body === "string" && body.length < MAX_REQUEST_BODY) {
      requestBodyText = body;
    }

    const onDone = () => {
      if (!meta) return;
      const status = this.status;
      if (status === 0) return;

      const wantResponse = status >= 400 || state.captureSuccessBodies;
      let responseBodyText = null;
      if (wantResponse) {
        try {
          const t = this.responseText;
          if (t && t.length < MAX_BODY) responseBodyText = t;
        } catch (e) {
          /* ignore */
        }
      }

      let contentType = null;
      try {
        contentType = this.getResponseHeader("content-type");
      } catch (e) {
        /* ignore */
      }

      let url = meta.url;
      try {
        url = new URL(meta.url, window.location.href).href;
      } catch (e) {
        /* ignore */
      }

      const auth = Object.keys(meta.reqHeaders).some((h) => AUTH_HEADERS.includes(h));

      dispatch({
        method: meta.method,
        url,
        status,
        hadAuth: auth,
        requestBodyText,
        responseBodyText,
        contentType,
      });
    };

    this.addEventListener("loadend", onDone);
    return origSend.apply(this, arguments);
  };
})();
