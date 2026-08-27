/**
 * RP360 // Chat Platform Main Entrypoint
 * Bootstraps ChatGPT-style layout, agent switches, modals, and telemetry.
 */

import { getApiBase, setApiBase, CONFIG } from "./config.js";
import { api } from "./api.js";
import { auth } from "./auth.js";
import { chatPlatform } from "./chat.js";
import { AGENTS } from "./agents.js";

class ChatApp {
  async init() {
    console.log("Starting RP360 Multi-Agent Chat Interface...");

    // Setup Marked.js & Highlight.js
    if (window.marked) {
      window.marked.setOptions({
        gfm: true,
        breaks: true,
        highlight: (code, lang) => {
          if (window.hljs && lang && window.hljs.getLanguage(lang)) {
            return window.hljs.highlight(code, { language: lang }).value;
          }
          return code;
        }
      });
    }

    if (window.mermaid) {
      window.mermaid.initialize({
        startOnLoad: false,
        theme: "neutral",
        flowchart: { curve: "linear" },
        themeVariables: {
          primaryColor: "#eceffc",
          primaryTextColor: "#0e1216",
          primaryBorderColor: "#2b44c7",
          lineColor: "#5a646e",
          secondaryColor: "#f4f5f3",
          tertiaryColor: "#ffffff",
        }
      });
    }

    // Initialize Auth & Chat Platform
    await auth.checkAuth();
    chatPlatform.init();

    this.setupAuthModals();
    this.setupAgentConfigModal();
    this.setupSettingsModal();
    this.setupToastNotifications();
    this.checkHealthStatus();

    // Periodic Health Check
    setInterval(() => this.checkHealthStatus(), 30000);
  }

  async checkHealthStatus() {
    const dot = document.getElementById("health-dot");
    const label = document.getElementById("health-label");

    try {
      const data = await api.request(CONFIG.ENDPOINTS.HEALTH, { includeAuth: false });
      if (dot) dot.className = "status-dot online";
      if (label) label.textContent = `API Connected (${data.database || 'in-memory'})`;
    } catch (e) {
      if (dot) dot.className = "status-dot offline";
      if (label) label.textContent = "Backend Offline";
    }
  }

  setupAuthModals() {
    const authBtn = document.getElementById("auth-nav-btn");
    const sidebarUser = document.getElementById("sidebar-user-item");
    const logoutBtn = document.getElementById("logout-btn");
    const authModal = document.getElementById("auth-modal");
    const resetModal = document.getElementById("reset-modal");

    const tabLogin = document.getElementById("auth-tab-login");
    const tabSignup = document.getElementById("auth-tab-signup");
    const tabForgot = document.getElementById("auth-tab-forgot");

    const formLogin = document.getElementById("form-login");
    const formSignup = document.getElementById("form-signup");
    const formForgot = document.getElementById("form-forgot");
    const formReset = document.getElementById("form-reset");

    const openAuth = () => authModal?.classList.add("is-open");

    if (authBtn) authBtn.addEventListener("click", openAuth);
    if (sidebarUser) sidebarUser.addEventListener("click", () => {
      if (!auth.currentUser) openAuth();
    });

    if (logoutBtn) {
      logoutBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        auth.logout();
      });
    }

    // Close Modals
    document.querySelectorAll(".modal-close, [data-modal-close]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".modal-backdrop, .drawer-backdrop").forEach(m => m.classList.remove("is-open"));
      });
    });

    const setAuthView = (view) => {
      [formLogin, formSignup, formForgot].forEach(f => f && (f.style.display = "none"));
      [tabLogin, tabSignup, tabForgot].forEach(t => t && t.classList.remove("is-active"));

      if (view === "login") {
        if (formLogin) formLogin.style.display = "block";
        if (tabLogin) tabLogin.classList.add("is-active");
      } else if (view === "signup") {
        if (formSignup) formSignup.style.display = "block";
        if (tabSignup) tabSignup.classList.add("is-active");
      } else if (view === "forgot") {
        if (formForgot) formForgot.style.display = "block";
        if (tabForgot) tabForgot.classList.add("is-active");
      }
    };

    if (tabLogin) tabLogin.addEventListener("click", () => setAuthView("login"));
    if (tabSignup) tabSignup.addEventListener("click", () => setAuthView("signup"));
    if (tabForgot) tabForgot.addEventListener("click", () => setAuthView("forgot"));

    // Login Form Submit
    if (formLogin) {
      formLogin.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("login-email")?.value;
        const password = document.getElementById("login-password")?.value;
        const submitBtn = formLogin.querySelector("button[type='submit']");

        if (submitBtn) submitBtn.disabled = true;

        try {
          await auth.login(email, password);
          authModal.classList.remove("is-open");
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: `Welcome back, ${email}!`, type: "success" }
          }));
        } catch (err) {
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: err.message, type: "error" }
          }));
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    // Signup Form Submit
    if (formSignup) {
      formSignup.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("signup-email")?.value;
        const name = document.getElementById("signup-name")?.value;
        const password = document.getElementById("signup-password")?.value;
        const submitBtn = formSignup.querySelector("button[type='submit']");

        if (submitBtn) submitBtn.disabled = true;

        try {
          await auth.signup(email, name, password);
          authModal.classList.remove("is-open");
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: "Account created and signed in!", type: "success" }
          }));
        } catch (err) {
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: err.message, type: "error" }
          }));
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    // Forgot Password Form Submit
    if (formForgot) {
      formForgot.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgot-email")?.value;
        const submitBtn = formForgot.querySelector("button[type='submit']");

        if (submitBtn) submitBtn.disabled = true;

        try {
          const res = await auth.forgotPassword(email);
          const token = res.reset_token;
          if (token && resetModal) {
            authModal.classList.remove("is-open");
            resetModal.classList.add("is-open");
            const tokenInput = document.getElementById("reset-token");
            if (tokenInput) tokenInput.value = token;
          }
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: res.message || "Reset token generated.", type: "info" }
          }));
        } catch (err) {
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: err.message, type: "error" }
          }));
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    // Reset Password Form Submit
    if (formReset) {
      formReset.addEventListener("submit", async (e) => {
        e.preventDefault();
        const token = document.getElementById("reset-token")?.value;
        const newPassword = document.getElementById("reset-new-password")?.value;
        const submitBtn = formReset.querySelector("button[type='submit']");

        if (submitBtn) submitBtn.disabled = true;

        try {
          const res = await auth.resetPassword(token, newPassword);
          if (resetModal) resetModal.classList.remove("is-open");
          setAuthView("login");
          if (authModal) authModal.classList.add("is-open");

          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: res.message || "Password updated. You can now log in.", type: "success" }
          }));
        } catch (err) {
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: err.message, type: "error" }
          }));
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }
  }

  setupAgentConfigModal() {
    const configBtn = document.getElementById("btn-agent-config");
    const modal = document.getElementById("agent-config-modal");
    const saveBtn = document.getElementById("config-save-btn");

    if (configBtn && modal) {
      configBtn.addEventListener("click", () => {
        modal.classList.add("is-open");
      });
    }

    if (saveBtn && modal) {
      saveBtn.addEventListener("click", () => {
        const devClass = document.getElementById("cfg-device-class")?.value;
        const predicate = document.getElementById("cfg-predicate")?.value;
        const samd = document.getElementById("cfg-samd")?.checked;
        const specs = document.getElementById("cfg-specs")?.value;

        AGENTS.regulatory.params.device_class = devClass;
        AGENTS.regulatory.params.predicate_device = predicate;
        AGENTS.regulatory.params.is_samd = samd;
        AGENTS.regulatory.params.device_specs = specs;

        chatPlatform.renderParamChips(AGENTS.regulatory);
        modal.classList.remove("is-open");

        window.dispatchEvent(new CustomEvent("rp360:notify", {
          detail: { message: "Agent parameters updated.", type: "success" }
        }));
      });
    }
  }

  setupSettingsModal() {
    const settingsBtn = document.getElementById("btn-open-settings");
    const modal = document.getElementById("settings-modal");
    const input = document.getElementById("settings-api-base");
    const saveBtn = document.getElementById("settings-save-btn");
    const resetBtn = document.getElementById("settings-reset-default-btn");

    if (settingsBtn && modal) {
      settingsBtn.addEventListener("click", () => {
        if (input) input.value = getApiBase();
        modal.classList.add("is-open");
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener("click", () => {
        const val = input ? input.value : "";
        if (val) {
          setApiBase(val);
          this.checkHealthStatus();
          modal?.classList.remove("is-open");
          window.dispatchEvent(new CustomEvent("rp360:notify", {
            detail: { message: `API Origin set to ${val}`, type: "success" }
          }));
        }
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        setApiBase(CONFIG.DEFAULT_API_BASE);
        if (input) input.value = CONFIG.DEFAULT_API_BASE;
        this.checkHealthStatus();
        modal?.classList.remove("is-open");
        window.dispatchEvent(new CustomEvent("rp360:notify", {
          detail: { message: "API Origin reset to default.", type: "info" }
        }));
      });
    }
  }

  setupToastNotifications() {
    const container = document.getElementById("toast-container");
    if (!container) return;

    window.addEventListener("rp360:notify", (e) => {
      const { message, type } = e.detail || {};
      if (!message) return;

      const toast = document.createElement("div");
      toast.className = `toast-item toast-${type || 'info'}`;

      let icon = "ℹ";
      if (type === "success") icon = "✓";
      if (type === "error") icon = "✕";

      toast.innerHTML = `
        <span class="toast-icon"><strong>${icon}</strong></span>
        <span class="toast-msg">${message}</span>
        <button type="button" class="toast-close">&times;</button>
      `;

      container.appendChild(toast);
      setTimeout(() => toast.classList.add("is-visible"), 10);

      const closeToast = () => {
        toast.classList.remove("is-visible");
        setTimeout(() => toast.remove(), 250);
      };

      toast.querySelector(".toast-close").addEventListener("click", closeToast);
      setTimeout(closeToast, 4000);
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const app = new ChatApp();
  app.init();
});
