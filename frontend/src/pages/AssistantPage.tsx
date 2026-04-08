import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  TextField,
  IconButton,
  Paper,
  Chip,
  CircularProgress,
  Avatar,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import SendIcon from "@mui/icons-material/Send";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import PersonIcon from "@mui/icons-material/Person";
import api from "../services/api";

const API_BASE = "http://localhost:8000/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function AssistantPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .get(`/assistant/suggestions?language=${i18n.language}`)
      .then((res) => setSuggestions(res.data.suggestions))
      .catch(() => {});
  }, [i18n.language]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;

    const userMsg: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Add empty assistant message to stream into
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const token = localStorage.getItem("token");

    try {
      const response = await fetch(`${API_BASE}/assistant/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text.trim(),
          language: i18n.language,
        }),
      });

      if (!response.ok) {
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            role: "assistant",
            content: t("ai_error"),
          };
          return updated;
        });
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = {
              ...last,
              content: last.content + chunk,
            };
            return updated;
          });
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: t("ai_error"),
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  }, [loading, i18n.language, t]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <Box sx={{ height: "100vh", display: "flex", flexDirection: "column", bgcolor: "grey.50" }}>
      <AppBar position="static">
        <Toolbar>
          <IconButton color="inherit" edge="start" onClick={() => navigate(-1)} sx={{ mr: 1 }}>
            <ArrowBackIcon />
          </IconButton>
          <SmartToyIcon sx={{ mr: 1 }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {t("ai_assistant")}
          </Typography>
        </Toolbar>
      </AppBar>

      {/* Messages area */}
      <Box sx={{ flex: 1, overflow: "auto", p: 2 }}>
        {messages.length === 0 && (
          <Box sx={{ textAlign: "center", mt: 8 }}>
            <SmartToyIcon sx={{ fontSize: 64, color: "grey.400", mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              {t("assistant_welcome")}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t("assistant_description")}
            </Typography>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, justifyContent: "center" }}>
              {suggestions.map((s, i) => (
                <Chip
                  key={i}
                  label={s}
                  variant="outlined"
                  onClick={() => sendMessage(s)}
                  sx={{ cursor: "pointer" }}
                />
              ))}
            </Box>
          </Box>
        )}

        {messages.map((msg, i) => (
          <Box
            key={i}
            sx={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              mb: 2,
            }}
          >
            {msg.role === "assistant" && (
              <Avatar sx={{ bgcolor: "primary.main", mr: 1, width: 32, height: 32 }}>
                <SmartToyIcon fontSize="small" />
              </Avatar>
            )}
            <Paper
              elevation={1}
              sx={{
                p: 2,
                maxWidth: "75%",
                bgcolor: msg.role === "user" ? "primary.main" : "white",
                color: msg.role === "user" ? "white" : "text.primary",
                borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
              }}
            >
              <Typography variant="body1" sx={{ whiteSpace: "pre-wrap" }}>
                {msg.content}
              </Typography>
            </Paper>
            {msg.role === "user" && (
              <Avatar sx={{ bgcolor: "grey.600", ml: 1, width: 32, height: 32 }}>
                <PersonIcon fontSize="small" />
              </Avatar>
            )}
          </Box>
        ))}

        {loading && messages[messages.length - 1]?.content === "" && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
            <Avatar sx={{ bgcolor: "primary.main", width: 32, height: 32 }}>
              <SmartToyIcon fontSize="small" />
            </Avatar>
            <Paper elevation={1} sx={{ p: 2, borderRadius: "16px 16px 16px 4px" }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2" color="text.secondary">
                  {t("ai_thinking")}
                </Typography>
              </Box>
            </Paper>
          </Box>
        )}

        <div ref={messagesEndRef} />
      </Box>

      {/* Input area */}
      <Paper
        elevation={3}
        sx={{
          p: 2,
          borderTop: 1,
          borderColor: "divider",
          display: "flex",
          gap: 1,
          alignItems: "flex-end",
        }}
      >
        <TextField
          fullWidth
          multiline
          maxRows={4}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("assistant_placeholder")}
          variant="outlined"
          size="small"
          disabled={loading}
        />
        <IconButton
          color="primary"
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || loading}
        >
          <SendIcon />
        </IconButton>
      </Paper>
    </Box>
  );
}
