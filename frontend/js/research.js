/**
 * RP360 // Autonomous Parallel Multi-Critic Research Engine
 * Connects to /research/stream (SSE), /research/run, and /research/mermaid.
 */

import { api } from "./api.js";
import { CONFIG } from "./config.js";

class ResearchController {
  constructor() {
    this.isStreaming = false;
    this.abortController = null;
    this.accumulatedReport = "";
    this.activeTopic = "";
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    const streamBtn = document.getElementById("res-stream-btn");
    const syncBtn = document.getElementById("res-sync-btn");
    const copyBtn = document.getElementById("res-copy-btn");
    const downloadBtn = document.getElementById("res-download-btn");
    const clearBtn = document.getElementById("res-clear-btn");

    if (streamBtn) {
      streamBtn.addEventListener("click", () => this.startResearch(true));
    }

    if (syncBtn) {
      syncBtn.addEventListener("click", () => this.startResearch(false));
    }

    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        if (this.accumulatedReport) {
          navigator.clipboard.writeText(this.accumulatedReport);
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "Research publication copied to clipboard.", type: "success" }
          }));
        }
      });
    }

    if (downloadBtn) {
      downloadBtn.addEventListener("click", () => this.downloadReport());
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", () => this.resetConsole());
    }

    // Research template pills
    const templatePills = document.querySelectorAll("[data-res-template]");
    templatePills.forEach(pill => {
      pill.addEventListener("click", () => {
        const topic = pill.getAttribute("data-res-template");
        const input = document.getElementById("res-topic-input");
        if (input) {
          input.value = topic;
          input.focus();
        }
      });
    });
  }

  setStageState(stageName, state) {
    // state: 'running' | 'completed' | 'idle'
    const card = document.getElementById(`stage-res-${stageName}`);
    if (!card) return;

    card.classList.remove("running", "completed");
    if (state !== "idle") {
      card.classList.add(state);
    }
  }

  resetAllStages() {
    const stages = [
      "planner",
      "approver",
      "researcher_dispatcher",
      "researcher",
      "synthesizer",
      "fact_critic",
      "style_critic_1",
      "style_critic_2",
      "publisher",
    ];
    stages.forEach(s => this.setStageState(s, "idle"));
  }

  resetConsole() {
    this.accumulatedReport = "";
    const consoleBody = document.getElementById("res-console-body");
    const reportBox = document.getElementById("res-report-box");
    if (consoleBody) consoleBody.innerHTML = '<span class="mono" style="color: #6e7681;">[Awaiting research pipeline kickoff...]</span>';
    if (reportBox) reportBox.innerHTML = '<p class="mono" style="color: var(--slate);">Final synthesized & audited research report will render here in real-time...</p>';
    this.resetAllStages();
  }

  appendConsoleLog(hint, type = "info") {
    const consoleBody = document.getElementById("res-console-body");
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
    const reportBox = document.getElementById("res-report-box");
    if (!reportBox) return;

    if (window.marked) {
      reportBox.innerHTML = window.marked.parse(this.accumulatedReport);
    } else {
      reportBox.textContent = this.accumulatedReport;
    }
  }

  async startResearch(stream = true) {
    if (this.isStreaming) {
      if (this.abortController) this.abortController.abort();
      this.isStreaming = false;
      this.onStreamCompleted();
      return;
    }

    const topicInput = document.getElementById("res-topic-input");
    const topic = topicInput ? topicInput.value.trim() : "";

    if (!topic) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "Please enter a research topic or select a template.", type: "error" }
      }));
      return;
    }

    this.activeTopic = topic;
    this.isStreaming = true;
    this.resetAllStages();
    this.accumulatedReport = "";
    const consoleBody = document.getElementById("res-console-body");
    if (consoleBody) consoleBody.innerHTML = "";

    const streamBtn = document.getElementById("res-stream-btn");
    if (streamBtn) {
      streamBtn.innerHTML = `<span class="spin">⟳</span> Stop Stream`;
      streamBtn.classList.remove("btn-primary");
      streamBtn.classList.add("btn-alert");
    }

    if (stream) {
      await this.runStreamingResearch(topic);
    } else {
      await this.runSynchronousResearch(topic);
    }
  }

  async runStreamingResearch(topic) {
    this.abortController = new AbortController();
    this.appendConsoleLog(`Launching Parallel Multi-Critic Research for: "${topic}"...`, "info");

    await api.streamSSE(CONFIG.ENDPOINTS.RESEARCH_STREAM, { topic }, {
      signal: this.abortController.signal,
      onEvent: (data) => {
        if (data.thread_id) {
          this.appendConsoleLog(`Parallel Thread Checkpoint: [${data.thread_id}]`, "info");
        }

        if (data.stage) {
          if (data.status === "started") {
            this.setStageState(data.stage, "running");
          } else if (data.status === "completed") {
            this.setStageState(data.stage, "completed");
          }
          if (data.hint) {
            this.appendConsoleLog(data.hint, data.status === "completed" ? "success" : "info");
          }
        }

        if (data.event === "tool_start" && data.data) {
          this.appendConsoleLog(data.data, "tool");
        } else if (data.event === "tool_end" && data.data) {
          this.appendConsoleLog(data.data, "success");
        }

        if (data.token) {
          this.appendToken(data.token);
        }

        if (data.error) {
          this.appendConsoleLog(`Pipeline Error: ${data.error}`, "tool");
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: `Research pipeline error: ${data.error}`, type: "error" }
          }));
        }
      },
      onDone: () => {
        this.appendConsoleLog("Parallel Research Publication synthesized and audited.", "success");
        this.onStreamCompleted();
        window.dispatchEvent(new CustomEvent("rp360:notify", {
          detail: { message: "Autonomous research publication ready.", type: "success" }
        }));
      },
      onError: (err) => {
        this.appendConsoleLog(`Stream disconnected: ${err.message}`, "tool");
        this.onStreamCompleted();
      }
    });
  }

  async runSynchronousResearch(topic) {
    this.appendConsoleLog(`Executing synchronous parallel pipeline for: "${topic}"...`, "info");

    try {
      const response = await api.request(CONFIG.ENDPOINTS.RESEARCH_RUN, {
        method: "POST",
        body: { topic },
      });

      const finalOutput = response.final_output || response.draft || "No output generated.";
      this.appendToken(finalOutput);
      this.appendConsoleLog(`Synchronous execution completed. Retrieved ${response.research_notes_count || 0} live intelligence notes.`, "success");
      
      const stages = ["planner", "approver", "researcher_dispatcher", "researcher", "synthesizer", "fact_critic", "style_critic_1", "style_critic_2", "publisher"];
      stages.forEach(s => this.setStageState(s, "completed"));

      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "Research execution completed successfully.", type: "success" }
      }));
    } catch (err) {
      this.appendConsoleLog(`Execution failed: ${err.message}`, "tool");
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: `Research failed: ${err.message}`, type: "error" }
      }));
    } finally {
      this.onStreamCompleted();
    }
  }

  onStreamCompleted() {
    this.isStreaming = false;
    const streamBtn = document.getElementById("res-stream-btn");
    if (streamBtn) {
      streamBtn.innerHTML = `Stream Research Pipeline <svg class="ico ico-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"></path></svg>`;
      streamBtn.classList.remove("btn-alert");
      streamBtn.classList.add("btn-primary");
    }
  }

  downloadReport() {
    if (!this.accumulatedReport) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "No report content to download.", type: "error" }
      }));
      return;
    }

    const blob = new Blob([this.accumulatedReport], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const safeTopic = (this.activeTopic || "research_report").replace(/[^a-z0-9]/gi, "_").toLowerCase();
    a.href = url;
    a.download = `RP360_Research_${safeTopic}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

export const research = new ResearchController();
