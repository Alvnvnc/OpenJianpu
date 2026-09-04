"""
Perkiraan kebutuhan ruang horizontal birama Not Angka (tanpa cairo).

Dipakai parser untuk memutuskan berapa birama per sistem, dan renderer untuk
membagi lebar sistem secara proporsional, sehingga keduanya sepakat.
"""

from typing import List
from .schema import Measure

PAGE_WIDTH = 595.28
MARGIN = 38.0
LABEL_GUTTER = 26.0
SYSTEM_USABLE_WIDTH = PAGE_WIDTH - 2 * MARGIN - LABEL_GUTTER  # ~493 pt


def estimate_measure_width(m: Measure, capacity_units: float = 4.0) -> float:
    """Lebar alami sebuah birama dalam pt (nyaman dibaca, sebelum dikompresi ke lebar sistem).

    Faktor: jumlah simbol suara terpadat, subdivisi (balok/tuplet), kepadatan suku kata lirik,
    panjang total teks lirik, birama diam, dan kapasitas ketukan (birama 2/4 lebih sempit).
    """
    v_counts = [len(v.notes) for v in m.voices.values() if v.notes]
    max_notes = max(v_counts) if v_counts else 4

    subdiv_factor = 1.0
    for v in m.voices.values():
        for n in v.notes:
            if n.beams >= 2 or n.tuplet:
                subdiv_factor = max(subdiv_factor, 1.5)
            elif n.beams >= 1:
                subdiv_factor = max(subdiv_factor, 1.2)

    min_lyric_measure_w = 0.0
    total_lyric_len = 0
    for v in m.voices.values():
        notes_with_lyric = [n for n in v.notes if n.lyric]
        for k in range(len(notes_with_lyric) - 1):
            n1 = notes_with_lyric[k]
            n2 = notes_with_lyric[k + 1]
            b1 = getattr(n1, "beat", 1.0) or 1.0
            b2 = getattr(n2, "beat", 1.0) or 1.0
            delta_b = max(b2 - b1, 0.25)
            syl_w = len(n1.lyric) * 5.6 + 4.0
            needed_w = min((syl_w / delta_b) * 2.5 + 60.0, 160.0)
            min_lyric_measure_w = max(min_lyric_measure_w, needed_w)
        syls = [n.lyric for n in v.notes if n.lyric]
        if syls:
            total_lyric_len = max(total_lyric_len, sum(len(s) for s in syls))
        for verse_idx in range(0, 8):
            vs = [n.verses[verse_idx] for n in v.notes if getattr(n, "verses", None) and len(n.verses) > verse_idx and n.verses[verse_idx]]
            if vs:
                total_lyric_len = max(total_lyric_len, sum(len(s) for s in vs))
    for l_txt in m.lyrics.values():
        if l_txt:
            total_lyric_len = max(total_lyric_len, len(l_txt))

    is_all_rests = all(all(n.text == "0" for n in v.notes) for v in m.voices.values() if v.notes)
    if is_all_rests and not total_lyric_len:
        combined_w = 55.0
    else:
        note_w = max_notes * subdiv_factor * 18.0
        lyric_total_w = total_lyric_len * 6.8 + 24.0
        combined_w = max(note_w, min_lyric_measure_w, lyric_total_w, 85.0)

    if capacity_units < 3.5 and not (max_notes >= 4 or total_lyric_len >= 8 or subdiv_factor > 1.0):
        combined_w = max(combined_w * (capacity_units / 4.0), 50.0)
    return combined_w
