import { useEffect, useRef, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ePub from "epubjs";
import type { Book as EpubBook, Rendition, NavItem } from "epubjs";
import {
  Box,
  Typography,
  IconButton,
  AppBar,
  Toolbar,
  CircularProgress,
  Select,
  MenuItem,
  type SelectChangeEvent,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import NavigateBeforeIcon from "@mui/icons-material/NavigateBefore";
import NavigateNextIcon from "@mui/icons-material/NavigateNext";
import SummarizeIcon from "@mui/icons-material/Summarize";
import ChatIcon from "@mui/icons-material/Chat";
import HeadphonesIcon from "@mui/icons-material/Headphones";
import MenuBookIcon from "@mui/icons-material/MenuBook";
import api from "../services/api";
import type { Book, Chapter } from "../types";
import ReaderSettings, {
  loadPreferences,
  getThemeColors,
  type ReaderPreferences,
} from "../components/reader/ReaderSettings";
import ReadingTimeEstimate from "../components/reader/ReadingTimeEstimate";
import AISummaryPanel from "../components/ai/AISummaryPanel";
import AIChatPanel from "../components/ai/AIChatPanel";
import AudioPlayer from "../components/audio/AudioPlayer";
import WordPopup from "../components/vocabulary/WordPopup";

const BACKEND_URL = "http://localhost:8000";

export default function ReaderPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const viewerRef = useRef<HTMLDivElement>(null);
  const renditionRef = useRef<Rendition | null>(null);
  const epubRef = useRef<EpubBook | null>(null);

  const [book, setBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [toc, setToc] = useState<NavItem[]>([]);
  const [currentHref, setCurrentHref] = useState("");
  const [currentChapterTitle, setCurrentChapterTitle] = useState("");
  const [preferences, setPreferences] = useState<ReaderPreferences>(loadPreferences);

  // Only one panel open at a time: 'settings' | 'summary' | 'chat' | 'audio' | null
  type PanelType = "settings" | "summary" | "chat" | "audio" | null;
  const [activePanel, setActivePanel] = useState<PanelType>(null);
  const togglePanel = (panel: NonNullable<PanelType>) =>
    setActivePanel((prev) => (prev === panel ? null : panel));

  // Vocabulary popup
  const [vocabMode, setVocabMode] = useState(false);
  const [selectedWord, setSelectedWord] = useState("");
  const [popupPosition, setPopupPosition] = useState<{ top: number; left: number } | null>(null);
  const vocabModeRef = useRef(false);

  // Reading time tracking
  const [currentChapterIndex, setCurrentChapterIndex] = useState(0);
  const [readingSpeed, setReadingSpeed] = useState(200);
  const lastPageTurnRef = useRef<number>(Date.now());
  const wordsOnPageRef = useRef(250); // rough estimate per page

  // Debounced progress save
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveProgress = useCallback(
    (cfi: string, chapterIdx: number) => {
      if (!bookId) return;
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        api
          .put("/reading/progress", {
            book_id: parseInt(bookId, 10),
            current_chapter: chapterIdx + 1,
            current_position: 0,
            cfi_position: cfi,
          })
          .catch(() => {});
      }, 2000);
    },
    [bookId]
  );

  // Apply rendition theme from preferences
  const applyTheme = useCallback(
    (rendition: Rendition, prefs: ReaderPreferences) => {
      const colors = getThemeColors(prefs.theme);
      rendition.themes.default({
        body: {
          "font-family": `${prefs.fontFamily} !important`,
          "font-size": `${prefs.fontSize}px !important`,
          "line-height": `${prefs.lineSpacing} !important`,
          background: `${colors.bg} !important`,
          color: `${colors.text} !important`,
        },
        p: {
          "font-family": `${prefs.fontFamily} !important`,
          "font-size": `${prefs.fontSize}px !important`,
          "line-height": `${prefs.lineSpacing} !important`,
          color: `${colors.text} !important`,
        },
        "*": {
          color: `${colors.text} !important`,
        },
      });
    },
    []
  );

  // Fetch book data + chapters
  useEffect(() => {
    if (!bookId) return;
    Promise.all([api.get(`/books/${bookId}`), api.get(`/books/${bookId}/chapters`)])
      .then(([bookRes, chapRes]) => {
        setBook(bookRes.data);
        setChapters(chapRes.data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [bookId]);

  // Initialize epub.js once book data is loaded
  useEffect(() => {
    if (!book?.epub_filename || !viewerRef.current) return;

    const epubUrl = `${BACKEND_URL}/uploads/${book.epub_filename}`;
    const epubBook = ePub(epubUrl);
    epubRef.current = epubBook;

    const rendition = epubBook.renderTo(viewerRef.current, {
      width: "100%",
      height: "100%",
      spread: "none",
      flow: "paginated",
    });
    renditionRef.current = rendition;

    applyTheme(rendition, preferences);

    // Load TOC
    epubBook.loaded.navigation.then((nav) => {
      setToc(nav.toc);
    });

    // Restore saved position or display from beginning
    api
      .get(`/reading/progress/${bookId}`)
      .then((res) => {
        const cfi = res.data.cfi_position;
        if (cfi) {
          rendition.display(cfi);
        } else {
          rendition.display();
        }
      })
      .catch(() => {
        rendition.display();
      });

    // Track location changes
    rendition.on("relocated", (location: any) => {
      const cfi = location.start?.cfi;
      if (!cfi) return;

      setCurrentHref(location.start?.href || "");

      // Find chapter index from href
      if (toc.length > 0 || epubRef.current) {
        epubRef.current?.loaded.navigation.then((nav) => {
          const href = location.start?.href || "";
          const idx = nav.toc.findIndex(
            (item) => href.includes(item.href.split("#")[0])
          );
          if (idx >= 0) {
            setCurrentChapterIndex(idx);
            setCurrentChapterTitle(nav.toc[idx].label.trim());
          }
        });
      }

      // Measure reading speed from page turns
      const now = Date.now();
      const elapsed = (now - lastPageTurnRef.current) / 1000; // seconds
      if (elapsed > 2 && elapsed < 300) {
        const speed = (wordsOnPageRef.current / elapsed) * 60;
        setReadingSpeed((prev) => {
          // Exponential moving average to smooth the speed
          const smoothed = prev * 0.7 + speed * 0.3;
          return Math.max(50, Math.min(1000, smoothed));
        });
      }
      lastPageTurnRef.current = now;

      // Save progress (debounced)
      saveProgress(cfi, currentChapterIndex);
    });

    // Keyboard navigation
    rendition.on("keyup", (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") rendition.prev();
      if (e.key === "ArrowRight") rendition.next();
    });

    // Vocabulary: handle click on words inside epub iframe
    rendition.on("click", (e: MouseEvent) => {
      if (!vocabModeRef.current) return;

      const target = e.target as HTMLElement;
      if (!target || !target.textContent) return;

      // Get the word at click position from the iframe document
      const iframeDoc = target.ownerDocument;
      if (!iframeDoc) return;

      const selection = iframeDoc.getSelection();
      if (selection && selection.toString().trim()) {
        // User selected text — use that
        const word = selection.toString().trim().split(/\s+/)[0];
        if (word && word.length > 1) {
          const rect = selection.getRangeAt(0).getBoundingClientRect();
          // Translate iframe-relative coords to page-relative
          const iframe = viewerRef.current?.querySelector("iframe");
          const iframeRect = iframe?.getBoundingClientRect() || { top: 0, left: 0 };
          setSelectedWord(word.replace(/[.,;:!?"'()]/g, ""));
          setPopupPosition({
            top: rect.bottom + iframeRect.top,
            left: rect.left + iframeRect.left,
          });
          e.preventDefault();
          e.stopPropagation();
          return;
        }
      }

      // No selection — try to extract word at click position using caretPositionFromPoint
      let word = "";
      let range: Range | null = null;

      if (iframeDoc.caretRangeFromPoint) {
        range = iframeDoc.caretRangeFromPoint(e.clientX, e.clientY);
      }

      if (range) {
        const textNode = range.startContainer;
        if (textNode.nodeType === Node.TEXT_NODE && textNode.textContent) {
          const offset = range.startOffset;
          const text = textNode.textContent;
          // Find word boundaries
          let start = offset;
          let end = offset;
          const wordChar = /[\p{L}\p{M}'-]/u;
          while (start > 0 && wordChar.test(text[start - 1])) start--;
          while (end < text.length && wordChar.test(text[end])) end++;
          word = text.slice(start, end);
        }
      }

      if (word && word.length > 1) {
        const iframe = viewerRef.current?.querySelector("iframe");
        const iframeRect = iframe?.getBoundingClientRect() || { top: 0, left: 0 };
        setSelectedWord(word);
        setPopupPosition({
          top: e.clientY + iframeRect.top,
          left: e.clientX + iframeRect.left,
        });
      }
    });

    return () => {
      rendition.destroy();
      epubBook.destroy();
      epubRef.current = null;
      renditionRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [book?.epub_filename]);

  // Re-apply theme when preferences change
  useEffect(() => {
    if (renditionRef.current) {
      applyTheme(renditionRef.current, preferences);
    }
  }, [preferences, applyTheme]);

  // Keep vocabModeRef in sync with vocabMode state
  useEffect(() => {
    vocabModeRef.current = vocabMode;
  }, [vocabMode]);

  // Keyboard handler on the document level
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") renditionRef.current?.prev();
      if (e.key === "ArrowRight") renditionRef.current?.next();
    };
    document.addEventListener("keyup", handler);
    return () => document.removeEventListener("keyup", handler);
  }, []);

  const handlePrev = () => renditionRef.current?.prev();
  const handleNext = () => renditionRef.current?.next();

  const handleChapterSelect = (e: SelectChangeEvent) => {
    const href = e.target.value;
    if (href && renditionRef.current) {
      renditionRef.current.display(href);
    }
  };

  // Calculate words remaining
  const chapterWordsLeft = (() => {
    if (!chapters.length) return 0;
    const ch = chapters[currentChapterIndex];
    return ch ? ch.word_count : 0;
  })();

  const bookWordsLeft = (() => {
    if (!chapters.length) return 0;
    return chapters
      .slice(currentChapterIndex)
      .reduce((sum, ch) => sum + ch.word_count, 0);
  })();

  const themeColors = getThemeColors(preferences.theme);

  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!book) {
    return (
      <Box sx={{ p: 4 }}>
        <Typography>{t("book_not_found")}</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        bgcolor: themeColors.bg,
      }}
    >
      {/* Top bar */}
      <AppBar position="static" sx={{ bgcolor: preferences.theme === "dark" ? "#16213e" : undefined }}>
        <Toolbar variant="dense">
          <IconButton
            color="inherit"
            onClick={() => navigate(`/book/${bookId}`)}
            edge="start"
          >
            <ArrowBackIcon />
          </IconButton>

          <Typography variant="subtitle2" noWrap sx={{ ml: 1, mr: 2, maxWidth: 200 }}>
            {book.title}
          </Typography>

          {/* Chapter dropdown */}
          {toc.length > 0 && (
            <Select
              value={currentHref || ""}
              onChange={handleChapterSelect}
              size="small"
              variant="outlined"
              displayEmpty
              sx={{
                color: "white",
                fontSize: 13,
                maxWidth: 300,
                ".MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255,255,255,0.3)" },
                ".MuiSvgIcon-root": { color: "white" },
              }}
            >
              {toc.map((item) => (
                <MenuItem key={item.href} value={item.href}>
                  {item.label.trim()}
                </MenuItem>
              ))}
            </Select>
          )}

          <Box sx={{ flexGrow: 1 }} />

          {/* AI buttons */}
          <IconButton
            color={activePanel === "summary" ? "warning" : "inherit"}
            onClick={() => togglePanel("summary")}
            title={t("ai_summary")}
            size="small"
            sx={{ mr: 0.5 }}
          >
            <SummarizeIcon fontSize="small" />
          </IconButton>
          <IconButton
            color={activePanel === "chat" ? "warning" : "inherit"}
            onClick={() => togglePanel("chat")}
            title={t("ai_chat")}
            size="small"
            sx={{ mr: 0.5 }}
          >
            <ChatIcon fontSize="small" />
          </IconButton>
          <IconButton
            color={activePanel === "audio" ? "warning" : "inherit"}
            onClick={() => togglePanel("audio")}
            title={t("listen")}
            size="small"
            sx={{ mr: 0.5 }}
          >
            <HeadphonesIcon fontSize="small" />
          </IconButton>
          <IconButton
            color={vocabMode ? "warning" : "inherit"}
            onClick={() => setVocabMode((v) => !v)}
            title={vocabMode ? t("vocab_mode_off") : t("vocab_mode_on")}
            size="small"
            sx={{ mr: 1 }}
          >
            <MenuBookIcon fontSize="small" />
          </IconButton>

          <Typography variant="caption" sx={{ opacity: 0.7 }}>
            {currentChapterTitle}
          </Typography>
        </Toolbar>
      </AppBar>

      {/* EPUB viewer */}
      <Box
        sx={{
          flex: 1,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <Box
          ref={viewerRef}
          sx={{
            width: "100%",
            height: "100%",
          }}
        />

        {/* Prev / Next overlay buttons */}
        <IconButton
          onClick={handlePrev}
          sx={{
            position: "absolute",
            left: 4,
            top: "50%",
            transform: "translateY(-50%)",
            bgcolor: "rgba(0,0,0,0.05)",
            "&:hover": { bgcolor: "rgba(0,0,0,0.15)" },
          }}
        >
          <NavigateBeforeIcon />
        </IconButton>
        <IconButton
          onClick={handleNext}
          sx={{
            position: "absolute",
            right: 4,
            top: "50%",
            transform: "translateY(-50%)",
            bgcolor: "rgba(0,0,0,0.05)",
            "&:hover": { bgcolor: "rgba(0,0,0,0.15)" },
          }}
        >
          <NavigateNextIcon />
        </IconButton>
      </Box>

      {/* Reader settings */}
      <ReaderSettings
        preferences={preferences}
        onChange={setPreferences}
        open={activePanel === "settings"}
        onToggle={() => togglePanel("settings")}
      />

      {/* Reading time estimate */}
      <ReadingTimeEstimate
        bookId={parseInt(bookId!, 10)}
        chapterNumber={currentChapterIndex + 1}
        chapterWordsLeft={chapterWordsLeft}
        bookWordsLeft={bookWordsLeft}
        readingSpeed={readingSpeed}
        theme={preferences.theme}
      />

      {/* AI Panels */}
      <AISummaryPanel
        open={activePanel === "summary"}
        onClose={() => setActivePanel(null)}
        bookId={parseInt(bookId!, 10)}
        chapterNumber={currentChapterIndex + 1}
      />
      <AIChatPanel
        open={activePanel === "chat"}
        onClose={() => setActivePanel(null)}
        bookId={parseInt(bookId!, 10)}
      />

      {/* Audio Player */}
      {activePanel === "audio" && (
        <AudioPlayer
          bookId={parseInt(bookId!, 10)}
          chapterNumber={currentChapterIndex + 1}
          language={book.language || "en"}
          onClose={() => setActivePanel(null)}
        />
      )}

      {/* Vocabulary Popup */}
      <WordPopup
        word={selectedWord}
        language={book.language || "en"}
        anchorPosition={popupPosition}
        onClose={() => {
          setSelectedWord("");
          setPopupPosition(null);
        }}
      />
    </Box>
  );
}
