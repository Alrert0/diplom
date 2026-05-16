import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Typography,
  Container,
  Box,
  Paper,
  Grid,
  Button,
  CircularProgress,
  Chip,
  Avatar,
  LinearProgress,
  Card,
  CardActionArea,
  CardMedia,
  CardContent,
  IconButton,
  Collapse,
  Divider,
  Tooltip,
} from "@mui/material";
import AppLayout from "../components/layout/AppLayout";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import SpeedIcon from "@mui/icons-material/Speed";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import StarIcon from "@mui/icons-material/Star";
import GroupIcon from "@mui/icons-material/Group";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import DeleteIcon from "@mui/icons-material/Delete";
import { HIGHLIGHT_COLORS } from "../components/reader/HighlightPopup";
import {
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
} from "recharts";
import api from "../services/api";
import useAuthStore from "../store/authStore";

const BACKEND_URL = "http://localhost:8000";

interface UserStats {
  total_books: number;
  total_words_read: number;
  total_reading_hours: number;
  total_sessions: number;
  avg_speed_wpm: number;
  total_ratings: number;
  avg_rating_given: number;
  cluster: number | null;
  genre_counts: Record<string, number>;
}

interface BookProgress {
  book_id: number;
  title: string;
  author: string;
  cover_url: string | null;
  current_chapter: number;
  total_chapters: number;
  percent: number;
  last_read_at: string | null;
}

interface ClusterData {
  points: { user_id: number; x: number; y: number; cluster: number }[];
  k: number;
}

interface HighlightWithBook {
  id: number;
  book_id: number;
  cfi_range: string;
  text: string;
  color: string;
  note: string | null;
  created_at: string;
  book_title: string;
  book_author: string;
  book_cover_url: string | null;
}

const CLUSTER_NAMES: Record<number, { en: string; ru: string; kk: string }> = {
  0: { en: "Casual Reader", ru: "Обычный читатель", kk: "Қарапайым оқырман" },
  1: { en: "Speed Reader", ru: "Скоростной читатель", kk: "Жылдам оқырман" },
  2: { en: "Deep Thinker", ru: "Глубокий мыслитель", kk: "Терең ойшыл" },
  3: { en: "Diverse Explorer", ru: "Разносторонний исследователь", kk: "Алуан қырлы зерттеуші" },
  4: { en: "Genre Specialist", ru: "Жанровый специалист", kk: "Жанр маманы" },
  5: { en: "Avid Critic", ru: "Заядлый критик", kk: "Белсенді сыншы" },
};

const PIE_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1", "#a4de6c", "#d084d0", "#ffb347"];
const CLUSTER_COLORS = PIE_COLORS;

export default function ProfilePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [stats, setStats] = useState<UserStats | null>(null);
  const [inProgress, setInProgress] = useState<BookProgress[]>([]);
  const [clusterData, setClusterData] = useState<ClusterData | null>(null);
  const [allHighlights, setAllHighlights] = useState<HighlightWithBook[]>([]);
  const [expandedBooks, setExpandedBooks] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);

  const lang = (i18n.language || "en").slice(0, 2) as "en" | "ru" | "kk";

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, progressRes, clusterRes, hlRes] = await Promise.allSettled([
          api.get("/reading/stats"),
          api.get("/reading/in-progress"),
          api.get("/ml/clustering-visualization"),
          api.get("/highlights"),
        ]);
        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
        if (progressRes.status === "fulfilled") setInProgress(progressRes.value.data);
        if (clusterRes.status === "fulfilled") setClusterData(clusterRes.value.data);
        if (hlRes.status === "fulfilled") {
          setAllHighlights(hlRes.value.data || []);
          // Auto-expand first book
          const firstBookId = hlRes.value.data?.[0]?.book_id;
          if (firstBookId) setExpandedBooks(new Set([firstBookId]));
        }
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const getClusterName = (cluster: number | null) => {
    if (cluster === null) return t("no_cluster");
    const names = CLUSTER_NAMES[cluster] || CLUSTER_NAMES[0];
    return names[lang] || names.en;
  };

  const genreData = stats?.genre_counts
    ? Object.entries(stats.genre_counts).map(([name, value]) => ({ name, value }))
    : [];

  // Group highlights by book
  const highlightsByBook = allHighlights.reduce<Record<number, HighlightWithBook[]>>((acc, h) => {
    if (!acc[h.book_id]) acc[h.book_id] = [];
    acc[h.book_id].push(h);
    return acc;
  }, {});

  const toggleBook = (bookId: number) => {
    setExpandedBooks((prev) => {
      const next = new Set(prev);
      if (next.has(bookId)) next.delete(bookId);
      else next.add(bookId);
      return next;
    });
  };

  const handleDeleteHighlight = async (id: number) => {
    try {
      await api.delete(`/highlights/${id}`);
      setAllHighlights((prev) => prev.filter((h) => h.id !== id));
    } catch {}
  };

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <AppLayout>

      <Container sx={{ py: 4 }}>
        {/* User header */}
        <Paper sx={{ p: 3, mb: 3, display: "flex", alignItems: "center", gap: 2 }}>
          <Avatar sx={{ width: 64, height: 64, bgcolor: "primary.main", fontSize: 28 }}>
            {user?.username?.[0]?.toUpperCase() || "U"}
          </Avatar>
          <Box>
            <Typography variant="h5">{user?.username}</Typography>
            <Typography variant="body2" color="text.secondary">{user?.email}</Typography>
            {stats?.cluster !== null && stats?.cluster !== undefined && (
              <Chip
                icon={<GroupIcon />}
                label={getClusterName(stats.cluster)}
                color="primary"
                variant="outlined"
                sx={{ mt: 1 }}
              />
            )}
          </Box>
        </Paper>

        {/* Stats cards */}
        <Grid container spacing={2} sx={{ mb: 4 }}>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 2, textAlign: "center" }}>
              <MenuBookIcon color="primary" sx={{ fontSize: 32 }} />
              <Typography variant="h4">{stats?.total_books ?? 0}</Typography>
              <Typography variant="caption" color="text.secondary">{t("books_read")}</Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 2, textAlign: "center" }}>
              <AccessTimeIcon color="primary" sx={{ fontSize: 32 }} />
              <Typography variant="h4">{stats?.total_reading_hours ?? 0}</Typography>
              <Typography variant="caption" color="text.secondary">{t("hours_read")}</Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 2, textAlign: "center" }}>
              <SpeedIcon color="primary" sx={{ fontSize: 32 }} />
              <Typography variant="h4">{stats?.avg_speed_wpm ?? 200}</Typography>
              <Typography variant="caption" color="text.secondary">{t("avg_wpm")}</Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 2, textAlign: "center" }}>
              <StarIcon color="primary" sx={{ fontSize: 32 }} />
              <Typography variant="h4">{stats?.avg_rating_given?.toFixed(1) ?? "—"}</Typography>
              <Typography variant="caption" color="text.secondary">{t("avg_rating_given")}</Typography>
            </Paper>
          </Grid>
        </Grid>

        {/* Currently reading */}
        {inProgress.length > 0 && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              {t("currently_reading")}
            </Typography>
            <Grid container spacing={2}>
              {inProgress.map((item) => (
                <Grid size={{ xs: 12, sm: 6, md: 4 }} key={item.book_id}>
                  <Card variant="outlined">
                    <CardActionArea
                      onClick={() => navigate(`/read/${item.book_id}`)}
                      sx={{ display: "flex", alignItems: "flex-start", p: 1, gap: 1.5 }}
                    >
                      <CardMedia
                        component="img"
                        image={item.cover_url ? `${BACKEND_URL}${item.cover_url}` : "/placeholder-cover.png"}
                        alt={item.title}
                        sx={{ width: 60, height: 90, objectFit: "cover", borderRadius: 1, flexShrink: 0 }}
                      />
                      <CardContent sx={{ p: 0, flex: 1, minWidth: 0 }}>
                        <Typography variant="subtitle2" noWrap title={item.title}>
                          {item.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" noWrap>
                          {item.author}
                        </Typography>
                        <Box sx={{ mt: 1 }}>
                          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                              {t("chapter")} {item.current_chapter}/{item.total_chapters}
                            </Typography>
                            <Typography variant="caption" color="primary" fontWeight={600}>
                              {item.percent}%
                            </Typography>
                          </Box>
                          <LinearProgress
                            variant="determinate"
                            value={item.percent}
                            sx={{ borderRadius: 2, height: 6 }}
                          />
                        </Box>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Paper>
        )}

        {/* My Highlights / Quotes */}
        {allHighlights.length > 0 && (
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
              <FormatQuoteIcon color="primary" />
              <Typography variant="h6">
                {t("my_highlights")} ({allHighlights.length})
              </Typography>
            </Box>

            {Object.entries(highlightsByBook).map(([bookIdStr, items]) => {
              const bookId = parseInt(bookIdStr);
              const first = items[0];
              const isExpanded = expandedBooks.has(bookId);

              return (
                <Box key={bookId} sx={{ mb: 1.5 }}>
                  {/* Book header row */}
                  <Box
                    onClick={() => toggleBook(bookId)}
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1.5,
                      p: 1.5,
                      borderRadius: 2,
                      cursor: "pointer",
                      bgcolor: "#f8f8f8",
                      "&:hover": { bgcolor: "#f0f0f0" },
                    }}
                  >
                    <Box
                      component="img"
                      src={first.book_cover_url ? `${BACKEND_URL}${first.book_cover_url}` : "/placeholder-cover.png"}
                      alt={first.book_title}
                      sx={{ width: 36, height: 54, objectFit: "cover", borderRadius: 1, flexShrink: 0 }}
                    />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="subtitle2" noWrap fontWeight={600}>
                        {first.book_title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" noWrap>
                        {first.book_author}
                      </Typography>
                    </Box>
                    <Chip
                      label={items.length}
                      size="small"
                      sx={{ bgcolor: "#000", color: "#fff", fontWeight: 700, minWidth: 28 }}
                    />
                    <IconButton size="small">
                      {isExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                    </IconButton>
                  </Box>

                  {/* Highlights list */}
                  <Collapse in={isExpanded}>
                    <Box sx={{ pl: 2, pt: 1, pb: 0.5 }}>
                      {items.map((h, i) => {
                        const colorInfo = HIGHLIGHT_COLORS[h.color] || HIGHLIGHT_COLORS.yellow;
                        return (
                          <Box key={h.id}>
                            <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1.5, py: 1.5 }}>
                              {/* Color strip */}
                              <Box
                                sx={{
                                  width: 4,
                                  minHeight: 36,
                                  borderRadius: 2,
                                  bgcolor: colorInfo.hex,
                                  flexShrink: 0,
                                  mt: 0.5,
                                }}
                              />
                              <Box sx={{ flex: 1, minWidth: 0 }}>
                                <Typography
                                  variant="body2"
                                  sx={{
                                    lineHeight: 1.7,
                                    bgcolor: colorInfo.hex + "44",
                                    px: 1.5,
                                    py: 0.75,
                                    borderRadius: 1.5,
                                    cursor: "pointer",
                                    "&:hover": { opacity: 0.85 },
                                  }}
                                  onClick={() => navigate(`/read/${h.book_id}`)}
                                >
                                  "{h.text}"
                                </Typography>
                                <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5, display: "block" }}>
                                  {new Date(h.created_at).toLocaleDateString()}
                                </Typography>
                              </Box>
                              <Tooltip title={t("delete")}>
                                <IconButton
                                  size="small"
                                  onClick={() => handleDeleteHighlight(h.id)}
                                  sx={{ color: "text.disabled", "&:hover": { color: "error.main" }, flexShrink: 0 }}
                                >
                                  <DeleteIcon sx={{ fontSize: 16 }} />
                                </IconButton>
                              </Tooltip>
                            </Box>
                            {i < items.length - 1 && <Divider sx={{ ml: 2 }} />}
                          </Box>
                        );
                      })}
                      <Box sx={{ pb: 0.5 }}>
                        <Button
                          size="small"
                          onClick={() => navigate(`/read/${bookId}`)}
                          sx={{ color: "text.secondary", fontSize: 12 }}
                        >
                          {t("open_book")} →
                        </Button>
                      </Box>
                    </Box>
                  </Collapse>
                </Box>
              );
            })}
          </Paper>
        )}

        {/* Charts */}
        <Grid container spacing={3}>
          {/* Cluster visualization */}
          {clusterData && clusterData.points.length > 0 && (
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>{t("reader_clusters")}</Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <ScatterChart>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="x" name="t-SNE 1" type="number" />
                    <YAxis dataKey="y" name="t-SNE 2" type="number" />
                    <ZAxis range={[40, 40]} />
                    <ChartTooltip
                      formatter={(_: unknown, name: string, props: { payload?: { user_id?: number; cluster?: number } }) => {
                        if (name === "x") return [props.payload?.user_id, "User"];
                        return [props.payload?.cluster, "Cluster"];
                      }}
                    />
                    {Array.from({ length: clusterData.k }, (_, i) => (
                      <Scatter
                        key={i}
                        name={getClusterName(i)}
                        data={clusterData.points.filter((p) => p.cluster === i)}
                        fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]}
                      />
                    ))}
                    <Legend />
                  </ScatterChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
          )}

          {/* Genre pie — only show if we have real data */}
          {genreData.length > 0 && (
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>{t("genre_distribution")}</Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie data={genreData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                      {genreData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <ChartTooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </Paper>
            </Grid>
          )}

          {/* Empty state when no reading activity */}
          {inProgress.length === 0 && !clusterData?.points?.length && (
            <Grid size={{ xs: 12 }}>
              <Paper sx={{ p: 4, textAlign: "center" }}>
                <MenuBookIcon sx={{ fontSize: 64, color: "text.disabled", mb: 1 }} />
                <Typography color="text.secondary">{t("no_reading_activity")}</Typography>
                <Button variant="contained" sx={{ mt: 2 }} onClick={() => navigate("/library")}>
                  {t("go_to_library")}
                </Button>
              </Paper>
            </Grid>
          )}
        </Grid>
      </Container>
    </AppLayout>
  );
}
