/**
 * RP360 // LangGraph Enterprise Agent Architecture
 * Application Configuration & LocalStorage Keys
 */

export const CONFIG = {
  // Default to standalone backend API server on localhost:8000
  DEFAULT_API_BASE: "http://localhost:8000",
    
  STORAGE_KEYS: {
    API_BASE: "rp360_api_base",
    AUTH_TOKEN: "rp360_jwt_token",
    USER_PROFILE: "rp360_user_profile",
    ACTIVE_TAB: "rp360_active_tab",
    CHAT_SESSION_ID: "rp360_chat_session_id",
    RECENT_SESSIONS: "rp360_recent_sessions",
    LAST_THREAD_ID: "rp360_last_thread_id",
  },

  ENDPOINTS: {
    HEALTH: "/health",
    GRAPH_MERMAID: "/graph/mermaid",
    RESEARCH_MERMAID: "/research/mermaid",
    MCP_MERMAID: "/mcp/travel/mermaid",
    
    // Auth
    SIGNUP: "/auth/signup",
    LOGIN: "/auth/login",
    ME: "/auth/me",
    LOGOUT: "/auth/logout",
    FORGOT_PASSWORD: "/auth/forgot-password",
    RESET_PASSWORD: "/auth/reset-password",
    
    // Regulatory Decision Graph
    INTERACT: "/interact",
    THREAD_STATE: (threadId) => `/thread/${threadId}/state`,
    DELETE_THREAD: "/delete_thread",
    WS_INTERACT: "/ws/interact",
    
    // Parallel Research
    RESEARCH_RUN: "/research/run",
    RESEARCH_STREAM: "/research/stream",
    
    // Model Context Protocol (MCP)
    MCP_TOOLS: "/mcp/tools",
    MCP_RUN: "/mcp/run",
    MCP_STREAM: "/mcp/stream",
    MCP_MERMAID: "/mcp/mermaid",
    MCP_TRAVEL_RUN: "/mcp/run",
    MCP_TRAVEL_STREAM: "/mcp/stream",
    
    // Text-to-SQL
    SQL_QUERY: "/get_sql_query",
    
    // Chat Memory
    GENERIC_CHAT: "/generic_chat",
    DELETE_SESSION: "/delete_session",
  }
};

export function getApiBase() {
  return localStorage.getItem(CONFIG.STORAGE_KEYS.API_BASE) || CONFIG.DEFAULT_API_BASE;
}

export function setApiBase(url) {
  let cleanUrl = url.trim().replace(/\/+$/, "");
  localStorage.setItem(CONFIG.STORAGE_KEYS.API_BASE, cleanUrl);
  return cleanUrl;
}
