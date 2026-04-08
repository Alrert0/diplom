import { useTranslation } from "react-i18next";
import { ToggleButtonGroup, ToggleButton } from "@mui/material";
import api from "../services/api";
import useAuthStore from "../store/authStore";

interface Props {
  size?: "small" | "medium" | "large";
}

export default function LanguageSelector({ size = "small" }: Props) {
  const { i18n } = useTranslation();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);

  const handleChange = async (_: unknown, lang: string | null) => {
    if (!lang) return;
    i18n.changeLanguage(lang);

    // Persist to backend if logged in
    if (isAuthenticated) {
      try {
        await api.put("/auth/me", { language_pref: lang });
        // Update local user object
        if (user) {
          const updated = { ...user, language_pref: lang };
          localStorage.setItem("user", JSON.stringify(updated));
          useAuthStore.setState({ user: updated });
        }
      } catch {
        // Silently fail — localStorage already has the language via i18next
      }
    }
  };

  return (
    <ToggleButtonGroup
      value={i18n.language.substring(0, 2)}
      exclusive
      onChange={handleChange}
      size={size}
    >
      <ToggleButton value="en">EN</ToggleButton>
      <ToggleButton value="ru">RU</ToggleButton>
      <ToggleButton value="kk">KK</ToggleButton>
    </ToggleButtonGroup>
  );
}
