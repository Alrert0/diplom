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
import FormatColorFillIcon from "@mui/icons-material/FormatColorFill";
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
import HighlightPopup, { HIGHLIGHT_COLORS, type HighlightSelection } from "../components/reader/HighlightPopup";
import HighlightsPanel, { type HighlightItem } from "../components/reader/HighlightsPanel";

const BACKEND_URL = "http://localhost:8000";

const SKIP_LABELS = new Set([
  "contents", "table of contents", "list of illustrations", "illustrations",
  "cover", "title page", "copyright", "index",
  "содержание", "оглавление", "мазмұны",
]);

function flattenToc(items: NavItem[]): NavItem[] {
  const result: NavItem[] = [];
  for (const item of items) {
    const label = item.label.trim().toLowerCase();
    if (!SKIP_LABELS.has(label)) {
      result.push(item);
    }
    if (item.subitems?.length) {
      result.push(...flattenToc(item.subitems));
    }
  }
  return result;
}

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
  const [flatToc, setFlatToc] = useState<NavItem[]>([]);
  const [currentHref, setCurrentHref] = useState("");
  const [currentChapterTitle, setCurrentChapterTitle] = useState("");
  const [preferences, setPreferences] = useState<ReaderPreferences>(loadPreferences);

  // Highlights
  const [highlights, setHighlights] = useState<HighlightItem[]>([]);
  const [highlightSelection, setHighlightSelection] = useState<HighlightSelection | null>(null);
  const [showHighlightsPanel, setShowHighlightsPanel] = useState(false);
  const highlightsRef = useRef<HighlightItem[]>([]);

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
  // DB chapter number for AI / TTS — matched by title, falls back to sequential index
  const [currentDbChapterNum, setCurrentDbChapterNum] = useState(1);
  const [readingSpeed, setReadingSpeed] = useState(200);
  const lastPageTurnRef = useRef<number>(Date.now());
  const wordsOnPageRef = useRef(250); // rough estimate per page

  // Session tracking — measure actual time & words per chapter
  const sessionStartRef = useRef<number>(Date.now());
  const sessionChapterRef = useRef<{ index: number; dbNum: number }>({ index: 0, dbNum: 1 });

  // Debounced progress save
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveSession = useCallback(
    (chapterIndex: number, dbChapterNum: number) => {
      if (!bookId) return;
      const elapsed = Math.round((Date.now() - sessionStartRef.current) / 1000);
      // Only save if user spent at least 10 seconds on the chapter
      if (elapsed < 10) return;
      const ch = chapters[chapterIndex];
      const wordsRead = ch?.word_count ?? 250;
      api.post("/reading/session", {
        book_id: parseInt(bookId, 10),
        chapter_number: dbChapterNum,
        words_read: wordsRead,
        time_spent_seconds: elapsed,
      }).catch(() => {});
    },
    [bookId, chapters]
  );

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

  // Keep highlightsRef in sync so epub.js event handlers can access current highlights
  useEffect(() => {
    highlightsRef.current = highlights;
  }, [highlights]);

  // Fetch book data + chapters + highlights
  useEffect(() => {
    if (!bookId) return;
    Promise.all([
      api.get(`/books/${bookId}`),
      api.get(`/books/${bookId}/chapters`),
      api.get(`/highlights/${bookId}`).catch(() => ({ data: [] })),
    ])
      .then(([bookRes, chapRes, hlRes]) => {
        setBook(bookRes.data);
        setChapters(chapRes.data);
        setHighlights(hlRes.data || []);
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

    // Load TOC — flatten nested structure so all chapters are visible
    epubBook.loaded.navigation.then((nav) => {
      setToc(nav.toc);
      setFlatToc(flattenToc(nav.toc));
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

      // Find chapter index from href using flattened TOC, then map to DB chapter number
      if (epubRef.current) {
        epubRef.current.loaded.navigation.then((nav) => {
          const flat = flattenToc(nav.toc);
          const href = location.start?.href || "";
          const idx = flat.findIndex(
            (item) => href.includes(item.href.split("#")[0])
          );
          if (idx >= 0) {
            // Save session for previous chapter before switching
            if (idx !== sessionChapterRef.current.index) {
              saveSession(sessionChapterRef.current.index, sessionChapterRef.current.dbNum);
              sessionStartRef.current = Date.now();
            }

            setCurrentChapterIndex(idx);
            setCurrentHref(flat[idx].href);
            const label = flat[idx].label.trim();
            setCurrentChapterTitle(label);

            // Map epub.js TOC label → DB chapter_number by title substring match
            const labelLow = label.toLowerCase();
            const match = chapters.find((ch) => {
              const t = (ch.title || "").toLowerCase();
              return (
                t.length > 3 &&
                labelLow.length > 3 &&
                (labelLow.includes(t.slice(0, 20)) || t.includes(labelLow.slice(0, 20)))
              );
            });
            const VOLUME_RE = /^(volume|part|book|том|часть|книга)\s/i;
            const contentIdx = flat
              .slice(0, idx + 1)
              .filter((item) => !VOLUME_RE.test(item.label.trim()))
              .length;
            const dbChapterNum =
              match?.chapter_number ??
              chapters[contentIdx - 1]?.chapter_number ??
              1;
            setCurrentDbChapterNum(dbChapterNum);
            sessionChapterRef.current = { index: idx, dbNum: dbChapterNum };

            // Save progress with the freshly computed chapter number (avoids stale closure)
            saveProgress(cfi, dbChapterNum - 1);
          }
        });
      }

      // Update words-per-page estimate from actual chapter word count
      if (epubRef.current) {
        epubRef.current.loaded.navigation.then((nav) => {
          const flat2 = flattenToc(nav.toc);
          const href2 = location.start?.href || "";
          const i2 = flat2.findIndex((item) => href2.includes(item.href.split("#")[0]));
          if (i2 >= 0 && chapters[i2]) {
            // Estimate ~15 pages per chapter → words per page
            wordsOnPageRef.current = Math.max(100, Math.round((chapters[i2].word_count || 250) / 15));
          }
        });
      }

      // Measure reading speed from page turns
      const now = Date.now();
      const elapsed = (now - lastPageTurnRef.current) / 1000;
      if (elapsed > 5 && elapsed < 600) {
        const speed = (wordsOnPageRef.current / elapsed) * 60;
        setReadingSpeed((prev) => {
          const smoothed = prev * 0.6 + speed * 0.4;
          return Math.max(50, Math.min(1000, Math.round(smoothed)));
        });
      }
      lastPageTurnRef.current = now;
    });

    // Keyboard navigation
    rendition.on("keyup", (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft") rendition.prev();
      if (e.key === "ArrowRight") rendition.next();
    });

    // Re-apply saved highlights whenever a section renders
    rendition.on("rendered", () => {
      highlightsRef.current.forEach((h) => {
        try {
          const colorInfo = HIGHLIGHT_COLORS[h.color] || HIGHLIGHT_COLORS.yellow;
          rendition.annotations.highlight(
            h.cfi_range,
            { id: h.id },
            () => {},
            `hl-${h.id}`,
            { fill: colorInfo.epubFill, "fill-opacity": "0.4" }
          );
        } catch {
          // CFI not in this section — ignore
        }
      });
    });

    // Text selection → show color picker
    rendition.on("selected", (cfiRange: string, contents: any) => {
      const selection = contents?.window?.getSelection();
      if (!selection || selection.isCollapsed) return;
      const text = selection.toString().trim();
      if (!text || text.length < 2) return;

      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const iframe = viewerRef.current?.querySelector("iframe");
      const iframeRect = iframe?.getBoundingClientRect() ?? { top: 0, left: 0 };

      // Check if this CFI already has a highlight
      const existing = highlightsRef.current.find((h) => h.cfi_range === cfiRange);

      setHighlightSelection({
        cfiRange,
        text,
        position: {
          top: rect.bottom + iframeRect.top,
          left: rect.left + iframeRect.left,
        },
        existingId: existing?.id,
        existingColor: existing?.color,
      });
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

  // Save session when user leaves the reader page
  useEffect(() => {
    return () => {
      saveSession(sessionChapterRef.current.index, sessionChapterRef.current.dbNum);
    };
  }, [saveSession]);

  const handlePrev = () => renditionRef.current?.prev();
  const handleNext = () => renditionRef.current?.next();

  const handleChapterSelect = (e: SelectChangeEvent) => {
    const href = e.target.value;
    if (href && renditionRef.current) {
      renditionRef.current.display(href);
    }
  };

  const applyHighlightAnnotation = (h: HighlightItem) => {
    if (!renditionRef.current) return;
    const colorInfo = HIGHLIGHT_COLORS[h.color] || HIGHLIGHT_COLORS.yellow;
    try {
      renditionRef.current.annotations.highlight(
        h.cfi_range,
        { id: h.id },
        () => {},
        `hl-${h.id}`,
        { fill: colorInfo.epubFill, "fill-opacity": "0.4" }
      );
    } catch {
      // CFI not currently visible — will be applied on next render
    }
  };

  const removeHighlightAnnotation = (cfiRange: string) => {
    try {
      renditionRef.current?.annotations.remove(cfiRange, "highlight");
    } catch {}
  };

  const handleSaveHighlight = async (color: string) => {
    if (!highlightSelection || !bookId) return;
    const { cfiRange, text, existingId } = highlightSelection;

    if (existingId) {
      // Delete old, re-create with new color
      await handleDeleteHighlight(existingId, cfiRange);
    }

    try {
      const res = await api.post("/highlights", {
        book_id: parseInt(bookId, 10),
        cfi_range: cfiRange,
        text,
        color,
      });
      const saved: HighlightItem = res.data;
      setHighlights((prev) => [...prev.filter((h) => h.cfi_range !== cfiRange), saved]);
      applyHighlightAnnotation(saved);
    } catch {}
    setHighlightSelection(null);
  };

  const handleDeleteHighlight = async (id: number, cfiRange?: string) => {
    try {
      await api.delete(`/highlights/${id}`);
      const toRemove = highlights.find((h) => h.id === id);
      if (toRemove) removeHighlightAnnotation(toRemove.cfi_range);
      setHighlights((prev) => prev.filter((h) => h.id !== id));
    } catch {}
    if (cfiRange === highlightSelection?.cfiRange) setHighlightSelection(null);
  };

  const handleDeleteFromPopup = async () => {
    if (highlightSelection?.existingId) {
      await handleDeleteHighlight(highlightSelection.existingId, highlightSelection.cfiRange);
    }
    setHighlightSelection(null);
  };

  const handleJumpToHighlight = (cfiRange: string) => {
    renditionRef.current?.display(cfiRange);
    setShowHighlightsPanel(false);
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
          {flatToc.length > 0 && (
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
              {flatToc.map((item) => (
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
            color={showHighlightsPanel ? "warning" : "inherit"}
            onClick={() => setShowHighlightsPanel((v) => !v)}
            title={t("highlights")}
            size="small"
            sx={{ mr: 0.5 }}
          >
            <FormatColorFillIcon fontSize="small" />
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
        chapterNumber={currentDbChapterNum}
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
          chapterNumber={currentDbChapterNum}
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

      {/* Highlight color picker popup */}
      <HighlightPopup
        selection={highlightSelection}
        onSave={handleSaveHighlight}
        onDelete={handleDeleteFromPopup}
        onClose={() => setHighlightSelection(null)}
      />

      {/* Highlights / quotes panel */}
      <HighlightsPanel
        open={showHighlightsPanel}
        onClose={() => setShowHighlightsPanel(false)}
        highlights={highlights}
        onDelete={(id) => handleDeleteHighlight(id)}
        onJump={handleJumpToHighlight}
      />
    </Box>
  );
}
