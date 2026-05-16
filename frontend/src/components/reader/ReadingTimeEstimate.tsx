import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Box, Typography, Chip } from "@mui/material";
import type { ReaderPreferences } from "./ReaderSettings";
import { getThemeColors } from "./ReaderSettings";
import api from "../../services/api";

interface Props {
  bookId: number;
  chapterNumber: number;
  chapterWordsLeft: number;
  bookWordsLeft: number;
  readingSpeed: number; // local WPM estimate from page turns
  theme: ReaderPreferences["theme"];
}

interface ApiEstimate {
  chapter_minutes: number;
  book_minutes: number;
  wpm: number;
  chapter_words: number;
  book_words_remaining: number;
  has_sessions: boolean;
}

export default function ReadingTimeEstimate({
  bookId,
  chapterNumber,
  chapterWordsLeft,
  bookWordsLeft,
  readingSpeed,
  theme,
}: Props) {
  const { t } = useTranslation();
  const colors = getThemeColors(theme);

  const [mlEstimate, setMlEstimate] = useState<ApiEstimate | null>(null);

  useEffect(() => {
    if (!bookId || !chapterNumber) return;
    api
      .get("/reading/time-estimate", { params: { book_id: bookId, chapter: chapterNumber } })
      .then((res) => setMlEstimate(res.data))
      .catch(() => setMlEstimate(null));
  }, [bookId, chapterNumber]);

  // Use ML speed only if user has real session history.
  // Otherwise use the live page-turn measurement.
  const hasRealData = mlEstimate?.has_sessions === true;
  const wpm = hasRealData
    ? mlEstimate!.wpm
    : readingSpeed > 0
    ? readingSpeed
    : 200;

  const chapterMinutes = hasRealData
    ? mlEstimate!.chapter_minutes
    : Math.max(1, Math.round((mlEstimate?.chapter_words ?? chapterWordsLeft) / wpm));
  const bookHours = hasRealData
    ? (mlEstimate!.book_minutes / 60).toFixed(1)
    : ((mlEstimate?.book_words_remaining ?? bookWordsLeft) / wpm / 60).toFixed(1);

  const personalized = hasRealData;

  return (
    <Box
      sx={{
        position: "fixed",
        bottom: 16,
        left: 16,
        zIndex: 1100,
        bgcolor: colors.bg,
        color: colors.text,
        border: "1px solid",
        borderColor: theme === "dark" ? "grey.700" : "grey.300",
        borderRadius: 1,
        px: 1.5,
        py: 0.75,
        opacity: 0.85,
      }}
    >
      <Typography variant="caption" display="block">
        {t("min_left_chapter", { minutes: chapterMinutes })}
      </Typography>
      <Typography variant="caption" display="block">
        {t("hrs_left_book", { hours: bookHours })}
      </Typography>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
        <Typography variant="caption" sx={{ opacity: 0.6 }}>
          {t("reading_speed", { wpm: Math.round(wpm) })}
        </Typography>
        {personalized && (
          <Chip label={t("personalized")} size="small" color="success" variant="outlined" sx={{ height: 16, fontSize: 9 }} />
        )}
      </Box>
    </Box>
  );
}
