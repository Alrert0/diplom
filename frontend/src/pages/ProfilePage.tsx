import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AppBar,
  Toolbar,
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
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import SpeedIcon from "@mui/icons-material/Speed";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import StarIcon from "@mui/icons-material/Star";
import GroupIcon from "@mui/icons-material/Group";
import {
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
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
  const [loading, setLoading] = useState(true);

  const lang = (i18n.language || "en").slice(0, 2) as "en" | "ru" | "kk";

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, progressRes, clusterRes] = await Promise.allSettled([
          api.get("/reading/stats"),
          api.get("/reading/in-progress"),
          api.get("/ml/clustering-visualization"),
        ]);
        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
        if (progressRes.status === "fulfilled") setInProgress(progressRes.value.data);
        if (clusterRes.status === "fulfilled") setClusterData(clusterRes.value.data);
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

  const genreData = (() => {
    const counts: Record<string, number> = {};
    inProgress.forEach(() => {});
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  })();

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "grey.50" }}>
      <AppBar position="static">
        <Toolbar>
          <Button color="inherit" startIcon={<ArrowBackIcon />} onClick={() => navigate("/")}>
            {t("back")}
          </Button>
          <Typography variant="h6" sx={{ flexGrow: 1, ml: 2 }}>
            {t("profile")}
          </Typography>
        </Toolbar>
      </AppBar>

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
                    <Tooltip
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
                    <Tooltip />
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
    </Box>
  );
}
