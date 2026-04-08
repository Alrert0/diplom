export interface User {
  id: number;
  email: string;
  username: string;
  language_pref: string;
  created_at: string;
}

export interface Book {
  id: number;
  title: string;
  author: string;
  description: string | null;
  genre: string | null;
  language: string;
  cover_url: string | null;
  epub_filename: string | null;
  total_chapters: number;
  total_words: number;
  created_at: string;
  avg_rating: number | null;
  ratings_count: number;
}

export interface Chapter {
  id: number;
  book_id: number;
  chapter_number: number;
  title: string | null;
  word_count: number;
}

export interface ChapterDetail extends Chapter {
  content: string;
}

export interface Rating {
  id: number;
  user_id: number;
  book_id: number;
  score: number;
  review_text: string | null;
  created_at: string;
}

export interface ReadingProgress {
  id: number;
  user_id: number;
  book_id: number;
  current_chapter: number;
  current_position: number;
  cfi_position: string | null;
  last_read_at: string;
}
