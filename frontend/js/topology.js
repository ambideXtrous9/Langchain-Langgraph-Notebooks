/**
 * RP360 // System Topology, Health Metrics & Interactive Mermaid Flowcharts
 * Connects to /health, /graph/mermaid, /research/mermaid, /mcp/travel/mermaid.
 */

import { api } from "./api.js";
import { CONFIG } from "./config.js";

class TopologyController {
  constructor() {
    this.activeGraphType = "regulatory"; // 'regulatory' | 'research' | 'mcp'
    this.mermaidSource = "";
  }

  init() {
    this.bindEvents();
    this.checkSystemHealth();
  }

  bindEvents() {
    const refreshHealthBtn = document.getElementById("health-refresh-btn");
    const graphSelectBtns = document.querySelectorAll("[data-graph-type]");
    const toggleSourceBtn = document.getElementById("topology-toggle-source-btn");
    const copyDslBtn = document.getElementById("topology-copy-dsl-btn");

    if (refreshHealthBtn) {
      refreshHealthBtn.addEventListener("click", () => this.checkSystemHealth());
    }

    graphSelectBtns.forEach(btn => {
      btn.addEventListener("click", (e) => {
        graphSelectBtns.forEach(b => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        this.activeGraphType = btn.getAttribute("data-graph-type");
        this.loadGraphMermaid(this.activeGraphType);
      });
    });

    if (toggleSourceBtn) {
      toggleSourceBtn.addEventListener("click", () => {
        const dslBox = document.getElementById("topology-dsl-container");
        const diagramBox = document.getElementById("topology-mermaid-render");
        if (dslBox && diagramBox) {
          const isHidden = dslBox.style.display === "none";
          dslBox.style.display = isHidden ? "block" : "none";
          toggleSourceBtn.textContent = isHidden ? "Hide Mermaid DSL" : "View Mermaid DSL";
        }
      });
    }

    if (copyDslBtn) {
      copyDslBtn.addEventListener("click", () => {
        if (this.mermaidSource) {
          navigator.clipboard.writeText(this.mermaidSource);
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "Mermaid DSL copied to clipboard.", type: "success" }
          }));
        }
      });
    }
  }

  async checkSystemHealth() {
    const statusPill = document.getElementById("header-status-pill");
    const statusDot = document.getElementById("header-status-dot");
    const statusText = document.getElementById("header-status-text");

    const healthVal = document.getElementById("metric-health-status");
    const dbVal = document.getElementById("metric-db-status");
    const langfuseVal = document.getElementById("metric-langfuse-status");
    const versionVal = document.getElementById("metric-version");

    try {
      const data = await api.request(CONFIG.ENDPOINTS.HEALTH, { includeAuth: false });
      
      if (statusDot) {
        statusDot.className = "status-dot online";
      }
      if (statusText) statusText.textContent = `API Connected (${data.database || 'in-memory'})`;

      if (healthVal) healthVal.textContent = data.status?.toUpperCase() || "HEALTHY";
      if (dbVal) dbVal.textContent = data.database === "connected" ? "POSTGRESQL (CONNECTED)" : "IN-MEMORY FALLBACK";
      if (langfuseVal) langfuseVal.textContent = data.langfuse_enabled ? "ENABLED" : "DISABLED";
      if (versionVal) versionVal.textContent = `v${data.version || '1.0.0'} [${data.environment || 'prod'}]`;
    } catch (err) {
      if (statusDot) {
        statusDot.className = "status-dot offline";
      }
      if (statusText) statusText.textContent = "Backend Offline";
      if (healthVal) healthVal.textContent = "OFFLINE";
      if (dbVal) dbVal.textContent = "UNREACHABLE";
    }
  }

  async loadGraphMermaid(type = "regulatory") {
    const renderBox = document.getElementById("topology-mermaid-render");
    const dslCode = document.getElementById("topology-dsl-code");
    if (!renderBox) return;

    renderBox.innerHTML = '<div class="mono" style="color: var(--slate);"><span class="spin">⟳</span> Fetching compiled graph definition...</div>';

    let dsl = "";

    try {
      if (type === "regulatory") {
        dsl = await api.request(CONFIG.ENDPOINTS.GRAPH_MERMAID, { includeAuth: false });
      } else if (type === "research") {
        dsl = await api.request(CONFIG.ENDPOINTS.RESEARCH_MERMAID, { includeAuth: false });
      } else if (type === "mcp") {
        const mode = localStorage.getItem("rp360_mcp_mode") || "harry_potter";
        dsl = await api.request(`${CONFIG.ENDPOINTS.MCP_MERMAID}?mode=${mode}`, { includeAuth: false });
      } else if (type === "sql") {
        dsl = `flowchart TD
    Start([User Natural Language Query]) --> SQLAgent[1. create_sql_agent\\nSQLDatabaseToolkit Orchestrator]
    SQLAgent --> ListTables[2. sql_db_list_tables\\nSchema Introspection & Table Discovery]
    ListTables --> QueryChecker[3. sql_db_query_checker\\nSyntax Validation & Dialect Correction]
    QueryChecker --> ExecuteSQL[4. sql_db_query\\nSafe Read-Only PostgreSQL Execution]
    ExecuteSQL --> Synthesizer[5. Tabular Data & Explanation Synthesizer]
    Synthesizer --> EndNode([Synthesized Explanation & Interactive Data Table])
    classDef default fill:#f2f0ff,line-height:1.2`;
      } else if (type === "chat") {
        dsl = `flowchart TD
    Start([User Message + Session ID]) --> FetchHistory[1. PostgresChatMessageHistory\\nThread Checkpoint & Session Memory Retrieval]
    FetchHistory --> ContextAssembler[2. Context & History Assembler\\nTrim & Token Budget Window]
    ContextAssembler --> ChatLLM[3. ChatGroq Inference\\nStateful Conversational Generation]
    ChatLLM --> AppendHistory[4. Append Message & Update Postgres Checkpoint]
    AppendHistory --> EndNode([Streaming Response & Memory Persisted])
    classDef default fill:#f2f0ff,line-height:1.2`;
      }

      this.mermaidSource = dsl;
      if (dslCode) dslCode.textContent = dsl;

      if (window.mermaid && dsl) {
        // Clean and render SVG
        const id = `mermaid-svg-${Date.now()}`;
        const { svg } = await window.mermaid.render(id, dsl);
        renderBox.innerHTML = svg;
      } else {
        renderBox.innerHTML = `<pre class="stream-console">${dsl}</pre>`;
      }
    } catch (err) {
      renderBox.innerHTML = `<div class="tag alert">DIAGRAM RENDER ERROR</div><p style="color: var(--alert); margin-top: 8px;">${err.message}</p>`;
    }
  }
}

export const topology = new TopologyController();
