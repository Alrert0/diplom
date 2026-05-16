import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Card,
  CardMedia,
  CardContent,
  CardActionArea,
  Rating as MuiRating,
  CircularProgress,
  IconButton,
  Chip,
  TextField,
  InputAdornment,
} from "@mui/material";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import SearchIcon from "@mui/icons-material/Search";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import StarIcon from "@mui/icons-material/Star";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import api from "../services/api";
import useAuthStore from "../store/authStore";
import AppLayout from "../components/layout/AppLayout";
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

type AnyBook = Recommendation | Book;

function BookCard({ book }: { book: AnyBook }) {
  const navigate = useNavigate();
  return (
    <Card
      sx={{
        width: 150,
        flexShrink: 0,
        borderRadius: 3,
        boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
        transition: "transform 0.2s, box-shadow 0.2s",
        "&:hover": { transform: "translateY(-4px)", boxShadow: "0 8px 24px rgba(0,0,0,0.14)" },
      }}
    >
      <CardActionArea onClick={() => navigate(`/book/${book.id}`)}>
        <CardMedia
          component="img"
          height={210}
          image={book.cover_url ? `${BACKEND_URL}${book.cover_url}` : "/placeholder-cover.png"}
          alt={book.title}
          sx={{ objectFit: "cover" }}
        />
        <CardContent sx={{ p: 1.5, pb: "12px !important" }}>
          <Typography variant="subtitle2" noWrap fontWeight={600} fontSize={13} title={book.title}>
            {book.title}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap display="block" fontSize={11}>
            {book.author}
          </Typography>
          {"avg_rating" in book && (book as Book).avg_rating != null && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.3, mt: 0.5 }}>
              <StarIcon sx={{ fontSize: 12, color: "#F59E0B" }} />
              <Typography variant="caption" fontWeight={600} fontSize={11} color="text.secondary">
                {(book as Book).avg_rating?.toFixed(1)}
              </Typography>
            </Box>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );
}

function BookRow({ title, icon, items, seeAllPath }: {
  title: string;
  icon: React.ReactNode;
  items: AnyBook[];
  seeAllPath?: string;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const rowRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: "left" | "right") => {
    if (rowRef.current) {
      rowRef.current.scrollBy({ left: dir === "right" ? 340 : -340, behavior: "smooth" });
    }
  };

  if (items.length === 0) return null;

  return (
    <Box sx={{ mb: 4 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          {icon}
          <Typography variant="h6" fontWeight={700} fontSize={18}>{title}</Typography>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          {seeAllPath && (
            <Typography
              variant="body2"
              color="primary"
              sx={{ cursor: "pointer", mr: 1, fontWeight: 500, "&:hover": { textDecoration: "underline" } }}
              onClick={() => navigate(seeAllPath)}
            >
              {t("view_all", "View all")}
            </Typography>
          )}
          <IconButton size="small" onClick={() => scroll("left")} sx={{ bgcolor: "#fff", boxShadow: 1, "&:hover": { bgcolor: "grey.100" } }}>
            <ChevronLeftIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={() => scroll("right")} sx={{ bgcolor: "#fff", boxShadow: 1, "&:hover": { bgcolor: "grey.100" } }}>
            <ChevronRightIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      <Box
        ref={rowRef}
        sx={{
          display: "flex",
          gap: 2,
          overflowX: "auto",
          pb: 1,
          scrollbarWidth: "none",
          "&::-webkit-scrollbar": { display: "none" },
        }}
      >
        {items.map((item) => <BookCard key={item.id} book={item} />)}
      </Box>
    </Box>
  );
}

export default function HomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [trending, setTrending] = useState<Book[]>([]);
  const [topRated, setTopRated] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [recRes, trendRes, topRes] = await Promise.allSettled([
          api.get("/recommendations?n=12"),
          api.get("/ratings/trending"),
          api.get("/ratings/top"),
        ]);
        if (recRes.status === "fulfilled") setRecommendations(recRes.value.data.recommendations || []);
        if (trendRes.status === "fulfilled") setTrending(trendRes.value.data);
        if (topRes.status === "fulfilled") setTopRated(topRes.value.data);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSearch = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && search.trim()) {
      navigate(`/library?q=${encodeURIComponent(search.trim())}`);
    }
  };

  const hour = new Date().getHours();
  const greeting = hour < 12 ? t("good_morning", "Good morning") : hour < 17 ? t("good_afternoon", "Good afternoon") : t("good_evening", "Good evening");

  return (
    <AppLayout>
      <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1200 }}>
        {/* Header */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h4" fontWeight={800} gutterBottom sx={{ color: "text.primary" }}>
            {greeting}, {user?.username} 👋
          </Typography>
          <Typography color="text.secondary" fontSize={15}>
            {t("discover_subtitle", "Discover your next favourite book")}
          </Typography>
        </Box>

        {/* Search bar */}
        <Box sx={{ mb: 4, display: "flex", gap: 2, flexWrap: "wrap", alignItems: "center" }}>
          <TextField
            placeholder={t("search_books")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={handleSearch}
            size="small"
            sx={{
              flexGrow: 1,
              maxWidth: 480,
              bgcolor: "#fff",
              borderRadius: 3,
              "& .MuiOutlinedInput-root": { borderRadius: 3 },
            }}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon color="action" />
                  </InputAdornment>
                ),
              },
            }}
          />
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            {["fiction", "science", "mystery", "philosophy"].map((g) => (
              <Chip
                key={g}
                label={g.charAt(0).toUpperCase() + g.slice(1)}
                size="small"
                onClick={() => navigate(`/library?genre=${g}`)}
                sx={{ bgcolor: "#fff", border: "1px solid #e4e4e7", "&:hover": { bgcolor: "#000", color: "#fff", borderColor: "#000" }, cursor: "pointer", transition: "all 0.15s" }}
              />
            ))}
          </Box>
        </Box>

        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <BookRow
              title={t("recommended_for_you")}
              icon={<AutoAwesomeIcon sx={{ color: "#000", fontSize: 20 }} />}
              items={recommendations}
              seeAllPath="/library"
            />
            <BookRow
              title={t("trending")}
              icon={<TrendingUpIcon sx={{ color: "#000", fontSize: 20 }} />}
              items={trending}
              seeAllPath="/library"
            />
            <BookRow
              title={t("top_rated")}
              icon={<StarIcon sx={{ color: "#000", fontSize: 20 }} />}
              items={topRated}
              seeAllPath="/library"
            />
          </>
        )}
      </Box>
    </AppLayout>
  );
}
