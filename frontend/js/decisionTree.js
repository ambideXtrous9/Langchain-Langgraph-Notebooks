/**
 * RP360 // Regulatory Decision-Tree & Human-in-the-Loop Navigator
 * Connects to /interact (SSE), /ws/interact (WebSocket), /thread/{id}/state, and /delete_thread.
 */

import { api } from "./api.js";
import { CONFIG } from "./config.js";

class DecisionTreeController {
  constructor() {
    this.activeThreadId = localStorage.getItem(CONFIG.STORAGE_KEYS.LAST_THREAD_ID) || null;
    this.isStreaming = false;
    this.abortController = null;
    this.ws = null;
    this.useWebSocket = false;
    this.accumulatedText = "";
  }

  init() {
    this.bindEvents();
    if (this.activeThreadId) {
      this.updateThreadDisplay(this.activeThreadId);
    }
  }

  bindEvents() {
    const runBtn = document.getElementById("dt-run-btn");
    const resumeBtn = document.getElementById("dt-resume-btn");
    const inspectBtn = document.getElementById("dt-inspect-btn");
    const deleteThreadBtn = document.getElementById("dt-delete-thread-btn");
    const wsToggle = document.getElementById("dt-protocol-ws");
    const sseToggle = document.getElementById("dt-protocol-sse");
    const copyBtn = document.getElementById("dt-copy-btn");
    const clearBtn = document.getElementById("dt-clear-btn");

    if (runBtn) {
      runBtn.addEventListener("click", () => this.startExecution(false));
    }

    if (resumeBtn) {
      resumeBtn.addEventListener("click", () => this.resumeExecution());
    }

    if (inspectBtn) {
      inspectBtn.addEventListener("click", () => this.inspectThreadState());
    }

    if (deleteThreadBtn) {
      deleteThreadBtn.addEventListener("click", () => this.deleteActiveThread());
    }

    if (wsToggle && sseToggle) {
      wsToggle.addEventListener("change", (e) => { this.useWebSocket = e.target.checked; });
      sseToggle.addEventListener("change", (e) => { this.useWebSocket = !e.target.checked; });
    }

    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        if (this.accumulatedText) {
          navigator.clipboard.writeText(this.accumulatedText);
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "Regulatory guidance copied to clipboard.", type: "success" }
          }));
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", () => this.resetConsole());
    }

    // Quick preset chips
    const chips = document.querySelectorAll("[data-dt-preset]");
    chips.forEach(chip => {
      chip.addEventListener("click", () => {
        const query = chip.getAttribute("data-dt-preset");
        const input = document.getElementById("dt-user-input");
        if (input) {
          input.value = query;
          input.focus();
        }
      });
    });
  }

  getFormData() {
    const deviceClass = document.getElementById("dt-device-class")?.value || "Class II";
    const intendedUse = document.getElementById("dt-intended-use")?.value || "Clinical diagnostics";
    const predicateDevice = document.getElementById("dt-predicate-device")?.value || "";
    const isSamd = document.getElementById("dt-is-samd")?.checked || false;
    const useDeviceData = document.getElementById("dt-use-device-data")?.checked || false;
    const deviceSpecs = document.getElementById("dt-device-specs")?.value || "";
    const userInput = document.getElementById("dt-user-input")?.value || "";

    return {
      user_choices: {
        device_class: deviceClass,
        intended_use: intendedUse,
        predicate_device: predicateDevice,
        software_as_medical_device: isSamd,
      },
      user_input: userInput,
      useDeviceData: useDeviceData,
      userProvidedDeiveceData: deviceSpecs,
      thread_id: this.activeThreadId || undefined,
    };
  }

  setNodeState(nodeName, state) {
    // state: 'running' | 'completed' | 'interrupted' | 'idle'
    const el = document.getElementById(`node-dt-${nodeName}`);
    if (!el) return;

    el.classList.remove("running", "completed", "interrupted");
    if (state !== "idle") {
      el.classList.add(state);
    }
  }

  resetAllNodes() {
    const nodes = ["user_initpath", "classify_node", "device_summary", "knowledge_base", "reason_llm", "process_feedback"];
    nodes.forEach(n => this.setNodeState(n, "idle"));
  }

  resetConsole() {
    this.accumulatedText = "";
    const consoleBody = document.getElementById("dt-console-body");
    const previewBox = document.getElementById("dt-preview-box");
    if (consoleBody) consoleBody.innerHTML = '<span class="mono" style="color: #6e7681;">[Awaiting execution start...]</span>';
    if (previewBox) previewBox.innerHTML = '<p class="mono" style="color: var(--slate);">Synthesized regulatory recommendations will appear here...</p>';
    this.hideHitlBanner();
    this.resetAllNodes();
  }

  appendConsoleLog(hint, type = "info") {
    const consoleBody = document.getElementById("dt-console-body");
    if (!consoleBody) return;

    const time = new Date().toLocaleTimeString();
    const pillClass = type === "tool" ? "tool" : (type === "success" ? "success" : "");
    const div = document.createElement("div");
    div.innerHTML = `<div class="stream-event-pill ${pillClass}"><small style="opacity: 0.6;">${time}</small> ${hint}</div>`;
    consoleBody.appendChild(div);
    consoleBody.scrollTop = consoleBody.scrollHeight;
  }

  appendToken(token) {
    this.accumulatedText += token;
    const previewBox = document.getElementById("dt-preview-box");
    if (!previewBox) return;

    if (window.marked) {
      previewBox.innerHTML = window.marked.parse(this.accumulatedText);
    } else {
      previewBox.textContent = this.accumulatedText;
    }
  }

  showHitlBanner(promptText) {
    const banner = document.getElementById("dt-hitl-banner");
    const promptEl = document.getElementById("dt-hitl-prompt");
    if (banner) {
      banner.classList.add("is-active");
      if (promptEl && promptText) promptEl.textContent = promptText;
    }
    this.setNodeState("process_feedback", "interrupted");
    window.dispatchEvent(new CustomEvent("rp360:notify", {
      detail: { message: "Human-in-the-Loop interrupt: Regulatory review required.", type: "info" }
    }));
  }

  hideHitlBanner() {
    const banner = document.getElementById("dt-hitl-banner");
    if (banner) banner.classList.remove("is-active");
  }

  updateThreadDisplay(threadId) {
    this.activeThreadId = threadId;
    if (threadId) {
      localStorage.setItem(CONFIG.STORAGE_KEYS.LAST_THREAD_ID, threadId);
    } else {
      localStorage.removeItem(CONFIG.STORAGE_KEYS.LAST_THREAD_ID);
    }

    const displayEl = document.getElementById("dt-active-thread-id");
    const threadStatusEl = document.getElementById("dt-thread-status");
    if (displayEl) displayEl.textContent = threadId ? threadId.slice(0, 18) + "..." : "None (New Thread)";
    if (threadStatusEl) {
      threadStatusEl.style.display = threadId ? "inline-flex" : "none";
    }
  }

  /**
   * Start new graph execution or continue thread
   */
  async startExecution(isResume = false) {
    if (this.isStreaming) {
      if (this.abortController) this.abortController.abort();
      if (this.ws) this.ws.close();
      this.isStreaming = false;
      return;
    }

    const formData = this.getFormData();
    if (!formData.user_input && !isResume) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "Please enter a device description or regulatory question.", type: "error" }
      }));
      return;
    }

    this.isStreaming = true;
    this.resetAllNodes();
    this.hideHitlBanner();
    if (!isResume) {
      this.accumulatedText = "";
      const consoleBody = document.getElementById("dt-console-body");
      if (consoleBody) consoleBody.innerHTML = "";
    }

    const runBtn = document.getElementById("dt-run-btn");
    if (runBtn) {
      runBtn.innerHTML = `<span class="spin">⟳</span> Stop Execution`;
      runBtn.classList.remove("btn-primary");
      runBtn.classList.add("btn-alert");
    }

    if (this.useWebSocket) {
      this.executeViaWebSocket(formData, isResume);
    } else {
      this.executeViaSSE(formData);
    }
  }

  /**
   * Resume paused interrupt node with human input
   */
  async resumeExecution() {
    const feedbackInput = document.getElementById("dt-hitl-feedback");
    const feedbackText = feedbackInput ? feedbackInput.value.trim() : "";

    if (!feedbackText) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "Please provide feedback or type 'approve' to continue.", type: "error" }
      }));
      return;
    }

    const userInputField = document.getElementById("dt-user-input");
    if (userInputField) userInputField.value = feedbackText;
    if (feedbackInput) feedbackInput.value = "";

    this.appendConsoleLog(`Resuming graph with feedback: "${feedbackText}"`, "success");
    await this.startExecution(true);
  }

  /**
   * SSE Stream Execution Protocol
   */
  async executeViaSSE(formData) {
    this.abortController = new AbortController();

    this.appendConsoleLog("Initiating LangGraph SSE streaming connection...", "info");

    await api.streamSSE(CONFIG.ENDPOINTS.INTERACT, formData, {
      signal: this.abortController.signal,
      onEvent: (data) => {
        if (data.thread_id) {
          this.updateThreadDisplay(data.thread_id);
          this.appendConsoleLog(`Thread Checkpoint Attached: [${data.thread_id}]`, "info");
        }

        if (data.stage) {
          if (data.status === "started") {
            this.setNodeState(data.stage, "running");
          } else if (data.status === "completed") {
            this.setNodeState(data.stage, "completed");
          }
          if (data.hint) {
            this.appendConsoleLog(data.hint, data.status === "completed" ? "success" : "info");
          }
          if (data.stage === "process_feedback" && data.status === "started") {
            this.showHitlBanner(data.hint);
          }
        }

        if (data.event === "tool_start" && data.data) {
          this.appendConsoleLog(data.data, "tool");
        } else if (data.event === "tool_end" && data.data) {
          this.appendConsoleLog(data.data, "success");
        }

        if (data.response) {
          this.appendToken(data.response);
        }

        if (data.error) {
          this.appendConsoleLog(`Error: ${data.error}`, "tool");
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: `Graph execution error: ${data.error}`, type: "error" }
          }));
        }
      },
      onDone: () => {
        this.onStreamCompleted();
      },
      onError: (err) => {
        this.appendConsoleLog(`Stream disconnected: ${err.message}`, "tool");
        this.onStreamCompleted();
      }
    });
  }

  /**
   * WebSocket Execution Protocol
   */
  executeViaWebSocket(formData, isResume) {
    this.appendConsoleLog("Connecting to LangGraph Bidirectional WebSocket...", "info");

    const payload = isResume
      ? {
          action: "resume",
          thread_id: this.activeThreadId,
          user_input: formData.user_input,
          useDeviceData: formData.useDeviceData,
          userProvidedDeiveceData: formData.userProvidedDeiveceData,
        }
      : {
          action: "start",
          user_choices: formData.user_choices,
          user_input: formData.user_input,
          useDeviceData: formData.useDeviceData,
          userProvidedDeiveceData: formData.userProvidedDeiveceData,
        };

    this.ws = api.createWebSocket(CONFIG.ENDPOINTS.WS_INTERACT, {
      onOpen: () => {
        this.ws.send(JSON.stringify(payload));
      },
      onMessage: (msg) => {
        if (msg.type === "thread_id") {
          this.updateThreadDisplay(msg.thread_id);
          this.appendConsoleLog(`WebSocket Thread Bound: [${msg.thread_id}]`, "info");
        } else if (msg.type === "hint") {
          this.appendConsoleLog(msg.hint || msg.data, msg.status === "completed" ? "success" : "info");
          if (msg.stage) {
            this.setNodeState(msg.stage, msg.status || "running");
          }
        } else if (msg.type === "token") {
          this.appendToken(msg.content || msg.token || "");
        } else if (msg.type === "interrupt") {
          this.showHitlBanner(msg.message || "Human-in-the-Loop review required");
        } else if (msg.type === "complete") {
          this.appendConsoleLog("Graph execution complete.", "success");
          this.onStreamCompleted();
          if (this.ws) this.ws.close();
        } else if (msg.type === "error") {
          this.appendConsoleLog(`WebSocket Error: ${msg.message}`, "tool");
          this.onStreamCompleted();
        }
      },
      onError: (err) => {
        this.appendConsoleLog(`WebSocket connection error.`, "tool");
        this.onStreamCompleted();
      },
      onClose: () => {
        this.onStreamCompleted();
      }
    });
  }

  onStreamCompleted() {
    this.isStreaming = false;
    const runBtn = document.getElementById("dt-run-btn");
    if (runBtn) {
      runBtn.innerHTML = `Start Decision Pathway <svg class="ico ico-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"></path></svg>`;
      runBtn.classList.remove("btn-alert");
      runBtn.classList.add("btn-primary");
    }
  }

  /**
   * Inspect Checkpoint State for active thread
   */
  async inspectThreadState() {
    if (!this.activeThreadId) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "No active thread ID to inspect. Run a pathway first.", type: "error" }
      }));
      return;
    }

    try {
      const state = await api.request(CONFIG.ENDPOINTS.THREAD_STATE(this.activeThreadId));
      const modalBody = document.getElementById("thread-state-modal-body");
      if (modalBody) {
        modalBody.innerHTML = `
          <div class="field" style="margin-bottom: 14px;">
            <span class="mono">Thread ID</span>
            <strong class="mono" style="color: var(--brand); font-size: 13px;">${state.thread_id}</strong>
          </div>
          <div class="field" style="margin-bottom: 14px;">
            <span class="mono">Next Pending Node(s)</span>
            <div>${state.next_nodes?.length ? state.next_nodes.map(n => `<span class="tag brand">${n}</span>`).join(" ") : '<span class="tag clear">Execution Completed</span>'}</div>
          </div>
          <div class="field">
            <span class="mono">Stored State Snapshot</span>
            <pre class="stream-console" style="max-height: 260px;">${JSON.stringify(state.values, null, 2)}</pre>
          </div>
        `;
      }
      const modal = document.getElementById("thread-state-modal");
      if (modal) modal.classList.add("is-open");
    } catch (err) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: `Failed to inspect state: ${err.message}`, type: "error" }
      }));
    }
  }

  /**
   * Evicts thread checkpoint from PostgreSQL AsyncPostgresSaver
   */
  async deleteActiveThread() {
    if (!this.activeThreadId) return;

    if (!confirm(`Are you sure you want to delete checkpoints for thread ${this.activeThreadId}?`)) {
      return;
    }

    try {
      await api.request(CONFIG.ENDPOINTS.DELETE_THREAD, {
        method: "DELETE",
        body: { thread_id: this.activeThreadId },
      });
      const deletedId = this.activeThreadId;
      this.updateThreadDisplay(null);
      this.resetConsole();
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: `Thread checkpoint [${deletedId}] evicted.`, type: "success" }
      }));
    } catch (err) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: `Failed to delete thread: ${err.message}`, type: "error" }
      }));
    }
  }
}

export const decisionTree = new DecisionTreeController();
