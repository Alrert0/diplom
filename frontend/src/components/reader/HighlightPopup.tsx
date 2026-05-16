import { Box, IconButton, Tooltip } from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import BookmarkIcon from "@mui/icons-material/Bookmark";

export const HIGHLIGHT_COLORS: Record<string, { hex: string; label: string; epubFill: string }> = {
  yellow: { hex: "#FFE066", label: "Yellow", epubFill: "#FFE066" },
  blue:   { hex: "#66B2FF", label: "Blue",   epubFill: "#66B2FF" },
  red:    { hex: "#FF7070", label: "Red",     epubFill: "#FF7070" },
  green:  { hex: "#66E096", label: "Green",   epubFill: "#66E096" },
  purple: { hex: "#CC66FF", label: "Purple",  epubFill: "#CC66FF" },
};

export interface HighlightSelection {
  cfiRange: string;
  text: string;
  position: { top: number; left: number };
  existingId?: number;
  existingColor?: string;
}

interface Props {
  selection: HighlightSelection | null;
  onSave: (color: string) => void;
  onDelete: () => void;
  onClose: () => void;
}

export default function HighlightPopup({ selection, onSave, onDelete, onClose }: Props) {
  if (!selection) return null;

  const { top, left } = selection.position;

  return (
    <>
      {/* Invisible backdrop to close on click outside */}
      <Box
        onClick={onClose}
        sx={{ position: "fixed", inset: 0, zIndex: 1299 }}
      />

      <Box
        sx={{
          position: "fixed",
          top: Math.min(top + 8, window.innerHeight - 60),
          left: Math.max(8, Math.min(left, window.innerWidth - 220)),
          zIndex: 1300,
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          bgcolor: "#fff",
          border: "1px solid #e0e0e0",
          borderRadius: 3,
          px: 1,
          py: 0.5,
          boxShadow: "0 4px 20px rgba(0,0,0,0.15)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <BookmarkIcon sx={{ fontSize: 16, color: "text.disabled", mr: 0.5 }} />

        {Object.entries(HIGHLIGHT_COLORS).map(([key, { hex, label }]) => (
          <Tooltip key={key} title={label} placement="top">
            <Box
              onClick={() => onSave(key)}
              sx={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                bgcolor: hex,
                cursor: "pointer",
                border: selection.existingColor === key ? "2px solid #000" : "2px solid transparent",
                transition: "transform 0.15s",
                "&:hover": { transform: "scale(1.25)" },
              }}
            />
          </Tooltip>
        ))}

        {selection.existingId && (
          <Tooltip title="Delete" placement="top">
            <IconButton size="small" onClick={onDelete} sx={{ ml: 0.5, color: "text.secondary" }}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>
    </>
  );
}
