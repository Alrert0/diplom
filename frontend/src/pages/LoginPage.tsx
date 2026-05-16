import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  TextField,
  Typography,
  Alert,
  IconButton,
  InputAdornment,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import AutoStoriesIcon from "@mui/icons-material/AutoStories";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import useAuthStore from "../store/authStore";
import LanguageSelector from "../components/LanguageSelector";

type Screen = "landing" | "login" | "register";

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { login, register } = useAuthStore();

  const [screen, setScreen] = useState<Screen>("landing");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const reset = () => { setEmail(""); setUsername(""); setPassword(""); setError(""); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (screen === "login") {
        await login(email, password);
        navigate("/");
      } else {
        await register(email, username, password, i18n.language);
        setScreen("login");
        reset();
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(detail || (screen === "login" ? t("login_error") : t("register_error")));
    } finally {
      setLoading(false);
    }
  };

  // ── Landing screen ──────────────────────────────────────────────
  if (screen === "landing") {
    return (
      <Box sx={{ minHeight: "100vh", bgcolor: "#fff", display: "flex", flexDirection: "column" }}>
        {/* Language top right */}
        <Box sx={{ position: "absolute", top: 20, right: 20 }}>
          <LanguageSelector />
        </Box>

        {/* Center logo */}
        <Box sx={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 1.5 }}>
          <AutoStoriesIcon sx={{ fontSize: 40, color: "#000" }} />
          <Typography sx={{ fontSize: 34, fontWeight: 800, letterSpacing: "-0.5px", color: "#000" }}>
            Kitap
          </Typography>
        </Box>

        {/* Bottom buttons */}
        <Box sx={{ p: 3, pb: 5, display: "flex", flexDirection: "column", gap: 2, maxWidth: 420, width: "100%", mx: "auto" }}>
          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={() => { reset(); setScreen("login"); }}
            sx={{ py: 1.8, fontSize: 16, borderRadius: 3 }}
          >
            {t("login")}
          </Button>
          <Button
            variant="outlined"
            size="large"
            fullWidth
            onClick={() => { reset(); setScreen("register"); }}
            sx={{ py: 1.8, fontSize: 16, borderRadius: 3 }}
          >
            {t("register")}
          </Button>
        </Box>
      </Box>
    );
  }

  // ── Login / Register form ────────────────────────────────────────
  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#fff", display: "flex", flexDirection: "column" }}>
      {/* Top bar */}
      <Box sx={{ px: 2, pt: 3, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <IconButton onClick={() => { reset(); setScreen("landing"); }}>
          <ArrowBackIcon />
        </IconButton>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <AutoStoriesIcon sx={{ fontSize: 22, color: "#000" }} />
          <Typography fontWeight={800} fontSize={18}>Kitap</Typography>
        </Box>
        <LanguageSelector />
      </Box>

      {/* Form */}
      <Box
        component="form"
        onSubmit={handleSubmit}
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          px: 3,
          maxWidth: 420,
          width: "100%",
          mx: "auto",
          pb: 4,
        }}
      >
        <Typography variant="h4" fontWeight={800} gutterBottom sx={{ mb: 0.5 }}>
          {screen === "login" ? t("welcome_back", "Welcome back") : t("create_account", "Create account")}
        </Typography>
        <Typography color="text.secondary" fontSize={14} sx={{ mb: 3 }}>
          {screen === "login"
            ? t("login_subtitle", "Sign in to continue reading")
            : t("register_subtitle", "Join to discover great books")}
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}

        <TextField
          label={t("email")}
          type="email"
          fullWidth
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          sx={{ mb: 2 }}
        />

        {screen === "register" && (
          <TextField
            label={t("username")}
            fullWidth
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            sx={{ mb: 2 }}
          />
        )}

        <TextField
          label={t("password")}
          type={showPassword ? "text" : "password"}
          fullWidth
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          sx={{ mb: 3 }}
          slotProps={{
            input: {
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShowPassword(!showPassword)} edge="end">
                    {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            },
          }}
        />

        <Button
          type="submit"
          variant="contained"
          fullWidth
          size="large"
          disabled={loading}
          sx={{ py: 1.8, fontSize: 16, borderRadius: 3, mb: 2 }}
        >
          {loading
            ? t("loading", "Loading...")
            : screen === "login"
            ? t("login")
            : t("register")}
        </Button>

        <Box sx={{ textAlign: "center" }}>
          <Typography variant="body2" color="text.secondary" display="inline">
            {screen === "login" ? t("no_account") : t("have_account")}{" "}
          </Typography>
          <Typography
            variant="body2"
            display="inline"
            fontWeight={600}
            sx={{ cursor: "pointer", textDecoration: "underline" }}
            onClick={() => { reset(); setScreen(screen === "login" ? "register" : "login"); }}
          >
            {screen === "login" ? t("register") : t("login")}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
