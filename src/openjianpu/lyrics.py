"""
Penyelarasan lirik dari berkas teks bersih (``--lyrics-file``).

Untuk partitur yang liriknya rusak di sumber (tergumpal, hilang, atau salah baca),
pengguna memberi syair bersih dan alat ini memetakannya suku kata demi suku kata ke
not-not bersuara, berurutan dari birama pertama.

Format berkas (baris kosong dan baris berawalan ``#`` diabaikan)::

    # tanpa awalan: berlaku untuk semua suara yang berlirik
    Ma-lam ku-dus, su-nyi se-nyap
    S: Ha-nya sopran yang me-nya-nyi-kan ba-ris i-ni
    2: Bait ke-dua di-tu-lis de-ngan a-wal-an nomor
    A 2: bait ke-dua khusus alto

Aturan pemenggalan:
* kata bertanda hubung dipakai apa adanya (``ku-dus`` -> ``ku-`` ``dus``);
* kata tanpa tanda hubung dipenggal dengan pemenggal PUEBI ``lirik/silabel.py``
  bila tersedia, jika tidak dipakai utuh satu not;
* ``_`` berarti satu not tanpa suku kata (melisma), ``|`` diabaikan.
"""

import os
import re
import sys
from typing import Dict, List, Optional, Tuple

from .schema import NotAngkaScore, NoteItem

_VOICE_RE = re.compile(r"^\s*([A-Za-z]+\s*\d*)?\s*(\d+)?\s*:\s*(.*)$")


def _load_syllabifier():
    try:
        from .silabel import syllabify
        return syllabify
    except (ImportError, ValueError):
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (here, os.path.join(here, "..", "..", "lirik"), os.path.join(here, "..", "lirik"), os.path.join(here, "lirik")):
        path = os.path.join(cand, "silabel.py")
        if os.path.exists(path):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("silabel", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.syllabify
            except Exception:
                return None
    return None


def tokenize_lyrics(text: str, syllabify=None) -> List[Optional[str]]:
    """Teks bersih -> daftar suku kata siap tempel (None = melisma / not tanpa suku kata).

    Suku kata di tengah kata mendapat tanda hubung penyambung ("ku-"), suku kata terakhir
    membawa tanda baca kata ("dus,").
    """
    out: List[Optional[str]] = []
    for word in text.replace("|", " ").split():
        if word == "_":
            out.append(None)
            continue
        m = re.match(r"^([^\w'’]*)(.*?)([^\w'’]*)$", word)
        lead, core, trail = (m.group(1), m.group(2), m.group(3)) if m else ("", word, "")
        if not core:
            continue
        if "-" in core.strip("-"):
            pieces = [p for p in core.split("-") if p]
        elif syllabify is not None and core.isalpha() and len(core) >= 3:
            try:
                pieces = list(syllabify(core, True))
            except Exception:
                pieces = [core]
        else:
            pieces = [core]
        for k, piece in enumerate(pieces):
            last = (k == len(pieces) - 1)
            syl = (lead if k == 0 else "") + piece + (trail if last else "-")
            out.append(syl)
    return out


def parse_lyrics_file(path: str, syllabify=None) -> Dict[Tuple[Optional[str], int], List[Optional[str]]]:
    """{(suara atau None, nomor bait): [suku kata...]} dari berkas lirik."""
    streams: Dict[Tuple[Optional[str], int], List[Optional[str]]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            voice: Optional[str] = None
            verse = 1
            text = line
            m = _VOICE_RE.match(line)
            if m and (m.group(1) or m.group(2)) and ":" in line:
                head = (m.group(1) or "").strip()
                if head.isdigit():
                    verse, voice = int(head), None
                else:
                    voice = head.replace(" ", "") or None
                    if voice:
                        # normalisasi "S 1" -> "S1", "solo" -> "Solo"
                        voice = voice[0].upper() + voice[1:]
                    if m.group(2):
                        verse = int(m.group(2))
                text = m.group(3)
            streams.setdefault((voice, verse), []).extend(tokenize_lyrics(text, syllabify))
    return streams


def apply_lyrics(score: NotAngkaScore, streams: Dict[Tuple[Optional[str], int], List[Optional[str]]]) -> Dict[str, int]:
    """Menempelkan aliran suku kata ke not bersuara tiap suara, berurutan lintas birama.

    Aliran bersuara tertentu ("S:") mengalahkan aliran umum. Bait 1 masuk ``lyric``,
    bait 2.. masuk ``verses``. Mengembalikan {suara: jumlah suku kata tertempel}.
    """
    voices = sorted({v for m in score.measures for v in m.voices})
    applied: Dict[str, int] = {}
    for v in voices:
        verse_streams = {}
        for (sv, verse), toks in streams.items():
            if sv is None and (v, verse) not in streams:
                verse_streams[verse] = toks
            elif sv == v:
                verse_streams[verse] = toks
        if not verse_streams:
            continue
        max_verse = max(verse_streams)
        cursors = {verse: 0 for verse in verse_streams}
        count = 0
        for m in score.measures:
            mv = m.voices.get(v)
            if not mv:
                continue
            for n in mv.notes:
                if n.text in ("0", ".") or getattr(n, "tie", False) and n.text == ".":
                    continue
                n.lyric = None
                n.verses = None
                for verse in sorted(verse_streams):
                    toks = verse_streams[verse]
                    c = cursors[verse]
                    if c >= len(toks):
                        continue
                    syl = toks[c]
                    cursors[verse] = c + 1
                    if syl is None:
                        continue
                    if verse == 1:
                        n.lyric = syl
                    else:
                        if n.verses is None:
                            n.verses = [None] * (max_verse - 1)
                        n.verses[verse - 2] = syl
                    count += 1
        applied[v] = count
        # perbarui teks lirik gabungan per birama (kompatibilitas)
        for m in score.measures:
            mv = m.voices.get(v)
            if mv:
                words = [n.lyric for n in mv.notes if n.lyric]
                if words:
                    m.lyrics[v] = " ".join(words)
    return applied


def apply_lyrics_file(score: NotAngkaScore, path: str) -> Dict[str, int]:
    streams = parse_lyrics_file(path, _load_syllabifier())
    return apply_lyrics(score, streams)
