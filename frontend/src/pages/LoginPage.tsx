import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Alert,
  Link,
  Container,
} from "@mui/material";
import useAuthStore from "../store/authStore";
import LanguageSelector from "../components/LanguageSelector";

export default function LoginPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { login, register } = useAuthStore();

  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
        navigate("/");
      } else {
        await register(email, username, password, i18n.language);
        setSuccess(t("register_success"));
        setIsLogin(true);
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(detail || (isLogin ? t("login_error") : t("register_error")));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <Paper sx={{ p: 4 }}>
          <Typography variant="h4" align="center" gutterBottom>
            {t("app_name")}
          </Typography>

          {/* Language selector */}
          <Box sx={{ display: "flex", justifyContent: "center", mb: 3 }}>
            <LanguageSelector />
          </Box>

          <Typography variant="h5" align="center" sx={{ mb: 2 }}>
            {isLogin ? t("login") : t("register")}
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          {success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {success}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit}>
            <TextField
              label={t("email")}
              type="email"
              fullWidth
              required
              margin="normal"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {!isLogin && (
              <TextField
                label={t("username")}
                fullWidth
                required
                margin="normal"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            )}
            <TextField
              label={t("password")}
              type="password"
              fullWidth
              required
              margin="normal"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={loading}
              sx={{ mt: 2, mb: 2 }}
            >
              {isLogin ? t("login") : t("register")}
            </Button>
          </Box>

          <Typography align="center">
            {isLogin ? t("no_account") : t("have_account")}{" "}
            <Link
              component="button"
              onClick={() => {
                setIsLogin(!isLogin);
                setError("");
                setSuccess("");
              }}
            >
              {isLogin ? t("register") : t("login")}
            </Link>
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
}
