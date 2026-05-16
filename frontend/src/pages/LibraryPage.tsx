import { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Typography,
  Container,
  Grid,
  Card,
  CardMedia,
  CardContent,
  CardActionArea,
  Rating,
  Box,
  IconButton,
  CircularProgress,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Pagination,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import AppLayout from "../components/layout/AppLayout";
import api from "../services/api";
import type { Book } from "../types";

const BACKEND_URL = "http://localhost:8000";
const LIMIT = 24;

interface BooksPage {
  items: Book[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export default function LibraryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [data, setData] = useState<BooksPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [genreFilter, setGenreFilter] = useState(searchParams.get("genre") || "");
  const [langFilter, setLangFilter] = useState("");
  const [page, setPage] = useState(1);

  // All genres/languages for filter dropdowns (loaded once)
  const [allGenres, setAllGenres] = useState<string[]>([]);
  const [allLanguages, setAllLanguages] = useState<string[]>([]);

  const fetchBooks = useCallback(async (p: number, q: string, genre: string, lang: string) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page: p, limit: LIMIT };
      if (q) params.q = q;
      if (genre) params.genre = genre;
      if (lang) params.language = lang;
      const res = await api.get("/books", { params });
      setData(res.data);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load genres/languages for filters from first full fetch
  useEffect(() => {
    api.get("/books", { params: { page: 1, limit: 200 } }).then((res) => {
      const items: Book[] = res.data.items || [];
      setAllGenres(Array.from(new Set(items.map((b) => b.genre).filter(Boolean))) as string[]);
      setAllLanguages(Array.from(new Set(items.map((b) => b.language).filter(Boolean))) as string[]);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    fetchBooks(page, search, genreFilter, langFilter);
  }, [page, genreFilter, langFilter, fetchBooks]);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setPage(1);
      fetchBooks(1, search, genreFilter, langFilter);
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  const handlePageChange = (_: React.ChangeEvent<unknown>, value: number) => {
    setPage(value);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const books = data?.items || [];

  return (
    <AppLayout>
      <Container sx={{ py: 4 }}>
        <Typography variant="h4" fontWeight={800} gutterBottom>
          {t("library")}
        </Typography>

        {/* Search & filters */}
        <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap", alignItems: "center" }}>
          <TextField
            size="small"
            placeholder={t("search_books")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ flexGrow: 1, minWidth: 200, bgcolor: "#fff", "& .MuiOutlinedInput-root": { borderRadius: 2 } }}
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
            <Select value={genreFilter} label={t("genre")} onChange={(e) => { setGenreFilter(e.target.value); setPage(1); }}>
              <MenuItem value="">{t("all")}</MenuItem>
              {allGenres.map((g) => <MenuItem key={g} value={g}>{g}</MenuItem>)}
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel>{t("language")}</InputLabel>
            <Select value={langFilter} label={t("language")} onChange={(e) => { setLangFilter(e.target.value); setPage(1); }}>
              <MenuItem value="">{t("all")}</MenuItem>
              {allLanguages.map((l) => <MenuItem key={l} value={l}>{l.toUpperCase()}</MenuItem>)}
            </Select>
          </FormControl>

          {data && (
            <Typography variant="body2" color="text.secondary" sx={{ ml: "auto" }}>
              {t("found_books", { count: data.total })}
            </Typography>
          )}
        </Box>

        {/* Books grid */}
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
            <CircularProgress sx={{ color: "#000" }} />
          </Box>
        ) : books.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 8, textAlign: "center" }}>
            {search || genreFilter || langFilter ? t("no_results") : t("no_books")}
          </Typography>
        ) : (
          <>
            <Grid container spacing={2.5}>
              {books.map((book) => (
                <Grid size={{ xs: 6, sm: 4, md: 3, lg: 2 }} key={book.id}>
                  <Card sx={{
                    height: "100%",
                    borderRadius: 3,
                    boxShadow: "0 2px 12px rgba(0,0,0,0.07)",
                    transition: "transform 0.2s, box-shadow 0.2s",
                    "&:hover": { transform: "translateY(-4px)", boxShadow: "0 8px 24px rgba(0,0,0,0.13)" },
                  }}>
                    <CardActionArea onClick={() => navigate(`/book/${book.id}`)}>
                      <CardMedia
                        component="img"
                        height="230"
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
                        <Box sx={{ display: "flex", alignItems: "center", mt: 0.5 }}>
                          <Rating value={book.avg_rating ?? 0} precision={0.5} size="small" readOnly />
                          <Typography variant="caption" sx={{ ml: 0.5, fontSize: 11 }}>
                            ({book.ratings_count})
                          </Typography>
                        </Box>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                </Grid>
              ))}
            </Grid>

            {/* Pagination */}
            {data && data.pages > 1 && (
              <Box sx={{ display: "flex", justifyContent: "center", mt: 5 }}>
                <Pagination
                  count={data.pages}
                  page={page}
                  onChange={handlePageChange}
                  size="large"
                  sx={{
                    "& .MuiPaginationItem-root": { borderRadius: 2 },
                    "& .Mui-selected": { bgcolor: "#000 !important", color: "#fff" },
                  }}
                />
              </Box>
            )}
          </>
        )}
      </Container>
    </AppLayout>
  );
}
