import { Box, Typography, IconButton, Divider, Drawer, Tooltip } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DeleteIcon from "@mui/icons-material/Delete";
import { useTranslation } from "react-i18next";
import { HIGHLIGHT_COLORS } from "./HighlightPopup";

export interface HighlightItem {
  id: number;
  book_id: number;
  cfi_range: string;
  text: string;
  color: string;
  note: string | null;
  created_at: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  highlights: HighlightItem[];
  onDelete: (id: number) => void;
  onJump: (cfiRange: string) => void;
}

export default function HighlightsPanel({ open, onClose, highlights, onDelete, onJump }: Props) {
  const { t } = useTranslation();

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 380 }, p: 0 } }}
    >
      <Box sx={{ display: "flex", alignItems: "center", px: 2, py: 1.5, borderBottom: "1px solid #eee" }}>
        <Typography fontWeight={700} fontSize={16} sx={{ flex: 1 }}>
          {t("highlights")} ({highlights.length})
        </Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <Box sx={{ flex: 1, overflowY: "auto", p: 2 }}>
        {highlights.length === 0 ? (
          <Box sx={{ textAlign: "center", py: 6 }}>
            <Typography color="text.secondary" fontSize={14}>
              {t("no_highlights")}
            </Typography>
          </Box>
        ) : (
          highlights.map((h, i) => {
            const colorInfo = HIGHLIGHT_COLORS[h.color] || HIGHLIGHT_COLORS.yellow;
            return (
              <Box key={h.id}>
                <Box
                  sx={{
                    py: 1.5,
                    cursor: "pointer",
                    "&:hover": { "& .highlight-text": { opacity: 0.8 } },
                  }}
                >
                  <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
                    {/* Color strip */}
                    <Box
                      sx={{
                        width: 4,
                        minHeight: 40,
                        borderRadius: 2,
                        bgcolor: colorInfo.hex,
                        flexShrink: 0,
                        mt: 0.5,
                      }}
                    />
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        className="highlight-text"
                        variant="body2"
                        sx={{
                          lineHeight: 1.6,
                          bgcolor: colorInfo.hex + "55",
                          px: 1,
                          py: 0.5,
                          borderRadius: 1,
                          cursor: "pointer",
                          transition: "opacity 0.15s",
                        }}
                        onClick={() => onJump(h.cfi_range)}
                      >
                        "{h.text}"
                      </Typography>
                      <Box sx={{ display: "flex", alignItems: "center", mt: 0.5, gap: 1 }}>
                        <Typography variant="caption" color="text.disabled">
                          {new Date(h.created_at).toLocaleDateString()}
                        </Typography>
                        <Box sx={{ flexGrow: 1 }} />
                        <Tooltip title={t("delete")}>
                          <IconButton
                            size="small"
                            onClick={() => onDelete(h.id)}
                            sx={{ color: "text.disabled", "&:hover": { color: "error.main" } }}
                          >
                            <DeleteIcon sx={{ fontSize: 16 }} />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </Box>
                  </Box>
                </Box>
                {i < highlights.length - 1 && <Divider />}
              </Box>
            );
          })
        )}
      </Box>
    </Drawer>
  );
}
