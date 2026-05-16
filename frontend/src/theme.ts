import { createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    primary: { main: "#000000", contrastText: "#ffffff" },
    secondary: { main: "#ffffff", contrastText: "#000000" },
    background: { default: "#ffffff", paper: "#ffffff" },
    text: { primary: "#0a0a0a", secondary: "#6b7280" },
    divider: "#e5e7eb",
    grey: {
      50: "#fafafa",
      100: "#f4f4f5",
      200: "#e4e4e7",
      300: "#d4d4d8",
      400: "#a1a1aa",
      500: "#71717a",
      600: "#52525b",
      700: "#3f3f46",
      800: "#27272a",
      900: "#18181b",
    },
  },
  typography: {
    fontFamily: "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif",
    h1: { fontWeight: 800 },
    h2: { fontWeight: 700 },
    h3: { fontWeight: 700 },
    h4: { fontWeight: 700 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 600,
          borderRadius: 12,
        },
        contained: {
          backgroundColor: "#000",
          color: "#fff",
          boxShadow: "none",
          "&:hover": { backgroundColor: "#1a1a1a", boxShadow: "none" },
        },
        outlined: {
          borderColor: "#000",
          color: "#000",
          "&:hover": { backgroundColor: "#f4f4f5", borderColor: "#000" },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: 12,
            "& fieldset": { borderColor: "#e4e4e7" },
            "&:hover fieldset": { borderColor: "#000" },
            "&.Mui-focused fieldset": { borderColor: "#000" },
          },
          "& label.Mui-focused": { color: "#000" },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          boxShadow: "0 2px 12px rgba(0,0,0,0.07)",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 8 },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: "none" },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { backgroundColor: "#e4e4e7" },
        bar: { backgroundColor: "#000" },
      },
    },
  },
});

export default theme;
