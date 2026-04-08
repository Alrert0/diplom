import { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  Box,
  IconButton,
  Typography,
  Slider,
  Select,
  MenuItem,
  CircularProgress,
  Paper,
  Chip,
  type SelectChangeEvent,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import StopIcon from "@mui/icons-material/Stop";
import CloseIcon from "@mui/icons-material/Close";
import SpeedIcon from "@mui/icons-material/Speed";
import api from "../../services/api";

interface AudioPlayerProps {
  bookId: number;
  chapterNumber: number;
  language: string;
  onClose: () => void;
}

const SPEED_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const MAX_CHARS_PER_REQUEST = 4500;

function splitTextIntoSegments(text: string, maxChars: number): string[] {
  if (text.length <= maxChars) return [text];

  const segments: string[] = [];
  const paragraphs = text.split(/\n\n+|\.\s+(?=[A-ZА-ЯЁҚӘҰҮІҺӨа-яёқәұүіһө])/);

  let current = "";
  for (const para of paragraphs) {
    if (current.length + para.length + 2 > maxChars && current.length > 0) {
      segments.push(current.trim());
      current = para;
    } else {
      current += (current ? ". " : "") + para;
    }
  }
  if (current.trim()) {
    segments.push(current.trim());
  }

  // If a single segment is still too long, force-split at sentence boundaries
  const result: string[] = [];
  for (const seg of segments) {
    if (seg.length <= maxChars) {
      result.push(seg);
    } else {
      let remaining = seg;
      while (remaining.length > maxChars) {
        let splitIdx = remaining.lastIndexOf(". ", maxChars);
        if (splitIdx < maxChars * 0.3) splitIdx = maxChars;
        result.push(remaining.slice(0, splitIdx + 1).trim());
        remaining = remaining.slice(splitIdx + 1).trim();
      }
      if (remaining) result.push(remaining);
    }
  }
  return result;
}

export default function AudioPlayer({
  bookId,
  chapterNumber,
  language,
  onClose,
}: AudioPlayerProps) {
  const { t } = useTranslation();

  const [gender, setGender] = useState<"female" | "male">("female");
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentSegment, setCurrentSegment] = useState(0);
  const [totalSegments, setTotalSegments] = useState(0);

  // Cache fetched chapter text so we don't re-fetch on every play
  const chapterTextRef = useRef<{ bookId: number; chapter: number; text: string } | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const stoppedRef = useRef(false);

  // Clean up audio on unmount
  useEffect(() => {
    return () => {
      stoppedRef.current = true;
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
      }
    };
  }, []);

  // Reset when chapter changes
  useEffect(() => {
    handleStop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId, chapterNumber]);

  const fetchChapterText = useCallback(async (): Promise<string> => {
    if (
      chapterTextRef.current &&
      chapterTextRef.current.bookId === bookId &&
      chapterTextRef.current.chapter === chapterNumber
    ) {
      return chapterTextRef.current.text;
    }
    const res = await api.get(`/books/${bookId}/chapters/${chapterNumber}`);
    const text = res.data.content as string;
    chapterTextRef.current = { bookId, chapter: chapterNumber, text };
    return text;
  }, [bookId, chapterNumber]);

  const synthesizeSegment = useCallback(
    async (text: string): Promise<string> => {
      const response = await api.post(
        "/tts/synthesize",
        { text, language, gender },
        { responseType: "blob" }
      );
      const blob = new Blob([response.data], { type: "audio/mpeg" });
      return URL.createObjectURL(blob);
    },
    [language, gender]
  );

  const playSegment = useCallback(
    (audioUrl: string): Promise<void> => {
      return new Promise((resolve, reject) => {
        if (audioRef.current) {
          audioRef.current.pause();
          audioRef.current.src = "";
        }

        const audio = new Audio(audioUrl);
        audio.playbackRate = playbackSpeed;
        audioRef.current = audio;

        audio.addEventListener("loadedmetadata", () => {
          setDuration(audio.duration);
        });

        audio.addEventListener("timeupdate", () => {
          setProgress(audio.currentTime);
        });

        audio.addEventListener("ended", () => {
          URL.revokeObjectURL(audioUrl);
          resolve();
        });

        audio.addEventListener("error", () => {
          URL.revokeObjectURL(audioUrl);
          reject(new Error("Audio playback error"));
        });

        audio.play().catch(reject);
      });
    },
    [playbackSpeed]
  );

  const handlePlay = useCallback(async () => {
    // Resume from pause
    if (isPaused && audioRef.current) {
      audioRef.current.play();
      setIsPlaying(true);
      setIsPaused(false);
      return;
    }

    setError("");
    setIsLoading(true);
    setIsPlaying(true);
    setIsPaused(false);
    stoppedRef.current = false;

    try {
      const chapterText = await fetchChapterText();
      const segments = splitTextIntoSegments(chapterText, MAX_CHARS_PER_REQUEST);
      setTotalSegments(segments.length);

      for (let i = currentSegment; i < segments.length; i++) {
        if (stoppedRef.current) break;

        setCurrentSegment(i);
        setProgress(0);

        const audioUrl = await synthesizeSegment(segments[i]);
        setIsLoading(false);

        if (stoppedRef.current) {
          URL.revokeObjectURL(audioUrl);
          break;
        }

        await playSegment(audioUrl);
      }
    } catch (err) {
      if (!stoppedRef.current) {
        setError(t("audio_error"));
      }
    } finally {
      if (!stoppedRef.current) {
        setIsPlaying(false);
        setCurrentSegment(0);
      }
      setIsLoading(false);
    }
  }, [isPaused, currentSegment, fetchChapterText, synthesizeSegment, playSegment, t]);

  const handlePause = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
      setIsPaused(true);
    }
  };

  const handleStop = () => {
    stoppedRef.current = true;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = "";
    }
    setIsPlaying(false);
    setIsPaused(false);
    setIsLoading(false);
    setProgress(0);
    setDuration(0);
    setCurrentSegment(0);
    setTotalSegments(0);
  };

  const handleSpeedChange = () => {
    const currentIdx = SPEED_OPTIONS.indexOf(playbackSpeed);
    const nextIdx = (currentIdx + 1) % SPEED_OPTIONS.length;
    const newSpeed = SPEED_OPTIONS[nextIdx];
    setPlaybackSpeed(newSpeed);
    if (audioRef.current) {
      audioRef.current.playbackRate = newSpeed;
    }
  };

  const handleProgressChange = (_: Event, value: number | number[]) => {
    const time = value as number;
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setProgress(time);
    }
  };

  const handleGenderChange = (e: SelectChangeEvent) => {
    handleStop();
    setGender(e.target.value as "female" | "male");
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <Paper
      elevation={8}
      sx={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1300,
        px: 2,
        py: 1,
        display: "flex",
        flexDirection: "column",
        gap: 0.5,
      }}
    >
      {/* Progress bar */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <Typography variant="caption" sx={{ minWidth: 36 }}>
          {formatTime(progress)}
        </Typography>
        <Slider
          size="small"
          value={progress}
          max={duration || 1}
          onChange={handleProgressChange}
          sx={{ flex: 1 }}
        />
        <Typography variant="caption" sx={{ minWidth: 36 }}>
          {formatTime(duration)}
        </Typography>
      </Box>

      {/* Controls row */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        {/* Play / Pause */}
        {isLoading ? (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <CircularProgress size={24} />
            <Typography variant="caption">{t("audio_loading")}</Typography>
          </Box>
        ) : isPlaying ? (
          <IconButton onClick={handlePause} size="small" color="primary">
            <PauseIcon />
          </IconButton>
        ) : (
          <IconButton onClick={handlePlay} size="small" color="primary">
            <PlayArrowIcon />
          </IconButton>
        )}

        {/* Stop */}
        <IconButton
          onClick={handleStop}
          size="small"
          disabled={!isPlaying && !isPaused && !isLoading}
        >
          <StopIcon />
        </IconButton>

        {/* Speed toggle */}
        <Chip
          icon={<SpeedIcon />}
          label={`${playbackSpeed}x`}
          size="small"
          onClick={handleSpeedChange}
          variant="outlined"
          sx={{ cursor: "pointer" }}
        />

        {/* Gender selector */}
        <Select
          value={gender}
          onChange={handleGenderChange}
          size="small"
          sx={{ minWidth: 100, fontSize: 13 }}
        >
          <MenuItem value="female">{t("female")}</MenuItem>
          <MenuItem value="male">{t("male")}</MenuItem>
        </Select>

        {/* Segment indicator */}
        {totalSegments > 1 && (
          <Typography variant="caption" sx={{ opacity: 0.7 }}>
            {t("audio_segment", { current: currentSegment + 1, total: totalSegments })}
          </Typography>
        )}

        {/* Error */}
        {error && (
          <Typography variant="caption" color="error" sx={{ ml: 1 }}>
            {error}
          </Typography>
        )}

        <Box sx={{ flexGrow: 1 }} />

        {/* Close */}
        <IconButton onClick={() => { handleStop(); onClose(); }} size="small">
          <CloseIcon />
        </IconButton>
      </Box>
    </Paper>
  );
}
