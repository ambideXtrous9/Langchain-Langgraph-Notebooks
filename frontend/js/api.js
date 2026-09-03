/**
 * AgentSphere // API Client & Stream Connection Manager
 * Handles HTTP requests, OAuth2 Bearer Tokens, Server-Sent Events (SSE), and WebSockets.
 */

import { CONFIG, getApiBase } from "./config.js";

class ApiClient {
  constructor() {
    this.token = localStorage.getItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN) || null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN, token);
    } else {
      localStorage.removeItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
    }
  }

  getToken() {
    return this.token || localStorage.getItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
  }

  getHeaders(customHeaders = {}, includeAuth = true) {
    const headers = {
      "Content-Type": "application/json",
      ...customHeaders,
    };

    const token = this.getToken();
    if (includeAuth && token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return headers;
  }

  /**
   * Performs standard HTTP requests (GET, POST, DELETE, etc.)
   */
  async request(endpoint, options = {}) {
    const baseUrl = getApiBase();
    const url = `${baseUrl}${endpoint}`;
    const includeAuth = options.includeAuth !== false;

    const fetchOptions = {
      method: options.method || "GET",
      headers: this.getHeaders(options.headers || {}, includeAuth),
      ...options,
    };

    // If body is URLSearchParams or FormData, delete Content-Type to allow browser or form boundary
    if (options.body instanceof URLSearchParams || options.body instanceof FormData) {
      delete fetchOptions.headers["Content-Type"];
    } else if (options.body && typeof options.body === "object") {
      fetchOptions.body = JSON.stringify(options.body);
    }

    try {
      const response = await fetch(url, fetchOptions);

      // Handle 401 Unauthorized (Expired or Revoked Token)
      if (response.status === 401 && includeAuth) {
        window.dispatchEvent(new CustomEvent("agentsphere:auth_expired", { detail: { status: 401 } }));
      }

      // Handle non-JSON response types (like Mermaid PlainText)
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("text/plain") || contentType.includes("text/html")) {
        const text = await response.text();
        if (!response.ok) {
          throw new Error(text || `HTTP Error ${response.status}`);
        }
        return text;
      }

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        const errorMessage = data.detail || data.message || `Request failed with status ${response.status}`;
        throw new Error(typeof errorMessage === "string" ? errorMessage : JSON.stringify(errorMessage));
      }

      return data;
    } catch (err) {
      console.error(`[API Error] ${options.method || 'GET'} ${url}:`, err);
      throw err;
    }
  }

  /**
   * Consumes a Server-Sent Events (SSE) stream via standard POST/GET with ReadableStream
   * @param {string} endpoint - API route
   * @param {object} body - Request JSON payload
   * @param {function} onEvent - Callback when an SSE data payload is received
   * @param {function} onDone - Callback when stream completes or ends with [DONE]
   * @param {function} onError - Callback on failure
   */
  async streamSSE(endpoint, body, { onEvent, onDone, onError, signal }) {
    const baseUrl = getApiBase();
    const url = `${baseUrl}${endpoint}`;

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: this.getHeaders({
          "Accept": "text/event-stream",
          "Cache-Control": "no-cache",
        }),
        body: JSON.stringify(body),
        signal,
      });

      if (!response.ok) {
        let errDetail = `HTTP ${response.status}`;
        try {
          const errJson = await response.json();
          errDetail = errJson.detail || errJson.message || errDetail;
        } catch (e) {
          errDetail = await response.text();
        }
        throw new Error(errDetail);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); // keep trailing incomplete chunk

        for (const block of lines) {
          const trimmed = block.trim();
          if (!trimmed) continue;

          for (const line of trimmed.split("\n")) {
            if (line.startsWith("data: ")) {
              const rawData = line.slice(6).trim();
              if (rawData === "[DONE]") {
                if (onDone) onDone();
                return;
              }

              try {
                const parsed = JSON.parse(rawData);
                if (onEvent) onEvent(parsed);
              } catch (parseErr) {
                // If not JSON, pass as raw string
                if (onEvent) onEvent({ text: rawData });
              }
            }
          }
        }
      }

      if (onDone) onDone();
    } catch (err) {
      if (err.name === "AbortError") {
        console.log("[Stream Aborted by User]");
        if (onDone) onDone();
      } else {
        console.error("[Stream Error]:", err);
        if (onError) onError(err);
      }
    }
  }

  /**
   * Creates a WebSocket connection for bidirectional graph interaction
   */
  createWebSocket(endpoint, { onOpen, onMessage, onError, onClose }) {
    const baseUrl = getApiBase();
    const wsProto = baseUrl.startsWith("https") ? "wss:" : "ws:";
    const host = baseUrl.replace(/^https?:\/\//, "");
    const token = this.getToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
    const wsUrl = `${wsProto}//${host}${endpoint}${tokenParam}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = (evt) => {
      console.log(`[WS Connected] ${wsUrl}`);
      if (onOpen) onOpen(evt);
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (onMessage) onMessage(data);
      } catch (e) {
        if (onMessage) onMessage({ type: "raw", content: evt.data });
      }
    };

    ws.onerror = (err) => {
      console.error("[WS Error]:", err);
      if (onError) onError(err);
    };

    ws.onclose = (evt) => {
      console.log("[WS Closed]", evt);
      if (onClose) onClose(evt);
    };

    return ws;
  }
}

export const api = new ApiClient();
