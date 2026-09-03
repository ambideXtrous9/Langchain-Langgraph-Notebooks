/**
 * RP360 // ChatGPT-style Multi-Agent Conversation Controller
 * Handles conversation sessions, multi-agent dispatching, SSE/WebSocket streaming,
 * dynamic thinking accordions, and Human-in-the-Loop interrupt resolution.
 */

import { api } from "./api.js";
import { CONFIG } from "./config.js";
import { AGENTS } from "./agents.js";

class ChatPlatformController {
  constructor() {
    this.activeAgentId = "regulatory";
    this.activeSessionId = null;
    this.sessions = [];
    this.isStreaming = false;
    this.abortController = null;
    this.ws = null;
    this.activeThreadId = null;
    this._rafId = null;
    this._pendingDeleteSessionId = null;
  }

  init() {
    this.loadSessions();
    this.bindEvents();
    this.renderSidebarHistory();
    this.renderActiveAgentUI();

    if (this.sessions.length > 0) {
      this.switchSession(this.sessions[0].id);
    } else {
      this.createNewSession(this.activeAgentId);
    }
  }

  loadSessions() {
    try {
      const stored = localStorage.getItem("rp360_chat_sessions_v2");
      this.sessions = stored ? JSON.parse(stored) : [];
    } catch (e) {
      this.sessions = [];
    }
  }

  saveSessions() {
    localStorage.setItem("rp360_chat_sessions_v2", JSON.stringify(this.sessions));
    this.renderSidebarHistory();
  }

  getActiveSession() {
    return this.sessions.find(s => s.id === this.activeSessionId);
  }

  createNewSession(agentId = "regulatory") {
    const session = {
      id: "sess_" + Math.random().toString(36).substring(2, 9) + "_" + Date.now().toString(36),
      agentId: agentId,
      title: "New Conversation",
      createdAt: new Date().toISOString(),
      threadId: null,
      messages: [],
    };

    this.sessions.unshift(session);
    this.saveSessions();
    this.switchSession(session.id);
  }

  switchSession(sessionId) {
    this.activeSessionId = sessionId;
    const session = this.getActiveSession();
    if (!session) return;

    this.activeAgentId = session.agentId || "regulatory";
    this.activeThreadId = session.threadId || null;

    this.renderActiveAgentUI();
    this.renderSidebarHistory();
    this.renderMessages();
  }

  promptDeleteSession(sessionId, e) {
    if (e) e.stopPropagation();
    const session = this.sessions.find(s => s.id === sessionId);
    if (!session) return;

    this._pendingDeleteSessionId = sessionId;

    const modal = document.getElementById("delete-chat-modal");
    const titleEl = document.getElementById("delete-chat-title");

    if (titleEl) {
      titleEl.textContent = `"${session.title}"`;
    }

    if (modal) {
      modal.classList.add("is-open");
    }
  }

  async deleteSession(sessionId, e) {
    if (e) e.stopPropagation();
    const sessionToDelete = this.sessions.find(s => s.id === sessionId);

    // 1. Delete Thread Checkpoint from PostgreSQL checkpointer (LangGraph)
    if (sessionToDelete?.threadId) {
      try {
        await api.request(CONFIG.ENDPOINTS.DELETE_THREAD, {
          method: "DELETE",
          body: { thread_id: sessionToDelete.threadId },
        });
        console.log(`Deleted thread checkpoint from Postgres: ${sessionToDelete.threadId}`);
      } catch (err) {
        console.warn(`Could not delete thread checkpoint: ${err.message}`);
      }
    }

    // 2. Delete Chat History from PostgreSQL PostgresChatMessageHistory
    if (sessionToDelete?.id) {
      try {
        await api.request(CONFIG.ENDPOINTS.DELETE_SESSION, {
          method: "DELETE",
          body: { session_id: sessionToDelete.id },
        });
        console.log(`Deleted chat history from Postgres: ${sessionToDelete.id}`);
      } catch (err) {
        // Safe to ignore if session had no records
      }
    }

    this.sessions = this.sessions.filter(s => s.id !== sessionId);
    this.saveSessions();

    if (this.activeSessionId === sessionId) {
      if (this.sessions.length > 0) {
        this.switchSession(this.sessions[0].id);
      } else {
        this.createNewSession(this.activeAgentId);
      }
    }

    window.dispatchEvent(new CustomEvent("rp360:notify", {
      detail: { message: "Conversation & PostgreSQL checkpoints deleted.", type: "info" }
    }));
  }

  setAgent(agentId) {
    if (!AGENTS[agentId]) return;
    this.activeAgentId = agentId;
    
    const session = this.getActiveSession();
    if (session && session.messages.length === 0) {
      session.agentId = agentId;
      this.saveSessions();
    } else {
      this.createNewSession(agentId);
    }

    this.renderActiveAgentUI();
  }

  switchMCPMode(targetMode) {
    if (!AGENTS.mcp || !AGENTS.mcp.modes || !AGENTS.mcp.modes[targetMode]) return;

    AGENTS.mcp.activeMode = targetMode;
    localStorage.setItem("rp360_mcp_mode", targetMode);

    const cfg = AGENTS.mcp.currentModeConfig;

    // 1. Update text input with new mode default prompt & placeholder
    const textarea = document.getElementById("chat-input-textarea");
    const sendBtn = document.getElementById("chat-send-trigger");
    if (textarea) {
      textarea.value = cfg.defaultPrompt;
      textarea.placeholder = cfg.inputPlaceholder;
      textarea.style.height = "auto";
      textarea.style.height = Math.min(160, textarea.scrollHeight) + "px";
      if (sendBtn) sendBtn.disabled = false;
    }

    // 2. Update navbar select dropdown
    const badgeEl = document.getElementById("active-agent-badge");
    if (badgeEl && this.activeAgentId === "mcp") {
      badgeEl.textContent = "MCP";
    }

    const selectEl = document.getElementById("mcp-mode-select");
    const iconEl = document.getElementById("mcp-select-icon");
    const labelEl = document.getElementById("mcp-mode-label");

    if (selectEl) selectEl.value = targetMode;
    if (iconEl) iconEl.textContent = targetMode === "harry_potter" ? "⚡" : "🏨";
    if (labelEl) labelEl.textContent = targetMode === "harry_potter" ? "Harry Potter Lore QA" : "Airbnb Travel Search";

    document.querySelectorAll(".mcp-option").forEach(opt => {
      const optMode = opt.getAttribute("data-mcp-option");
      opt.classList.toggle("is-selected", optMode === targetMode);
    });

    // 3. Re-render empty state / suggestion cards if session has no messages
    const session = this.getActiveSession();
    if (!session || session.messages.length === 0) {
      this.renderEmptyState();
    }

    // 4. Re-render parameter bar chips
    this.renderParamChips(AGENTS.mcp);

    // 5. Update flowchart drawer if currently open
    const drawer = document.getElementById("flowchart-drawer");
    if (drawer && drawer.classList.contains("is-open")) {
      this.openFlowchartDrawer();
    }

    window.dispatchEvent(new CustomEvent("rp360:notify", {
      detail: {
        message: targetMode === "harry_potter"
          ? "Switched to Harry Potter Universe QA (Pinecone MCP)"
          : "Switched to Airbnb Travel & Lodging Search (OpenBNB MCP)",
        type: "success"
      }
    }));
  }

  renderActiveAgentUI() {
    const agent = AGENTS[this.activeAgentId] || AGENTS.regulatory;

    // Navbar dropdown
    const nameEl = document.getElementById("active-agent-name");
    const badgeEl = document.getElementById("active-agent-badge");
    const iconEl = document.getElementById("active-agent-icon");
    const mcpDropdown = document.getElementById("navbar-mcp-dropdown");

    if (nameEl) nameEl.textContent = agent.name;
    if (iconEl) iconEl.innerHTML = agent.icon;

    if (this.activeAgentId === "mcp") {
      const mode = agent.activeMode || "harry_potter";
      if (badgeEl) badgeEl.textContent = "MCP";
      if (mcpDropdown) {
        mcpDropdown.style.display = "inline-flex";
        const selectEl = document.getElementById("mcp-mode-select");
        const iconEl = document.getElementById("mcp-select-icon");
        const labelEl = document.getElementById("mcp-mode-label");
        if (selectEl) selectEl.value = mode;
        if (iconEl) iconEl.textContent = mode === "harry_potter" ? "⚡" : "🏨";
        if (labelEl) labelEl.textContent = mode === "harry_potter" ? "Harry Potter Lore QA" : "Airbnb Travel Search";

        document.querySelectorAll(".mcp-option").forEach(opt => {
          const optMode = opt.getAttribute("data-mcp-option");
          opt.classList.toggle("is-selected", optMode === mode);
        });
      }
    } else {
      if (badgeEl) badgeEl.innerHTML = agent.badge;
      if (mcpDropdown) mcpDropdown.style.display = "none";
    }

    // Configure Parameters Button: Only display/enable for agents that require parameter inputs (e.g. FDA Regulatory)
    const configBtn = document.getElementById("btn-agent-config");
    if (configBtn) {
      const hasConfigurableParams = Boolean(agent.hasParams || (agent.params && Object.keys(agent.params).length > 0));
      configBtn.style.display = hasConfigurableParams ? "inline-flex" : "none";
      if (hasConfigurableParams) {
        configBtn.title = `Configure ${agent.name} Parameters`;
      }
    }

    const configModal = document.getElementById("agent-config-modal");
    if (configModal && (!agent.hasParams && (!agent.params || Object.keys(agent.params).length === 0)) && configModal.classList.contains("is-open")) {
      configModal.classList.remove("is-open");
    }

    // Sidebar items active state
    document.querySelectorAll(".agent-nav-item").forEach(item => {
      const aId = item.getAttribute("data-agent-id");
      if (aId === this.activeAgentId) {
        item.classList.add("is-active");
      } else {
        item.classList.remove("is-active");
      }
    });

    // Dropdown items active state
    document.querySelectorAll(".agent-option").forEach(opt => {
      const aId = opt.getAttribute("data-agent-option");
      if (aId === this.activeAgentId) {
        opt.classList.add("is-selected");
      } else {
        opt.classList.remove("is-selected");
      }
    });

    // Update Textarea Placeholder & Default Prompt dynamically per Agent
    const textarea = document.getElementById("chat-input-textarea");
    const sendBtn = document.getElementById("chat-send-trigger");
    if (textarea) {
      textarea.placeholder = agent.inputPlaceholder || "Ask a question or enter a prompt...";
      if (agent.defaultPrompt && (!textarea.value.trim() || Object.values(AGENTS).some(a => a.defaultPrompt === textarea.value.trim() || (a.modes && Object.values(a.modes).some(m => m.defaultPrompt === textarea.value.trim()))))) {
        textarea.value = agent.defaultPrompt;
        textarea.style.height = "auto";
        textarea.style.height = Math.min(160, textarea.scrollHeight) + "px";
        if (sendBtn) sendBtn.disabled = false;
      }
    }

    // Update parameter chips in bottom bar
    this.renderParamChips(agent);

    // If session has no messages, re-render agent-specific welcome prompt cards
    const session = this.getActiveSession();
    if (!session || session.messages.length === 0) {
      this.renderEmptyState();
    }
  }

  renderParamChips(agent) {
    const container = document.getElementById("chat-params-container");
    if (!container) return;

    if (agent.id === "regulatory") {
      const p = AGENTS.regulatory?.params || {};
      const devClass = p.device_class ? p.device_class.split(" ")[0] + " " + (p.device_class.split(" ")[1] || "") : "Class II";
      const samdStatus = p.is_samd ? "SaMD: ON" : "SaMD: OFF";
      container.style.display = "flex";
      container.innerHTML = `
        <span class="param-pill is-active" id="chip-param-class" title="Device Class">${devClass}</span>
        <span class="param-pill is-active" id="chip-param-samd" title="Software as Medical Device">${samdStatus}</span>
        <span class="param-pill" id="chip-param-config" title="Open Agent Configuration Modal">⚙ Parameters</span>
      `;
      document.getElementById("chip-param-config")?.addEventListener("click", () => {
        const p = AGENTS.regulatory?.params || {};
        const devClassEl = document.getElementById("cfg-device-class");
        const predicateEl = document.getElementById("cfg-predicate");
        const samdEl = document.getElementById("cfg-samd");
        const specsEl = document.getElementById("cfg-specs");
        if (devClassEl && p.device_class) devClassEl.value = p.device_class;
        if (predicateEl) predicateEl.value = p.predicate_device || "";
        if (samdEl) samdEl.checked = Boolean(p.is_samd);
        if (specsEl) specsEl.value = p.device_specs || "";
        document.getElementById("agent-config-modal")?.classList.add("is-open");
      });
    } else if (agent.id === "research") {
      container.style.display = "flex";
      container.innerHTML = `
        <span class="param-pill is-active">9 Parallel Nodes</span>
        <span class="param-pill is-active">defer=True Join</span>
        <span class="param-pill is-active">Live DuckDuckGo</span>
      `;
    } else if (agent.id === "mcp") {
      const activeMode = agent.activeMode || "harry_potter";
      const cfg = agent.currentModeConfig || (agent.modes ? agent.modes[activeMode] : null);
      const pills = (cfg && cfg.pills) ? cfg.pills : ["Pinecone MCP", "OpenBNB MCP"];
      container.style.display = "flex";
      container.innerHTML = `
        ${pills.map(p => `<span class="param-pill is-active">${p}</span>`).join("")}
      `;
    } else if (agent.id === "sql") {
      container.style.display = "flex";
      container.innerHTML = `
        <span class="param-pill is-active">PostgreSQL DB</span>
        <span class="param-pill is-active">SQLDatabaseToolkit</span>
      `;
    } else {
      container.style.display = "none";
    }
  }

  renderSidebarHistory() {
    const list = document.getElementById("sidebar-history-list");
    if (!list) return;

    if (this.sessions.length === 0) {
      list.innerHTML = `<div style="padding: 12px; font-size: 13px; color: var(--slate);">No conversations yet.</div>`;
      return;
    }

    list.innerHTML = this.sessions.map(s => {
      const isActive = s.id === this.activeSessionId;
      const agent = AGENTS[s.agentId] || AGENTS.regulatory;
      return `
        <div class="history-item ${isActive ? 'is-active' : ''}" data-session-id="${s.id}">
          <div class="history-item-title" title="${s.title}">
            <span style="opacity: 0.7; font-size: 11px;">[${agent.name.split(" ")[0]}]</span> ${s.title}
          </div>
          <button type="button" class="history-item-delete" data-delete-session="${s.id}" title="Delete chat">&times;</button>
        </div>
      `;
    }).join("");

    // Bind click handlers
    list.querySelectorAll(".history-item").forEach(el => {
      el.addEventListener("click", () => {
        const id = el.getAttribute("data-session-id");
        this.switchSession(id);
      });
    });

    list.querySelectorAll("[data-delete-session]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const id = btn.getAttribute("data-delete-session");
        this.promptDeleteSession(id, e);
      });
    });
  }

  renderMessages() {
    const container = document.getElementById("chat-scroll-content");
    if (!container) return;

    const session = this.getActiveSession();
    if (!session || session.messages.length === 0) {
      this.renderEmptyState();
      return;
    }

    const agent = AGENTS[session.agentId] || AGENTS.regulatory;

    let html = "";
    session.messages.forEach((msg, idx) => {
      const isUser = msg.role === "user";
      if (isUser) {
        html += `
          <div class="message-row user-row">
            <div class="message-body">
              <div class="message-bubble">
                <div class="user-message-header">
                  <span class="user-tag">YOU</span>
                  <span class="mono" style="font-size: 10px; color: rgba(244, 245, 243, 0.6);">${msg.timestamp || ''}</span>
                </div>
                <div class="prose" style="color: var(--bone);">${this.formatContent(msg.content)}</div>
              </div>
            </div>
          </div>
        `;
      } else {
        const formatted = this.formatContent(msg.content);
        const stepsHtml = this.renderThinkingAccordion(msg.steps || [], idx, msg.isStreaming);
        const hitlHtml = msg.hitlPending ? this.renderHitlCard(msg.hitlPrompt, idx) : "";
        const tableHtml = msg.sqlTable ? this.renderSqlTable(msg.sqlTable, idx) : "";

        html += `
          <div class="message-row assistant-row" id="msg-row-${idx}">
            <div class="message-body">
              <div class="message-bubble">
                <div class="message-agent-header">
                  <div class="message-agent-identity">
                    <span class="message-avatar-inline agent-avatar">${agent.icon}</span>
                    <span class="message-agent-tag">${agent.name}</span>
                  </div>
                  <span class="mono" style="font-size: 10px; color: var(--slate);">${msg.timestamp || ''}</span>
                </div>

                ${stepsHtml}

                <div class="prose" id="msg-content-${idx}">
                  ${formatted || (msg.isStreaming ? '<span class="stream-cursor"></span>' : '')}
                </div>

                ${tableHtml}
                ${hitlHtml}

                <div class="message-actions">
                  <button type="button" class="message-action-btn" data-copy-msg="${idx}" title="Copy response">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
                    Copy
                  </button>
                  ${msg.threadId ? `<span class="mono" style="font-size: 10px; color: var(--slate); margin-left: auto;">THREAD: ${msg.threadId.slice(0, 12)}...</span>` : ''}
                </div>
              </div>
            </div>
          </div>
        `;
      }
    });

    container.innerHTML = html;
    this.bindMessageInteractions();
    this.scrollToBottom();
  }

  renderEmptyState() {
    const container = document.getElementById("chat-scroll-content");
    if (!container) return;

    const agent = AGENTS[this.activeAgentId] || AGENTS.regulatory;

    if (this.activeAgentId === "mcp") {
      const cfg = agent.currentModeConfig;

      container.innerHTML = `
        <div class="empty-state">
          <span class="empty-state-badge">${cfg.badge}</span>
          <h2 class="empty-state-title">${cfg.label}</h2>
          <p class="empty-state-desc">${cfg.description}</p>

          <div class="prompt-grid">
            ${cfg.suggestions.map((s, idx) => `
              <div class="prompt-card" data-prompt-index="${idx}">
                <div class="prompt-card-title">
                  <span>${s.title}</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
                </div>
                <p class="prompt-card-desc">${s.desc}</p>
              </div>
            `).join("")}
          </div>
        </div>
      `;

      // Bind suggestion cards click
      container.querySelectorAll(".prompt-card").forEach(card => {
        card.addEventListener("click", () => {
          const idx = parseInt(card.getAttribute("data-prompt-index"));
          const suggestion = cfg.suggestions[idx];
          if (suggestion) {
            this.sendMessage(suggestion.prompt);
          }
        });
      });
      return;
    }

    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-state-badge">${agent.badge}</span>
        <h2 class="empty-state-title">${agent.name}</h2>
        <p class="empty-state-desc">${agent.description}</p>

        <div class="prompt-grid">
          ${agent.suggestions.map((s, idx) => `
            <div class="prompt-card" data-prompt-index="${idx}">
              <div class="prompt-card-title">
                <span>${s.title}</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
              </div>
              <p class="prompt-card-desc">${s.desc}</p>
            </div>
          `).join("")}
        </div>
      </div>
    `;

    // Bind suggestion cards click
    container.querySelectorAll(".prompt-card").forEach(card => {
      card.addEventListener("click", () => {
        const idx = parseInt(card.getAttribute("data-prompt-index"));
        const suggestion = agent.suggestions[idx];
        if (suggestion) {
          this.sendMessage(suggestion.prompt);
        }
      });
    });
  }

  renderThinkingAccordion(steps, msgIdx, isStreaming = false) {
    const hasSteps = steps && steps.length > 0;
    const isVisible = hasSteps || isStreaming;
    return `
      <div class="thinking-accordion" id="thinking-acc-${msgIdx}" style="${isVisible ? 'display: block;' : 'display: none;'}">
        <div class="thinking-header" data-toggle-thinking="${msgIdx}">
          <span id="thinking-title-${msgIdx}">Thinking & Execution Process (${steps ? steps.length : 0} step${steps && steps.length === 1 ? '' : 's'}${isStreaming ? ' · running...' : ''})</span>
          <span id="thinking-chevron-${msgIdx}">&#x25BE;</span>
        </div>
        <div class="thinking-steps" id="thinking-steps-${msgIdx}">
          ${(steps || []).map(st => `
            <div class="thinking-step ${st.status === 'completed' ? 'completed' : 'active'}">
              <span class="thinking-step-icon">${st.status === 'completed' ? '✓' : '<span class="spin">⟳</span>'}</span>
              <span>${st.hint}</span>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  renderHitlCard(promptText, msgIdx) {
    return `
      <div class="chat-hitl-card" id="chat-hitl-${msgIdx}">
        <div class="chat-hitl-card-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8c5800" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          Human-in-the-Loop Interruption Active
        </div>
        <p style="font-size: 13.5px; color: #5a3e00; margin-bottom: 8px;">${promptText || 'Regulatory pathway generated. Review recommendations or provide modifications:'}</p>
        <div class="chat-hitl-actions">
          <input type="text" class="field-input" id="hitl-input-${msgIdx}" placeholder="e.g., 'Approve guidance', 'Include predicate K201842', or 'Refine for SaMD'" style="flex: 1; min-width: 220px; font-size: 13.5px; padding: 6px 10px;" />
          <button type="button" class="btn btn-primary btn-sm" data-resume-hitl="${msgIdx}">Resume Graph &rarr;</button>
        </div>
      </div>
    `;
  }

  renderSqlTable(tableData, msgIdx) {
    if (!tableData || !tableData.headers || tableData.headers.length === 0) return "";
    return `
      <div class="sql-table-wrap" style="margin: 12px 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--bone); border-bottom: 1px solid var(--rule);">
          <span class="mono" style="font-size: 11px;">RECORDS: ${tableData.rows.length} ROWS</span>
          <button type="button" class="btn btn-secondary btn-sm" data-export-csv="${msgIdx}" style="padding: 2px 8px; font-size: 11px;">CSV Export</button>
        </div>
        <table class="sql-table">
          <thead>
            <tr>${tableData.headers.map(h => `<th>${h}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${tableData.rows.map(r => `<tr>${r.map(c => `<td>${c || '&mdash;'}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  bindMessageInteractions() {
    // Copy buttons
    document.querySelectorAll("[data-copy-msg]").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-copy-msg"));
        const session = this.getActiveSession();
        if (session && session.messages[idx]) {
          navigator.clipboard.writeText(session.messages[idx].content);
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "Message copied to clipboard.", type: "success" }
          }));
        }
      });
    });

    // Thinking toggle
    document.querySelectorAll("[data-toggle-thinking]").forEach(header => {
      header.addEventListener("click", () => {
        const idx = header.getAttribute("data-toggle-thinking");
        const stepsEl = document.getElementById(`thinking-steps-${idx}`);
        if (stepsEl) {
          stepsEl.style.display = stepsEl.style.display === "none" ? "flex" : "none";
        }
      });
    });

    // HITL Resume buttons
    document.querySelectorAll("[data-resume-hitl]").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = btn.getAttribute("data-resume-hitl");
        const input = document.getElementById(`hitl-input-${idx}`);
        const text = input ? input.value.trim() : "";
        if (!text) {
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "Please enter feedback or type 'approve' to resume.", type: "error" }
          }));
          return;
        }
        this.resumeHITL(text, idx);
      });
    });

    // CSV Export buttons
    document.querySelectorAll("[data-export-csv]").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-export-csv"));
        const session = this.getActiveSession();
        if (session && session.messages[idx]?.sqlTable) {
          this.exportTableToCSV(session.messages[idx].sqlTable);
        }
      });
    });
  }

  formatContent(text) {
    if (!text) return "";
    if (window.marked) {
      return window.marked.parse(text);
    }
    return `<p>${text}</p>`;
  }

  scrollToBottom() {
    const scrollContainer = document.querySelector(".chat-scroll-container");
    if (scrollContainer) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
  }

  bindEvents() {
    // New Chat Button
    document.getElementById("btn-new-chat")?.addEventListener("click", () => {
      this.createNewSession(this.activeAgentId);
    });

    // Sidebar Agent Switcher
    document.querySelectorAll(".agent-nav-item").forEach(item => {
      item.addEventListener("click", () => {
        const aId = item.getAttribute("data-agent-id");
        this.setAgent(aId);
      });
    });

    // Dropdown Agent Switcher
    const dropdownBtn = document.getElementById("agent-dropdown-trigger");
    const dropdownMenu = document.getElementById("agent-dropdown-menu");
    const mcpDropdownBtn = document.getElementById("mcp-dropdown-trigger");
    const mcpDropdownMenu = document.getElementById("mcp-dropdown-menu");

    if (dropdownBtn && dropdownMenu) {
      dropdownBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (mcpDropdownMenu) mcpDropdownMenu.classList.remove("is-open");
        dropdownMenu.classList.toggle("is-open");
      });

      document.querySelectorAll(".agent-option").forEach(opt => {
        opt.addEventListener("click", () => {
          const aId = opt.getAttribute("data-agent-option");
          this.setAgent(aId);
          dropdownMenu.classList.remove("is-open");
        });
      });
    }

    // Top Navbar MCP Mode Custom Dropdown Selector
    if (mcpDropdownBtn && mcpDropdownMenu) {
      mcpDropdownBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (dropdownMenu) dropdownMenu.classList.remove("is-open");
        mcpDropdownMenu.classList.toggle("is-open");
      });

      document.querySelectorAll(".mcp-option").forEach(opt => {
        opt.addEventListener("click", (e) => {
          e.stopPropagation();
          const targetMode = opt.getAttribute("data-mcp-option");
          this.switchMCPMode(targetMode);
          mcpDropdownMenu.classList.remove("is-open");
        });
      });
    }

    // Close any open navbar dropdowns on outside click
    document.addEventListener("click", () => {
      if (dropdownMenu) dropdownMenu.classList.remove("is-open");
      if (mcpDropdownMenu) mcpDropdownMenu.classList.remove("is-open");
    });

    const mcpSelect = document.getElementById("mcp-mode-select");
    if (mcpSelect) {
      mcpSelect.addEventListener("change", (e) => {
        this.switchMCPMode(e.target.value);
      });
    }

    // Sidebar Collapse Toggle
    const sidebarToggle = document.getElementById("sidebar-toggle-btn");
    const sidebar = document.querySelector(".sidebar");
    if (sidebarToggle && sidebar) {
      sidebarToggle.addEventListener("click", () => {
        sidebar.classList.toggle("is-collapsed");
      });
    }

    // Chat Textarea & Send Button
    const textarea = document.getElementById("chat-input-textarea");
    const sendBtn = document.getElementById("chat-send-trigger");

    if (textarea && sendBtn) {
      textarea.addEventListener("input", () => {
        textarea.style.height = "auto";
        textarea.style.height = Math.min(160, textarea.scrollHeight) + "px";
        sendBtn.disabled = !textarea.value.trim() && !this.isStreaming;
      });

      textarea.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          if (!sendBtn.disabled) {
            this.handleSendClick();
          }
        }
      });

      sendBtn.addEventListener("click", () => this.handleSendClick());
    }

    // Flowchart Drawer Button
    document.getElementById("btn-view-flowchart")?.addEventListener("click", () => {
      this.openFlowchartDrawer();
    });

    document.getElementById("drawer-close-btn")?.addEventListener("click", () => {
      document.getElementById("flowchart-drawer")?.classList.remove("is-open");
    });

    // Delete Chat Confirmation Modal Confirm Action
    document.getElementById("delete-chat-confirm-btn")?.addEventListener("click", async () => {
      if (this._pendingDeleteSessionId) {
        const idToDelete = this._pendingDeleteSessionId;
        this._pendingDeleteSessionId = null;
        document.getElementById("delete-chat-modal")?.classList.remove("is-open");
        await this.deleteSession(idToDelete);
      }
    });
  }

  handleSendClick() {
    if (this.isStreaming) {
      this.stopStreaming();
      return;
    }

    const textarea = document.getElementById("chat-input-textarea");
    const text = textarea ? textarea.value.trim() : "";
    if (!text) return;

    textarea.value = "";
    textarea.style.height = "auto";
    this.sendMessage(text);
  }

  stopStreaming() {
    if (this.abortController) {
      this.abortController.abort();
    }
    if (this.ws) {
      this.ws.close();
    }
    this.isStreaming = false;
    this.updateSendButtonState();
  }

  updateSendButtonState() {
    const sendBtn = document.getElementById("chat-send-trigger");
    const textarea = document.getElementById("chat-input-textarea");

    if (sendBtn) {
      if (this.isStreaming) {
        sendBtn.innerHTML = `■`;
        sendBtn.classList.add("is-streaming");
        sendBtn.disabled = false;
        sendBtn.title = "Stop generating";
      } else {
        sendBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>`;
        sendBtn.classList.remove("is-streaming");
        sendBtn.disabled = textarea ? !textarea.value.trim() : true;
        sendBtn.title = "Send message (Enter)";
      }
    }
  }

  async sendMessage(userText) {
    const session = this.getActiveSession();
    if (!session) return;

    // First message sets the title
    if (session.messages.length === 0) {
      session.title = userText.length > 36 ? userText.slice(0, 36) + "..." : userText;
      this.saveSessions();
    }

    // 1. Push user message
    session.messages.push({
      role: "user",
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });

    // 2. Prepare assistant placeholder message
    const assistantMsgIndex = session.messages.length;
    session.messages.push({
      role: "assistant",
      content: "",
      steps: [],
      hitlPending: false,
      isStreaming: true,
      threadId: this.activeThreadId,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });

    this.renderMessages();
    this.isStreaming = true;
    this.updateSendButtonState();

    // 3. Dispatch to appropriate Agent
    try {
      if (this.activeAgentId === "regulatory") {
        await this.streamRegulatoryAgent(userText, assistantMsgIndex);
      } else if (this.activeAgentId === "research") {
        await this.streamResearchAgent(userText, assistantMsgIndex);
      } else if (this.activeAgentId === "mcp") {
        await this.streamMCPAgent(userText, assistantMsgIndex);
      } else if (this.activeAgentId === "sql") {
        await this.executeSQLAgent(userText, assistantMsgIndex);
      } else {
        await this.executeGeneralChat(userText, assistantMsgIndex);
      }
    } catch (err) {
      const msg = session.messages[assistantMsgIndex];
      if (msg) {
        msg.content += `\n\n**Error during execution:** ${err.message}`;
        msg.isStreaming = false;
      }
      this.renderMessages();
    } finally {
      this.isStreaming = false;
      const msg = session.messages[assistantMsgIndex];
      if (msg) msg.isStreaming = false;
      this.saveSessions();
      this.updateSendButtonState();
    }
  }

  /**
   * Resume Regulatory HITL from within chat bubble
   */
  async resumeHITL(feedbackText, msgIdx) {
    const session = this.getActiveSession();
    if (!session) return;

    // Push feedback as user reply
    session.messages.push({
      role: "user",
      content: feedbackText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });

    // Dismiss previous HITL prompt
    const prevMsg = session.messages[msgIdx];
    if (prevMsg) prevMsg.hitlPending = false;

    // New assistant response placeholder
    const newIdx = session.messages.length;
    session.messages.push({
      role: "assistant",
      content: "",
      steps: [{ hint: `Resuming graph with human feedback: "${feedbackText}"`, status: 'completed' }],
      hitlPending: false,
      isStreaming: true,
      threadId: this.activeThreadId,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });

    this.renderMessages();
    this.isStreaming = true;
    this.updateSendButtonState();

    try {
      await this.streamRegulatoryAgent(feedbackText, newIdx, true);
    } catch (err) {
      session.messages[newIdx].content += `\n\n**Resume Error:** ${err.message}`;
    } finally {
      this.isStreaming = false;
      session.messages[newIdx].isStreaming = false;
      this.saveSessions();
      this.updateSendButtonState();
    }
  }

  // --------------------------------------------------------------------------
  // Agent Stream Handlers
  // --------------------------------------------------------------------------

  async streamRegulatoryAgent(userText, msgIdx, isResume = false) {
    this.abortController = new AbortController();
    const session = this.getActiveSession();
    const msg = session.messages[msgIdx];

    const p = AGENTS.regulatory?.params || {};
    const payload = {
      user_choices: {
        device_class: p.device_class || "Class II (510k Premarket Notification)",
        intended_use: p.intended_use || "Clinical monitoring",
        predicate_device: p.predicate_device || "",
        software_as_medical_device: p.is_samd !== undefined ? p.is_samd : true,
      },
      user_input: userText,
      useDeviceData: Boolean(p.device_specs),
      user_provided_device_data: p.device_specs || "",
      userProvidedDeiveceData: p.device_specs || "",
      thread_id: this.activeThreadId || undefined,
    };

    await api.streamSSE(CONFIG.ENDPOINTS.INTERACT, payload, {
      signal: this.abortController.signal,
      onEvent: (data) => {
        if (data.thread_id) {
          this.activeThreadId = data.thread_id;
          session.threadId = data.thread_id;
          msg.threadId = data.thread_id;
        }

        if (data.stage && data.hint) {
          msg.steps.push({
            stage: data.stage,
            hint: data.hint,
            status: data.status || 'running'
          });
          if (data.stage === "process_feedback" && data.status === "started") {
            msg.hitlPending = true;
            msg.hitlPrompt = data.hint;
          }
        }

        if (data.event === "tool_start" && data.data) {
          msg.steps.push({ hint: data.data, status: 'running' });
        } else if (data.event === "tool_end" && data.data) {
          msg.steps.push({ hint: data.data, status: 'completed' });
        }

        if (data.response) {
          msg.content += data.response;
        }

        this.scheduleLiveMessageUpdate(msgIdx);
      },
      onDone: () => {
        if (this._rafId) {
          cancelAnimationFrame(this._rafId);
          this._rafId = null;
        }
        msg.isStreaming = false;
        this.renderMessages();
      },
      onError: (err) => {
        if (this._rafId) {
          cancelAnimationFrame(this._rafId);
          this._rafId = null;
        }
        msg.content += `\n\n[Connection Error: ${err.message}]`;
        msg.isStreaming = false;
        this.renderMessages();
      }
    });
  }

  async streamResearchAgent(topic, msgIdx) {
    this.abortController = new AbortController();
    const session = this.getActiveSession();
    const msg = session.messages[msgIdx];

    await api.streamSSE(CONFIG.ENDPOINTS.RESEARCH_STREAM, { topic }, {
      signal: this.abortController.signal,
      onEvent: (data) => {
        if (data.thread_id) {
          this.activeThreadId = data.thread_id;
          session.threadId = data.thread_id;
          msg.threadId = data.thread_id;
        }

        if (data.stage && data.hint) {
          msg.steps.push({
            stage: data.stage,
            hint: data.hint,
            status: data.status || 'running'
          });
        }

        if (data.event === "tool_start" && data.data) {
          msg.steps.push({ hint: data.data, status: 'running' });
        } else if (data.event === "tool_end" && data.data) {
          msg.steps.push({ hint: data.data, status: 'completed' });
        }

        if (data.token) {
          msg.content += data.token;
        }

        this.scheduleLiveMessageUpdate(msgIdx);
      },
      onDone: () => {
        if (this._rafId) {
          cancelAnimationFrame(this._rafId);
          this._rafId = null;
        }
        msg.isStreaming = false;
        this.renderMessages();
      },
      onError: (err) => {
        if (this._rafId) {
          cancelAnimationFrame(this._rafId);
          this._rafId = null;
        }
        msg.content += `\n\n[Stream Error: ${err.message}]`;
        msg.isStreaming = false;
        this.renderMessages();
      }
    });
  }

  async streamMCPAgent(topic, msgIdx) {
    this.abortController = new AbortController();
    const session = this.getActiveSession();
    const msg = session.messages[msgIdx];
    const mode = AGENTS.mcp.activeMode || "harry_potter";

    await api.streamSSE(CONFIG.ENDPOINTS.MCP_TRAVEL_STREAM, { topic, mode }, {
      signal: this.abortController.signal,
      onEvent: (data) => {
        if (data.event === "hint" && data.data) {
          msg.steps.push({ hint: data.data, status: 'running' });
        } else if (data.event === "tool_start" && data.data) {
          msg.steps.push({ hint: data.data, status: 'running' });
        } else if (data.event === "tool_end" && data.data) {
          msg.steps.push({ hint: data.data, status: 'completed' });
        } else if (data.event === "token" && data.data) {
          msg.content += data.data;
        } else if (data.event === "done") {
          msg.steps.push({ hint: data.data || "Multi-agent synthesis complete", status: 'completed' });
        }

        this.scheduleLiveMessageUpdate(msgIdx);
      },
      onDone: () => {
        if (this._rafId) {
          cancelAnimationFrame(this._rafId);
          this._rafId = null;
        }
        msg.isStreaming = false;
        this.renderMessages();
      },
      onError: (err) => {
        if (this._rafId) {
          cancelAnimationFrame(this._rafId);
          this._rafId = null;
        }
        msg.content += `\n\n[MCP Stream Error: ${err.message}]`;
        msg.isStreaming = false;
        this.renderMessages();
      }
    });
  }

  async executeSQLAgent(query, msgIdx) {
    const session = this.getActiveSession();
    const msg = session.messages[msgIdx];

    msg.steps.push({ hint: "Analyzing schema and generating SQL query...", status: 'running' });
    this.renderMessages();

    const data = await api.request(CONFIG.ENDPOINTS.SQL_QUERY, {
      method: "POST",
      body: { query },
    });

    msg.steps.push({ hint: "SQL query executed against PostgreSQL database", status: 'completed' });
    
    let content = `${data.final_answer || 'Query executed successfully.'}\n\n`;
    if (data.sql_query) {
      content += `\`\`\`sql\n${data.sql_query}\n\`\`\``;
    }
    msg.content = content;

    // Parse tabular result
    if (data.table_result && typeof data.table_result === "string" && data.table_result.includes("|")) {
      const lines = data.table_result.trim().split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("+-") && !l.startsWith("|--") && !l.startsWith("|-"));
      if (lines.length > 0) {
        const headers = lines[0].split("|").map(h => h.trim()).filter(h => h);
        const rows = lines.slice(1).filter(l => !l.match(/^\|?\s*[-:]+[-| :]*$/)).map(row => {
          return row.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length || !row.startsWith("|"));
        });
        msg.sqlTable = { headers, rows };
      }
    }

    msg.isStreaming = false;
    this.renderMessages();
  }

  async executeGeneralChat(userText, msgIdx) {
    const session = this.getActiveSession();
    const msg = session.messages[msgIdx];

    msg.steps.push({ hint: "Retrieving conversation context from PostgreSQL memory...", status: 'running' });
    this.renderMessages();

    const data = await api.request(CONFIG.ENDPOINTS.GENERIC_CHAT, {
      method: "POST",
      body: {
        user_input: userText,
        session_id: session.id,
      },
    });

    msg.steps.push({ hint: "Context memory updated", status: 'completed' });
    msg.content = data.response || "No response received.";
    msg.isStreaming = false;
    this.renderMessages();
  }

  scheduleLiveMessageUpdate(msgIdx) {
    if (this._rafId) return;
    this._rafId = requestAnimationFrame(() => {
      this._rafId = null;
      this.updateLiveMessageDOM(msgIdx);
    });
  }

  updateLiveMessageDOM(msgIdx) {
    const session = this.getActiveSession();
    if (!session || !session.messages[msgIdx]) return;

    const msg = session.messages[msgIdx];
    const contentEl = document.getElementById(`msg-content-${msgIdx}`);
    if (contentEl) {
      contentEl.innerHTML = this.formatContent(msg.content) + (msg.isStreaming ? '<span class="stream-cursor"></span>' : '');
    }

    const accEl = document.getElementById(`thinking-acc-${msgIdx}`);
    const stepsEl = document.getElementById(`thinking-steps-${msgIdx}`);
    const titleEl = document.getElementById(`thinking-title-${msgIdx}`);

    if (accEl && stepsEl) {
      if (msg.steps && msg.steps.length > 0) {
        accEl.style.display = "block";
        if (titleEl) {
          titleEl.textContent = `Thinking & Execution Process (${msg.steps.length} step${msg.steps.length === 1 ? '' : 's'}${msg.isStreaming ? ' · running...' : ''})`;
        }
        stepsEl.innerHTML = msg.steps.map(st => `
          <div class="thinking-step ${st.status === 'completed' ? 'completed' : 'active'}">
            <span class="thinking-step-icon">${st.status === 'completed' ? '✓' : '<span class="spin">⟳</span>'}</span>
            <span>${st.hint}</span>
          </div>
        `).join("");
      } else if (msg.isStreaming) {
        accEl.style.display = "block";
        if (titleEl) {
          titleEl.textContent = `Thinking & Execution Process (Running...)`;
        }
        stepsEl.innerHTML = `
          <div class="thinking-step active">
            <span class="thinking-step-icon"><span class="spin">⟳</span></span>
            <span>Initiating agent execution pipeline...</span>
          </div>
        `;
      }
    }

    // Dynamic HITL card injection if pending
    if (msg.hitlPending) {
      const hitlCard = document.getElementById(`chat-hitl-${msgIdx}`);
      if (!hitlCard) {
        const bubble = document.querySelector(`#msg-row-${msgIdx} .message-bubble`);
        if (bubble) {
          const div = document.createElement("div");
          div.innerHTML = this.renderHitlCard(msg.hitlPrompt, msgIdx);
          const actionsBar = bubble.querySelector(".message-actions");
          if (actionsBar) {
            bubble.insertBefore(div.firstElementChild, actionsBar);
          } else {
            bubble.appendChild(div.firstElementChild);
          }
          this.bindMessageInteractions();
        }
      }
    }

    this.smoothScrollToBottom();
  }

  smoothScrollToBottom() {
    const scrollContainer = document.querySelector(".chat-scroll-container");
    if (!scrollContainer) return;

    // Only scroll if the user was already near bottom to prevent scroll tearing/jitter
    const isNearBottom = (scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight) <= 180;
    if (isNearBottom) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
  }

  async openFlowchartDrawer() {
    const drawer = document.getElementById("flowchart-drawer");
    const container = document.getElementById("drawer-mermaid-content");
    const title = document.getElementById("drawer-agent-title");
    if (!drawer || !container) return;

    const agent = AGENTS[this.activeAgentId] || AGENTS.regulatory;
    const mode = this.activeAgentId === "mcp" ? (AGENTS.mcp.activeMode || "harry_potter") : "";
    const modeSuffix = mode === "harry_potter" ? " · Harry Potter QA" : (mode === "airbnb" ? " · Airbnb Search" : "");
    if (title) title.textContent = `${agent.name}${modeSuffix} Flowchart`;

    drawer.classList.add("is-open");
    container.innerHTML = '<div class="mono" style="color: var(--slate); padding: 24px;"><span class="spin">⟳</span> Rendering compiled StateGraph...</div>';

    let dsl = "";

    try {
      if (this.activeAgentId === "regulatory") {
        dsl = await api.request(CONFIG.ENDPOINTS.GRAPH_MERMAID, { includeAuth: false });
      } else if (this.activeAgentId === "research") {
        dsl = await api.request(CONFIG.ENDPOINTS.RESEARCH_MERMAID, { includeAuth: false });
      } else if (this.activeAgentId === "mcp") {
        dsl = await api.request(`${CONFIG.ENDPOINTS.MCP_MERMAID}?mode=${mode}`, { includeAuth: false });
      } else if (this.activeAgentId === "sql") {
        dsl = `flowchart TD
    Start([User Natural Language Query]) --> SQLAgent[1. create_sql_agent\\nSQLDatabaseToolkit Orchestrator]
    SQLAgent --> ListTables[2. sql_db_list_tables\\nSchema Introspection & Table Discovery]
    ListTables --> QueryChecker[3. sql_db_query_checker\\nSyntax Validation & Dialect Correction]
    QueryChecker --> ExecuteSQL[4. sql_db_query\\nSafe Read-Only PostgreSQL Execution]
    ExecuteSQL --> Synthesizer[5. Tabular Data & Explanation Synthesizer]
    Synthesizer --> EndNode([Synthesized Explanation & Interactive Data Table])
    classDef default fill:#f2f0ff,line-height:1.2`;
      } else if (this.activeAgentId === "chat") {
        dsl = `flowchart TD
    Start([User Message + Session ID]) --> FetchHistory[1. PostgresChatMessageHistory\\nThread Checkpoint & Session Memory Retrieval]
    FetchHistory --> ContextAssembler[2. Context & History Assembler\\nTrim & Token Budget Window]
    ContextAssembler --> ChatLLM[3. ChatGroq Inference\\nStateful Conversational Generation]
    ChatLLM --> AppendHistory[4. Append Message & Update Postgres Checkpoint]
    AppendHistory --> EndNode([Streaming Response & Memory Persisted])
    classDef default fill:#f2f0ff,line-height:1.2`;
      }

      if (window.mermaid && dsl) {
        const id = `drawer-mermaid-${Date.now()}`;
        const { svg } = await window.mermaid.render(id, dsl);
        container.innerHTML = svg;
      } else {
        container.innerHTML = `<pre class="stream-console">${dsl}</pre>`;
      }
    } catch (err) {
      container.innerHTML = `<div class="tag alert">FLOWCHART ERROR</div><p style="color: var(--alert); margin-top: 8px;">${err.message}</p>`;
    }
  }

  exportTableToCSV(tableData) {
    if (!tableData || !tableData.headers) return;
    const all = [tableData.headers, ...tableData.rows];
    const csvContent = all.map(r => r.map(c => `"${(c || '').replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `RP360_Table_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

export const chatPlatform = new ChatPlatformController();
