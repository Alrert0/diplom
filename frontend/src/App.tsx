import { useEffect, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CssBaseline, CircularProgress, Box } from "@mui/material";
import useAuthStore from "./store/authStore";
import ProtectedRoute from "./components/ProtectedRoute";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const HomePage = lazy(() => import("./pages/HomePage"));
const LibraryPage = lazy(() => import("./pages/LibraryPage"));
const BookPage = lazy(() => import("./pages/BookPage"));
const ReaderPage = lazy(() => import("./pages/ReaderPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));
const AssistantPage = lazy(() => import("./pages/AssistantPage"));

function Loading() {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
      <CircularProgress />
    </Box>
  );
}

export default function App() {
  const { i18n } = useTranslation();
  const loadFromStorage = useAuthStore((s) => s.loadFromStorage);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  // Sync i18n language with user preference on login/load
  useEffect(() => {
    if (user?.language_pref && user.language_pref !== i18n.language) {
      i18n.changeLanguage(user.language_pref);
    }
  }, [user?.language_pref, i18n]);

  return (
    <>
      <CssBaseline />
      <BrowserRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <HomePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/library"
              element={
                <ProtectedRoute>
                  <LibraryPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/book/:id"
              element={
                <ProtectedRoute>
                  <BookPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/read/:bookId"
              element={
                <ProtectedRoute>
                  <ReaderPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/assistant"
              element={
                <ProtectedRoute>
                  <AssistantPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </>
  );
}
