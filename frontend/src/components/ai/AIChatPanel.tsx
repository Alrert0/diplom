import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Drawer,
  Box,
  Typography,
  TextField,
  IconButton,
  CircularProgress,
  Paper,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import SendIcon from "@mui/icons-material/Send";

const API_BASE = "http://localhost:8000/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  bookId: number;
}

export default function AIChatPanel({ open, onClose, bookId }: Props) {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastBookIdRef = useRef(bookId);

  useEffect(() => {
    if (bookId !== lastBookIdRef.current) {
      setMessages([]);
      lastBookIdRef.current = bookId;
    }
  }, [bookId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    // Add empty assistant message that we'll stream into
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    const token = localStorage.getItem("token");

    try {
      const response = await fetch(`${API_BASE}/ai/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ book_id: bookId, message: question }),
      });

      if (!response.ok) {
        const status = response.status;
        let errorMsg: string;
        if (status === 503) {
          errorMsg = t("ai_error");
        } else if (status === 202) {
          errorMsg = t("book_indexing");
        } else {
          errorMsg = t("error_occurred");
        }
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { role: "assistant", content: errorMsg };
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
  }, [input, loading, bookId, t]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: { xs: "100%", sm: 420 },
          display: "flex",
          flexDirection: "column",
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2,
          py: 1,
          borderBottom: 1,
          borderColor: "divider",
          flexShrink: 0,
        }}
      >
        <Typography variant="h6">{t("ai_chat")}</Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Messages area */}
      <Box sx={{ flex: 1, overflow: "auto", p: 2 }}>
        {messages.length === 0 && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ textAlign: "center", mt: 4 }}
          >
            {t("no_messages_yet")}
          </Typography>
        )}

        {messages.map((msg, i) => (
          <Box
            key={i}
            sx={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              mb: 1.5,
            }}
          >
            <Paper
              elevation={1}
              sx={{
                px: 2,
                py: 1,
                maxWidth: "85%",
                bgcolor:
                  msg.role === "user" ? "primary.main" : "grey.100",
                color: msg.role === "user" ? "white" : "text.primary",
                borderRadius:
                  msg.role === "user"
                    ? "16px 16px 4px 16px"
                    : "16px 16px 16px 4px",
              }}
            >
              <Typography
                variant="body2"
                sx={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}
              >
                {msg.content}
              </Typography>
            </Paper>
          </Box>
        ))}

        {loading && messages[messages.length - 1]?.content === "" && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
            <CircularProgress size={18} />
            <Typography variant="body2" color="text.secondary">
              {t("ai_thinking")}
            </Typography>
          </Box>
        )}

        <div ref={messagesEndRef} />
      </Box>

      {/* Input area */}
      <Box
        sx={{
          p: 1.5,
          borderTop: 1,
          borderColor: "divider",
          display: "flex",
          gap: 1,
          flexShrink: 0,
        }}
      >
        <TextField
          fullWidth
          size="small"
          placeholder={t("ask_about_book")}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          multiline
          maxRows={3}
        />
        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Drawer>
  );
}
