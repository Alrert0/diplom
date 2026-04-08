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
} from "@mui/material";
import LogoutIcon from "@mui/icons-material/Logout";
import HomeIcon from "@mui/icons-material/Home";
import PersonIcon from "@mui/icons-material/Person";
import SmartToyIcon from "@mui/icons-material/SmartToy";
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

  useEffect(() => {
    api
      .get("/books")
      .then((res) => setBooks(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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

        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
            <CircularProgress />
          </Box>
        ) : books.length === 0 ? (
          <Typography color="text.secondary" sx={{ py: 8, textAlign: "center" }}>
            {t("no_books")}
          </Typography>
        ) : (
          <Grid container spacing={3}>
            {books.map((book) => (
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
