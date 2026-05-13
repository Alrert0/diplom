import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  AppBar,
  Toolbar,
  Typography,
  Container,
  Grid,
  Card,
  CardMedia,
  CardContent,
  CardActionArea,
  Rating,
  Box,
  Button,
  IconButton,
  CircularProgress,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from "@mui/material";
import LogoutIcon from "@mui/icons-material/Logout";
import HomeIcon from "@mui/icons-material/Home";
import PersonIcon from "@mui/icons-material/Person";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import api from "../services/api";
import useAuthStore from "../store/authStore";
import LanguageSelector from "../components/LanguageSelector";
import type { Book } from "../types";

const BACKEND_URL = "http://localhost:8000";

export default function LibraryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [genreFilter, setGenreFilter] = useState("");
  const [langFilter, setLangFilter] = useState("");

  useEffect(() => {
    api
      .get("/books")
      .then((res) => setBooks(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const genres = Array.from(new Set(books.map((b) => b.genre).filter(Boolean))) as string[];
  const languages = Array.from(new Set(books.map((b) => b.language).filter(Boolean))) as string[];

  const filtered = books.filter((book) => {
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      book.title.toLowerCase().includes(q) ||
      book.author.toLowerCase().includes(q);
    const matchGenre = !genreFilter || book.genre === genreFilter;
    const matchLang = !langFilter || book.language === langFilter;
    return matchSearch && matchGenre && matchLang;
  });

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "grey.50" }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {t("app_name")}
          </Typography>
          <Button color="inherit" startIcon={<HomeIcon />} onClick={() => navigate("/")} sx={{ mr: 1 }}>
            {t("home")}
          </Button>
          <Button color="inherit" startIcon={<SmartToyIcon />} onClick={() => navigate("/assistant")} sx={{ mr: 1 }}>
            {t("ai_assistant")}
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
        <Typography variant="h4" gutterBottom>
          {t("library")}
        </Typography>

        {/* Search & filters */}
        <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap", alignItems: "center" }}>
          <TextField
            size="small"
            placeholder={t("search_books")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ flexGrow: 1, minWidth: 200 }}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
                endAdornment: search ? (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setSearch("")}>
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ) : null,
              },
            }}
          />

          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>{t("genre")}</InputLabel>
            <Select
              value={genreFilter}
              label={t("genre")}
              onChange={(e) => setGenreFilter(e.target.value)}
            >
              <MenuItem value="">{t("all")}</MenuItem>
              {genres.map((g) => (
                <MenuItem key={g} value={g}>{g}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel>{t("language")}</InputLabel>
            <Select
              value={langFilter}
              label={t("language")}
              onChange={(e) => setLangFilter(e.target.value)}
            >
              <MenuItem value="">{t("all")}</MenuItem>
              {languages.map((l) => (
                <MenuItem key={l} value={l}>{l.toUpperCase()}</MenuItem>
              ))}
            </Select>
          </FormControl>

          {(search || genreFilter || langFilter) && (
            <Typography variant="body2" color="text.secondary">
              {t("found_books", { count: filtered.length })}
            </Typography>
          )}
        </Box>

        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        ) : filtered.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 8, textAlign: "center" }}>
            {search || genreFilter || langFilter ? t("no_results") : t("no_books")}
          </Typography>
        ) : (
          <Grid container spacing={3}>
            {filtered.map((book) => (
              <Grid size={{ xs: 6, sm: 4, md: 3, lg: 2 }} key={book.id}>
                <Card sx={{ height: "100%" }}>
                  <CardActionArea onClick={() => navigate(`/book/${book.id}`)}>
                    <CardMedia
                      component="img"
                      height="280"
                      image={
                        book.cover_url
                          ? `${BACKEND_URL}${book.cover_url}`
                          : "/placeholder-cover.png"
                      }
                      alt={book.title}
                      sx={{ objectFit: "cover" }}
                    />
                    <CardContent>
                      <Typography
                        variant="subtitle2"
                        noWrap
                        title={book.title}
                      >
                        {book.title}
                      </Typography>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        noWrap
                      >
                        {book.author}
                      </Typography>
                      <Box sx={{ display: "flex", alignItems: "center", mt: 0.5 }}>
                        <Rating
                          value={book.avg_rating ?? 0}
                          precision={0.5}
                          size="small"
                          readOnly
                        />
                        <Typography variant="caption" sx={{ ml: 0.5 }}>
                          ({book.ratings_count})
                        </Typography>
                      </Box>
                    </CardContent>
                  </CardActionArea>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Container>
    </Box>
  );
}
