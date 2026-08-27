/**
 * RP360 // Model Context Protocol (MCP) Multi-Agent Intelligence
 * Connects to /mcp/tools, /mcp/travel/stream (SSE), /mcp/travel/run, and /mcp/travel/mermaid.
 */

import { api } from "./api.js";
import { CONFIG } from "./config.js";

class MCPController {
  constructor() {
    this.isStreaming = false;
    this.abortController = null;
    this.accumulatedReport = "";
    this.discoveredTools = [];
  }

  init() {
    this.bindEvents();
    this.loadDiscoveredTools();
  }

  bindEvents() {
    const streamBtn = document.getElementById("mcp-stream-btn");
    const syncBtn = document.getElementById("mcp-sync-btn");
    const refreshToolsBtn = document.getElementById("mcp-refresh-tools-btn");
    const copyBtn = document.getElementById("mcp-copy-btn");
    const clearBtn = document.getElementById("mcp-clear-btn");

    if (streamBtn) {
      streamBtn.addEventListener("click", () => this.startTravelPlanning(true));
    }

    if (syncBtn) {
      syncBtn.addEventListener("click", () => this.startTravelPlanning(false));
    }

    if (refreshToolsBtn) {
      refreshToolsBtn.addEventListener("click", () => this.loadDiscoveredTools());
    }

    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        if (this.accumulatedReport) {
          navigator.clipboard.writeText(this.accumulatedReport);
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "Accommodation & itinerary guide copied.", type: "success" }
          }));
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", () => this.resetConsole());
    }

    // Query presets
    const presets = document.querySelectorAll("[data-mcp-preset]");
    presets.forEach(preset => {
      preset.addEventListener("click", () => {
        const query = preset.getAttribute("data-mcp-preset");
        const input = document.getElementById("mcp-query-input");
        if (input) {
          input.value = query;
          input.focus();
        }
      });
    });
  }

  async loadDiscoveredTools() {
    const registryContainer = document.getElementById("mcp-tools-registry");
    if (!registryContainer) return;

    registryContainer.innerHTML = '<div class="mono" style="color: var(--slate); padding: 12px;"><span class="spin">⟳</span> Querying active MCP stdio sessions...</div>';

    try {
      const data = await api.request(CONFIG.ENDPOINTS.MCP_TOOLS);
      const servers = data.servers || {};
      let html = "";

      for (const [serverName, sInfo] of Object.entries(servers)) {
        const isConnected = sInfo.connected !== false;
        const toolList = sInfo.tools || [];
        html += `
          <div class="mcp-server-card">
            <div class="mcp-server-head">
              <div>
                <span class="mono" style="font-size: 10px; color: var(--slate);">TRANSPORT: ${sInfo.transport || 'stdio'}</span>
                <h4 class="mcp-server-title">${serverName.toUpperCase()} MCP SERVER</h4>
              </div>
              <span class="tag ${isConnected ? 'clear' : 'alert'}">${isConnected ? 'ACTIVE' : 'OFFLINE'}</span>
            </div>
            <p style="font-size: 13.5px; color: var(--slate);">${sInfo.description || 'Native subprocess connection over standard I/O.'}</p>
            <div class="mcp-tools-list">
              ${toolList.map(t => `<span class="mcp-tool-pill">${typeof t === 'string' ? t : t.name || 'tool'}</span>`).join("")}
            </div>
          </div>
        `;
      }

      registryContainer.innerHTML = html || '<p class="mono" style="color: var(--slate);">No MCP servers registered.</p>';
    } catch (err) {
      registryContainer.innerHTML = `
        <div class="mcp-server-card" style="border-left: 3px solid var(--alert);">
          <div class="mcp-server-head">
            <h4 class="mcp-server-title">MCP DISCOVERY NOTICE</h4>
            <span class="tag alert">AUTH REQUIRED</span>
          </div>
          <p style="font-size: 13.5px; color: var(--slate);">Sign in or verify backend MCP subprocess to inspect live stdio tools.</p>
        </div>
      `;
    }
  }

  setAgentState(agentName, state) {
    // agentName: 'airbnbAgent' | 'weatherAgent' | 'tourAgent'
    // state: 'running' | 'completed' | 'idle'
    const box = document.getElementById(`agent-box-${agentName}`);
    if (!box) return;

    box.classList.remove("running", "completed");
    if (state !== "idle") {
      box.classList.add(state);
    }
  }

  resetAllAgents() {
    ["airbnbAgent", "weatherAgent", "tourAgent"].forEach(a => this.setAgentState(a, "idle"));
  }

  resetConsole() {
    this.accumulatedReport = "";
    const consoleBody = document.getElementById("mcp-console-body");
    const guideBox = document.getElementById("mcp-guide-box");
    if (consoleBody) consoleBody.innerHTML = '<span class="mono" style="color: #6e7681;">[Awaiting MCP multi-agent kickoff...]</span>';
    if (guideBox) guideBox.innerHTML = '<p class="mono" style="color: var(--slate);">Tour Guide synthesized recommendations and Airbnb listings will stream here...</p>';
    this.resetAllAgents();
  }

  appendConsoleLog(hint, type = "info") {
    const consoleBody = document.getElementById("mcp-console-body");
    if (!consoleBody) return;

    const time = new Date().toLocaleTimeString();
    const pillClass = type === "tool" ? "tool" : (type === "success" ? "success" : "");
    const div = document.createElement("div");
    div.innerHTML = `<div class="stream-event-pill ${pillClass}"><small style="opacity: 0.6;">${time}</small> ${hint}</div>`;
    consoleBody.appendChild(div);
    consoleBody.scrollTop = consoleBody.scrollHeight;
  }

  appendToken(token) {
    this.accumulatedReport += token;
    const guideBox = document.getElementById("mcp-guide-box");
    if (!guideBox) return;

    if (window.marked) {
      guideBox.innerHTML = window.marked.parse(this.accumulatedReport);
    } else {
      guideBox.textContent = this.accumulatedReport;
    }
  }

  async startTravelPlanning(stream = true) {
    if (this.isStreaming) {
      if (this.abortController) this.abortController.abort();
      this.isStreaming = false;
      this.onStreamCompleted();
      return;
    }

    const queryInput = document.getElementById("mcp-query-input");
    const topic = queryInput ? queryInput.value.trim() : "";

    if (!topic) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "Please enter accommodation criteria & destination.", type: "error" }
      }));
      return;
    }

    this.isStreaming = true;
    this.resetAllAgents();
    this.accumulatedReport = "";
    const consoleBody = document.getElementById("mcp-console-body");
    if (consoleBody) consoleBody.innerHTML = "";

    const streamBtn = document.getElementById("mcp-stream-btn");
    if (streamBtn) {
      streamBtn.innerHTML = `<span class="spin">⟳</span> Stop Stream`;
      streamBtn.classList.remove("btn-primary");
      streamBtn.classList.add("btn-alert");
    }

    if (stream) {
      await this.runStreamingTravel(topic);
    } else {
      await this.runSynchronousTravel(topic);
    }
  }

  async runStreamingTravel(topic) {
    this.abortController = new AbortController();
    this.appendConsoleLog(`Dispatching concurrent Airbnb & Weather agents for: "${topic}"...`, "info");

    await api.streamSSE(CONFIG.ENDPOINTS.MCP_TRAVEL_STREAM, { topic }, {
      signal: this.abortController.signal,
      onEvent: (data) => {
        if (data.agent) {
          if (data.event === "hint") {
            this.setAgentState(data.agent, "running");
            this.appendConsoleLog(data.data || `Agent [${data.agent}]: Processing...`, "info");
          } else if (data.event === "token") {
            this.setAgentState("tourAgent", "running");
            this.appendToken(data.data || "");
          }
        }

        if (data.event === "tool_start" && data.data) {
          this.appendConsoleLog(data.data, "tool");
        } else if (data.event === "tool_end" && data.data) {
          this.appendConsoleLog(data.data, "success");
        }

        if (data.event === "done") {
          ["airbnbAgent", "weatherAgent", "tourAgent"].forEach(a => this.setAgentState(a, "completed"));
          this.appendConsoleLog(data.data || "Travel planning complete.", "success");
        }

        if (data.event === "error" || data.error) {
          const errText = data.data || data.error;
          this.appendConsoleLog(`MCP Error: ${errText}`, "tool");
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: `MCP agent error: ${errText}`, type: "error" }
          }));
        }
      },
      onDone: () => {
        this.onStreamCompleted();
        window.dispatchEvent(new CustomEvent("rp360:notify", {
          detail: { message: "MCP accommodation & weather synthesis ready.", type: "success" }
        }));
      },
      onError: (err) => {
        this.appendConsoleLog(`Stream disconnected: ${err.message}`, "tool");
        this.onStreamCompleted();
      }
    });
  }

  async runSynchronousTravel(topic) {
    this.appendConsoleLog(`Executing synchronous multi-agent travel graph for: "${topic}"...`, "info");

    try {
      const response = await api.request(CONFIG.ENDPOINTS.MCP_TRAVEL_RUN, {
        method: "POST",
        body: { topic },
      });

      const finalPlan = response.final_plan || response.summary || "No travel plan generated.";
      this.appendToken(finalPlan);
      this.appendConsoleLog("Multi-agent travel synthesis complete.", "success");
      ["airbnbAgent", "weatherAgent", "tourAgent"].forEach(a => this.setAgentState(a, "completed"));

      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "Travel guide generated successfully.", type: "success" }
      }));
    } catch (err) {
      this.appendConsoleLog(`Execution failed: ${err.message}`, "tool");
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: `MCP travel failed: ${err.message}`, type: "error" }
      }));
    } finally {
      this.onStreamCompleted();
    }
  }

  onStreamCompleted() {
    this.isStreaming = false;
    const streamBtn = document.getElementById("mcp-stream-btn");
    if (streamBtn) {
      streamBtn.innerHTML = `Stream Multi-Agent Pipeline <svg class="ico ico-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"></path></svg>`;
      streamBtn.classList.remove("btn-alert");
      streamBtn.classList.add("btn-primary");
    }
  }
}

export const mcp = new MCPController();
