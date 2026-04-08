import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Card,
  CardMedia,
  CardContent,
  CardActionArea,
  Rating as MuiRating,
  Box,
  Button,
  CircularProgress,
  IconButton,
  Fab,
} from "@mui/material";
import LogoutIcon from "@mui/icons-material/Logout";
import PersonIcon from "@mui/icons-material/Person";
import LibraryBooksIcon from "@mui/icons-material/LibraryBooks";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import api from "../services/api";
import useAuthStore from "../store/authStore";
import LanguageSelector from "../components/LanguageSelector";
import type { Book } from "../types";

const BACKEND_URL = "http://localhost:8000";

interface Recommendation {
  id: number;
  title: string;
  author: string;
  genre: string | null;
  language: string;
  cover_url: string | null;
  description: string | null;
}

export default function HomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [trending, setTrending] = useState<Book[]>([]);
  const [topRated, setTopRated] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [recRes, trendRes, topRes] = await Promise.allSettled([
          api.get("/recommendations?n=10"),
          api.get("/ratings/trending"),
          api.get("/ratings/top"),
        ]);

        if (recRes.status === "fulfilled") {
          setRecommendations(recRes.value.data.recommendations || []);
        }
        if (trendRes.status === "fulfilled") {
          setTrending(trendRes.value.data);
        }
        if (topRes.status === "fulfilled") {
          setTopRated(topRes.value.data);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const BookCard = ({ book }: { book: Recommendation | Book }) => (
    <Card sx={{ minWidth: 160, maxWidth: 180, flexShrink: 0, height: "100%" }}>
      <CardActionArea onClick={() => navigate(`/book/${book.id}`)}>
        <CardMedia
          component="img"
          height="240"
          image={
            book.cover_url
              ? `${BACKEND_URL}${book.cover_url}`
              : "/placeholder-cover.png"
          }
          alt={book.title}
          sx={{ objectFit: "cover" }}
        />
        <CardContent sx={{ p: 1.5 }}>
          <Typography variant="subtitle2" noWrap title={book.title}>
            {book.title}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap>
            {book.author}
          </Typography>
          {"avg_rating" in book && (
            <Box sx={{ display: "flex", alignItems: "center", mt: 0.5 }}>
              <MuiRating
                value={(book as Book).avg_rating ?? 0}
                precision={0.5}
                size="small"
                readOnly
              />
            </Box>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );

  const HorizontalScroll = ({
    title,
    items,
    emptyMessage,
  }: {
    title: string;
    items: (Recommendation | Book)[];
    emptyMessage?: string;
  }) => (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h5" gutterBottom>
        {title}
      </Typography>
      {items.length === 0 ? (
        <Typography color="text.secondary" sx={{ py: 2 }}>
          {emptyMessage || t("no_books")}
        </Typography>
      ) : (
        <Box
          sx={{
            display: "flex",
            gap: 2,
            overflowX: "auto",
            pb: 1,
            "&::-webkit-scrollbar": { height: 6 },
            "&::-webkit-scrollbar-thumb": { bgcolor: "grey.400", borderRadius: 3 },
          }}
        >
          {items.map((item) => (
            <BookCard key={item.id} book={item} />
          ))}
        </Box>
      )}
    </Box>
  );

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "grey.50" }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {t("app_name")}
          </Typography>
          <Button
            color="inherit"
            startIcon={<SmartToyIcon />}
            onClick={() => navigate("/assistant")}
            sx={{ mr: 1 }}
          >
            {t("ai_assistant")}
          </Button>
          <Button
            color="inherit"
            startIcon={<LibraryBooksIcon />}
            onClick={() => navigate("/library")}
            sx={{ mr: 1 }}
          >
            {t("library")}
          </Button>
          <Box sx={{ mr: 1 }}>
            <LanguageSelector />
          </Box>
          <IconButton color="inherit" onClick={() => navigate("/profile")} title={t("profile")}>
            <PersonIcon />
          </IconButton>
          <Typography sx={{ mr: 1, ml: 0.5 }}>{user?.username}</Typography>
          <Button
            color="inherit"
            onClick={() => {
              logout();
              navigate("/login");
            }}
            startIcon={<LogoutIcon />}
          >
            {t("logout")}
          </Button>
        </Toolbar>
      </AppBar>

      <Container sx={{ py: 4 }}>
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <HorizontalScroll
              title={t("recommended_for_you")}
              items={recommendations}
              emptyMessage={t("rate_books_for_recommendations")}
            />
            <HorizontalScroll
              title={t("trending")}
              items={trending}
            />
            <HorizontalScroll
              title={t("top_rated")}
              items={topRated}
            />
          </>
        )}
      </Container>

      {/* FAB for AI Assistant */}
      <Fab
        color="primary"
        onClick={() => navigate("/assistant")}
        sx={{ position: "fixed", bottom: 24, right: 24 }}
        title={t("ai_assistant")}
      >
        <SmartToyIcon />
      </Fab>
    </Box>
  );
}
