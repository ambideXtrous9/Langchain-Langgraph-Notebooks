# RP360 Multi-Agent Chat Interface (Frontend)

Standalone, decoupled ChatGPT-style multi-agent conversational client with **RP360** design system.

---

## 🎨 Theme & Design System (RP360)

- **Colors**: Bone (`#f4f5f3`), Off-White Paper (`#ffffff`), Deep Ink (`#0e1216`), Muted Slate (`#5a646e`), Precision Cobalt (`#2b44c7`), Alert Crimson (`#b3341f`), and Clear Emerald (`#1f6f52`).
- **Typography**: Google Fonts *Archivo*, *IBM Plex Sans*, and *IBM Plex Mono*.
- **Layout**: ChatGPT-style left collapsible sidebar (history + agent selector) + main conversational canvas + top navbar + bottom floating input dock with parameter chips.

---

## 🤖 Supported Backend Agents

1. **FDA Regulatory Navigator Agent** (`/interact`, `/ws/interact`, `/thread/{id}/state`): Stateful LangGraph decision tree with Human-in-the-Loop review interrupts and 510(k)/PMA reasoning.
2. **Autonomous Deep Research Agent** (`/research/stream`, `/research/run`): 9-node parallel multi-critic research pipeline with live DuckDuckGo web searches and `defer=True` publisher join.
3. **MCP Multi-Agent Travel & Intelligence** (`/mcp/travel/stream`, `/mcp/tools`): Subprocess stdio MCP tools (`@openbnb/mcp-server-airbnb`) and Weather ReAct agents.
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

The frontend will automatically connect to the backend at `http://localhost:8000`. You can also configure the backend URL via the Settings gear in the frontend UI.
