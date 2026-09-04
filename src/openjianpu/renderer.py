"""
Engine Renderer Vektor PDF Not Angka Mandiri.
Menghasilkan dokumen PDF Vektor presisi tinggi berstandar lagumisa.web.id
menggunakan PyCairo, tanpa LilyPond.
"""

import cairo
import math
import os
from typing import List, Dict, Optional, Tuple
from .schema import (
    NotAngkaScore, Measure, MeasureVoice, NoteItem, DynamicMark, SystemBlockConfig
)
from .meter import parse_meter, group_index, POLICY_QUARTER
from .layout import estimate_measure_width

# Dimensi A4 standar dalam poin (72 pt = 1 inch)
PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89

# Tipografi
FONT_TITLE = "Liberation Serif"
FONT_META = "Liberation Serif"
FONT_DYNAMICS = "Liberation Serif"
FONT_MUSIC = "Liberation Sans"
FONT_LYRICS = "Liberation Sans"


class NotAngkaRenderer:
    def __init__(self, score: NotAngkaScore, out_path: str):
        self.score = score
        self.out_path = out_path
        self.margin_left = 38.0
        self.margin_right = PAGE_WIDTH - 38.0
        self.margin_top = 40.0
        self.margin_bottom = 40.0
        self.content_width = self.margin_right - self.margin_left

        self.surface = cairo.PDFSurface(self.out_path, PAGE_WIDTH, PAGE_HEIGHT)
        self.cr = cairo.Context(self.surface)
        self.current_page = 1
        self.current_y = self.margin_top

    def render(self):
        """Merender seluruh partitur ke file PDF."""
        # 1. Halaman Pertama: Gambar Header
        self._init_page()
        self._render_header()

        # 2. Render Sistem-Sistem
        # Jika score.systems belum didefinisikan, bagi otomatis
        systems = self.score.systems if self.score.systems else self._auto_split_systems()

        for sys_idx, sys_cfg in enumerate(systems):
            # Cek apakah sistem ini muat di halaman saat ini
            sys_height = self._estimate_system_height(sys_cfg)
            if self.current_y + sys_height > PAGE_HEIGHT - self.margin_bottom:
                self._draw_page_number()
                self.cr.show_page()
                self.current_page += 1
                self._init_page()
                self._draw_running_header()

            self._render_system(sys_cfg)

        # Halaman terakhir: nomor halaman
        self._draw_page_number()
        self.surface.show_page()
        self.surface.finish()

    def _init_page(self):
        """Menginisialisasi latar putih bersih."""
        self.cr.set_source_rgb(1.0, 1.0, 1.0)
        self.cr.paint()
        self.cr.set_source_rgb(0.0, 0.0, 0.0)

    def _draw_running_header(self):
        """Menulis judul partitur elegan di atas halaman kedua dan seterusnya."""
        self.cr.select_font_face(FONT_TITLE, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(9.0)
        self.cr.move_to(self.margin_left, self.margin_top + 4.0)
        self.cr.show_text(self.score.meta.title)

        # Garis batas header tipis
        self.cr.set_line_width(0.5)
        self.cr.move_to(self.margin_left, self.margin_top + 8.0)
        self.cr.line_to(self.margin_right, self.margin_top + 8.0)
        self.cr.stroke()

        self.current_y = self.margin_top + 24.0

    def _draw_page_number(self):
        """Menulis nomor halaman di bawah tengah."""
        self.cr.select_font_face(FONT_LYRICS, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(10.0)
        num_str = str(self.current_page)
        xbear, ybear, w, h, dx, dy = self.cr.text_extents(num_str)
        self.cr.move_to((PAGE_WIDTH - w) / 2.0, PAGE_HEIGHT - 22.0)
        self.cr.show_text(num_str)

    def _render_header(self):
        """Menggambar judul utama, subjudul, dan metadata komposer/arranger berstandar tinggi."""
        box_top = self.current_y
        has_subtitle = bool(getattr(self.score.meta, "subtitle", None))
        box_height = 54.0 if has_subtitle else 44.0

        # Bingkai Judul Elegan
        self.cr.set_line_width(1.0)
        self.cr.rectangle(self.margin_left, box_top, self.content_width, box_height)
        self.cr.stroke()

        # Teks Judul Utama (Serif Italic Bold)
        self.cr.select_font_face(FONT_TITLE, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        self.cr.set_font_size(20.0)
        title_text = self.score.meta.title
        _, _, tw, th, _, _ = self.cr.text_extents(title_text)

        if has_subtitle:
            self.cr.move_to(self.margin_left + (self.content_width - tw) / 2.0, box_top + 24.0)
            self.cr.show_text(title_text)

            self.cr.select_font_face(FONT_TITLE, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
            self.cr.set_font_size(10.5)
            sub_text = self.score.meta.subtitle
            _, _, sub_w, _, _, _ = self.cr.text_extents(sub_text)
            self.cr.move_to(self.margin_left + (self.content_width - sub_w) / 2.0, box_top + 42.0)
            self.cr.show_text(sub_text)
        else:
            self.cr.move_to(self.margin_left + (self.content_width - tw) / 2.0, box_top + (box_height + th) / 2.0 - 2.0)
            self.cr.show_text(title_text)

        # Metadata Bawah Kotak
        meta_y1 = box_top + box_height + 18.0
        meta_y2 = meta_y1 + 15.0

        # Kiri: Do=X, metrum, dan Lirik/Puisi jika ada
        lyricist_txt = getattr(self.score.meta, "lyricist", "")
        tonal_str = f"{self.score.meta.tonic_label}, {self.score.meta.time_signature}"

        if lyricist_txt:
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
            self.cr.set_font_size(11.0)
            self.cr.move_to(self.margin_left, meta_y1)
            self.cr.show_text(lyricist_txt)

            self.cr.set_font_size(11.0)
            self.cr.move_to(self.margin_left, meta_y2)
            self.cr.show_text(tonal_str)

            _, _, tw_tonal, _, _, _ = self.cr.text_extents(tonal_str)
            tempo_base_x = self.margin_left + tw_tonal + 14.0
        else:
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
            self.cr.set_font_size(12.0)
            self.cr.move_to(self.margin_left, meta_y1)
            self.cr.show_text(tonal_str)
            tempo_base_x = self.margin_left

        # Tempo: kata tempo dan/atau ikon not + BPM; tidak dicetak bila sumber tidak menyebutnya
        tempo = self.score.meta.tempo
        tempo_text = getattr(tempo, "text", "") or ""
        tx = tempo_base_x
        if tempo_text:
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            self.cr.set_font_size(11.0)
            self.cr.move_to(tx, meta_y2)
            self.cr.show_text(tempo_text)
            tx += self.cr.text_extents(tempo_text)[4] + 10.0
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
            self.cr.set_font_size(11.0)
        if tempo.bpm:
            self.cr.save()
            self.cr.translate(tx + 4.0, meta_y2 - 3.0)
            self.cr.rotate(-0.35)
            self.cr.scale(1.2, 0.8)
            self.cr.arc(0, 0, 3.2, 0, 2 * math.pi)
            self.cr.fill()
            self.cr.restore()

            self.cr.set_line_width(0.9)
            self.cr.move_to(tx + 7.2, meta_y2 - 3.5)
            self.cr.line_to(tx + 7.2, meta_y2 - 14.5)
            self.cr.stroke()

            self.cr.move_to(tx + 14.0, meta_y2)
            self.cr.show_text(f"= {tempo.bpm}")

        # Kanan: Komposer dan/atau Arranger
        self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(11.0)
        comp_txt = getattr(self.score.meta, "composer", "")
        arr_txt = getattr(self.score.meta, "arranger", "")

        if comp_txt and arr_txt:
            _, _, cw, _, _, _ = self.cr.text_extents(comp_txt)
            self.cr.move_to(self.margin_right - cw, meta_y1)
            self.cr.show_text(comp_txt)

            _, _, aw, _, _, _ = self.cr.text_extents(arr_txt)
            self.cr.move_to(self.margin_right - aw, meta_y2)
            self.cr.show_text(arr_txt)
        elif comp_txt:
            _, _, cw, _, _, _ = self.cr.text_extents(comp_txt)
            self.cr.move_to(self.margin_right - cw, meta_y1)
            self.cr.show_text(comp_txt)
        elif arr_txt:
            _, _, aw, _, _, _ = self.cr.text_extents(arr_txt)
            self.cr.move_to(self.margin_right - aw, meta_y1)
            self.cr.show_text(arr_txt)

        self.current_y = meta_y2 + 20.0

    def _estimate_system_height(self, sys_cfg: SystemBlockConfig) -> float:
        """Menghitung estimasi tinggi vertikal sistem secara adaptif."""
        measures_all = [m for m in self.score.measures if m.number in sys_cfg.measure_indices]
        if sys_cfg.block_type == "single_solo":
            v = (sys_cfg.voices or ["S"])[0]
            return 65.0 + 11.0 * self._extra_verses(measures_all, [v])
        elif sys_cfg.block_type == "sa_duet":
            return 85.0 + 11.0 * self._extra_verses(measures_all, ["S", "A"])
        elif sys_cfg.block_type == "satb_paired":
            measures = measures_all
            sa_ind = self._voices_have_independent_lyrics(measures, "S", "A")
            tb_ind = self._voices_have_independent_lyrics(measures, "T", "B")
            h = 160.0
            if sa_ind:
                h += 30.0 + 11.0 * (self._extra_verses(measures, ["S"]) + self._extra_verses(measures, ["A"]))
            else:
                h += 11.0 * self._extra_verses(measures, ["S", "A"])
            if tb_ind:
                h += 30.0 + 11.0 * (self._extra_verses(measures, ["T"]) + self._extra_verses(measures, ["B"]))
            else:
                h += 11.0 * self._extra_verses(measures, ["T", "B"])
            return h
        elif sys_cfg.block_type == "general_multivoice":
            measures = [m for m in self.score.measures if m.number in sys_cfg.measure_indices]
            voices = sys_cfg.voices or []
            if not voices:
                voices = list({v for m in measures for v in m.voices})
            num_staves = max(len(voices), 1)
            num_lyrics = sum(
                1 for v in voices
                if any(n.lyric for m in measures for n in m.voices.get(v, MeasureVoice(v)).notes)
            )
            num_lyrics += sum(self._extra_verses(measures, [v]) * (11.0 / 13.5) for v in voices)
            section_changes = 0
            for k in range(len(voices) - 1):
                fam1 = voices[k][:1]
                fam2 = voices[k + 1][:1]
                if fam1 != fam2:
                    section_changes += 1

            h = 16.0 + (num_staves * 22.0) + (num_lyrics * 13.5) + (section_changes * 7.0) + 26.0
            return h
        return 90.0

    def _auto_split_systems(self) -> List[SystemBlockConfig]:
        """Jika konfigurasi sistem tidak dispesifikasi, bagi rata 4 birama per sistem."""
        systems = []
        n = len(self.score.measures)
        i = 0
        while i < n:
            chunk = [self.score.measures[j].number for j in range(i, min(i + 4, n))]
            systems.append(SystemBlockConfig(measure_indices=chunk, block_type="satb_paired"))
            i += 4
        return systems

    def _render_system(self, sys_cfg: SystemBlockConfig):
        """Merender satu baris sistem partitur."""
        measures = [m for m in self.score.measures if m.number in sys_cfg.measure_indices]
        if not measures:
            return

        measure_widths = self._calculate_measure_widths(measures)

        measure_x_starts = []
        cur_x = self.margin_left + 26.0
        for w in measure_widths:
            measure_x_starts.append(cur_x)
            cur_x += w

        if sys_cfg.block_type == "single_solo":
            self._render_single_voice_block(sys_cfg, measures, measure_widths, measure_x_starts)
        elif sys_cfg.block_type == "sa_duet":
            self._render_sa_duet_block(sys_cfg, measures, measure_widths, measure_x_starts)
        elif sys_cfg.block_type == "satb_paired":
            self._render_paired_choral_block(sys_cfg, measures, measure_widths, measure_x_starts)
        elif sys_cfg.block_type == "general_multivoice":
            self._render_general_multivoice_block(sys_cfg, measures, measure_widths, measure_x_starts)
        else:
            self._render_general_multivoice_block(sys_cfg, measures, measure_widths, measure_x_starts)

    def _policy(self) -> str:
        return getattr(self.score.meta, "beat_unit", POLICY_QUARTER) or POLICY_QUARTER

    def _meter_of(self, m: Optional[Measure] = None):
        ts = (m.time_signature if m and m.time_signature else None) or self.score.meta.time_signature or "4/4"
        return parse_meter(ts)

    def _get_measure_total_beats(
        self, m: Optional[Measure] = None, notes: Optional[List[NoteItem]] = None
    ) -> float:
        """Kapasitas grid birama dalam unit ketuk (lihat notangka.meter).

        Grid dihitung SEKALI untuk seluruh suara dalam birama (bukan per suara) agar
        S/A/T/B yang berbagi birama selalu sejajar pada ketukan yang sama. Kapasitas
        diambil dari sukat (atau capacity_beats untuk birama gantung/penggenap) dan
        hanya diperlebar bila ada suara yang isinya meluap.
        """
        meter = self._meter_of(m)
        cap = meter.capacity_units(self._policy())
        if m is not None and getattr(m, "capacity_beats", None):
            cap = float(m.capacity_beats)

        voice_note_lists: List[List[NoteItem]] = []
        if m is not None:
            voice_note_lists = [v.notes for v in m.voices.values() if v.notes]
        if notes and not voice_note_lists:
            voice_note_lists = [notes]

        content = 0.0
        for ns in voice_note_lists:
            if len(ns) == 1 and ns[0].text == "0":
                continue  # tanda diam satu birama penuh: durasinya = kapasitas
            for n in ns:
                dur = getattr(n, "duration_beats", 1.0) or 1.0
                b = getattr(n, "beat", 1.0) or 1.0
                content = max(content, b - 1.0 + dur)

        return max(cap, content)

    def _meter_change_label(self, m: Measure) -> Optional[str]:
        """Teks sukat yang harus dicetak di awal birama ini bila sukatnya berubah."""
        if not m or not m.time_signature:
            return None
        ms = self.score.measures
        idx = next((i for i, mm in enumerate(ms) if mm is m), None)
        if idx is None:
            idx = next((i for i, mm in enumerate(ms) if mm.number == m.number), 0)
        if idx == 0:
            return None  # sukat awal sudah tercetak di kepala partitur
        prev_ts = None
        for j in range(idx - 1, -1, -1):
            if ms[j].time_signature:
                prev_ts = ms[j].time_signature
                break
        prev_ts = prev_ts or self.score.meta.time_signature or "4/4"
        if parse_meter(m.time_signature).label != parse_meter(prev_ts).label:
            return m.time_signature
        return None

    def _tonic_change_label(self, m: Measure) -> Optional[str]:
        """Teks 'Do=X' yang harus dicetak di awal birama ini bila nada dasarnya berubah (modulasi)."""
        if not m or not getattr(m, "tonic_label", None):
            return None
        ms = self.score.measures
        idx = next((i for i, mm in enumerate(ms) if mm is m), None)
        if idx is None:
            idx = next((i for i, mm in enumerate(ms) if mm.number == m.number), 0)
        prev = None
        for j in range(idx - 1, -1, -1):
            if getattr(ms[j], "tonic_label", None):
                prev = ms[j].tonic_label
                break
        prev = prev or self.score.meta.tonic_label
        if idx == 0:
            prev = self.score.meta.tonic_label
        if m.tonic_label != prev:
            return m.tonic_label
        return None

    def _draw_meter_change(self, m: Measure, m_x: float, bar_top: float) -> bool:
        """Mencetak tanda-tanda awal birama di atas garis awal birama, untuk SEMUA jenis blok:
        pergantian sukat (misal 7/8), pergantian nada dasar (Do=X), dan hitungan birama diam beruntun.
        """
        self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        self.cr.set_font_size(10.0)
        x = m_x + 2.5
        drawn = False
        label = self._meter_change_label(m)
        if label:
            self.cr.move_to(x, bar_top - 4.5)
            self.cr.show_text(label)
            x += self.cr.text_extents(label)[4] + 7.0
            drawn = True
        tonic = self._tonic_change_label(m)
        if tonic:
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            self.cr.set_font_size(10.0)
            self.cr.move_to(x, bar_top - 4.5)
            self.cr.show_text(tonic)
            drawn = True
        if getattr(m, "multi_rest", 1) > 1:
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
            self.cr.set_font_size(8.5)
            txt = f"{m.multi_rest} birama"
            self.cr.move_to(x if drawn else m_x + 4.0, bar_top - 4.5)
            self.cr.show_text(txt)
            x += self.cr.text_extents(txt)[4] + 7.0
            drawn = True
        if self._measure_overflows(m):
            # Penanda diagnostik: isi birama melebihi sukat di sumbernya (tidak disembunyikan)
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            self.cr.set_font_size(8.5)
            txt = f"! m{m.number}"
            self.cr.move_to(x if drawn else m_x + 4.0, bar_top - 4.5)
            self.cr.show_text(txt)
            drawn = True
        return drawn

    def _measure_overflows(self, m: Measure) -> bool:
        """True bila ada suara yang jumlah durasinya melebihi kapasitas birama."""
        cap = self._meter_of(m).capacity_units(self._policy())
        if getattr(m, "capacity_beats", None):
            cap = float(m.capacity_beats)
        for v in m.voices.values():
            if not v.notes or (len(v.notes) == 1 and v.notes[0].text == "0"):
                continue
            total = sum((n.duration_beats or 0.0) for n in v.notes)
            if total > cap + 0.03:
                return True
        return False

    def _extra_verses(self, measures: List[Measure], voices: List[str]) -> int:
        """Jumlah bait tambahan (bait 2, 3, ...) yang ada pada suara-suara ini dalam sistem."""
        n = 0
        for m in measures:
            for v in voices:
                mv = m.voices.get(v)
                if not mv:
                    continue
                for note in mv.notes:
                    vs = getattr(note, "verses", None)
                    if vs:
                        k = len(vs)
                        while k > 0 and not vs[k - 1]:
                            k -= 1
                        n = max(n, k)
        return n

    def _heal_notes(self, notes: List[NoteItem]):
        """
        Memulihkan bendera (beams) dan durasi nada yang hilang secara otomatis dan dinamis:
        1. Titik perpanjangan (text == '.') satu unit penuh tidak berbendera; titik sub-unit
           (misal 0,5 ketuk) berbendera sesuai nilainya.
        2. Jika nada bertitik tunggal (dot=True, beams=0), nada berikutnya yang non-titik (text != '.')
           dan berjarak sub-ketukan WAJIB memiliki bendera balok (beams=1, durasi 0.5 ketuk).
        3. Jika nada memiliki durasi <= 0.58 ketuk, pastikan memiliki minimal 1 balok.
        4. Jika nada memiliki durasi <= 0.28 ketuk, pastikan memiliki 2 balok.
        """
        for i, n in enumerate(notes):
            # Jika sudah ada triplet, tidak perlu bendera garis datar lagi
            if getattr(n, "tuplet", None) == "3":
                n.beams = 0
                continue

            # Titik perpanjangan: satu unit penuh tanpa balok; sub-unit berbalok sesuai nilainya
            # (Puji Syukur 347b menulis "3 .̅ 3̅" untuk seperempat bertitik + seperdelapan).
            if n.text == ".":
                dur = getattr(n, "duration_beats", None)
                if dur is None or dur >= 0.85:
                    n.beams = 0
                elif dur <= 0.28 and n.beams < 2:
                    n.beams = 2
                elif dur <= 0.58 and n.beams == 0:
                    n.beams = 1
                continue

            # Kasus A: Nada setelah not bertitik tunggal (1.5 ketuk)
            if i > 0 and notes[i - 1].dot and notes[i - 1].beams == 0:
                if n.beams == 0 and n.text != "." and not n.dot:
                    n.beams = 1
                    n.duration_beats = 0.5

            # Kasus B: Nada sub-ketukan yang kehilangan bendera
            if getattr(n, "duration_beats", None) is not None and n.text != ".":
                if n.duration_beats <= 0.28 and n.beams < 2:
                    n.beams = 2
                elif n.duration_beats <= 0.58 and n.beams == 0:
                    n.beams = 1

    def _calculate_measure_widths(self, measures: List[Measure]) -> List[float]:
        """
        Menghitung alokasi lebar birama secara dinamis dan otomatis menyesuaikan:
        - Memperhitungkan jumlah nada pada suara paling padat
        - Memberi ruang ekstra untuk birama yang memuat nada 1/16 atau triplet
        - Menganalisis densitas suku kata lirik agar tidak ada teks yang bertabrakan
        - Menyesuaikan secara proporsional dengan lebar halaman yang tersedia
        """
        available_w = self.content_width - 26.0
        weights = []

        for m in measures:
            # Sembuhkan nada-nada pada semua suara terlebih dahulu
            for v in m.voices.values():
                self._heal_notes(v.notes)
            weights.append(estimate_measure_width(m, self._get_measure_total_beats(m)))

        total_weight = sum(weights)
        widths = [(w / total_weight) * available_w for w in weights]

        # Penyesuaian batas minimum per birama
        min_w = 85.0 if available_w >= 85.0 * len(widths) else 60.0
        for i in range(len(widths)):
            m_beats = self._get_measure_total_beats(measures[i])
            m_all_rests = all(all(n.text == "0" for n in v.notes) for v in measures[i].voices.values() if v.notes)
            if m_all_rests and not measures[i].lyrics:
                m_min_w = 50.0
            elif m_beats <= 2.0:
                m_min_w = 50.0
            else:
                m_min_w = min_w
            if widths[i] < m_min_w and available_w >= m_min_w * len(widths):
                diff = m_min_w - widths[i]
                widths[i] = m_min_w
                max_idx = widths.index(max(widths))
                widths[max_idx] -= diff

        return widths

    def _render_single_voice_block(
        self, sys_cfg: SystemBlockConfig, measures: List[Measure],
        widths: List[float], x_starts: List[float]
    ):
        """Merender sistem satu suara (misalnya Sopran Solo Intro)."""
        sys_top = self.current_y
        dyn_y = sys_top + 8.0
        voice_y = sys_top + 34.0
        lyric_y = voice_y + 17.0
        vname = (sys_cfg.voices or ["S"])[0]
        n_extra = self._extra_verses(measures, [vname])

        bar_top = voice_y - 13.0
        bar_bot = voice_y + 4.0

        # Label suara di kiri (S, Solo, U, T, ...)
        self.cr.select_font_face(FONT_MUSIC, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(13.5 if len(vname) <= 2 else 10.0)
        self.cr.move_to(self.margin_left, voice_y)
        self.cr.show_text(vname)

        # Garis birama pembuka sistem
        self.cr.set_line_width(0.8)
        self.cr.move_to(x_starts[0], bar_top)
        self.cr.line_to(x_starts[0], bar_bot)
        self.cr.stroke()

        for idx, m in enumerate(measures):
            m_x = x_starts[idx]
            m_w = widths[idx]
            m_end_x = m_x + m_w

            # 0. Pergantian sukat (misal 4/4 -> 2/4) di atas garis awal birama, garis kiri khusus
            has_ts_change = self._draw_meter_change(m, m_x, bar_top)
            self._draw_left_barline(m, m_x, bar_top, bar_bot)

            # 1. Gambar Not-not suara sistem ini
            v = m.voices.get(vname)
            s_pos = []
            if v and v.notes:
                s_pos = self._draw_voice_notes(v.notes, m_x, m_w, voice_y, m)

            # 2. Gambar Dinamika
            for dyn in m.dynamics:
                dy = dyn_y - 11.0 if (has_ts_change and dyn.beat <= 1.5) else dyn_y
                self._draw_dynamic(dyn, m_x, m_w, dy, m)

            # 3. Gambar Lirik Presisi per Suku Kata (bait 1 dan bait-bait berikutnya)
            self._draw_voice_lyrics(m, m_x, m_w, lyric_y, v, None, s_pos, [])
            for k in range(1, n_extra + 1):
                self._draw_single_voice_lyrics(m, m_x, m_w, lyric_y + 11.0 * k, v, s_pos, verse=k)

            # 4. Gambar Garis Birama Penutup
            self._draw_barline(m.barline_type, m_end_x, bar_top, bar_bot)

        self.current_y = lyric_y + 22.0 + 11.0 * n_extra

    def _render_sa_duet_block(
        self, sys_cfg: SystemBlockConfig, measures: List[Measure],
        widths: List[float], x_starts: List[float]
    ):
        """Merender sistem dua suara (Sopran & Alto) dengan lirik bersama."""
        sys_top = self.current_y
        sa_dyn_y = sys_top + 10.0
        s_y = sys_top + 26.0
        a_y = sys_top + 46.0
        sa_lyric_y = sys_top + 63.0

        sa_bar_top = s_y - 13.0
        sa_bar_bot = a_y + 4.0
        n_extra = self._extra_verses(measures, ["S", "A"])

        # Label S & A
        self.cr.select_font_face(FONT_MUSIC, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(13.0)
        self.cr.move_to(self.margin_left, s_y)
        self.cr.show_text("S")
        self.cr.move_to(self.margin_left, a_y)
        self.cr.show_text("A")

        # Garis birama awal sistem SA
        self.cr.set_line_width(0.8)
        self.cr.move_to(x_starts[0], sa_bar_top)
        self.cr.line_to(x_starts[0], sa_bar_bot)
        self.cr.stroke()

        for idx, m in enumerate(measures):
            m_x = x_starts[idx]
            m_w = widths[idx]
            m_end_x = m_x + m_w

            # Pergantian sukat di atas garis awal birama, garis kiri khusus
            has_ts_change = self._draw_meter_change(m, m_x, sa_bar_top)
            self._draw_left_barline(m, m_x, sa_bar_top, sa_bar_bot)

            # Suara S & A
            v_s = m.voices.get("S")
            s_pos = []
            if v_s and v_s.notes:
                s_pos = self._draw_voice_notes(v_s.notes, m_x, m_w, s_y, m)

            v_a = m.voices.get("A")
            a_pos = []
            if v_a and v_a.notes:
                a_pos = self._draw_voice_notes(v_a.notes, m_x, m_w, a_y, m)

            # Dinamika di atas S
            for dyn in m.dynamics:
                dy = sa_dyn_y - 11.0 if (has_ts_change and dyn.beat <= 1.5) else sa_dyn_y
                self._draw_dynamic(dyn, m_x, m_w, dy, m)

            # Lirik Bersama presisi di bawah A (bait 1 dan bait-bait berikutnya)
            self._draw_voice_lyrics(m, m_x, m_w, sa_lyric_y, v_s, v_a, s_pos, a_pos)
            for k in range(1, n_extra + 1):
                self._draw_voice_lyrics(m, m_x, m_w, sa_lyric_y + 11.0 * k, v_s, v_a, s_pos, a_pos, verse=k)

            # Garis birama menembus S dan A
            self._draw_barline(m.barline_type, m_end_x, sa_bar_top, sa_bar_bot)

        self.current_y = sa_lyric_y + 20.0 + 11.0 * n_extra

    def _voices_have_independent_lyrics(
        self, measures: List[Measure], v1_name: str, v2_name: str
    ) -> bool:
        """
        Mendeteksi apakah dua suara dalam sistem ini memiliki lirik atau ritme yang berbeda (polifonik),
        sehingga membutuhkan baris lirik terpisah untuk masing-masing suara.
        """
        for m in measures:
            v1 = m.voices.get(v1_name)
            v2 = m.voices.get(v2_name)
            n1 = [n for n in v1.notes if n.lyric] if v1 else []
            n2 = [n for n in v2.notes if n.lyric] if v2 else []
            if n1 and n2:
                s1 = [(round(n.beat, 2), n.lyric.strip()) for n in n1]
                s2 = [(round(n.beat, 2), n.lyric.strip()) for n in n2]
                if s1 != s2:
                    return True
            elif (n1 and not n2) or (n2 and not n1):
                return True
        return False

    def _render_paired_choral_block(
        self, sys_cfg: SystemBlockConfig, measures: List[Measure],
        widths: List[float], x_starts: List[float]
    ):
        """
        Merender sistem paduan suara berpasangan khas Indonesia:
        - Mendukung lirik bersama jika suara seirama (homofonik)
        - Mendukung baris lirik mandiri jika suara berirama/berlirik beda (polifonik/kontrapung)
        - Blok Treble (Sopran & Alto) dan Blok Bass (Tenor & Bas) kompak terpadu dalam satu akolade SATB.
        """
        sys_top = self.current_y

        sa_independent = self._voices_have_independent_lyrics(measures, "S", "A")
        tb_independent = self._voices_have_independent_lyrics(measures, "T", "B")

        # Deteksi kebutuhan ruang ekstra dinamis jika terdapat oktaf ekstrim
        max_s_low = max((abs(n.octave) for m in measures for n in m.voices.get("S", MeasureVoice("S")).notes if n.octave < 0), default=0)
        max_a_high = max((n.octave for m in measures for n in m.voices.get("A", MeasureVoice("A")).notes if n.octave > 0 and n.beams > 0), default=0)
        sa_extra = max(0.0, (max_s_low - 1) * 3.5 + max_a_high * 4.0)

        max_t_low = max((abs(n.octave) for m in measures for n in m.voices.get("T", MeasureVoice("T")).notes if n.octave < 0), default=0)
        max_b_high = max((n.octave for m in measures for n in m.voices.get("B", MeasureVoice("B")).notes if n.octave > 0 and n.beams > 0), default=0)
        tb_extra = max(0.0, (max_t_low - 1) * 3.5 + max_b_high * 4.0)

        # --- 1. BLOK TREBLE (SA) ---
        sa_dyn_y = sys_top + 6.0
        s_y = sys_top + 22.0
        if sa_independent:
            nv_s = self._extra_verses(measures, ["S"])
            nv_a = self._extra_verses(measures, ["A"])
            s_lyric_y = s_y + 14.0
            a_y = s_lyric_y + 22.0 + sa_extra + 11.0 * nv_s
            a_lyric_y = a_y + 14.0
            sa_bridge_y = a_lyric_y + 11.0 * nv_a
        else:
            nv_sa = self._extra_verses(measures, ["S", "A"])
            a_y = s_y + 24.0 + sa_extra
            sa_lyric_y = a_y + 16.0
            sa_bridge_y = sa_lyric_y + 11.0 * nv_sa

        sa_bar_top = s_y - 12.0
        sa_bar_bot = a_y + 4.0

        # Label S & A
        self.cr.select_font_face(FONT_MUSIC, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(13.0)
        self.cr.move_to(self.margin_left, s_y)
        self.cr.show_text("S")
        self.cr.move_to(self.margin_left, a_y)
        self.cr.show_text("A")

        # Garis birama awal sistem SA
        self.cr.set_line_width(0.8)
        self.cr.move_to(x_starts[0], sa_bar_top)
        self.cr.line_to(x_starts[0], sa_bar_bot)
        self.cr.stroke()

        for idx, m in enumerate(measures):
            m_x = x_starts[idx]
            m_w = widths[idx]
            m_end_x = m_x + m_w

            # Pergantian sukat di atas garis awal birama, garis kiri khusus
            has_ts_change = self._draw_meter_change(m, m_x, sa_bar_top)
            self._draw_left_barline(m, m_x, sa_bar_top, sa_bar_bot)

            # Suara S & A
            v_s = m.voices.get("S")
            s_pos = []
            if v_s and v_s.notes:
                s_pos = self._draw_voice_notes(v_s.notes, m_x, m_w, s_y, m)

            v_a = m.voices.get("A")
            a_pos = []
            if v_a and v_a.notes:
                a_pos = self._draw_voice_notes(v_a.notes, m_x, m_w, a_y, m)

            # Dinamika di atas S
            for dyn in m.dynamics:
                dy = sa_dyn_y - 11.0 if (has_ts_change and dyn.beat <= 1.5) else sa_dyn_y
                self._draw_dynamic(dyn, m_x, m_w, dy, m)

            # Lirik S & A (mandiri jika polifonik, bersama jika homofonik), termasuk bait 2..n
            if sa_independent:
                self._draw_single_voice_lyrics(m, m_x, m_w, s_lyric_y, v_s, s_pos)
                for k in range(1, nv_s + 1):
                    self._draw_single_voice_lyrics(m, m_x, m_w, s_lyric_y + 11.0 * k, v_s, s_pos, verse=k)
                self._draw_single_voice_lyrics(m, m_x, m_w, a_lyric_y, v_a, a_pos)
                for k in range(1, nv_a + 1):
                    self._draw_single_voice_lyrics(m, m_x, m_w, a_lyric_y + 11.0 * k, v_a, a_pos, verse=k)
            else:
                self._draw_voice_lyrics(m, m_x, m_w, sa_lyric_y, v_s, v_a, s_pos, a_pos)
                for k in range(1, nv_sa + 1):
                    self._draw_voice_lyrics(m, m_x, m_w, sa_lyric_y + 11.0 * k, v_s, v_a, s_pos, a_pos, verse=k)

            # Garis birama menembus S dan A
            self._draw_barline(m.barline_type, m_end_x, sa_bar_top, sa_bar_bot)

        # --- 2. BLOK BASS (TB) ---
        has_tb = any(
            (m.voices.get("T") and m.voices["T"].notes) or
            (m.voices.get("B") and m.voices["B"].notes)
            for m in measures
        )
        if not has_tb:
            self.current_y = sa_bridge_y + 24.0
            return

        t_y = sa_bridge_y + 22.0
        tb_dyn_y = t_y - 13.0

        if tb_independent:
            nv_t = self._extra_verses(measures, ["T"])
            nv_b = self._extra_verses(measures, ["B"])
            t_lyric_y = t_y + 14.0
            b_y = t_lyric_y + 22.0 + tb_extra + 11.0 * nv_t
            b_lyric_y = b_y + 14.0
            tb_end_y = b_lyric_y + 11.0 * nv_b
        else:
            nv_tb = self._extra_verses(measures, ["T", "B"])
            b_y = t_y + 24.0 + tb_extra
            tb_lyric_y = b_y + 16.0
            tb_end_y = tb_lyric_y + 11.0 * nv_tb

        tb_bar_top = t_y - 12.0
        tb_bar_bot = b_y + 4.0

        # Bracket sistem paduan suara '[' di margin kiri menyatukan SA dan TB
        bracket_x = self.margin_left - 7.0
        self.cr.set_line_width(1.2)
        self.cr.move_to(bracket_x + 4.0, sa_bar_top)
        self.cr.line_to(bracket_x, sa_bar_top)
        self.cr.line_to(bracket_x, tb_bar_bot)
        self.cr.line_to(bracket_x + 4.0, tb_bar_bot)
        self.cr.stroke()

        # Label T & B
        self.cr.select_font_face(FONT_MUSIC, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(13.0)
        self.cr.move_to(self.margin_left, t_y)
        self.cr.show_text("T")
        self.cr.move_to(self.margin_left, b_y)
        self.cr.show_text("B")

        # Garis birama awal sistem TB
        self.cr.set_line_width(0.8)
        self.cr.move_to(x_starts[0], tb_bar_top)
        self.cr.line_to(x_starts[0], tb_bar_bot)
        self.cr.stroke()

        for idx, m in enumerate(measures):
            m_x = x_starts[idx]
            m_w = widths[idx]
            m_end_x = m_x + m_w

            self._draw_left_barline(m, m_x, tb_bar_top, tb_bar_bot)

            # Suara T & B
            v_t = m.voices.get("T")
            t_pos = []
            if v_t and v_t.notes:
                t_pos = self._draw_voice_notes(v_t.notes, m_x, m_w, t_y, m)

            v_b = m.voices.get("B")
            b_pos = []
            if v_b and v_b.notes:
                b_pos = self._draw_voice_notes(v_b.notes, m_x, m_w, b_y, m)

            # Dinamika di atas T
            for dyn in m.dynamics:
                self._draw_dynamic(dyn, m_x, m_w, tb_dyn_y, m)

            # Lirik T & B (mandiri jika polifonik, bersama jika homofonik), termasuk bait 2..n
            if tb_independent:
                self._draw_single_voice_lyrics(m, m_x, m_w, t_lyric_y, v_t, t_pos)
                for k in range(1, nv_t + 1):
                    self._draw_single_voice_lyrics(m, m_x, m_w, t_lyric_y + 11.0 * k, v_t, t_pos, verse=k)
                self._draw_single_voice_lyrics(m, m_x, m_w, b_lyric_y, v_b, b_pos)
                for k in range(1, nv_b + 1):
                    self._draw_single_voice_lyrics(m, m_x, m_w, b_lyric_y + 11.0 * k, v_b, b_pos, verse=k)
            else:
                self._draw_voice_lyrics(m, m_x, m_w, tb_lyric_y, v_t, v_b, t_pos, b_pos)
                for k in range(1, nv_tb + 1):
                    self._draw_voice_lyrics(m, m_x, m_w, tb_lyric_y + 11.0 * k, v_t, v_b, t_pos, b_pos, verse=k)

            # Garis birama menembus T dan B
            self._draw_barline(m.barline_type, m_end_x, tb_bar_top, tb_bar_bot)

        # Jarak konstan antar sistem baris (26 pt)
        self.current_y = tb_end_y + 26.0

    def _render_general_multivoice_block(
        self, sys_cfg: SystemBlockConfig, measures: List[Measure],
        widths: List[float], x_starts: List[float]
    ):
        """
        Merender sistem multi-suara arbitrer (misalnya paduan suara 8-16 suara SSAATTBB / divisi).
        - Tata letak vertikal fleksibel sesuai keberadaan lirik per suara
        - Braket seksi (S, A, T, B) dan akolade penutup '[' di margin kiri
        - Pergantian sukat birama otomatis tercetak di awal birama terkait
        """
        sys_top = self.current_y
        voices = sys_cfg.voices or []
        if not voices:
            voices_set = {v for m in measures for v in m.voices if any(n.text != "0" for n in m.voices[v].notes)}
            from .xml_parser import voice_sort_key
            voices = sorted(list(voices_set), key=voice_sort_key)

        if not voices:
            return

        # Tentukan posisi vertikal y tiap suara dan lirik
        cur_y = sys_top + 16.0
        voice_y_map = {}
        lyric_y_map = {}
        section_ranges = {}

        for i, vname in enumerate(voices):
            has_lyric = any(
                n.lyric for m in measures
                for n in m.voices.get(vname, MeasureVoice(vname)).notes
            )
            v_y = cur_y
            voice_y_map[vname] = v_y

            fam = vname[:1] if not vname.startswith("Solo") else "Solo"
            if fam not in section_ranges:
                section_ranges[fam] = [v_y, v_y]
            else:
                section_ranges[fam][1] = v_y

            if has_lyric:
                l_y = v_y + 13.5
                lyric_y_map[vname] = l_y
                cur_y = l_y + 22.0 + 11.0 * self._extra_verses(measures, [vname])
            else:
                cur_y = v_y + 22.0

            # Celah ekstra antar-seksi vokal (misal antara S dan A, A dan T, T dan B)
            if i + 1 < len(voices):
                next_v = voices[i + 1]
                next_fam = next_v[:1] if not next_v.startswith("Solo") else "Solo"
                if fam != next_fam:
                    cur_y += 7.0

        bar_top = voice_y_map[voices[0]] - 11.5
        bar_bot = voice_y_map[voices[-1]] + 4.5

        # 1. Label Suara di Margin Kiri
        self.cr.select_font_face(FONT_MUSIC, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        self.cr.set_font_size(11.0)
        for vname in voices:
            vy = voice_y_map[vname]
            self.cr.move_to(self.margin_left, vy)
            self.cr.show_text(vname)

        # 2. Bracket Akolade '[' di Margin Kiri menyatukan seluruh suara
        bracket_x = self.margin_left - 8.0
        self.cr.set_line_width(1.4)
        self.cr.move_to(bracket_x + 4.5, bar_top)
        self.cr.line_to(bracket_x, bar_top)
        self.cr.line_to(bracket_x, bar_bot)
        self.cr.line_to(bracket_x + 4.5, bar_bot)
        self.cr.stroke()

        # Braket sub-seksi paduan suara (S, A, T, B) jika ada multi-staf per seksi
        self.cr.set_line_width(0.9)
        for fam, (sy_min, sy_max) in section_ranges.items():
            if sy_max > sy_min + 5.0:
                sub_bx = self.margin_left - 3.5
                sub_top = sy_min - 10.0
                sub_bot = sy_max + 3.5
                self.cr.move_to(sub_bx + 2.5, sub_top)
                self.cr.line_to(sub_bx, sub_top)
                self.cr.line_to(sub_bx, sub_bot)
                self.cr.line_to(sub_bx + 2.5, sub_bot)
                self.cr.stroke()

        # 3. Garis Birama Awal Sistem
        self.cr.set_line_width(0.8)
        self.cr.move_to(x_starts[0], bar_top)
        self.cr.line_to(x_starts[0], bar_bot)
        self.cr.stroke()

        # 4. Render Birama demi Birama
        for idx, m in enumerate(measures):
            m_x = x_starts[idx]
            m_w = widths[idx]
            m_end_x = m_x + m_w

            # Perubahan Sukat Birama di Tengah Lagu:
            # Diletakkan tepat DI ATAS garis awal birama (above system barline),
            # standar partitur paduan suara kontemporer, sehingga 100% bebas tabrakan
            # dengan nada, titik oktaf, maupun teks lirik suara teratas (S1).
            has_ts_change = self._draw_meter_change(m, m_x, bar_top)
            self._draw_left_barline(m, m_x, bar_top, bar_bot)

            # Gambar Dinamika di atas sistem
            for dyn in m.dynamics:
                dyn_y = bar_top - 14.0 if (has_ts_change and dyn.beat <= 1.5) else bar_top - 3.0
                self._draw_dynamic(dyn, m_x, m_w, dyn_y, m)

            # Gambar nada dan lirik per suara
            for vname in voices:
                vy = voice_y_map[vname]
                v = m.voices.get(vname)
                pos = []
                if v and v.notes:
                    pos = self._draw_voice_notes(v.notes, m_x, m_w, vy, m)

                if vname in lyric_y_map:
                    ly = lyric_y_map[vname]
                    if v and v.notes:
                        self._draw_single_voice_lyrics(m, m_x, m_w, ly, v, pos)
                        for k in range(1, self._extra_verses(measures, [vname]) + 1):
                            self._draw_single_voice_lyrics(m, m_x, m_w, ly + 11.0 * k, v, pos, verse=k)

            # Garis Birama Penutup
            self._draw_barline(m.barline_type, m_end_x, bar_top, bar_bot)

        self.current_y = cur_y + 22.0

    def _compute_note_positions(
        self, notes: List[NoteItem], m_x: float, m_w: float, m: Optional[Measure] = None
    ) -> List[float]:
        """
        Menghitung posisi horizontal X nada secara beat-grid adaptif.
        Menjaga alignment vertikal antar suara SATB pada ketukan yang sama.
        """
        num_notes = len(notes)
        if num_notes == 0:
            return []

        # Tanda istirahat 1 birama penuh (single whole-measure rest '0'):
        # Diletakkan persis di tengah birama (horizontal center) sesuai konvensi baku Not Angka
        if num_notes == 1 and notes[0].text == "0":
            return [m_x + (m_w - 7.0) / 2.0]

        self._heal_notes(notes)

        pad_left = 8.0
        pad_right = 8.0
        usable_w = m_w - pad_left - pad_right
        total_beats = self._get_measure_total_beats(m, notes)

        # Ambil atau estimasikan ketukan (beat) untuk setiap not
        beats = []
        has_distinct_beats = len(notes) <= 1 or any(notes[i].beat > notes[i-1].beat for i in range(1, len(notes)))
        if has_distinct_beats and not (len(notes) > 1 and all(n.beat == 1.0 for n in notes)):
            beats = [n.beat for n in notes]
        else:
            cur_b = 1.0
            beats = []
            for n in notes:
                beats.append(cur_b)
                n.beat = cur_b
                if getattr(n, "duration_beats", None) and n.duration_beats > 0:
                    dur = n.duration_beats
                elif getattr(n, "tuplet", None) == "3":
                    dur = 1.0 / 3.0
                elif getattr(n, "beams", 0) == 2:
                    dur = 0.25 * (1.5 if getattr(n, "dot", False) else 1.0)
                elif getattr(n, "beams", 0) == 1:
                    dur = 0.5 * (1.5 if getattr(n, "dot", False) else 1.0)
                elif n.text == ".":
                    dur = 1.0
                else:
                    dur = 1.0 * (1.5 if getattr(n, "dot", False) else 1.0)
                cur_b += dur

        beat_w = usable_w / max(total_beats, 1.0)
        positions = []
        for b in beats:
            rel_beat = max(0.0, b - 1.0)
            nx = m_x + pad_left + (rel_beat * beat_w) + (beat_w * 0.12)
            positions.append(nx)

        # Anti-tabrakan horizontal antar not berurutan
        min_gap = 10.0
        for i in range(1, num_notes):
            if positions[i] < positions[i - 1] + min_gap:
                positions[i] = positions[i - 1] + min_gap

        # Jaga batas kanan birama
        max_x = m_x + m_w - pad_right - 3.0
        if positions[-1] > max_x:
            span = positions[-1] - positions[0]
            if span > 0:
                overflow = positions[-1] - max_x
                scale = max(0.2, (span - overflow) / span)
                p0 = positions[0]
                for i in range(num_notes):
                    positions[i] = p0 + (positions[i] - p0) * scale

        return positions

    def _draw_voice_notes(
        self, notes: List[NoteItem], m_x: float, m_w: float, base_y: float, m: Optional[Measure] = None
    ) -> List[float]:
        """
        Menggambar seluruh nada, oktaf, balok, titik nilai, dan tanda kromatis.
        Mengembalikan daftar posisi horizontal X masing-masing nada untuk lirik.
        """
        num_notes = len(notes)
        if num_notes == 0:
            return []

        positions = self._compute_note_positions(notes, m_x, m_w, m)

        for i, note in enumerate(notes):
            nx = positions[i]

            self.cr.select_font_face(FONT_MUSIC, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            self.cr.set_font_size(13.0)

            if note.text == ".":
                # Titik perpanjangan ketukan (extension dot)
                # Diletakkan tepat di tengah ketinggian angka
                self.cr.new_sub_path()
                self.cr.arc(nx + 3.5, base_y - 3.5, 1.45, 0, 2 * math.pi)
                self.cr.fill()
            else:
                # Angka nada (0-7)
                self.cr.move_to(nx, base_y)
                self.cr.show_text(note.text)

                # Titik Oktaf
                if note.octave > 0:
                    # Oktaf Atas: di atas angka, di bawah garis balok
                    for o in range(note.octave):
                        oy = base_y - 12.0 - (o * 3.2)
                        self.cr.new_sub_path()
                        self.cr.arc(nx + 3.5, oy, 1.25, 0, 2 * math.pi)
                        self.cr.fill()
                elif note.octave < 0:
                    # Oktaf Bawah: di bawah angka
                    for o in range(abs(note.octave)):
                        oy = base_y + 4.5 + (o * 3.2)
                        self.cr.new_sub_path()
                        self.cr.arc(nx + 3.5, oy, 1.25, 0, 2 * math.pi)
                        self.cr.fill()

                # Tanda Kromatis Garis Miring
                if note.accidental == "kres":
                    self.cr.set_line_width(0.75)
                    self.cr.move_to(nx + 0.5, base_y + 1.0)
                    self.cr.line_to(nx + 7.0, base_y - 9.5)
                    self.cr.stroke()
                elif note.accidental == "mol":
                    self.cr.set_line_width(0.75)
                    self.cr.move_to(nx + 0.5, base_y - 9.5)
                    self.cr.line_to(nx + 7.0, base_y + 1.0)
                    self.cr.stroke()

                # Titik Nilai Bawaan (misal nada bertitik 3.)
                if note.dot:
                    if i + 1 < num_notes and positions[i + 1] > nx + 10.0:
                        # Pusatkan titik persis di tengah celah antara batas kanan angka ini dan batas kiri nada berikutnya
                        dot_x = ((nx + 7.0) + positions[i + 1]) / 2.0
                    else:
                        dot_x = nx + 9.5
                    self.cr.new_sub_path()
                    self.cr.arc(dot_x, base_y - 3.5, 1.35, 0, 2 * math.pi)
                    self.cr.fill()

                # Fermata: di atas balok dan titik oktaf
                if note.fermata:
                    fy = base_y - 18.0 - (4.0 if note.octave > 0 else 0.0) - (5.0 if note.beams > 0 else 0.0)
                    self._draw_fermata(nx + 3.5, fy)

            # Busur Legatura / Tie
            if note.tie and i + 1 < num_notes:
                next_note = notes[i + 1]
                # Jika nada berikutnya adalah titik (.), busur tidak diperlukan
                # karena titik di Not Angka secara inheren telah merepresentasikan perpanjangan nada.
                if next_note.text != ".":
                    next_x = positions[i + 1]
                    mid_x = (nx + next_x) / 2.0
                    # Jika ada lirik di bawahnya, gambar busur di atas angka agar tidak menabrak teks lirik
                    has_lyric_below = any(n.lyric for n in notes)
                    if has_lyric_below:
                        tie_y = base_y - 12.0 if note.octave <= 0 else base_y - 16.0
                        self.cr.set_line_width(0.75)
                        self.cr.move_to(nx + 3.5, tie_y)
                        self.cr.curve_to(mid_x, tie_y - 3.5, mid_x, tie_y - 3.5, next_x + 3.5, tie_y)
                        self.cr.stroke()
                    else:
                        tie_y = base_y + 8.0 if note.octave < 0 else base_y + 4.5
                        self.cr.set_line_width(0.75)
                        self.cr.move_to(nx + 3.5, tie_y)
                        self.cr.curve_to(mid_x, tie_y + 3.5, mid_x, tie_y + 3.5, next_x + 3.5, tie_y)
                        self.cr.stroke()

        # Gambar Garis Balok (Overlines)
        self._draw_beams(notes, positions, base_y, m)

        # Gambar Kurung Triplet Berbusur (Arched Tuplet Brackets)
        self._draw_tuplet_brackets(notes, positions, base_y)

        # Busur melisma: satu suku kata dinyanyikan pada beberapa angka
        self._draw_melisma_arcs(notes, positions, base_y)

        return positions

    def _draw_melisma_arcs(self, notes: List[NoteItem], positions: List[float], base_y: float):
        """Busur legato di bawah angka dari suku kata ke angka-angka berikutnya yang tanpa suku kata
        (PS 421a: busur di bawah "i . i"). Hanya untuk suara yang memang berlirik pada birama ini."""
        n = len(notes)
        if n < 2 or len(positions) != n or not any(x.lyric for x in notes):
            return
        i = 0
        while i < n:
            note = notes[i]
            if not note.lyric or note.text in ("0", "."):
                i += 1
                continue
            j = i + 1
            run = []
            while j < n and notes[j].text != "0" and not notes[j].lyric:
                if notes[j].text != ".":
                    run.append(j)
                j += 1
            if run:
                x1 = positions[i] + 3.5
                x2 = positions[run[-1]] + 3.5
                span_min_oct = min(notes[k].octave for k in [i] + run)
                y = base_y + (9.0 if span_min_oct < 0 else 5.0)
                mid = (x1 + x2) / 2.0
                self.cr.set_line_width(0.7)
                self.cr.move_to(x1, y)
                self.cr.curve_to(mid, y + 3.5, mid, y + 3.5, x2, y)
                self.cr.stroke()
            i = j if run else i + 1

    def _beam_groups(self, notes: List[NoteItem], m: Optional[Measure] = None) -> List[List[int]]:
        """Mengelompokkan simbol berbalok per kelompok ketuk sukat (lihat Meter.groups_units).

        * Angka, titik (.), tanda diam (0) yang berbalok ikut kelompok (PS 390b "0̅3̅", PS 347b "3 .̅ 3̅").
        * Kelompok terputus pada batas ketuk (7/8 = 2+2+3, 9/8 = 3+3+3, 6/8 = 3+3, x/4 per seperempat).
        * Triplet tidak berbalok (kurung ╭─3─╮ yang menandainya).
        * Kelompok satu simbol tetap dikembalikan: not 1/8 tunggal harus tetap berbendera.
        """
        n = len(notes)
        if n == 0:
            return []
        meter = self._meter_of(m)
        groups_u = meter.groups_units(self._policy())
        offset = 0.0
        if m is not None and getattr(m, "capacity_beats", None):
            # Birama gantung: kelompok ketuk dihitung rapat ke garis birama berikutnya
            offset = max(0.0, meter.capacity_units(self._policy()) - float(m.capacity_beats))

        def gidx(note: NoteItem) -> int:
            return group_index(max(0.0, (getattr(note, "beat", 1.0) or 1.0) - 1.0) + offset, groups_u)

        groups: List[List[int]] = []
        cur: List[int] = []
        for i, note in enumerate(notes):
            eligible = note.beams > 0 and getattr(note, "tuplet", None) != "3"
            if eligible and cur and gidx(note) == gidx(notes[cur[-1]]):
                cur.append(i)
            elif eligible:
                if cur:
                    groups.append(cur)
                cur = [i]
            else:
                if cur:
                    groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        return groups

    def _draw_beams(
        self, notes: List[NoteItem], positions: List[float], base_y: float, m: Optional[Measure] = None
    ):
        """
        Menggambar garis balok murni horizontal di atas simbol:
        - Balok 1 (1/8) membentang seluruh kelompok ketuk; balok 2 (1/16) dan 3 (1/32)
          hanya di atas rentetan simbol yang bernilai lebih kecil.
        - Balok terpanjang selalu di paling atas; jarak antar balok 3,5 pt.
        - Memiliki jarak aman (clearance) di atas titik oktaf agar tidak bertabrakan.
        """
        n = len(notes)
        if n == 0 or len(positions) != n:
            return

        groups = self._beam_groups(notes, m)
        if not groups:
            return

        max_beams = max(notes[k].beams for g in groups for k in g)
        max_octave = max((notes[k].octave for g in groups for k in g), default=0)
        oct_extra = 0.0 if max_octave <= 0 else (4.0 if max_octave == 1 else 7.5)
        beam1_y = base_y - 13.0 - 3.5 * (max_beams - 1) - oct_extra

        self.cr.set_line_width(1.0)
        for grp in groups:
            for level in range(1, max_beams + 1):
                y = beam1_y + 3.5 * (level - 1)
                run: List[int] = []
                for k in list(grp) + [None]:
                    if k is not None and notes[k].beams >= level:
                        run.append(k)
                        continue
                    if run:
                        x1 = positions[run[0]]
                        x2 = positions[run[-1]] + 7.0
                        self.cr.move_to(x1, y)
                        self.cr.line_to(x2, y)
                        self.cr.stroke()
                        run = []

    def _draw_tuplet_brackets(
        self, notes: List[NoteItem], positions: List[float], base_y: float
    ):
        """
        Menggambar kurung triplet berbusur elegan sesuai standar baku Not Angka:
        ╭── 3 ──╮
        - Dimulai dari nada pertama triplet dengan kait lengkung ke bawah (downward hook).
        - Garis horizontal membentang dengan celah bersih di tengah untuk angka '3'.
        - Angka '3' diletakkan proporsional dan elegan tepat di tengah celah garis kurung.
        - Kait lengkung ke bawah menutup di atas nada terakhir triplet.
        - Memiliki clearance aman di atas titik oktaf atas maupun garis balok (beams).
        """
        n = len(notes)
        if n < 2 or len(positions) != n:
            return

        tuplet_groups = []
        cur_tup = []
        for i, note in enumerate(notes):
            if getattr(note, "tuplet", None) == "3" and note.text != ".":
                cur_tup.append(i)
            else:
                if len(cur_tup) >= 3:
                    tuplet_groups.append(cur_tup)
                cur_tup = []
        if len(cur_tup) >= 3:
            tuplet_groups.append(cur_tup)

        for grp in tuplet_groups:
            i_start = grp[0]
            i_end = grp[-1]

            x1 = positions[i_start] - 1.0
            x2 = positions[i_end] + 8.0
            mid_x = (x1 + x2) / 2.0

            max_octave = max((notes[k].octave for k in grp), default=0)

            # Sesuai kaidah Not Angka: bila sudah ada triplet (╭── 3 ──╮), bendera garis datar
            # tidak digambar lagi. Kurung triplet berbusur diletakkan langsung di atas nada
            # atau titik oktaf dengan jarak yang proporsional dan elegan.
            if max_octave <= 0:
                y_bracket = base_y - 13.5
            elif max_octave == 1:
                y_bracket = base_y - 19.0
            else:
                y_bracket = base_y - 22.5

            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            self.cr.set_font_size(8.5)
            xbear, ybear, tw, th, dx, dy = self.cr.text_extents("3")
            gap_half = (tw / 2.0) + 2.5

            hook_h = 3.5
            r = 2.5
            self.cr.set_line_width(0.75)

            # Kait kiri dan garis horizontal kiri: ╭──
            self.cr.move_to(x1, y_bracket + hook_h)
            self.cr.curve_to(x1, y_bracket + 0.5, x1 + 0.5, y_bracket, x1 + r, y_bracket)
            self.cr.line_to(mid_x - gap_half, y_bracket)
            self.cr.stroke()

            # Garis horizontal kanan dan kait kanan: ──╮
            self.cr.move_to(mid_x + gap_half, y_bracket)
            self.cr.line_to(x2 - r, y_bracket)
            self.cr.curve_to(x2 - 0.5, y_bracket, x2, y_bracket + 0.5, x2, y_bracket + hook_h)
            self.cr.stroke()

            # Angka '3' di tengah celah kurung
            self.cr.move_to(mid_x - (tw / 2.0), y_bracket + (th / 2.0) - 0.5)
            self.cr.show_text("3")

    def _layout_and_draw_lyrics(
        self, m_x: float, m_w: float, lyric_y: float,
        syl_notes: List[NoteItem], positions: List[float]
    ):
        """
        Menggambar baris lirik dengan algoritma anti-tabrakan mutlak:
        1. Forward pass menjamin suku kata tidak pernah menabrak suku kata sebelumnya (min_gap).
        2. Jika terdapat overflow di batas kanan birama, font discale down secara adaptif.
        3. Backward pass menjamin tidak ada suku kata yang melebihi batas kanan birama
           tanpa pernah melanggar batas min_gap dari suku kata sebelumnya.
        """
        if not syl_notes or len(syl_notes) != len(positions):
            return

        self.cr.select_font_face(FONT_LYRICS, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        syl_texts = [n.lyric for n in syl_notes]
        syl_count = len(syl_texts)

        base_font_sz = 8.5 if syl_count >= 6 else 9.5
        font_sz = base_font_sz

        min_gap = 2.0
        final_xs = []

        for iteration in range(6):
            self.cr.set_font_size(font_sz)
            widths = [self.cr.text_extents(s)[2] for s in syl_texts]

            # Forward pass: pusatkan di bawah not, jaga min_gap
            xs = []
            prev_end = m_x + 2.0
            for s, nx, tw in zip(syl_texts, positions, widths):
                center_x = nx + 3.5
                lx = center_x - (tw / 2.0)
                if lx < prev_end + min_gap:
                    lx = prev_end + min_gap
                xs.append(lx)
                prev_end = lx + tw

            overflow = prev_end - (m_x + m_w - 2.0)
            if overflow <= 0 or font_sz <= 6.5:
                if overflow > 0:
                    # Backward pass: geser proporsional dari kanan ke kiri tanpa pernah melanggar min_gap
                    right_limit = m_x + m_w - 2.0
                    for i in range(syl_count - 1, -1, -1):
                        if xs[i] + widths[i] > right_limit:
                            xs[i] = right_limit - widths[i]
                        right_limit = xs[i] - min_gap
                    # Jika setelah backward pass elemen paling kiri terdesak keluar batas kiri,
                    # ratakan kembali dari kiri ke kanan dengan spasi minimal
                    if xs[0] < m_x + 2.0:
                        cur_left = m_x + 2.0
                        for i in range(syl_count):
                            xs[i] = cur_left
                            cur_left += widths[i] + 1.2
                final_xs = xs
                break

            # Scale down font_sz
            avail = m_w - 4.0
            needed = sum(widths) + (syl_count - 1) * min_gap + overflow * 0.5
            scale = min(0.92, avail / max(needed, avail + 1.0))
            font_sz = max(6.5, font_sz * scale)

        self.cr.set_font_size(font_sz)
        for s, lx in zip(syl_texts, final_xs):
            self.cr.move_to(lx, lyric_y)
            self.cr.show_text(s)

    @staticmethod
    def _verse_text(n: NoteItem, verse: int) -> Optional[str]:
        """Suku kata bait ke-verse (0 = bait 1 dari n.lyric, k = bait k+1 dari n.verses[k-1])."""
        if verse <= 0:
            return n.lyric
        vs = getattr(n, "verses", None)
        if vs and len(vs) >= verse:
            return vs[verse - 1]
        return None

    def _draw_single_voice_lyrics(
        self, m: Measure, m_x: float, m_w: float, lyric_y: float,
        voice: Optional[MeasureVoice], positions: List[float], verse: int = 0
    ):
        """Menggambar lirik khusus satu suara secara independen tepat di bawah notnya."""
        if not voice or not voice.notes or len(positions) != len(voice.notes):
            return
        pairs = [(NoteItem(text=n.text, lyric=self._verse_text(n, verse)), positions[i])
                 for i, n in enumerate(voice.notes) if self._verse_text(n, verse)]
        if not pairs:
            return
        self._layout_and_draw_lyrics(m_x, m_w, lyric_y, [p[0] for p in pairs], [p[1] for p in pairs])

    def _draw_voice_lyrics(
        self, m: Measure, m_x: float, m_w: float, lyric_y: float,
        v_primary: Optional[MeasureVoice], v_secondary: Optional[MeasureVoice],
        prim_positions: List[float], sec_positions: List[float], verse: int = 0
    ):
        """Menggambar lirik bersama untuk dua suara yang berirama sama."""
        if v_primary and v_primary.notes and any(self._verse_text(n, verse) for n in v_primary.notes):
            self._draw_single_voice_lyrics(m, m_x, m_w, lyric_y, v_primary, prim_positions, verse=verse)
            return
        elif v_secondary and v_secondary.notes and any(self._verse_text(n, verse) for n in v_secondary.notes):
            self._draw_single_voice_lyrics(m, m_x, m_w, lyric_y, v_secondary, sec_positions, verse=verse)
            return
        if verse > 0:
            return

        # Fallback teks gabungan jika partitur JSON manual belum memiliki note-level lyric
        fallback_text = (
            m.lyrics.get("SA") or m.lyrics.get("TB") or
            m.lyrics.get("S") or m.lyrics.get("A") or
            m.lyrics.get("T") or m.lyrics.get("B")
        )
        if fallback_text:
            v_ref = v_primary if (v_primary and v_primary.notes) else (v_secondary if (v_secondary and v_secondary.notes) else None)
            pos_ref = prim_positions if (v_primary and v_primary.notes) else sec_positions
            words = fallback_text.split()
            sounding_indices = [i for i, n in enumerate(v_ref.notes) if n.text not in ("0", ".")] if v_ref else []

            if v_ref and sounding_indices and len(words) == len(sounding_indices):
                dummy_notes = [NoteItem(text=v_ref.notes[i].text, lyric=words[k]) for k, i in enumerate(sounding_indices)]
                dummy_pos = [pos_ref[i] for i in sounding_indices]
                self._layout_and_draw_lyrics(m_x, m_w, lyric_y, dummy_notes, dummy_pos)
            else:
                self._draw_lyrics(fallback_text, m_x, m_w, lyric_y)

    def _draw_dynamic(
        self, dyn: DynamicMark, m_x: float, m_w: float, dyn_y: float, m: Optional[Measure] = None
    ):
        """Menggambar tanda dinamika teks atau hairpin."""
        pad_left = 8.0
        pad_right = 8.0
        usable_w = m_w - pad_left - pad_right
        total_beats = max(1.0, self._get_measure_total_beats(m))
        beat_w = usable_w / total_beats

        dx = m_x + pad_left + (dyn.beat - 1.0) * beat_w + 3.5

        if dyn.is_hairpin:
            end_beat = dyn.hairpin_end_beat if dyn.hairpin_end_beat else dyn.beat + 1.0
            end_x = m_x + pad_left + (end_beat - 1.0) * beat_w + 3.5

            # Enforce minimum length and symmetrical opening
            h_open = 2.8
            min_len = 16.0
            self.cr.set_line_width(0.8)
            self.cr.new_sub_path()

            if dyn.hairpin_type == "cresc":
                if end_x < dx + min_len:
                    end_x = dx + min_len
                self.cr.move_to(end_x, dyn_y - h_open)
                self.cr.line_to(dx, dyn_y)
                self.cr.line_to(end_x, dyn_y + h_open)
                self.cr.stroke()
            else:
                if end_x < dx + min_len:
                    end_x = dx + min_len
                self.cr.move_to(dx, dyn_y - h_open)
                self.cr.line_to(end_x, dyn_y)
                self.cr.line_to(dx, dyn_y + h_open)
                self.cr.stroke()
        else:
            self.cr.select_font_face(FONT_DYNAMICS, cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
            self.cr.set_font_size(10.0)
            self.cr.move_to(dx, dyn_y)
            self.cr.show_text(dyn.text)

    def _draw_lyrics(self, text: str, m_x: float, m_w: float, lyric_y: float):
        """Menggambar baris lirik fallback jika tidak ada lirik per nada."""
        self.cr.select_font_face(FONT_LYRICS, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        self.cr.set_font_size(9.5)
        _, _, tw, _, _, _ = self.cr.text_extents(text)
        lx = m_x + max(4.0, (m_w - tw) / 2.0)
        self.cr.move_to(lx, lyric_y)
        self.cr.show_text(text)

    def _draw_fermata(self, cx: float, cy: float):
        """Menggambar simbol fermata (busur lengkung + titik)."""
        self.cr.set_line_width(0.8)
        self.cr.arc(cx, cy, 5.0, math.pi, 2 * math.pi)
        self.cr.stroke()
        self.cr.arc(cx, cy - 1.5, 1.2, 0, 2 * math.pi)
        self.cr.fill()

    def _draw_repeat_dots(self, x: float, top_y: float, bot_y: float):
        h = bot_y - top_y
        for frac in (0.38, 0.62):
            self.cr.new_sub_path()
            self.cr.arc(x, top_y + h * frac, 1.2, 0, 2 * math.pi)
            self.cr.fill()

    def _draw_left_barline(self, m: Measure, x: float, top_y: float, bot_y: float):
        """Garis birama kiri khusus: awal ulangan ||: atau garis ganda, plus kamar ulangan 1./2."""
        kind = getattr(m, "barline_left", None)
        if kind == "repeat_start":
            self.cr.set_line_width(2.2)
            self.cr.move_to(x, top_y)
            self.cr.line_to(x, bot_y)
            self.cr.stroke()
            self.cr.set_line_width(0.8)
            self.cr.move_to(x + 3.5, top_y)
            self.cr.line_to(x + 3.5, bot_y)
            self.cr.stroke()
            self._draw_repeat_dots(x + 7.0, top_y, bot_y)
        elif kind == "double":
            self.cr.set_line_width(0.8)
            self.cr.move_to(x + 2.5, top_y)
            self.cr.line_to(x + 2.5, bot_y)
            self.cr.stroke()
        ending = getattr(m, "ending", None)
        if ending:
            self.cr.select_font_face(FONT_META, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            self.cr.set_font_size(8.5)
            self.cr.set_line_width(0.7)
            self.cr.move_to(x, top_y - 3.0)
            self.cr.line_to(x, top_y - 13.0)
            self.cr.line_to(x + 34.0, top_y - 13.0)
            self.cr.stroke()
            self.cr.move_to(x + 3.0, top_y - 5.0)
            self.cr.show_text(ending)

    def _draw_barline(self, bar_type: str, x: float, top_y: float, bot_y: float):
        """Menggambar garis birama (tunggal, ganda, penutup tebal, atau akhir ulangan :||)."""
        self.cr.set_line_width(0.8)
        if bar_type == "repeat_end":
            self._draw_repeat_dots(x - 7.0, top_y, bot_y)
            self.cr.move_to(x - 3.5, top_y)
            self.cr.line_to(x - 3.5, bot_y)
            self.cr.stroke()
            self.cr.set_line_width(2.2)
            self.cr.move_to(x, top_y)
            self.cr.line_to(x, bot_y)
            self.cr.stroke()
            self.cr.set_line_width(0.8)
            return
        if bar_type == "single":
            self.cr.move_to(x, top_y)
            self.cr.line_to(x, bot_y)
            self.cr.stroke()
        elif bar_type == "double":
            self.cr.move_to(x - 2.5, top_y)
            self.cr.line_to(x - 2.5, bot_y)
            self.cr.stroke()
            self.cr.move_to(x, top_y)
            self.cr.line_to(x, bot_y)
            self.cr.stroke()
        elif bar_type == "final":
            self.cr.move_to(x - 3.5, top_y)
            self.cr.line_to(x - 3.5, bot_y)
            self.cr.stroke()
            self.cr.set_line_width(2.2)
            self.cr.move_to(x, top_y)
            self.cr.line_to(x, bot_y)
            self.cr.stroke()
            self.cr.set_line_width(0.8)

