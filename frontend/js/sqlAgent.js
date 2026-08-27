/**
 * RP360 // Text-to-SQL Natural Language Analytics Agent
 * Connects to /get_sql_query.
 */

import { api } from "./api.js";
import { CONFIG } from "./config.js";

class SQLAgentController {
  constructor() {
    this.currentSql = "";
    this.currentTableData = [];
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    const runBtn = document.getElementById("sql-run-btn");
    const copySqlBtn = document.getElementById("sql-copy-btn");
    const exportCsvBtn = document.getElementById("sql-export-csv-btn");

    if (runBtn) {
      runBtn.addEventListener("click", () => this.executeQuery());
    }

    if (copySqlBtn) {
      copySqlBtn.addEventListener("click", () => {
        if (this.currentSql) {
          navigator.clipboard.writeText(this.currentSql);
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "SQL query copied to clipboard.", type: "success" }
          }));
        }
      });
    }

    if (exportCsvBtn) {
      exportCsvBtn.addEventListener("click", () => this.exportCsv());
    }

    // Query preset chips
    const presetChips = document.querySelectorAll("[data-sql-preset]");
    presetChips.forEach(chip => {
      chip.addEventListener("click", () => {
        const query = chip.getAttribute("data-sql-preset");
        const input = document.getElementById("sql-query-input");
        if (input) {
          input.value = query;
          input.focus();
        }
      });
    });
  }

  async executeQuery() {
    const inputEl = document.getElementById("sql-query-input");
    const query = inputEl ? inputEl.value.trim() : "";

    if (!query) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "Please enter a natural language database question.", type: "error" }
      }));
      return;
    }

    const runBtn = document.getElementById("sql-run-btn");
    const answerBox = document.getElementById("sql-answer-box");
    const codeBox = document.getElementById("sql-code-box");
    const tableWrap = document.getElementById("sql-table-container");

    if (runBtn) {
      runBtn.disabled = true;
      runBtn.innerHTML = `<span class="spin">⟳</span> Generating Query...`;
    }

    if (answerBox) answerBox.innerHTML = '<span class="mono" style="color: var(--slate);"><span class="spin">⟳</span> Synthesizing answer and generating SQL...</span>';
    if (codeBox) codeBox.textContent = "-- Generating SQL query from schema...";
    if (tableWrap) tableWrap.innerHTML = "";

    try {
      const response = await api.request(CONFIG.ENDPOINTS.SQL_QUERY, {
        method: "POST",
        body: { query },
      });

      const finalAnswer = response.final_answer || "Query executed successfully.";
      this.currentSql = response.sql_query || "-- No query generated";
      const tableResult = response.table_result || "";

      if (answerBox) {
        if (window.marked) {
          answerBox.innerHTML = window.marked.parse(finalAnswer);
        } else {
          answerBox.textContent = finalAnswer;
        }
      }

      if (codeBox) {
        codeBox.textContent = this.currentSql;
        if (window.hljs) {
          window.hljs.highlightElement(codeBox);
        }
      }

      this.renderTable(tableResult);

      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "SQL query and result table generated.", type: "success" }
      }));
    } catch (err) {
      if (answerBox) {
        answerBox.innerHTML = `<div class="tag alert" style="margin-bottom: 8px;">EXECUTION ERROR</div><p style="color: var(--alert);">${err.message}</p>`;
      }
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: `SQL Agent Error: ${err.message}`, type: "error" }
      }));
    } finally {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.innerHTML = `Execute Natural Query <svg class="ico ico-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"></path></svg>`;
      }
    }
  }

  renderTable(rawTable) {
    const tableWrap = document.getElementById("sql-table-container");
    if (!tableWrap) return;

    if (!rawTable || typeof rawTable !== "string" || !rawTable.trim()) {
      tableWrap.innerHTML = '<p class="mono" style="padding: 16px; color: var(--slate);">No tabular records returned or non-tabular result.</p>';
      this.currentTableData = [];
      return;
    }

    // Try parsing markdown table or CSV/raw lines
    const lines = rawTable.trim().split("\n").map(l => l.trim()).filter(l => l && !l.startsWith("+-") && !l.startsWith("|--") && !l.startsWith("|-"));
    if (lines.length === 0) {
      tableWrap.innerHTML = `<pre class="stream-console">${rawTable}</pre>`;
      return;
    }

    // Check if markdown pipe table
    if (lines[0].includes("|")) {
      const headers = lines[0].split("|").map(h => h.trim()).filter(h => h);
      const rows = lines.slice(1).filter(l => !l.match(/^\|?\s*[-:]+[-| :]*$/)).map(row => {
        return row.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length || !row.startsWith("|"));
      });

      this.currentTableData = [headers, ...rows];

      let html = `
        <div class="panel-header" style="margin-bottom: 0; padding: 12px 16px; background: var(--bone);">
          <span class="mono" style="color: var(--slate);">RECORDS RETURNED: ${rows.length} ROW(S)</span>
        </div>
        <table class="sql-table">
          <thead>
            <tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${rows.map(r => `<tr>${r.map(cell => `<td>${cell || '&mdash;'}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      `;
      tableWrap.innerHTML = html;
    } else {
      tableWrap.innerHTML = `<pre class="stream-console">${rawTable}</pre>`;
    }
  }

  exportCsv() {
    if (!this.currentTableData || this.currentTableData.length === 0) {
      window.dispatchEvent(new CustomEvent("rp360:notify", {
        detail: { message: "No table data available to export.", type: "error" }
      }));
      return;
    }

    const csvContent = this.currentTableData.map(row => 
      row.map(cell => `"${(cell || "").replace(/"/g, '""')}"`).join(",")
    ).join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `RP360_Query_Results_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

export const sqlAgent = new SQLAgentController();
