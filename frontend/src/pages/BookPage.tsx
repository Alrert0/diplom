import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Container,
  Typography,
  Box,
  Button,
  Rating,
  Chip,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  CircularProgress,
  Paper,
  AppBar,
  Toolbar,
  IconButton,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import api from "../services/api";
import type { Book, Chapter, ReadingProgress } from "../types";

const BACKEND_URL = "http://localhost:8000";

export default function BookPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [book, setBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [progress, setProgress] = useState<ReadingProgress | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get(`/books/${id}`),
      api.get(`/books/${id}/chapters`),
      api.get(`/reading/progress/${id}`).catch(() => null),
    ])
      .then(([bookRes, chaptersRes, progressRes]) => {
        setBook(bookRes.data);
        setChapters(chaptersRes.data);
        if (progressRes) setProgress(progressRes.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!book) {
    return (
      <Container sx={{ py: 4 }}>
        <Typography>{t("book_not_found")}</Typography>
      </Container>
    );
  }

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "grey.50" }}>
      <AppBar position="static">
        <Toolbar>
          <IconButton color="inherit" onClick={() => navigate("/")} edge="start">
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1 }}>
            {book.title}
          </Typography>
        </Toolbar>
      </AppBar>

      <Container sx={{ py: 4 }}>
        <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {/* Cover */}
          <Box
            component="img"
            src={
              book.cover_url
                ? `${BACKEND_URL}${book.cover_url}`
                : "/placeholder-cover.png"
            }
            alt={book.title}
            sx={{
              width: 250,
              height: 375,
              objectFit: "cover",
              borderRadius: 1,
              boxShadow: 3,
            }}
          />

          {/* Info */}
          <Box sx={{ flex: 1, minWidth: 280 }}>
            <Typography variant="h4" gutterBottom>
              {book.title}
            </Typography>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              {book.author}
            </Typography>

            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
              <Rating value={book.avg_rating ?? 0} precision={0.5} readOnly />
              <Typography variant="body2">
                ({book.ratings_count} {t("ratings")})
              </Typography>
            </Box>

            {book.genre && <Chip label={book.genre} sx={{ mr: 1, mb: 1 }} />}
            <Chip label={`${book.total_chapters} ${t("chapters")}`} sx={{ mr: 1, mb: 1 }} />
            <Chip
              label={`${book.total_words.toLocaleString()} ${t("words")}`}
              sx={{ mb: 1 }}
            />

            {book.description && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  {t("description")}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {book.description}
                </Typography>
              </Box>
            )}

            <Box sx={{ display: "flex", gap: 2, mt: 3, flexWrap: "wrap" }}>
              {progress ? (
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<PlayArrowIcon />}
                  onClick={() => navigate(`/read/${book.id}`)}
                >
                  {t("continue_chapter", { chapter: progress.current_chapter })}
                </Button>
              ) : (
                <Button
                  variant="contained"
                  size="large"
                  startIcon={<PlayArrowIcon />}
                  onClick={() => navigate(`/read/${book.id}`)}
                >
                  {t("start_reading")}
                </Button>
              )}
            </Box>
          </Box>
        </Box>

        {/* Chapters list */}
        <Paper sx={{ mt: 4, p: 2 }}>
          <Typography variant="h6" gutterBottom>
            {t("chapters")}
          </Typography>
          <List disablePadding>
            {chapters.map((ch) => (
              <ListItem key={ch.id} disablePadding divider>
                <ListItemButton
                  onClick={() => navigate(`/read/${book.id}`)}
                  selected={progress?.current_chapter === ch.chapter_number}
                >
                  <ListItemText
                    primary={`${ch.chapter_number}. ${ch.title || t("chapter") + " " + ch.chapter_number}`}
                    secondary={`${ch.word_count.toLocaleString()} ${t("words")}`}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Paper>
      </Container>
    </Box>
  );
}
