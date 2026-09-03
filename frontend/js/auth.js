/**
 * AgentSphere // Authentication & Access Controller
 * Argon2id Hashing, JWT Bearer Token, Blacklisting on Logout, Password Reset.
 */

import { api } from "./api.js";
import { CONFIG } from "./config.js";

class AuthManager {
  constructor() {
    this.currentUser = null;
    this.init();
  }

  init() {
    // Listen for auth expired event
    window.addEventListener("agentsphere:auth_expired", () => {
      this.handleSessionExpired();
    });
  }

  async checkAuth() {
    const token = api.getToken();
    if (!token) {
      this.currentUser = null;
      this.updateUI();
      return null;
    }

    try {
      const user = await api.request(CONFIG.ENDPOINTS.ME);
      this.currentUser = user;
      localStorage.setItem(CONFIG.STORAGE_KEYS.USER_PROFILE, JSON.stringify(user));
      this.updateUI();
      return user;
    } catch (err) {
      console.warn("Auth check failed:", err.message);
      this.currentUser = null;
      api.setToken(null);
      this.updateUI();
      return null;
    }
  }

  async signup(email, fullName, password) {
    const payload = {
      email: email.trim().toLowerCase(),
      full_name: fullName.trim(),
      password: password,
    };

    const user = await api.request(CONFIG.ENDPOINTS.SIGNUP, {
      method: "POST",
      body: payload,
      includeAuth: false,
    });

    // Auto-login after signup
    return await this.login(email, password);
  }

  async login(email, password) {
    const payload = {
      email: email.trim().toLowerCase(),
      password: password,
    };

    const tokenData = await api.request(CONFIG.ENDPOINTS.LOGIN, {
      method: "POST",
      body: payload,
      includeAuth: false,
    });

    if (tokenData.access_token) {
      api.setToken(tokenData.access_token);
      this.currentUser = tokenData.user || null;
      if (!this.currentUser) {
        await this.checkAuth();
      } else {
        localStorage.setItem(CONFIG.STORAGE_KEYS.USER_PROFILE, JSON.stringify(this.currentUser));
        this.updateUI();
      }
    }

    return tokenData;
  }

  async logout() {
    try {
      if (api.getToken()) {
        await api.request(CONFIG.ENDPOINTS.LOGOUT, {
          method: "POST",
        });
      }
    } catch (err) {
      console.warn("Logout endpoint error:", err.message);
    } finally {
      api.setToken(null);
      this.currentUser = null;
      localStorage.removeItem(CONFIG.STORAGE_KEYS.USER_PROFILE);
      this.updateUI();
      window.dispatchEvent(new CustomEvent("agentsphere:notify", {
        detail: { message: "Logged out. Token has been revoked.", type: "info" }
      }));
    }
  }

  async forgotPassword(email) {
    return await api.request(CONFIG.ENDPOINTS.FORGOT_PASSWORD, {
      method: "POST",
      body: { email: email.trim().toLowerCase() },
      includeAuth: false,
    });
  }

  async resetPassword(token, newPassword) {
    return await api.request(CONFIG.ENDPOINTS.RESET_PASSWORD, {
      method: "POST",
      body: {
        token: token.trim(),
        new_password: newPassword,
      },
      includeAuth: false,
    });
  }

  handleSessionExpired() {
    api.setToken(null);
    this.currentUser = null;
    this.updateUI();
    window.dispatchEvent(new CustomEvent("agentsphere:notify", {
      detail: { message: "Your session has expired. Please sign in again.", type: "error" }
    }));
  }

  updateUI() {
    const authBtn = document.getElementById("auth-nav-btn");
    const userNavChip = document.getElementById("user-nav-chip");
    const userNavAvatar = document.getElementById("user-nav-avatar");
    const userNavEmail = document.getElementById("user-nav-email");
    const btnNavLogout = document.getElementById("btn-nav-logout");

    const sidebarAvatar = document.getElementById("sidebar-user-avatar");
    const sidebarEmail = document.getElementById("user-display-email");
    const sidebarRole = document.getElementById("user-display-role");
    const logoutBtn = document.getElementById("logout-btn");

    if (this.currentUser) {
      const email = this.currentUser.email || "user@agentsphere.local";
      const name = this.currentUser.full_name || email;
      const initials = name
        .split(" ")
        .map(w => w[0])
        .filter(Boolean)
        .join("")
        .toUpperCase()
        .slice(0, 2) || "U";
      const role = (this.currentUser.role || "user").toUpperCase();

      // Top navbar
      if (authBtn) authBtn.style.display = "none";
      if (userNavChip) {
        userNavChip.style.display = "inline-flex";
        if (userNavAvatar) userNavAvatar.textContent = initials;
        if (userNavEmail) userNavEmail.textContent = email;
      }

      // Sidebar footer
      if (sidebarAvatar) {
        sidebarAvatar.textContent = initials;
        sidebarAvatar.style.background = "var(--brand)";
        sidebarAvatar.style.color = "#ffffff";
      }
      if (sidebarEmail) sidebarEmail.textContent = name;
      if (sidebarRole) sidebarRole.textContent = `AUTHENTICATED (${role})`;
      if (logoutBtn) logoutBtn.style.display = "inline-flex";

      // Bind nav logout click
      if (btnNavLogout && !btnNavLogout._bound) {
        btnNavLogout._bound = true;
        btnNavLogout.addEventListener("click", (e) => {
          e.stopPropagation();
          this.logout();
        });
      }
    } else {
      // Top navbar
      if (authBtn) authBtn.style.display = "inline-flex";
      if (userNavChip) userNavChip.style.display = "none";

      // Sidebar footer
      if (sidebarAvatar) {
        sidebarAvatar.textContent = "?";
        sidebarAvatar.style.background = "var(--ink)";
        sidebarAvatar.style.color = "var(--bone)";
      }
      if (sidebarEmail) sidebarEmail.textContent = "Guest User";
      if (sidebarRole) sidebarRole.textContent = "Click to Sign In";
      if (logoutBtn) logoutBtn.style.display = "none";
    }
  }
}

export const auth = new AuthManager();
