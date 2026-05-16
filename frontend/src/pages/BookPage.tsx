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
  CircularProgress,
  Paper,
  TextField,
  Avatar,
  Divider,
  IconButton,
  Tooltip,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StarIcon from "@mui/icons-material/Star";
import EditIcon from "@mui/icons-material/Edit";
import api from "../services/api";
import useAuthStore from "../store/authStore";
import AppLayout from "../components/layout/AppLayout";
import type { Book, Chapter, ReadingProgress } from "../types";

const BACKEND_URL = "http://localhost:8000";

interface RatingItem {
  id: number;
  user_id: number;
  username: string | null;
  score: number;
  review_text: string | null;
  created_at: string;
}

function ReviewCard({ review, isOwn }: { review: RatingItem; isOwn: boolean }) {
  const { t } = useTranslation();
  const date = new Date(review.created_at).toLocaleDateString();
  return (
    <Box sx={{ py: 2 }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5 }}>
        <Avatar sx={{ width: 36, height: 36, bgcolor: "#000", fontSize: 14, flexShrink: 0 }}>
          {(review.username?.[0] || "U").toUpperCase()}
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5, flexWrap: "wrap" }}>
            <Typography fontWeight={600} fontSize={14}>
              {review.username || "User"}
            </Typography>
            {isOwn && (
              <Chip label={t("your_review")} size="small" sx={{ bgcolor: "#f4f4f5", fontSize: 11 }} />
            )}
            <Rating value={review.score} size="small" readOnly />
            <Typography variant="caption" color="text.disabled" sx={{ ml: "auto" }}>
              {date}
            </Typography>
          </Box>
          {review.review_text && (
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
              {review.review_text}
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}

export default function BookPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [book, setBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [progress, setProgress] = useState<ReadingProgress | null>(null);
  const [reviews, setReviews] = useState<RatingItem[]>([]);
  const [myRating, setMyRating] = useState<RatingItem | null>(null);
  const [loading, setLoading] = useState(true);

  // Review form state
  const [showForm, setShowForm] = useState(false);
  const [score, setScore] = useState<number | null>(null);
  const [reviewText, setReviewText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const bookId = parseInt(id || "0", 10);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get(`/books/${bookId}`),
      api.get(`/books/${bookId}/chapters`),
      api.get(`/reading/progress/${bookId}`).catch(() => null),
      api.get(`/ratings/book/${bookId}`).catch(() => ({ data: [] })),
      api.get(`/ratings/my/${bookId}`).catch(() => ({ data: null })),
    ])
      .then(([bookRes, chapRes, progRes, ratRes, myRes]) => {
        setBook(bookRes.data);
        setChapters(chapRes.data);
        if (progRes) setProgress(progRes.data);
        setReviews(ratRes.data || []);
        if (myRes.data) {
          setMyRating(myRes.data);
          setScore(myRes.data.score);
          setReviewText(myRes.data.review_text || "");
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  const handleSubmitReview = async () => {
    if (!score) { setFormError(t("select_rating", "Please select a rating")); return; }
    setFormError("");
    setSubmitting(true);
    try {
      const res = await api.post("/ratings", {
        book_id: bookId,
        score,
        review_text: reviewText.trim() || null,
      });
      const saved = { ...res.data, username: user?.username };
      setMyRating(saved);
      setReviews((prev) => {
        const without = prev.filter((r) => r.user_id !== user?.id);
        return [saved, ...without];
      });
      // Refresh book to get updated avg_rating
      const bookRes = await api.get(`/books/${bookId}`);
      setBook(bookRes.data);
      setShowForm(false);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || t("error_occurred"));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <AppLayout>
        <Box sx={{ display: "flex", justifyContent: "center", py: 12 }}>
          <CircularProgress sx={{ color: "#000" }} />
        </Box>
      </AppLayout>
    );
  }

  if (!book) {
    return (
      <AppLayout>
        <Container sx={{ py: 4 }}>
          <Typography>{t("book_not_found")}</Typography>
        </Container>
      </AppLayout>
    );
  }

  const avgRating = book.avg_rating ?? 0;

  return (
    <AppLayout>
      <Container maxWidth="lg" sx={{ py: 4 }}>
        {/* Back button */}
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate(-1)}
          sx={{ mb: 3, color: "#000", fontWeight: 600 }}
        >
          {t("back")}
        </Button>

        {/* Book hero */}
        <Box sx={{ display: "flex", gap: { xs: 2, md: 5 }, flexWrap: "wrap", mb: 5 }}>
          {/* Cover */}
          <Box
            component="img"
            src={book.cover_url ? `${BACKEND_URL}${book.cover_url}` : "/placeholder-cover.png"}
            alt={book.title}
            sx={{ width: { xs: 160, md: 220 }, height: { xs: 240, md: 330 }, objectFit: "cover", borderRadius: 3, boxShadow: "0 8px 32px rgba(0,0,0,0.15)", flexShrink: 0 }}
          />

          {/* Info */}
          <Box sx={{ flex: 1, minWidth: 240 }}>
            <Typography variant="h4" fontWeight={800} gutterBottom lineHeight={1.2}>
              {book.title}
            </Typography>
            <Typography variant="h6" color="text.secondary" fontWeight={400} gutterBottom>
              {book.author}
            </Typography>

            {/* Rating summary */}
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, my: 2, flexWrap: "wrap" }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <StarIcon sx={{ fontSize: 22, color: "#000" }} />
                <Typography fontWeight={800} fontSize={22}>{avgRating > 0 ? avgRating.toFixed(1) : "—"}</Typography>
              </Box>
              <Typography color="text.secondary" fontSize={14}>
                {book.ratings_count} {t("ratings")}
              </Typography>
              <Divider orientation="vertical" flexItem />
              {book.genre && <Chip label={book.genre} size="small" sx={{ bgcolor: "#f4f4f5" }} />}
              <Chip label={`${book.total_chapters} ${t("chapters")}`} size="small" sx={{ bgcolor: "#f4f4f5" }} />
              <Chip label={`${book.total_words?.toLocaleString()} ${t("words")}`} size="small" sx={{ bgcolor: "#f4f4f5" }} />
            </Box>

            {book.description && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3, lineHeight: 1.7, maxWidth: 520 }}>
                {book.description}
              </Typography>
            )}

            <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
              <Button
                variant="contained"
                size="large"
                startIcon={<PlayArrowIcon />}
                onClick={() => navigate(`/read/${book.id}`)}
                sx={{ borderRadius: 3, px: 4 }}
              >
                {progress
                  ? t("continue_chapter", { chapter: progress.current_chapter })
                  : t("start_reading")}
              </Button>
              <Button
                variant="outlined"
                size="large"
                startIcon={<EditIcon />}
                onClick={() => setShowForm(!showForm)}
                sx={{ borderRadius: 3 }}
              >
                {myRating ? t("edit_review", "Edit review") : t("write_review", "Write review")}
              </Button>
            </Box>
          </Box>
        </Box>

        {/* Review form */}
        {showForm && (
          <Paper variant="outlined" sx={{ p: 3, mb: 4, borderRadius: 3 }}>
            <Typography fontWeight={700} fontSize={16} gutterBottom>
              {myRating ? t("edit_review", "Edit your review") : t("write_review", "Write a review")}
            </Typography>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                {t("your_rating", "Your rating")} *
              </Typography>
              <Rating
                value={score}
                onChange={(_, v) => setScore(v)}
                size="large"
                sx={{ "& .MuiRating-iconFilled": { color: "#000" }, "& .MuiRating-iconHover": { color: "#000" } }}
              />
            </Box>

            <TextField
              label={t("review_optional", "Review (optional)")}
              multiline
              rows={3}
              fullWidth
              value={reviewText}
              onChange={(e) => setReviewText(e.target.value)}
              placeholder={t("review_placeholder", "Share your thoughts about this book...")}
              sx={{ mb: 2 }}
            />

            {formError && (
              <Typography color="error" fontSize={13} sx={{ mb: 1 }}>{formError}</Typography>
            )}

            <Box sx={{ display: "flex", gap: 1.5 }}>
              <Button
                variant="contained"
                onClick={handleSubmitReview}
                disabled={submitting || !score}
                sx={{ borderRadius: 2 }}
              >
                {submitting ? t("saving", "Saving...") : t("submit", "Submit")}
              </Button>
              <Button variant="outlined" onClick={() => setShowForm(false)} sx={{ borderRadius: 2 }}>
                {t("cancel")}
              </Button>
            </Box>
          </Paper>
        )}

        {/* Reviews section */}
        <Paper variant="outlined" sx={{ p: 3, mb: 4, borderRadius: 3 }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
            <Typography fontWeight={700} fontSize={18}>
              {t("reviews", "Reviews")} ({reviews.length})
            </Typography>
            {!showForm && (
              <Tooltip title={myRating ? t("edit_review", "Edit review") : t("write_review", "Write review")}>
                <IconButton size="small" onClick={() => setShowForm(true)}>
                  <EditIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>

          {reviews.length === 0 ? (
            <Box sx={{ py: 4, textAlign: "center" }}>
              <Typography color="text.secondary">{t("no_reviews", "No reviews yet. Be the first to write one!")}</Typography>
              <Button variant="outlined" size="small" sx={{ mt: 2, borderRadius: 2 }} onClick={() => setShowForm(true)}>
                {t("write_review", "Write review")}
              </Button>
            </Box>
          ) : (
            reviews.map((review, i) => (
              <Box key={review.id}>
                <ReviewCard review={review} isOwn={review.user_id === user?.id} />
                {i < reviews.length - 1 && <Divider />}
              </Box>
            ))
          )}
        </Paper>

        {/* Chapters list */}
        {chapters.length > 0 && (
          <Paper variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
            <Typography fontWeight={700} fontSize={18} gutterBottom>
              {t("chapters")} ({chapters.length})
            </Typography>
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0 }}>
              {chapters.map((ch, i) => (
                <Box
                  key={ch.id}
                  onClick={() => navigate(`/read/${book.id}`)}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    py: 1.5,
                    px: 1,
                    borderRadius: 2,
                    cursor: "pointer",
                    bgcolor: progress?.current_chapter === ch.chapter_number ? "#f4f4f5" : "transparent",
                    "&:hover": { bgcolor: "#f4f4f5" },
                    borderBottom: i < chapters.length - 1 ? "1px solid" : "none",
                    borderColor: "grey.100",
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                    <Typography variant="caption" color="text.disabled" sx={{ minWidth: 24, textAlign: "right", fontWeight: 600 }}>
                      {ch.chapter_number}
                    </Typography>
                    <Typography variant="body2" fontWeight={progress?.current_chapter === ch.chapter_number ? 700 : 400}>
                      {ch.title || `${t("chapter")} ${ch.chapter_number}`}
                    </Typography>
                    {progress?.current_chapter === ch.chapter_number && (
                      <Chip label={t("current", "Current")} size="small" sx={{ bgcolor: "#000", color: "#fff", fontSize: 10, height: 20 }} />
                    )}
                  </Box>
                  <Typography variant="caption" color="text.disabled">
                    {ch.word_count?.toLocaleString()} {t("words")}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Paper>
        )}
      </Container>
    </AppLayout>
  );
}
