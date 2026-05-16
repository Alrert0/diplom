import { useEffect, useState } from "react";
import { Box, Typography } from "@mui/material";
import AutoStoriesIcon from "@mui/icons-material/AutoStories";

export default function SplashScreen({ onDone }: { onDone: () => void }) {
  const [fade, setFade] = useState(false);

  useEffect(() => {
    // Show splash for 1.6s then fade out
    const fadeTimer = setTimeout(() => setFade(true), 1600);
    const doneTimer = setTimeout(onDone, 2200);
    return () => { clearTimeout(fadeTimer); clearTimeout(doneTimer); };
  }, [onDone]);

  return (
    <Box
      sx={{
        position: "fixed",
        inset: 0,
        bgcolor: "#fff",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        opacity: fade ? 0 : 1,
        transition: "opacity 0.5s ease",
        pointerEvents: "none",
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          animation: "fadeUp 0.6s ease forwards",
          "@keyframes fadeUp": {
            from: { opacity: 0, transform: "translateY(16px)" },
            to: { opacity: 1, transform: "translateY(0)" },
          },
        }}
      >
        <AutoStoriesIcon sx={{ fontSize: 36, color: "#000" }} />
        <Typography
          sx={{
            fontSize: 32,
            fontWeight: 800,
            letterSpacing: "-0.5px",
            color: "#000",
            fontFamily: "'Inter', sans-serif",
          }}
        >
          Kitap
        </Typography>
      </Box>
    </Box>
  );
}
