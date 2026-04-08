import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Popover,
  Box,
  Typography,
  CircularProgress,
  Divider,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Avatar,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import PublicIcon from "@mui/icons-material/Public";
import api from "../../services/api";

interface Definition {
  definition: string;
  pos: string;
  examples?: string[];
  translation_ru?: string;
}

interface WikiData {
  title: string;
  extract: string;
  thumbnail?: string;
}

interface VocabResult {
  word: string;
  language: string;
  definitions: Definition[];
  wikipedia: WikiData | null;
}

interface WordPopupProps {
  word: string;
  language: string;
  anchorPosition: { top: number; left: number } | null;
  onClose: () => void;
}

export default function WordPopup({ word, language, anchorPosition, onClose }: WordPopupProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VocabResult | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!word || !anchorPosition) return;

    setLoading(true);
    setError(false);
    setResult(null);

    api
      .get("/vocabulary/define", { params: { word, lang: language, online: true } })
      .then((res) => setResult(res.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [word, language, anchorPosition]);

  if (!anchorPosition) return null;

  return (
    <Popover
      open
      onClose={onClose}
      anchorReference="anchorPosition"
      anchorPosition={anchorPosition}
      transformOrigin={{ vertical: "top", horizontal: "left" }}
      slotProps={{
        paper: {
          sx: { maxWidth: 380, maxHeight: 450, overflow: "auto", p: 2 },
        },
      }}
    >
      {/* Word header */}
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 0.5 }}>
        {word}
      </Typography>

      {loading && (
        <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
          <CircularProgress size={28} />
        </Box>
      )}

      {error && (
        <Typography variant="body2" color="text.secondary">
          {t("no_definition_found")}
        </Typography>
      )}

      {result && (
        <>
          {/* Definitions */}
          {result.definitions.length > 0 ? (
            <Box sx={{ mb: 1 }}>
              {result.definitions.map((def, i) => (
                <Box key={i} sx={{ mb: 1.5 }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 0.3 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {i + 1}.
                    </Typography>
                    {def.pos && (
                      <Chip label={def.pos} size="small" variant="outlined" sx={{ height: 20, fontSize: 11 }} />
                    )}
                  </Box>
                  <Typography variant="body2">{def.definition}</Typography>
                  {def.translation_ru && (
                    <Typography variant="body2" color="primary" sx={{ mt: 0.3 }}>
                      🇷🇺 {def.translation_ru}
                    </Typography>
                  )}
                  {def.examples && def.examples.length > 0 && (
                    <Box sx={{ mt: 0.5 }}>
                      {def.examples.map((ex, j) => (
                        <Typography
                          key={j}
                          variant="body2"
                          sx={{ fontStyle: "italic", color: "text.secondary", pl: 1 }}
                        >
                          &ldquo;{ex}&rdquo;
                        </Typography>
                      ))}
                    </Box>
                  )}
                </Box>
              ))}
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {t("no_definition_found")}
            </Typography>
          )}

          {/* Wikipedia section */}
          {result.wikipedia && (
            <>
              <Divider sx={{ my: 1 }} />
              <Accordion disableGutters elevation={0} sx={{ "&:before": { display: "none" } }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 36 }}>
                  <PublicIcon sx={{ fontSize: 18, mr: 0.5, color: "text.secondary" }} />
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    Wikipedia
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ px: 0, pt: 0 }}>
                  <Box sx={{ display: "flex", gap: 1 }}>
                    {result.wikipedia.thumbnail && (
                      <Avatar
                        src={result.wikipedia.thumbnail}
                        variant="rounded"
                        sx={{ width: 60, height: 60, flexShrink: 0 }}
                      />
                    )}
                    <Box>
                      <Typography variant="subtitle2">{result.wikipedia.title}</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ fontSize: 12 }}>
                        {result.wikipedia.extract}
                      </Typography>
                    </Box>
                  </Box>
                </AccordionDetails>
              </Accordion>
            </>
          )}
        </>
      )}
    </Popover>
  );
}
