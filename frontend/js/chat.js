/**
 * AgentSphere // Multi-Agent Conversation Controller
 * Handles conversation sessions, multi-agent dispatching, SSE/WebSocket streaming,
 * dynamic thinking accordions, and Human-in-the-Loop interrupt resolution.
 */

import { api } from "./api.js";
import { CONFIG, getApiBase } from "./config.js";
import { AGENTS } from "./agents.js";

class ChatPlatformController {
  constructor() {
    this.activeAgentId = "policy";
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
      const stored = localStorage.getItem("agentsphere_chat_sessions_v2");
      this.sessions = stored ? JSON.parse(stored) : [];
    } catch (e) {
      this.sessions = [];
    }
  }

  saveSessions() {
    localStorage.setItem("agentsphere_chat_sessions_v2", JSON.stringify(this.sessions));
    this.renderSidebarHistory();
  }

  getActiveSession() {
    return this.sessions.find(s => s.id === this.activeSessionId);
  }

  createNewSession(agentId = "policy") {
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

    this.activeAgentId = session.agentId || "policy";
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

    window.dispatchEvent(new CustomEvent("agentsphere:notify", {
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
    localStorage.setItem("agentsphere_mcp_mode", targetMode);

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

    window.dispatchEvent(new CustomEvent("agentsphere:notify", {
      detail: {
        message: targetMode === "harry_potter"
          ? "Switched to Harry Potter Universe QA (Pinecone MCP)"
          : "Switched to Airbnb Travel & Lodging Search (OpenBNB MCP)",
        type: "success"
      }
    }));
  }

  renderActiveAgentUI() {
    const agent = AGENTS[this.activeAgentId] || AGENTS.policy;

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

    // Configure Parameters Button: Only display/enable for agents that require parameter inputs (e.g. Policy Navigator)
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

    if (agent.id === "policy") {
      const p = AGENTS.policy?.params || {};
      const tier = p.system_tier ? p.system_tier.split(" ")[0] + " " + (p.system_tier.split(" ")[1] || "") : "Tier 2";
      const autoStatus = p.is_autonomous ? "Autonomous: ON" : "Autonomous: OFF";
      container.style.display = "flex";
      container.innerHTML = `
        <span class="param-pill is-active" id="chip-param-class" title="System Tier">${tier}</span>
        <span class="param-pill is-active" id="chip-param-auto" title="Autonomous AI / Cloud Engine">${autoStatus}</span>
        <span class="param-pill" id="chip-param-config" title="Open Agent Configuration Modal">⚙ Parameters</span>
      `;
      document.getElementById("chip-param-config")?.addEventListener("click", () => {
        const p = AGENTS.policy?.params || {};
        const devClassEl = document.getElementById("cfg-device-class");
        const predicateEl = document.getElementById("cfg-predicate");
        const autoEl = document.getElementById("cfg-autonomous");
        const specsEl = document.getElementById("cfg-specs");
        if (devClassEl && (p.system_tier || p.device_class)) devClassEl.value = p.system_tier || p.device_class;
        if (predicateEl) predicateEl.value = p.reference_standard || p.predicate_device || "";
        if (autoEl) autoEl.checked = Boolean(p.is_autonomous);
        if (specsEl) specsEl.value = p.system_specs || p.device_specs || "";
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
    } else if (agent.id === "stock") {
      const p = AGENTS.stock?.params || {};
      const sector = p.sector_filter ? `Sector: ${p.sector_filter}` : "Sector: All NIFTY 500";
      const lenses = `Lenses: ${p.max_lenses || 6} / 13`;
      container.style.display = "flex";
      container.innerHTML = `
        <span class="param-pill is-active" id="chip-stock-sector" title="Selected NSE Sector">${sector}</span>
        <span class="param-pill is-active" id="chip-stock-lenses" title="Analyst Lenses Fan-Out">${lenses}</span>
        <span class="param-pill is-active" title="Vector Database">Pinecone MCP</span>
        <span class="param-pill is-active" title="Real-Time Market Tools">Yahoo Finance</span>
        <span class="param-pill is-active" title="Indian Market Intelligence">GNews</span>
        <span class="param-pill" id="chip-stock-config" title="Open Stock Swarm Configuration">⚙ Parameters</span>
      `;
      document.getElementById("chip-stock-config")?.addEventListener("click", () => {
        const modal = document.getElementById("agent-config-modal");
        const policyForm = document.getElementById("policy-config-form");
        const stockForm = document.getElementById("stock-config-form");
        const modalTitle = document.getElementById("config-modal-title");
        if (policyForm) policyForm.style.display = "none";
        if (stockForm) stockForm.style.display = "block";
        if (modalTitle) modalTitle.textContent = "NSE Stock Swarm Configuration";
        const sp = AGENTS.stock?.params || {};
        const sectorEl = document.getElementById("cfg-stock-sector");
        const lensesEl = document.getElementById("cfg-stock-lenses");
        if (sectorEl) sectorEl.value = sp.sector_filter || "";
        if (lensesEl) lensesEl.value = sp.max_lenses || 6;
        modal?.classList.add("is-open");
      });
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
      const agent = AGENTS[s.agentId] || AGENTS.policy;
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

    const agent = AGENTS[session.agentId] || AGENTS.policy;

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
        const stockHtml = msg.stockResult ? this.renderStockCard(msg.stockResult, idx) : "";

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

                ${stockHtml}
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

    const agent = AGENTS[this.activeAgentId] || AGENTS.policy;

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
        <p style="font-size: 13.5px; color: #5a3e00; margin-bottom: 8px;">${promptText || 'Policy pathway generated. Review recommendations or provide modifications:'}</p>
        <div class="chat-hitl-actions">
          <input type="text" class="field-input" id="hitl-input-${msgIdx}" placeholder="e.g., 'Approve guidance', 'Include benchmark ISO-27001', or 'Refine for autonomous engine'" style="flex: 1; min-width: 220px; font-size: 13.5px; padding: 6px 10px;" />
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

  renderStockCard(stockData, msgIdx) {
    if (!stockData) return "";
    const apiBase = getApiBase();
    const token = api.getToken();
    const reportUrl = token
      ? `${apiBase}${stockData.report_url}?token=${encodeURIComponent(token)}`
      : `${apiBase}${stockData.report_url}`;
    const lensesCount = stockData.enabled_lenses?.length || 6;
    const verifiedCount = stockData.verified_findings_count || 0;
    const rejectedCount = stockData.rejected_findings_count || 0;
    const figuresCount = stockData.figures_count || 0;

    let figuresHtml = "";
    if (stockData.figures && stockData.figures.length > 0) {
      figuresHtml = `
        <div class="stock-figures-grid">
          ${stockData.figures.map(fig => {
            let path = fig.file_path || "";
            if (path.startsWith("app/static/")) {
              path = "/" + path.slice(4);
            } else if (path.startsWith("static/")) {
              path = "/" + path;
            } else if (!path.startsWith("/") && !path.startsWith("http") && path) {
              path = "/" + path;
            }
            const cleanApiBase = (apiBase || "").replace(/\/+$/, "");
            const fullUrl = path.startsWith("http") ? path : `${cleanApiBase}${path}`;
            const chartType = (fig.chart_type || "CHART").toUpperCase();
            const verdict = (fig.critic_verdict || "APPROVED").toUpperCase();
            const title = fig.title || "Market Exhibit";
            return `
            <div class="stock-figure-card">
              <a href="${fullUrl}" target="_blank" title="View Full Chart Exhibit">
                <img src="${fullUrl}" alt="${title}" class="stock-figure-img" loading="lazy" onerror="this.onerror=null; this.src='${cleanApiBase}/static/top_charts/${fig.id || 'chart'}.png';" />
              </a>
              <div class="stock-figure-caption">
                <span style="font-weight: 500; font-size: 11px; line-height: 1.3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 65%; color: #1e293b;" title="${title}">${title}</span>
                <span class="tag brand" style="font-size: 9.5px; white-space: nowrap; flex-shrink: 0;">${chartType} &middot; ${verdict}</span>
              </div>
            </div>
            `;
          }).join("")}
        </div>
      `;
    }

    let targetsHeaderHtml = "";
    if (stockData.target_symbols && stockData.target_symbols.length > 0) {
      targetsHeaderHtml = `
        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; align-items: center;">
          <span style="font-size: 11px; font-weight: 600; color: #475569;">TARGETS:</span>
          ${stockData.target_symbols.map(s => `<span class="tag brand" style="font-size: 11px; background: #0284c7; color: white; padding: 2px 8px; border-radius: 9999px;">🏦 ${s}</span>`).join("")}
          <span class="tag" style="font-size: 11px; background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 9999px;">⏱ ${stockData.time_horizon || "6 Months"}</span>
          <span class="tag" style="font-size: 11px; background: #ecfdf5; color: #065f46; padding: 2px 8px; border-radius: 9999px;">🎯 ${(stockData.analysis_mode || "sector").toUpperCase()}</span>
        </div>
      `;
    }

    let matrixHtml = "";
    if (stockData.comparative_matrix && stockData.comparative_matrix.length > 0) {
      matrixHtml = `
        <div style="overflow-x: auto; margin: 12px 0; border: 1px solid #e2e8f0; border-radius: 8px;">
          <table style="width: 100%; border-collapse: collapse; font-size: 11.5px; text-align: left; background: #ffffff;">
            <thead>
              <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0; color: #475569;">
                <th style="padding: 6px 10px;">Stock</th>
                <th style="padding: 6px 10px; text-align: right;">Price</th>
                <th style="padding: 6px 10px; text-align: right;">P/E</th>
                <th style="padding: 6px 10px; text-align: right;">P/B</th>
                <th style="padding: 6px 10px; text-align: right;">ROE</th>
                <th style="padding: 6px 10px; text-align: right;">6M Ret</th>
              </tr>
            </thead>
            <tbody>
              ${stockData.comparative_matrix.map(c => `
                <tr style="border-bottom: 1px solid #f1f5f9;">
                  <td style="padding: 6px 10px; font-weight: 600;">${c.company_name} <span style="color: #64748b; font-weight: normal;">(${c.symbol})</span></td>
                  <td style="padding: 6px 10px; text-align: right;">₹${(c.current_price || 0).toLocaleString()}</td>
                  <td style="padding: 6px 10px; text-align: right; font-weight: 600;">${(c.pe_ratio || 0).toFixed(1)}</td>
                  <td style="padding: 6px 10px; text-align: right;">${(c.pb_ratio || 0).toFixed(2)}</td>
                  <td style="padding: 6px 10px; text-align: right; color: #16a34a; font-weight: 600;">${(c.roe_pct || 0).toFixed(1)}%</td>
                  <td style="padding: 6px 10px; text-align: right; font-weight: 600; color: ${(c.return_6m_pct || 0) >= 0 ? '#16a34a' : '#dc2626'};">${(c.return_6m_pct || 0) >= 0 ? '+' : ''}${(c.return_6m_pct || 0).toFixed(1)}%</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    return `
      <div class="stock-report-card">
        <div class="stock-report-header">
          <div class="stock-report-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
            NSE Institutional Research Dossier &middot; Run #${stockData.run_id}
          </div>
          <a href="${reportUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="display: inline-flex; align-items: center; gap: 6px; text-decoration: none;">
            <span>Open Publication Report</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </a>
        </div>

        ${targetsHeaderHtml}

        <div class="stock-stats-grid">
          <div class="stock-stat-box">
            <span class="stat-label">Universe</span>
            <span class="stat-val">${stockData.target_symbols && stockData.target_symbols.length > 0 ? stockData.target_symbols.join(" vs ") : "NIFTY 500"}</span>
          </div>
          <div class="stock-stat-box">
            <span class="stat-label">Analyst Lenses</span>
            <span class="stat-val">${lensesCount} Active</span>
          </div>
          <div class="stock-stat-box">
            <span class="stat-label">Verified Facts</span>
            <span class="stat-val" style="color: #15803d;">${verifiedCount} Passed</span>
          </div>
          <div class="stock-stat-box">
            <span class="stat-label">Skeptic Audit</span>
            <span class="stat-val" style="color: ${rejectedCount > 0 ? '#b91c1c' : '#64748b'};">${rejectedCount} Rejected</span>
          </div>
          <div class="stock-stat-box">
            <span class="stat-label">Visual Exhibits</span>
            <span class="stat-val">${figuresCount} Charts</span>
          </div>
        </div>

        ${matrixHtml}
        ${figuresHtml}
        ${stockData.quant_simulations && stockData.quant_simulations.length > 0 ? `
          <div style="margin-top: 12px; padding: 12px; background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 8px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
              <div style="font-size: 12px; font-weight: 700; color: #6d28d9; display: flex; align-items: center; gap: 6px;">
                <span>⚡ DeepAgent Quant Sandbox</span>
                <span class="tag brand" style="font-size: 9px; background: #8b5cf6; color: white; padding: 1px 6px; border-radius: 4px;">ACTIVE</span>
              </div>
              <span style="font-size: 11px; color: #7c3aed; font-weight: 500;">${stockData.quant_simulations.length} Sim(s) Completed</span>
            </div>
            <div style="font-size: 11.5px; color: #4c1d95; line-height: 1.45;">
              ${stockData.quant_simulations.map(s => `
                <div style="margin-bottom: 4px; padding: 4px 6px; background: rgba(255,255,255,0.7); border-radius: 4px;">
                  <strong style="color: #5b21b6;">${(s.type || "Simulation").replace('_', ' ').toUpperCase()}:</strong>
                  ${s.type === "monte_carlo" ? `Mean Projected Return: <strong>${s.data?.expected_return_pct}%</strong> | 95% VaR: <strong>${s.data?.var_95_pct}%</strong> | Terminal: <strong>₹${s.data?.mean_terminal_price}</strong>` : ""}
                  ${s.type === "portfolio_optimization" ? `Optimal Sharpe: <strong>${s.data?.max_sharpe_portfolio?.sharpe_ratio}</strong> | Expected Return: <strong>${s.data?.max_sharpe_portfolio?.expected_return_pct}%</strong> | Volatility: <strong>${s.data?.max_sharpe_portfolio?.volatility_pct}%</strong>` : ""}
                </div>
              `).join("")}
            </div>
          </div>
        ` : ""}
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
          window.dispatchEvent(new CustomEvent("agentsphere:notify", {
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
          window.dispatchEvent(new CustomEvent("agentsphere:notify", {
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

  cleanCitationTokens(text) {
    if (!text || typeof text !== "string") return text || "";
    let cleaned = text;
    // 1. Remove bracketed finding tokens at start of sentences e.g. "【F_TEMPOR_01】. Monte-Carlo" -> "Monte-Carlo"
    cleaned = cleaned.replace(/(?:^|(?<=[\.\?\!\n]))\s*[【\[][\s,]*F_[^】\]]*[】\]][\.\,\;\:]?\s*/g, " ");
    // 2. Remove any bracket containing F_ citation tokens (single or comma-separated list e.g. [F_01, F_02])
    cleaned = cleaned.replace(/\s*[【\[][\s,]*F_[^】\]]*[】\]]/g, "");
    // 3. Remove any remaining lenticular brackets e.g. "【...】"
    cleaned = cleaned.replace(/\s*【[^】]*】/g, "");
    // 4. Clean up redundant spaces around punctuation
    cleaned = cleaned.replace(/\s+([.,;:!?])/g, "$1");
    cleaned = cleaned.replace(/\.{2,}/g, ".");
    cleaned = cleaned.replace(/[ \t]{2,}/g, " ");
    cleaned = cleaned.replace(/(?:^|(?<=\n))\s*[\.\,\;\:]\s*/g, "");
    return cleaned.trim();
  }

  formatContent(text) {
    if (!text) return "";
    const cleanText = this.cleanCitationTokens(text);
    if (window.marked) {
      return window.marked.parse(cleanText);
    }
    return `<p>${cleanText}</p>`;
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
      if (this.activeAgentId === "policy") {
        await this.streamPolicyAgent(userText, assistantMsgIndex);
      } else if (this.activeAgentId === "research") {
        await this.streamResearchAgent(userText, assistantMsgIndex);
      } else if (this.activeAgentId === "mcp") {
        await this.streamMCPAgent(userText, assistantMsgIndex);
      } else if (this.activeAgentId === "stock") {
        await this.executeStockAgent(userText, assistantMsgIndex);
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
   * Resume Policy HITL from within chat bubble
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
      await this.streamPolicyAgent(feedbackText, newIdx, true);
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

  async streamPolicyAgent(userText, msgIdx, isResume = false) {
    this.abortController = new AbortController();
    const session = this.getActiveSession();
    const msg = session.messages[msgIdx];

    const p = AGENTS.policy?.params || {};
    const payload = {
      user_choices: {
        system_tier: p.system_tier || "Tier 2 (Advanced Verification Standards)",
        intended_use: p.intended_use || "Continuous cloud telemetry monitoring and identity verification",
        reference_standard: p.reference_standard || "",
        is_autonomous: p.is_autonomous !== undefined ? p.is_autonomous : true,
      },
      user_input: userText,
      useDeviceData: Boolean(p.system_specs),
      useSystemData: Boolean(p.system_specs),
      user_provided_system_data: p.system_specs || "",
      user_provided_spec_data: p.system_specs || "",
      user_provided_device_data: p.system_specs || "",
      userProvidedDeiveceData: p.system_specs || "",
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

  async executeStockAgent(query, msgIdx) {
    const session = this.getActiveSession();
    const msg = session.messages[msgIdx];

    if (!api.getToken()) {
      window.dispatchEvent(new CustomEvent("agentsphere:notify", {
        detail: {
          message: "Authentication required to run Institutional Stock Swarm. Please sign in or create an account.",
          type: "warning"
        }
      }));
      document.getElementById("auth-modal")?.classList.add("is-open");
      msg.content = "🔒 **Authentication Required**: Access to the Institutional NSE Stock Analysis Swarm and Deep Agents Sandboxes requires an authenticated user account. Please sign in via the dialog or top navigation bar to execute your query.";
      msg.isStreaming = false;
      this.renderMessages();
      return;
    }

    const sp = AGENTS.stock?.params || {};

    const steps = [
      "Master Deep Agent: Parsing query, resolving target entities & horizon planning...",
      "Executing targeted search across CSV constituents, DuckDB fact store & SQLite blackboard...",
      "Querying Yahoo Finance & GNews sentiment for target companies...",
      "Fanning out deep agent lenses & executing Quant Sandbox simulations (Monte Carlo + Markowitz)...",
      "Running 4-Tier Verification Suite (DuckDB Numeric Tracer, Quote Audit, Skeptic Quorum)...",
      "Synthesizing Head-to-Head Comparative Valuation & assembling publication HTML report..."
    ];

    let stepIndex = 0;
    msg.steps.push({ hint: steps[stepIndex++], status: 'running' });
    this.renderMessages();

    const stepInterval = setInterval(() => {
      if (stepIndex < steps.length && msg.isStreaming) {
        if (msg.steps.length > 0) {
          msg.steps[msg.steps.length - 1].status = 'completed';
        }
        msg.steps.push({ hint: steps[stepIndex++], status: 'running' });
        this.scheduleLiveMessageUpdate(msgIdx);
      }
    }, 1600);

    try {
      const data = await api.request(CONFIG.ENDPOINTS.STOCK_ANALYZE, {
        method: "POST",
        body: {
          query: query,
          sector_filter: sp.sector_filter || null,
          max_lenses: sp.max_lenses || 6,
        },
      });

      clearInterval(stepInterval);
      msg.steps.forEach(st => st.status = 'completed');
      if (stepIndex < steps.length) {
        msg.steps.push({ hint: "Institutional analysis completed & publication report assembled.", status: 'completed' });
      }

      msg.stockResult = data;

      const titleHeader = (data.target_names && data.target_names.length > 0)
        ? `## Institutional Research Briefing: ${data.target_names.join(' vs ')} (${data.time_horizon || 'Horizon'})\n\n`
        : `## Institutional Research Briefing: NSE Stock Universe\n\n`;

      let md = titleHeader;

      // Master Deep Agent Strategic Execution Plan
      if (data.master_strategic_plan) {
        const mp = data.master_strategic_plan;
        const qi = data.query_intelligence || {};
        const intentBadge = (qi.intent || 'EQUITY RESEARCH').replace(/_/g, ' ').toUpperCase();
        md += `> 🎯 **Master Deep Agent Query Intelligence: \`${intentBadge}\`**\n`;
        if (qi.primary_research_question) {
          md += `> **Primary Strategic Question**: _${qi.primary_research_question}_\n\n`;
        } else {
          md += `\n`;
        }

        md += `### 🧭 Master Strategic Research Plan\n\n`;
        if (mp.strategic_thesis) {
          md += `**Investment Thesis & Mission**: ${mp.strategic_thesis}\n\n`;
        }

        if (mp.phased_execution_plan && mp.phased_execution_plan.length > 0) {
          md += `**Execution Roadmap**:\n`;
          mp.phased_execution_plan.forEach(p => {
            md += `- **${p.phase}**: ${p.description}\n`;
          });
          md += `\n`;
        }

        if (mp.subgoals && mp.subgoals.length > 0) {
          md += `**Prioritized Subgoals & Verification Gates**:\n`;
          mp.subgoals.forEach(sg => {
            const lensTag = sg.target_lens ? ` (\`${sg.target_lens}\` lens)` : '';
            md += `- \`${sg.id || 'SG'}\`: ${sg.description}${lensTag}\n`;
          });
          md += `\n`;
        }

        if (mp.traps && mp.traps.length > 0) {
          md += `**Cognitive & Valuation Traps Guarded Against**:\n`;
          mp.traps.forEach(tr => {
            md += `- ⚠️ **${tr.name}**: ${tr.warning}\n`;
          });
          md += `\n`;
        }
      }

      if (data.executive_summary) {
        md += `### Executive Briefing\n\n${data.executive_summary}\n\n`;
      }


      if (data.comparative_matrix && data.comparative_matrix.length > 0) {
        md += `### 📊 Head-to-Head Comparative Valuation & Fundamentals\n\n`;
        md += `| Company | Symbol | Price | P/E | P/B | ROE % | ROCE % | D/E | 6M Ret |\n`;
        md += `|---|---|---:|---:|---:|---:|---:|---:|---:|\n`;
        data.comparative_matrix.forEach(c => {
          const ret6m = (c.return_6m_pct || 0);
          const retStr = (ret6m >= 0 ? '+' : '') + ret6m.toFixed(1) + '%';
          md += `| **${c.company_name}** | \`${c.symbol}\` | ₹${(c.current_price || 0).toLocaleString()} | ${(c.pe_ratio || 0).toFixed(1)} | ${(c.pb_ratio || 0).toFixed(2)} | ${(c.roe_pct || 0).toFixed(1)}% | ${(c.roce_pct || 0).toFixed(1)}% | ${(c.debt_to_equity || 0).toFixed(2)} | ${retStr} |\n`;
        });
        md += `\n`;
      }

      if (data.verified_findings && data.verified_findings.length > 0) {
        md += `### 🔍 Top Verified Findings (DuckDB Proof + 4-Tier Audit)\n\n`;
        data.verified_findings.slice(0, 5).forEach((f, i) => {
          const rank = f.rank || (i + 1);
          const conf = Math.round((f.confidence || 0.9) * 100);
          md += `#### ${rank}. ${f.title || f.claim}\n`;
          md += `- **Analyst Lens**: \`${f.lens}\` &nbsp;|&nbsp; **Confidence**: **${conf}%** &nbsp;|&nbsp; **Audit**: ✅ Verified\n`;
          md += `- **Claim**: ${f.claim}\n`;
          if (f.sql_query) {
            md += `- **DuckDB Proof Query**: \`${f.sql_query}\`\n`;
          }
          if (f.numeric_scalar !== null && f.numeric_scalar !== undefined) {
            md += `- **Verified Metric**: **${f.numeric_scalar}**\n`;
          }
          if (f.verbatim_quote) {
            md += `- **Source Quote**: _"${f.verbatim_quote}"_\n`;
          }
          md += `\n`;
        });
      }

      if (data.sections && Object.keys(data.sections).length > 0) {
        md += `### 📑 Core Research Sections\n\n`;
        for (const [secTitle, secContent] of Object.entries(data.sections)) {
          md += `#### ${secTitle}\n${secContent}\n\n`;
        }
      }

      msg.content = this.cleanCitationTokens(md);
      msg.isStreaming = false;
      this.renderMessages();
    } catch (err) {
      clearInterval(stepInterval);
      msg.steps.forEach(st => {
        if (st.status === 'running') st.status = 'completed';
      });
      throw err;
    }
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

    const agent = AGENTS[this.activeAgentId] || AGENTS.policy;
    const mode = this.activeAgentId === "mcp" ? (AGENTS.mcp.activeMode || "harry_potter") : "";
    const modeSuffix = mode === "harry_potter" ? " · Harry Potter QA" : (mode === "airbnb" ? " · Airbnb Search" : "");
    if (title) title.textContent = `${agent.name}${modeSuffix} Flowchart`;

    drawer.classList.add("is-open");
    container.innerHTML = '<div class="mono" style="color: var(--slate); padding: 24px;"><span class="spin">⟳</span> Rendering compiled StateGraph...</div>';

    let dsl = "";

    try {
      if (this.activeAgentId === "policy") {
        dsl = await api.request(CONFIG.ENDPOINTS.GRAPH_MERMAID, { includeAuth: false });
      } else if (this.activeAgentId === "research") {
        dsl = await api.request(CONFIG.ENDPOINTS.RESEARCH_MERMAID, { includeAuth: false });
      } else if (this.activeAgentId === "mcp") {
        dsl = await api.request(`${CONFIG.ENDPOINTS.MCP_MERMAID}?mode=${mode}`, { includeAuth: false });
      } else if (this.activeAgentId === "stock") {
        dsl = await api.request(CONFIG.ENDPOINTS.STOCK_MERMAID, { includeAuth: false });
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
    a.download = `AgentSphere_Table_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

export const chatPlatform = new ChatPlatformController();
