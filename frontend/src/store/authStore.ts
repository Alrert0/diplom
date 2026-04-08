import { create } from "zustand";
import api from "../services/api";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    username: string,
    password: string,
    language_pref?: string
  ) => Promise<void>;
  logout: () => void;
  loadFromStorage: () => void;
}

const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,

  login: async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    const token = data.access_token;
    localStorage.setItem("token", token);

    // Fetch user profile
    const userRes = await api.get("/auth/me");
    const user = userRes.data;
    localStorage.setItem("user", JSON.stringify(user));

    set({ token, user, isAuthenticated: true });
  },

  register: async (email, username, password, language_pref = "en") => {
    await api.post("/auth/register", {
      email,
      username,
      password,
      language_pref,
    });
  },

  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    set({ token: null, user: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    const token = localStorage.getItem("token");
    const userStr = localStorage.getItem("user");
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as User;
        set({ token, user, isAuthenticated: true });
      } catch {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
      }
    }
  },
}));

export default useAuthStore;
