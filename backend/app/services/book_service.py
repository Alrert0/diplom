import hashlib
import logging
import os
import re
import textwrap
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup, NavigableString
import ebooklib
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

logger = logging.getLogger(__name__)

COVERS_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "covers"
COVERS_DIR.mkdir(parents=True, exist_ok=True)

COVER_SIZE = (400, 600)

MIN_CHAPTER_WORDS = 50
MAX_CHAPTER_WORDS = 10000


@dataclass
class ChapterData:
    chapter_number: int
    title: str
    content: str
    word_count: int


@dataclass
class BookData:
    title: str
    author: str
    description: str
    language: str
    cover_image_bytes: bytes | None
    chapters: list[ChapterData] = field(default_factory=list)
    total_words: int = 0


def _html_to_text(html: str) -> str:
    """Strip HTML tags and return clean text."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── Chapter heading patterns ──
# English word numerals and ordinals (one, twentieth, etc.)
_WORD_NUMS = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"

# Russian ordinals/cardinals for "Глава первая / Глава 1"
_RU_NUMS = r"(?:перв(?:ая|ый)|втор(?:ая|ой)|треть(?:я|ий)|четвёртая|четвертая|пят(?:ая|ый)|шест(?:ая|ой)|седьм(?:ая|ой)|восьм(?:ая|ой)|девят(?:ая|ый)|десят(?:ая|ый)|одиннадцат(?:ая|ый)|двенадцат(?:ая|ый))"

# Kazakh ordinal endings
_KK_NUMS = r"(?:бірінші|екінші|үшінші|төртінші|бесінші|алтыншы|жетінші|сегізінші|тоғызыншы|оныншы)"

# Combined chapter regex — EN/RU/KK
# EN: Chapter I/1/One/Twenty-three     RU: Глава 1 / Глава первая    KK: Тарау 1 / Бірінші тарау
_CHAPTER_RE = re.compile(
    rf"(?:Chapter|CHAPTER|Глава|ГЛАВА|глава|Тарау|ТАРАУ|тарау|Бөлім|БӨЛІМ|бөлім)\s*(?:[IVXLCivxlc\d]+|{_WORD_NUMS}(?:[- ]{_WORD_NUMS})*|{_RU_NUMS})"
    rf"|(?:{_KK_NUMS})\s*(?:тарау|Тарау|бөлім|Бөлім)",
    re.IGNORECASE | re.UNICODE,
)
# Part / Book / Volume — EN/RU/KK
_PART_RE = re.compile(
    rf"(?:PART|Part|BOOK|Book|VOLUME|Volume|Часть|ЧАСТЬ|часть|Книга|КНИГА|книга|Том|ТОМ|том|Кітап|КІТАП|кітап)\s+"
    rf"(?:[IVXLCivxlc\d]+|{_WORD_NUMS}(?:[- ]{_WORD_NUMS})*|{_RU_NUMS}|{_KK_NUMS})",
    re.IGNORECASE | re.UNICODE,
)
# Matches: standalone "I.", "II.", "III.", "IV.", "XII." as chapter markers (in headings only)
_ROMAN_RE = re.compile(r"^[IVXLC]+\.?$")

# Non-content TOC entries to skip (multilingual)
_TOC_SKIP_KEYWORDS = {
    # English
    "contents", "table of contents", "cover", "title page", "half-title", "half title",
    "copyright", "license", "licence", "colophon", "index", "bibliography",
    "dedication", "acknowledgments", "acknowledgements", "about the author",
    "frontispiece", "imprint", "endnotes", "footnotes",
    # Russian
    "содержание", "оглавление", "обложка", "титульный лист", "авторские права",
    "об авторе", "выходные данные", "примечания", "сноски",
    # Kazakh
    "мазмұны", "мұқаба", "титул беті", "авторлық құқық", "автор туралы",
}


def _is_chapter_heading(text: str) -> str | None:
    """Check if text looks like a chapter/part/section heading. Returns normalized title or None."""
    text = text.strip()
    if not text:
        return None

    m = _CHAPTER_RE.search(text)
    if m:
        return text

    m = _PART_RE.search(text)
    if m:
        return text

    if _ROMAN_RE.match(text):
        return text

    return None


def _split_document_into_chapters(html_content: str) -> list[tuple[str, str]]:
    """
    Split a single HTML document into multiple chapters.
    Handles diverse heading formats from Project Gutenberg and other sources.
    Returns list of (title, text) tuples.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    for tag in soup(["script", "style"]):
        tag.decompose()

    # Strategy 1: Find chapter markers in heading tags (h1-h4)
    heading_tags: list[tuple] = []
    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = heading.get_text(strip=True)
        title = _is_chapter_heading(text)
        if title:
            heading_tags.append((heading, title))
        elif heading.name in ("h1", "h2") and len(text) > 2 and len(text) < 100:
            # h1/h2 headings that aren't chapter markers but could be section titles
            heading_tags.append((heading, text))

    # If 0 or 1 headings, treat the whole document as one chunk
    if len(heading_tags) <= 1:
        text = soup.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        word_count = len(text.split())
        if word_count < 20:
            return []

        title = heading_tags[0][1] if heading_tags else None
        if not title:
            first_h = soup.find(["h1", "h2", "h3"])
            title = first_h.get_text(strip=True) if first_h else None

        # If single chunk is very long, try splitting by h2/h3 tags
        if word_count > MAX_CHAPTER_WORDS:
            sub_split = _split_by_sub_headings(soup)
            if len(sub_split) > 1:
                return sub_split

        return [(title or "", text)]

    # Multiple chapter headings — split by inserting unique markers
    marker_prefix = "\x00CHAPTER_SPLIT\x00"
    for i, (heading_tag, _chapter_title) in enumerate(heading_tags):
        marker = NavigableString(f"{marker_prefix}{i}\x00")
        heading_tag.insert_before(marker)

    full_text = soup.get_text(separator=" ", strip=True)
    full_text = re.sub(r"\s+", " ", full_text).strip()

    chapters: list[tuple[str, str]] = []
    for i, (_, chapter_title) in enumerate(heading_tags):
        marker = f"{marker_prefix}{i}\x00"
        start = full_text.find(marker)
        if start == -1:
            continue

        if i + 1 < len(heading_tags):
            next_marker = f"{marker_prefix}{i + 1}\x00"
            end = full_text.find(next_marker)
            if end == -1:
                end = len(full_text)
        else:
            end = len(full_text)

        chunk = full_text[start + len(marker):end].strip()
        chunk = re.sub(r"\x00[^\x00]*\x00\d+\x00", " ", chunk)
        chunk = chunk.replace("\x00", "")
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk.split()) >= 20:
            chapters.append((chapter_title, chunk))

    # Merge very short chapters with the next one
    chapters = _merge_short_chapters(chapters)

    return chapters


def _split_by_sub_headings(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Split document by h2/h3 headings when a single chunk is too long."""
    headings = soup.find_all(["h2", "h3"])
    if len(headings) < 2:
        return []

    marker_prefix = "\x00SUB_SPLIT\x00"
    for i, heading in enumerate(headings):
        marker = NavigableString(f"{marker_prefix}{i}\x00")
        heading.insert_before(marker)

    full_text = soup.get_text(separator=" ", strip=True)
    full_text = re.sub(r"\s+", " ", full_text).strip()

    chunks: list[tuple[str, str]] = []
    for i, heading in enumerate(headings):
        title = heading.get_text(strip=True)
        marker = f"{marker_prefix}{i}\x00"
        start = full_text.find(marker)
        if start == -1:
            continue

        if i + 1 < len(headings):
            next_marker = f"{marker_prefix}{i + 1}\x00"
            end = full_text.find(next_marker)
            if end == -1:
                end = len(full_text)
        else:
            end = len(full_text)

        chunk = full_text[start + len(marker):end].strip()
        chunk = re.sub(r"\x00[^\x00]*\x00\d+\x00", " ", chunk)
        chunk = chunk.replace("\x00", "")
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk.split()) >= 20:
            chunks.append((title, chunk))

    return chunks


def _merge_short_chapters(chapters: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge chapters with < MIN_CHAPTER_WORDS into the next chapter."""
    if not chapters:
        return chapters

    merged: list[tuple[str, str]] = []
    pending_title = ""
    pending_text = ""

    for title, text in chapters:
        if pending_text:
            # Merge pending into this chapter
            combined_text = pending_text + " " + text
            combined_title = pending_title or title
            if len(combined_text.split()) < MIN_CHAPTER_WORDS:
                # Still too short, keep accumulating
                pending_text = combined_text
                pending_title = combined_title
            else:
                merged.append((combined_title, combined_text))
                pending_text = ""
                pending_title = ""
        elif len(text.split()) < MIN_CHAPTER_WORDS:
            pending_text = text
            pending_title = title
        else:
            merged.append((title, text))

    # Flush any remaining pending text
    if pending_text:
        if merged:
            last_title, last_text = merged[-1]
            merged[-1] = (last_title, last_text + " " + pending_text)
        else:
            merged.append((pending_title, pending_text))

    return merged


@dataclass
class TocEntry:
    title: str
    file_href: str  # XHTML file path inside EPUB
    anchor: str | None  # fragment id within file, or None


def _walk_toc(items, out: list[TocEntry] | None = None) -> list[TocEntry]:
    """Flatten EPUB TOC tree (Section/Link nodes) into ordered list of entries."""
    if out is None:
        out = []
    for item in items:
        if isinstance(item, tuple):
            section, children = item
            href = getattr(section, "href", None)
            title = getattr(section, "title", None)
            if href and title:
                file_part, _, anchor = href.partition("#")
                out.append(TocEntry(title.strip(), unquote(file_part), anchor or None))
            _walk_toc(children, out)
        elif isinstance(item, epub.Link):
            href = item.href or ""
            title = (item.title or "").strip()
            if href and title:
                file_part, _, anchor = href.partition("#")
                out.append(TocEntry(title, unquote(file_part), anchor or None))
    return out


def _clean_toc_title(title: str) -> str:
    """
    Strip caption/illustration text that Project Gutenberg sometimes prepends to TOC entries.
    Example: "I hope Mr. Bingley will like it. CHAPTER II." -> "CHAPTER II."
    Heuristic: if a chapter/part marker is preceded by a sentence-ending punctuation
    (a real preamble), drop the preamble.
    """
    title = re.sub(r"\s+", " ", title).strip()
    for pattern in (_CHAPTER_RE, _PART_RE):
        m = pattern.search(title)
        if not m or m.start() == 0:
            continue
        preamble = title[: m.start()].rstrip()
        # Preamble is a real prefix (not "in Chapter 5") if it ends with sentence punctuation.
        # Includes ASCII (.!?"':) plus curly quotes/guillemets used by Project Gutenberg.
        if preamble and preamble[-1] in '.!?":\'»)”’»':
            return title[m.start():].strip()
    return title


def _is_skippable_toc_title(title: str) -> bool:
    """Return True if TOC title looks like front/back matter we should drop."""
    t = title.strip().lower()
    if not t:
        return True
    if t in _TOC_SKIP_KEYWORDS:
        return True
    # Substring check for things like "Project Gutenberg License"
    for kw in ("project gutenberg", "gutenberg license"):
        if kw in t:
            return True
    return False


def _normalize_filename(name: str) -> str:
    """Normalize EPUB internal filename (strip leading folders, decode, lowercase)."""
    name = unquote(name or "")
    # Drop leading directory segments — TOC may use 'OEBPS/file.xhtml' while
    # ebooklib stores items as 'file.xhtml'. Compare on basename.
    return name.split("/")[-1].lower()


def _split_html_by_anchors(
    html: str, anchors_in_order: list[tuple[str | None, str]]
) -> list[tuple[str, str]]:
    """
    Split a single XHTML document into chapters using DOM anchor IDs.
    `anchors_in_order` is a list of (anchor_id_or_None, title) in TOC order.
    The first entry may have anchor=None meaning "start of document".
    Returns list of (title, plain_text) tuples.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Insert a unique marker text node immediately before each anchor element.
    # For anchor=None (first/only chapter), the marker goes at the very start of <body>.
    marker_prefix = "\x00TOC_SPLIT\x00"
    inserted = 0
    for i, (anchor, _title) in enumerate(anchors_in_order):
        marker = NavigableString(f"{marker_prefix}{i}\x00")
        if anchor is None:
            body = soup.body or soup
            if body.contents:
                body.insert(0, marker)
            else:
                body.append(marker)
            inserted += 1
            continue
        # Find element whose id == anchor, or an <a name="anchor">
        target = soup.find(attrs={"id": anchor})
        if target is None:
            target = soup.find("a", attrs={"name": anchor})
        if target is None:
            continue  # anchor not found — entry will be empty, will be merged later
        target.insert_before(marker)
        inserted += 1

    if inserted == 0:
        return []

    full_text = soup.get_text(separator=" ", strip=True)
    full_text = re.sub(r"\s+", " ", full_text).strip()

    chunks: list[tuple[str, str]] = []
    for i, (_anchor, title) in enumerate(anchors_in_order):
        marker = f"{marker_prefix}{i}\x00"
        start = full_text.find(marker)
        if start == -1:
            continue
        if i + 1 < len(anchors_in_order):
            next_marker = f"{marker_prefix}{i + 1}\x00"
            end = full_text.find(next_marker)
            if end == -1:
                end = len(full_text)
        else:
            end = len(full_text)
        chunk = full_text[start + len(marker):end].strip()
        # Scrub any leaked split markers (can happen if TOC anchor order != DOM order)
        chunk = re.sub(r"\x00[^\x00]*\x00\d+\x00", " ", chunk)
        chunk = chunk.replace("\x00", "")
        chunk = re.sub(r"\s+", " ", chunk).strip()
        chunks.append((title, chunk))

    return chunks


def _extract_chapters_from_toc(book: epub.EpubBook) -> list[tuple[str, str]]:
    """
    Build chapter list using the EPUB TOC (NCX/NAV) as the authoritative outline.
    Returns ordered list of (title, plain_text). Empty list if TOC is unusable.
    """
    toc_entries = _walk_toc(book.toc)
    if not toc_entries:
        return []

    # Index spine documents by basename for lookup
    docs_by_name: dict[str, str] = {}
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        key = _normalize_filename(item.get_name())
        docs_by_name[key] = item.get_content().decode("utf-8", errors="replace")

    # Group TOC entries by file (preserving order across files)
    file_order: list[str] = []
    grouped: dict[str, list[TocEntry]] = {}
    for entry in toc_entries:
        key = _normalize_filename(entry.file_href)
        if key not in grouped:
            grouped[key] = []
            file_order.append(key)
        grouped[key].append(entry)

    chapters: list[tuple[str, str]] = []
    for fname in file_order:
        html = docs_by_name.get(fname)
        if html is None:
            # Try to find by suffix match (TOC may reference relative path differently)
            for k, v in docs_by_name.items():
                if k.endswith(fname) or fname.endswith(k):
                    html = v
                    break
        if html is None:
            continue

        entries = grouped[fname]
        # Single entry without anchor — whole file is one chapter
        if len(entries) == 1 and entries[0].anchor is None:
            text = _html_to_text(html)
            chapters.append((entries[0].title, text))
            continue

        # Multiple entries OR single entry with anchor — split by anchor positions
        anchors = [(e.anchor, e.title) for e in entries]
        # If first anchor isn't at document start, prepend a synthetic None entry to capture lead-in
        # but only if the first entry actually points to a non-start anchor (otherwise we'd duplicate).
        sub = _split_html_by_anchors(html, anchors)
        chapters.extend(sub)

    # Filter front/back matter and very short entries; clean illustration captions from titles
    cleaned: list[tuple[str, str]] = []
    for title, text in chapters:
        title = _clean_toc_title(title)
        if _is_skippable_toc_title(title):
            continue
        word_count = len(text.split())
        if word_count < 20:
            continue
        cleaned.append((title, text))

    # Merge tiny entries with their neighbors (Preface fragments, etc.)
    cleaned = _merge_short_chapters(cleaned)
    return cleaned


def _extract_cover(book: epub.EpubBook) -> bytes | None:
    """Extract cover image bytes from EPUB."""
    # Try the cover-image metadata id
    cover_id = None
    for meta in book.get_metadata("OPF", "meta"):
        attrs = meta[1] if len(meta) > 1 else {}
        if attrs.get("name") == "cover":
            cover_id = attrs.get("content")
            break

    if cover_id:
        try:
            item = book.get_item_with_id(cover_id)
            if item:
                return item.get_content()
        except Exception:
            pass

    # Fallback: look for items with "cover" in the id/name
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        item_id = (item.get_id() or "").lower()
        item_name = (item.get_name() or "").lower()
        if "cover" in item_id or "cover" in item_name:
            return item.get_content()

    # Last fallback: first image in the book
    for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
        return item.get_content()

    return None


def save_cover(image_bytes: bytes, book_id: int) -> str:
    """Resize cover to 400x600 and save as JPEG. Returns the URL path."""
    img = Image.open(BytesIO(image_bytes))
    img = img.convert("RGB")
    img = img.resize(COVER_SIZE, Image.LANCZOS)

    cover_path = COVERS_DIR / f"{book_id}.jpg"
    img.save(cover_path, "JPEG", quality=85)

    return f"/static/covers/{book_id}.jpg"


def generate_placeholder_cover(title: str, author: str) -> bytes:
    """Generate a placeholder cover image with the book title and author."""
    # Deterministic color from title hash
    h = hashlib.md5(title.encode()).hexdigest()
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    # Darken slightly for readability of white text
    bg_color = (max(30, r // 2 + 40), max(30, g // 2 + 40), max(30, b // 2 + 40))

    img = Image.new("RGB", COVER_SIZE, bg_color)
    draw = ImageDraw.Draw(img)

    # Draw a subtle decorative bar at top and bottom
    accent = (min(255, bg_color[0] + 60), min(255, bg_color[1] + 60), min(255, bg_color[2] + 60))
    draw.rectangle([(0, 0), (400, 12)], fill=accent)
    draw.rectangle([(0, 588), (400, 600)], fill=accent)
    draw.rectangle([(30, 50), (370, 52)], fill=accent)
    draw.rectangle([(30, 548), (370, 550)], fill=accent)

    # Try to load a font; fall back to default
    title_font = None
    author_font = None
    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
        author_font = ImageFont.truetype("arial.ttf", 18)
    except (OSError, IOError):
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            author_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except (OSError, IOError):
            title_font = ImageFont.load_default()
            author_font = title_font

    # Word-wrap the title
    max_chars = 20
    title_lines = textwrap.wrap(title, width=max_chars) or [title]
    if len(title_lines) > 5:
        title_lines = title_lines[:5]
        title_lines[-1] = title_lines[-1][:max_chars - 3] + "..."

    # Draw title centered
    y = 180
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        tw = bbox[2] - bbox[0]
        x = (400 - tw) // 2
        draw.text((x, y), line, fill="white", font=title_font)
        y += 38

    # Draw author
    author_lines = textwrap.wrap(author, width=28) or [author]
    y = max(y + 30, 420)
    for line in author_lines[:2]:
        bbox = draw.textbbox((0, 0), line, font=author_font)
        tw = bbox[2] - bbox[0]
        x = (400 - tw) // 2
        draw.text((x, y), line, fill=(220, 220, 220), font=author_font)
        y += 26

    buf = BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


_BOILERPLATE_KW = [
    "gutenberg", "license", "copyright", "table of contents", "contents",
    "list of illustrations", "illustrations", "list of plates",
]


def parse_epub(file_path: str) -> BookData:
    """Parse an EPUB file and extract metadata, cover, and chapters."""
    # ignore_ncx=False so we can read the TOC (NCX/NAV) for chapter boundaries
    book = epub.read_epub(file_path, options={"ignore_ncx": False})

    # Metadata
    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else "Unknown Title"

    creator = book.get_metadata("DC", "creator")
    author = creator[0][0] if creator else "Unknown Author"

    desc = book.get_metadata("DC", "description")
    description = ""
    if desc:
        description = _html_to_text(desc[0][0]) if desc[0][0] else ""

    lang = book.get_metadata("DC", "language")
    language = lang[0][0][:2].lower() if lang else "en"

    # Cover — extract from EPUB or generate placeholder
    cover_bytes = _extract_cover(book)
    if not cover_bytes:
        cover_bytes = generate_placeholder_cover(title, author)

    # Chapters — try TOC first (authoritative), fall back to heading-based splitting
    chapters: list[ChapterData] = []
    raw_chapters: list[tuple[str, str]] = _extract_chapters_from_toc(book)
    used_toc = bool(raw_chapters)

    # Detect "TOC too sparse" via spine coverage: some EPUBs (Gibran's Prophet) have a TOC
    # that references only a few files while the real content is split across many spine docs.
    if used_toc:
        toc_files = {_normalize_filename(e.file_href) for e in _walk_toc(book.toc)}
        substantial_spine = [
            item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
            if len(item.get_content()) > 1500  # skip cover/wrap pages
        ]
        if substantial_spine:
            covered = sum(
                1 for item in substantial_spine
                if _normalize_filename(item.get_name()) in toc_files
            )
            coverage = covered / len(substantial_spine)
            if coverage < 0.5:
                logger.info(
                    "TOC covers only %.0f%% of spine in %s — falling back to heading split",
                    coverage * 100, file_path,
                )
                raw_chapters = []
                used_toc = False

    if not used_toc:
        # Fallback: scan spine documents and split by heading regex
        logger.info("No usable TOC found in %s, falling back to heading-based split", file_path)
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html_content = item.get_content().decode("utf-8", errors="replace")
            raw_chapters.extend(_split_document_into_chapters(html_content))

    chapter_num = 0
    for chapter_title, text in raw_chapters:
        # Skip Project Gutenberg boilerplate
        title_lower = (chapter_title or "").lower()
        text_lower = text[:500].lower()
        if any(kw in title_lower for kw in _BOILERPLATE_KW):
            continue
        if any(kw in text_lower for kw in ["project gutenberg", "*** start of", "*** end of"]):
            continue
        # Skip TOC-like pages (only meaningful for the regex fallback path)
        if not used_toc:
            chapter_heading_count = len(_CHAPTER_RE.findall(text))
            word_count_check = len(text.split())
            if chapter_heading_count > 5 and word_count_check < chapter_heading_count * 30:
                continue

        chapter_num += 1
        word_count = len(text.split())
        clean_title = chapter_title or f"Chapter {chapter_num}"
        # Normalize "CHAPTERXXVII" → "Chapter XXVII" for english headings only
        clean_title = re.sub(
            r"(?i)chapter\s*([IVXLC\d]+)",
            lambda m: f"Chapter {m.group(1)}",
            clean_title,
        )
        # Normalize whitespace (TOC titles sometimes contain weird spacing)
        clean_title = re.sub(r"\s+", " ", clean_title).strip()
        chapters.append(
            ChapterData(
                chapter_number=chapter_num,
                title=clean_title,
                content=text,
                word_count=word_count,
            )
        )

    total_words = sum(ch.word_count for ch in chapters)

    return BookData(
        title=title,
        author=author,
        description=description,
        language=language,
        cover_image_bytes=cover_bytes,
        chapters=chapters,
        total_words=total_words,
    )
