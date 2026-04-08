import { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  Drawer,
  Box,
  Typography,
  Button,
  CircularProgress,
  Tabs,
  Tab,
  IconButton,
  Alert,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import api from "../../services/api";
import TextRankSummary from "./TextRankSummary";

interface Props {
  open: boolean;
  onClose: () => void;
  bookId: number;
  chapterNumber: number;
}

export default function AISummaryPanel({
  open,
  onClose,
  bookId,
  chapterNumber,
}: Props) {
  const { t } = useTranslation();
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Cache: chapter summaries keyed by "bookId-chapterNum"
  const chapterCacheRef = useRef<Record<string, string>>({});
  const [chapterSummary, setChapterSummary] = useState("");

  const [progressSummary, setProgressSummary] = useState("");

  const cacheKey = `${bookId}-${chapterNumber}`;

  const handleChapterSummary = async () => {
    // Check cache
    if (chapterCacheRef.current[cacheKey]) {
      setChapterSummary(chapterCacheRef.current[cacheKey]);
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await api.post("/ai/summary", {
        book_id: bookId,
        chapter_number: chapterNumber,
      });
      const content = res.data.content;
      chapterCacheRef.current[cacheKey] = content;
      setChapterSummary(content);
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 503) {
        setError(t("ai_error"));
      } else {
        setError(err.response?.data?.detail || t("error_occurred"));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleProgressSummary = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/ai/summary-progress", {
        book_id: bookId,
      });
      setProgressSummary(res.data.content);
    } catch (err: any) {
      const status = err.response?.status;
      if (status === 503) {
        setError(t("ai_error"));
      } else {
        setError(err.response?.data?.detail || t("error_occurred"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 420 }, p: 0 } }}
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
        }}
      >
        <Typography variant="h6">{t("ai_summary")}</Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </Box>

      {/* Tabs */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        variant="fullWidth"
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        <Tab label={t("chapter_summary")} />
        <Tab label={t("read_so_far")} />
      </Tabs>

      <Box sx={{ p: 2, overflow: "auto", flex: 1 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>
            {error}
          </Alert>
        )}

        {/* Chapter Summary Tab */}
        {tab === 0 && (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t("chapter")} {chapterNumber}
            </Typography>

            <Button
              variant="contained"
              onClick={handleChapterSummary}
              disabled={loading}
              fullWidth
              sx={{ mb: 2 }}
            >
              {loading ? (
                <>
                  <CircularProgress size={20} sx={{ mr: 1 }} color="inherit" />
                  {t("generating")}
                </>
              ) : (
                t("generate_summary")
              )}
            </Button>

            {chapterSummary && (
              <Typography
                variant="body2"
                sx={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}
              >
                {chapterSummary}
              </Typography>
            )}

            {/* TextRank key sentences */}
            <TextRankSummary bookId={bookId} chapterNumber={chapterNumber} />
          </>
        )}

        {/* Read So Far Tab */}
        {tab === 1 && (
          <>
            <Button
              variant="contained"
              onClick={handleProgressSummary}
              disabled={loading}
              fullWidth
              sx={{ mb: 2 }}
            >
              {loading ? (
                <>
                  <CircularProgress size={20} sx={{ mr: 1 }} color="inherit" />
                  {t("generating")}
                </>
              ) : (
                t("summarize_progress")
              )}
            </Button>

            {progressSummary && (
              <Typography
                variant="body2"
                sx={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}
              >
                {progressSummary}
              </Typography>
            )}
          </>
        )}
      </Box>
    </Drawer>
  );
}
