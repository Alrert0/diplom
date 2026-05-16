import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Typography,
  Avatar,
  Tooltip,
  IconButton,
  Divider,
  useMediaQuery,
  useTheme,
  Drawer,
} from "@mui/material";
import HomeRoundedIcon from "@mui/icons-material/HomeRounded";
import MenuBookRoundedIcon from "@mui/icons-material/MenuBookRounded";
import PersonRoundedIcon from "@mui/icons-material/PersonRounded";
import SmartToyRoundedIcon from "@mui/icons-material/SmartToyRounded";
import LogoutRoundedIcon from "@mui/icons-material/LogoutRounded";
import MenuIcon from "@mui/icons-material/Menu";
import AutoStoriesIcon from "@mui/icons-material/AutoStories";
import useAuthStore from "../../store/authStore";
import LanguageSelector from "../LanguageSelector";

const SIDEBAR_WIDTH = 220;

const NAV_ITEMS = [
  { key: "home", icon: HomeRoundedIcon, path: "/" },
  { key: "library", icon: MenuBookRoundedIcon, path: "/library" },
  { key: "ai_assistant", icon: SmartToyRoundedIcon, path: "/assistant" },
  { key: "profile", icon: PersonRoundedIcon, path: "/profile" },
];

function SidebarContent({ onClose }: { onClose?: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const handleNav = (path: string) => {
    navigate(path);
    onClose?.();
  };

  return (
    <Box
      sx={{
        width: SIDEBAR_WIDTH,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        bgcolor: "#fff",
        borderRight: "1px solid",
        borderColor: "grey.100",
      }}
    >
      {/* Logo */}
      <Box sx={{ px: 3, py: 3, display: "flex", alignItems: "center", gap: 1.5 }}>
        <AutoStoriesIcon sx={{ fontSize: 26, color: "#000" }} />
        <Typography fontWeight={800} fontSize={18} color="#000" noWrap letterSpacing="-0.3px">
          Kitap
        </Typography>
      </Box>

      <Divider sx={{ mx: 2 }} />

      {/* Navigation */}
      <Box sx={{ px: 1.5, py: 2, flex: 1 }}>
        <Typography variant="caption" color="text.disabled" sx={{ px: 1.5, mb: 1, display: "block", letterSpacing: 1, textTransform: "uppercase", fontSize: 10 }}>
          {t("menu", "Menu")}
        </Typography>
        {NAV_ITEMS.map(({ key, icon: Icon, path }) => {
          const active = location.pathname === path;
          return (
            <Box
              key={key}
              onClick={() => handleNav(path)}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1.5,
                px: 1.5,
                py: 1.1,
                mb: 0.5,
                borderRadius: 2,
                cursor: "pointer",
                bgcolor: active ? "#f4f4f5" : "transparent",
                color: active ? "#000" : "text.secondary",
                fontWeight: active ? 700 : 400,
                transition: "all 0.15s",
                "&:hover": {
                  bgcolor: "#f4f4f5",
                  color: "#000",
                },
              }}
            >
              <Icon sx={{ fontSize: 20 }} />
              <Typography variant="body2" fontWeight="inherit" fontSize={14}>
                {t(key)}
              </Typography>
            </Box>
          );
        })}
      </Box>

      <Divider sx={{ mx: 2 }} />

      {/* Language + User */}
      <Box sx={{ px: 2, py: 2 }}>
        <Box sx={{ mb: 1.5 }}>
          <LanguageSelector />
        </Box>

        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            p: 1,
            borderRadius: 2,
            bgcolor: "grey.50",
          }}
        >
          <Avatar sx={{ width: 32, height: 32, bgcolor: "#000", fontSize: 14 }}>
            {user?.username?.[0]?.toUpperCase() || "U"}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="body2" fontWeight={600} noWrap fontSize={13}>
              {user?.username}
            </Typography>
            <Typography variant="caption" color="text.disabled" noWrap fontSize={11}>
              {user?.email}
            </Typography>
          </Box>
          <Tooltip title={t("logout")}>
            <IconButton
              size="small"
              onClick={() => {
                logout();
                navigate("/login");
              }}
              sx={{ color: "text.disabled", "&:hover": { color: "error.main" } }}
            >
              <LogoutRoundedIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "#F0F2F5" }}>
      {/* Desktop sidebar */}
      {!isMobile && (
        <Box sx={{ width: SIDEBAR_WIDTH, flexShrink: 0 }}>
          <Box sx={{ position: "fixed", top: 0, left: 0, height: "100vh", width: SIDEBAR_WIDTH, zIndex: 100 }}>
            <SidebarContent />
          </Box>
        </Box>
      )}

      {/* Mobile drawer */}
      {isMobile && (
        <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} PaperProps={{ sx: { width: SIDEBAR_WIDTH } }}>
          <SidebarContent onClose={() => setDrawerOpen(false)} />
        </Drawer>
      )}

      {/* Main content */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Mobile top bar */}
        {isMobile && (
          <Box sx={{ bgcolor: "#fff", px: 2, py: 1.5, display: "flex", alignItems: "center", gap: 1, borderBottom: "1px solid", borderColor: "grey.100" }}>
            <IconButton onClick={() => setDrawerOpen(true)} size="small">
              <MenuIcon />
            </IconButton>
            <Typography fontWeight={700} fontSize={16}>AI Book Reader</Typography>
          </Box>
        )}
        <Box sx={{ flex: 1, overflowY: "auto" }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
