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
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import SpeedIcon from "@mui/icons-material/Speed";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import StarIcon from "@mui/icons-material/Star";
import GroupIcon from "@mui/icons-material/Group";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";
import api from "../services/api";
import useAuthStore from "../store/authStore";

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
  6: { en: "Night Owl", ru: "Полуночник", kk: "Түнгі құс" },
  7: { en: "Weekend Warrior", ru: "Читатель выходного дня", kk: "Демалыс оқырманы" },
};

const PIE_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1", "#a4de6c", "#d084d0", "#ffb347"];
const CLUSTER_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7c7c", "#8dd1e1", "#a4de6c", "#d084d0", "#ffb347"];

export default function ProfilePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [stats, setStats] = useState<UserStats | null>(null);
  const [clusterData, setClusterData] = useState<ClusterData | null>(null);
  const [loading, setLoading] = useState(true);

  const lang = (i18n.language || "en").slice(0, 2) as "en" | "ru" | "kk";

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, clusterRes] = await Promise.allSettled([
          api.get("/reading/stats"),
          api.get("/ml/clustering-visualization"),
        ]);
        if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
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

  // Mock genre distribution from stats (we'd need a separate endpoint for real data)
  const genreData = [
    { name: "Fiction", value: 40 },
    { name: "Science", value: 20 },
    { name: "History", value: 15 },
    { name: "Fantasy", value: 15 },
    { name: "Other", value: 10 },
  ];

  // Mock monthly reading data
  const monthlyData = [
    { month: "Oct", books: 2 },
    { month: "Nov", books: 3 },
    { month: "Dec", books: 1 },
    { month: "Jan", books: 4 },
    { month: "Feb", books: 2 },
    { month: "Mar", books: 3 },
  ];

  // Mock speed over time
  const speedData = [
    { session: 1, wpm: 180 },
    { session: 5, wpm: 195 },
    { session: 10, wpm: 210 },
    { session: 15, wpm: 220 },
    { session: 20, wpm: 235 },
    { session: 25, wpm: 240 },
  ];

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
              <Typography variant="caption" color="text.secondary">
                {t("books_read")}
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 2, textAlign: "center" }}>
              <AccessTimeIcon color="primary" sx={{ fontSize: 32 }} />
              <Typography variant="h4">{stats?.total_reading_hours ?? 0}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t("hours_read")}
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 2, textAlign: "center" }}>
              <SpeedIcon color="primary" sx={{ fontSize: 32 }} />
              <Typography variant="h4">{stats?.avg_speed_wpm ?? 200}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t("avg_wpm")}
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 6, sm: 3 }}>
            <Paper sx={{ p: 2, textAlign: "center" }}>
              <StarIcon color="primary" sx={{ fontSize: 32 }} />
              <Typography variant="h4">{stats?.avg_rating_given?.toFixed(1) ?? "—"}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t("avg_rating_given")}
              </Typography>
            </Paper>
          </Grid>
        </Grid>

        {/* Charts */}
        <Grid container spacing={3}>
          {/* Books per month */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t("books_per_month")}
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={monthlyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="books" fill="#8884d8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>

          {/* Genre distribution */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t("genre_distribution")}
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={genreData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {genreData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>

          {/* Reading speed over time */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t("speed_over_time")}
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={speedData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="session" label={{ value: t("session"), position: "insideBottom", offset: -5 }} />
                  <YAxis label={{ value: t("wpm"), angle: -90, position: "insideLeft" }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="wpm" stroke="#82ca9d" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </Paper>
          </Grid>

          {/* Cluster visualization */}
          <Grid size={{ xs: 12, md: 6 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom>
                {t("reader_clusters")}
              </Typography>
              {clusterData && clusterData.points.length > 0 ? (
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
              ) : (
                <Typography color="text.secondary" sx={{ py: 4, textAlign: "center" }}>
                  {t("not_enough_data_for_clusters")}
                </Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}
