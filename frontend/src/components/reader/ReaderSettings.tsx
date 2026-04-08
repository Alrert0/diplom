import { useTranslation } from "react-i18next";
import {
  Box,
  IconButton,
  Paper,
  Typography,
  Slider,
  ToggleButtonGroup,
  ToggleButton,
  Fade,
} from "@mui/material";
import SettingsIcon from "@mui/icons-material/Settings";
import CloseIcon from "@mui/icons-material/Close";
import LanguageSelector from "../LanguageSelector";

export interface ReaderPreferences {
  fontFamily: "serif" | "sans-serif" | "monospace";
  fontSize: number;
  lineSpacing: number;
  theme: "white" | "sepia" | "dark";
}

const STORAGE_KEY = "reader_preferences";

const THEME_COLORS = {
  white: { bg: "#ffffff", text: "#000000" },
  sepia: { bg: "#f4ecd8", text: "#5b4636" },
  dark: { bg: "#1a1a2e", text: "#e0e0e0" },
} as const;

export function getThemeColors(theme: ReaderPreferences["theme"]) {
  return THEME_COLORS[theme];
}

export function loadPreferences(): ReaderPreferences {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch {}
  return { fontFamily: "serif", fontSize: 18, lineSpacing: 1.5, theme: "white" };
}

function savePreferences(prefs: ReaderPreferences) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

interface Props {
  preferences: ReaderPreferences;
  onChange: (prefs: ReaderPreferences) => void;
  open: boolean;
  onToggle: () => void;
}

export default function ReaderSettings({ preferences, onChange, open, onToggle }: Props) {
  const { t } = useTranslation();

  const update = (partial: Partial<ReaderPreferences>) => {
    const next = { ...preferences, ...partial };
    savePreferences(next);
    onChange(next);
  };

  return (
    <>
      {/* Gear icon button */}
      <IconButton
        onClick={onToggle}
        sx={{
          position: "fixed",
          top: 72,
          right: 16,
          zIndex: 1300,
          bgcolor: "background.paper",
          boxShadow: 2,
          "&:hover": { bgcolor: "grey.100" },
        }}
      >
        {open ? <CloseIcon /> : <SettingsIcon />}
      </IconButton>

      {/* Settings panel */}
      <Fade in={open}>
        <Paper
          elevation={6}
          sx={{
            position: "fixed",
            top: 120,
            right: 16,
            zIndex: 1200,
            width: 280,
            p: 2.5,
            display: open ? "block" : "none",
          }}
        >
          {/* Font family */}
          <Typography variant="caption" gutterBottom display="block">
            {t("font_family")}
          </Typography>
          <ToggleButtonGroup
            value={preferences.fontFamily}
            exclusive
            onChange={(_, v) => v && update({ fontFamily: v })}
            size="small"
            fullWidth
            sx={{ mb: 2 }}
          >
            <ToggleButton value="serif" sx={{ fontFamily: "serif", textTransform: "none" }}>
              {t("serif")}
            </ToggleButton>
            <ToggleButton value="sans-serif" sx={{ fontFamily: "sans-serif", textTransform: "none" }}>
              {t("sans_serif")}
            </ToggleButton>
            <ToggleButton value="monospace" sx={{ fontFamily: "monospace", textTransform: "none" }}>
              {t("monospace")}
            </ToggleButton>
          </ToggleButtonGroup>

          {/* Font size */}
          <Typography variant="caption" gutterBottom display="block" sx={{ fontWeight: 600 }}>
            {t("font_size")}: {preferences.fontSize}px
          </Typography>
          <Slider
            value={preferences.fontSize}
            min={12}
            max={32}
            step={1}
            valueLabelDisplay="auto"
            valueLabelFormat={(v) => `${v}px`}
            onChange={(_, v) => update({ fontSize: v as number })}
            sx={{ mb: 2 }}
          />

          {/* Line spacing */}
          <Typography variant="caption" gutterBottom display="block" sx={{ fontWeight: 600 }}>
            {t("line_spacing")}: {preferences.lineSpacing.toFixed(1)}
          </Typography>
          <ToggleButtonGroup
            value={preferences.lineSpacing}
            exclusive
            onChange={(_, v) => v != null && update({ lineSpacing: v })}
            size="small"
            fullWidth
            sx={{ mb: 2 }}
          >
            {[1.0, 1.2, 1.5, 1.8, 2.0].map((v) => (
              <ToggleButton key={v} value={v}>
                {v.toFixed(1)}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>

          {/* Theme */}
          <Typography variant="caption" gutterBottom display="block">
            {t("theme")}
          </Typography>
          <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
            {(["white", "sepia", "dark"] as const).map((theme) => (
              <Box
                key={theme}
                onClick={() => update({ theme })}
                sx={{
                  flex: 1,
                  py: 1.5,
                  textAlign: "center",
                  cursor: "pointer",
                  borderRadius: 1,
                  border: preferences.theme === theme ? "2px solid" : "1px solid",
                  borderColor: preferences.theme === theme ? "primary.main" : "grey.300",
                  bgcolor: THEME_COLORS[theme].bg,
                  color: THEME_COLORS[theme].text,
                  fontSize: 12,
                  fontWeight: preferences.theme === theme ? 700 : 400,
                }}
              >
                {t(`theme_${theme}`)}
              </Box>
            ))}
          </Box>

          {/* Language */}
          <Typography variant="caption" gutterBottom display="block">
            {t("interface_language")}
          </Typography>
          <Box sx={{ display: "flex", justifyContent: "center" }}>
            <LanguageSelector />
          </Box>
        </Paper>
      </Fade>
    </>
  );
}
