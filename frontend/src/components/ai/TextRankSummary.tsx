import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Typography,
  Button,
  CircularProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import api from "../../services/api";

interface Props {
  bookId: number;
  chapterNumber: number;
}

export default function TextRankSummary({ bookId, chapterNumber }: Props) {
  const { t } = useTranslation();
  const [sentences, setSentences] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  const handleExtract = async () => {
    setLoading(true);
    try {
      const res = await api.get("/ai/textrank", {
        params: { book_id: bookId, chapter_number: chapterNumber },
      });
      setSentences(res.data.sentences);
      setFetched(true);
    } catch {
      setSentences([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Accordion sx={{ mt: 2 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="subtitle2">{t("key_sentences")}</Typography>
      </AccordionSummary>
      <AccordionDetails>
        {!fetched && !loading && (
          <Button
            variant="outlined"
            size="small"
            onClick={handleExtract}
            fullWidth
          >
            {t("extract_key_sentences")}
          </Button>
        )}

        {loading && (
          <CircularProgress size={24} sx={{ display: "block", mx: "auto" }} />
        )}

        {fetched && sentences.length > 0 && (
          <List dense disablePadding>
            {sentences.map((s, i) => (
              <ListItem key={i} alignItems="flex-start" sx={{ px: 0 }}>
                <ListItemIcon sx={{ minWidth: 32, mt: 0.5 }}>
                  <FormatQuoteIcon fontSize="small" color="action" />
                </ListItemIcon>
                <ListItemText
                  primary={s}
                  primaryTypographyProps={{ variant: "body2" }}
                />
              </ListItem>
            ))}
          </List>
        )}

        {fetched && sentences.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            {t("error_occurred")}
          </Typography>
        )}
      </AccordionDetails>
    </Accordion>
  );
}
