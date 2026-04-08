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

  // Use ML estimate if available, otherwise fall back to local calculation
  const personalized = mlEstimate !== null;
  const wpm = personalized ? mlEstimate.wpm : readingSpeed > 0 ? readingSpeed : 200;
  const chapterMinutes = personalized
    ? mlEstimate.chapter_minutes
    : Math.max(1, Math.round(chapterWordsLeft / wpm));
  const bookHours = personalized
    ? (mlEstimate.book_minutes / 60).toFixed(1)
    : (bookWordsLeft / wpm / 60).toFixed(1);

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
