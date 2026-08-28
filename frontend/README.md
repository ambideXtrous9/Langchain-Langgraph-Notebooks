# RP360 Multi-Agent Chat Interface (Frontend)

Standalone, decoupled ChatGPT-style multi-agent conversational client built on the **RP360** design system.

---

## 🎨 Theme & Design System (RP360)

- **Design Tokens**: Bone (`#f4f5f3`), Off-White Paper (`#ffffff`), Deep Ink (`#0e1216`), Muted Slate (`#5a646e`), Precision Cobalt (`#2b44c7`), Alert Crimson (`#b3341f`), and Clear Emerald (`#1f6f52`).
- **Typography**: Google Fonts *Archivo* (Display), *IBM Plex Sans* (Body), and *IBM Plex Mono* (Code / Metadata).
- **Layout**:
  - Collapsible left navigation sidebar (conversation history + agent selector).
  - Symmetrically centered widescreen conversational canvas (**`1140px`** max width, matching 20px padding on scroll canvas and bottom dock).
  - Floating bottom input dock with parameter quick-chips and auto-resizing prompt textarea.
  - Custom responsive Markdown tables (`.prose table`) with zebra striping, sticky headers, and non-breaking entity columns.
  - Cache-busting static asset versioning (`?v=3.3`).

---

## 🤖 Supported Backend Agents

1. **FDA Regulatory Navigator Agent** (`/interact`, `/ws/interact`, `/thread/{id}/state`): Stateful LangGraph decision tree with Human-in-the-Loop review interrupts and 510(k)/PMA pathway reasoning.
2. **Autonomous Deep Research Agent** (`/research/stream`, `/research/run`): 9-node parallel multi-critic research pipeline with live DuckDuckGo web searches and `defer=True` publisher join.
3. **MCP Multi-Agent Intelligence** (`/mcp/stream`, `/mcp/run`, `/mcp/mermaid`, `/mcp/tools`): Subprocess stdio MCP manager with a native top-navbar **Domain Selector Dropdown**:
   - **⚡ Harry Potter Multi-Hop Universe QA**: 3-hop iterative retrieval using the full 9-tool suite of `@pinecone-database/mcp` across `hpvdb-openai`, reranked via `pinecone-rerank-v0` and synthesized by `hpLoreScholar`.
   - **🏨 Airbnb Travel & Lodging Search**: `@openbnb/mcp-server-airbnb` stdio tool synthesis combined with real-time 3-day meteorological forecasting.
4. **Text-to-SQL Analyst Agent** (`/get_sql_query`): Natural language questions compiled to verified SQL with interactive data tables & CSV export.
5. **General Assistant Agent** (`/generic_chat`): Contextual dialogue with PostgreSQL `PostgresChatMessageHistory` persistence.

---

## 🚀 Running the Frontend (Standalone)

The frontend is completely decoupled from the backend. Run it on any independent local port (e.g. `3000`):

```bash
# Option 1: Using npm / npx serve (Port 3000)
cd frontend
npm start

# Option 2: Using Python HTTP server (Port 3000)
cd frontend
python3 -m http.server 3000

# Option 3: Using VS Code Live Server or Vite
```

The frontend automatically connects to the backend at `http://localhost:8000`. You can also configure the backend URL via the Settings gear in the frontend UI.
