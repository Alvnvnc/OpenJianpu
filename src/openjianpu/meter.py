"""
Model sukat (tanda birama) dan satuan ketuk Not Angka.

Modul ini adalah SATU-SATUNYA tempat yang tahu bagaimana sebuah sukat
(4/4, 3/4, 7/8, 9/8, 2/2, 2+2+3/8, ...) diterjemahkan menjadi:

1. satuan ketuk (unit)   : nilai not yang dicetak sebagai satu simbol polos
                            (angka / 0 / titik tanpa garis balok);
2. kapasitas birama      : berapa unit yang muat dalam satu birama;
3. kelompok ketuk        : batas-batas balok (beam) di dalam birama,
                            misal 7/8 = 2+2+3, 9/8 = 3+3+3, 6/8 = 3+3.

Parser (MusicXML -> skema) dan renderer (skema -> PDF) sama-sama memakai
modul ini sehingga keduanya tidak mungkin berbeda pendapat tentang ketukan.

Kebijakan satuan ketuk (``beat_unit``):

* ``"quarter"``     (bawaan) - satu simbol = not seperempat pada SEMUA sukat.
  Ini praktik Puji Syukur / lagumisa.web.id (PS 324 bersukat 2/2 tetap
  menulis not seperempat sebagai angka polos) dan praktik jianpu-ly.
  Pada 7/8 satu birama berkapasitas 3,5 unit; not 1/8 berbalok satu.
* ``"denominator"`` - satu simbol = nilai penyebut sukat (aturan formal
  "penyebut menunjukkan nilai satu ketuk"): pada 7/8 not 1/8 polos,
  kapasitas 7 unit; pada 2/2 not setengah polos, not seperempat berbalok.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

EPS = 1e-6

POLICY_QUARTER = "quarter"
POLICY_DENOMINATOR = "denominator"
POLICIES = (POLICY_QUARTER, POLICY_DENOMINATOR)

# Nilai sub-unit baku beserta (jumlah balok, titik nilai terpasang).
# Urutan dari yang terpanjang. Toleransi pencocokan 0.02 unit.
_STANDARD_SUBUNITS: List[Tuple[float, int, bool]] = [
    (0.75, 1, True),     # 1/8 bertitik (pada satuan seperempat)
    (0.5, 1, False),     # 1/8
    (0.375, 2, True),    # 1/16 bertitik
    (0.25, 2, False),    # 1/16
    (0.1875, 3, True),   # 1/32 bertitik
    (0.125, 3, False),   # 1/32
]
_BINARY_SUBUNITS: List[Tuple[float, int]] = [(0.5, 1), (0.25, 2), (0.125, 3)]


@dataclass(frozen=True)
class Meter:
    numerator_text: str   # "7" atau "2+2+3"
    beat_type: int        # 2, 4, 8, 16

    @property
    def parts(self) -> List[int]:
        out = []
        for p in self.numerator_text.split("+"):
            p = p.strip()
            if p:
                out.append(int(p))
        return out or [4]

    @property
    def beats(self) -> int:
        return sum(self.parts)

    @property
    def label(self) -> str:
        return f"{self.numerator_text}/{self.beat_type}"

    @property
    def is_composite(self) -> bool:
        return len(self.parts) > 1

    # ---- satuan & kapasitas -------------------------------------------------

    def unit_quarters(self, policy: str = POLICY_QUARTER) -> float:
        """Panjang satu unit (simbol polos) dalam not seperempat."""
        if policy == POLICY_DENOMINATOR:
            return 4.0 / float(self.beat_type)
        return 1.0

    def capacity_quarters(self) -> float:
        return self.beats * (4.0 / float(self.beat_type))

    def capacity_units(self, policy: str = POLICY_QUARTER) -> float:
        return self.capacity_quarters() / self.unit_quarters(policy)

    # ---- kelompok ketuk (batas balok) --------------------------------------

    def groups_quarters(self) -> List[float]:
        """Panjang tiap kelompok ketuk dalam not seperempat.

        Kelompok inilah yang membatasi garis balok: dua not 1/8 yang berada
        pada kelompok berbeda tidak boleh disatukan baloknya.
        """
        q = 4.0 / float(self.beat_type)
        parts = self.parts
        if len(parts) > 1:
            return [p * q for p in parts]
        n = parts[0]
        if self.beat_type == 8:
            if n % 3 == 0:
                return [1.5] * (n // 3)
            if n == 5:
                return [1.5, 1.0]
            if n == 7:
                return [1.0, 1.0, 1.5]
            if n == 8:
                return [1.5, 1.5, 1.0]
            if n % 2 == 0:
                return [1.0] * (n // 2)
            return [0.5] * n
        if self.beat_type == 16:
            if n % 3 == 0:
                return [0.75] * (n // 3)
            if n % 2 == 0:
                return [0.5] * (n // 2)
            return [0.25] * n
        # Penyebut 1, 2, 4: satu kelompok per ketuk sukat (half pada /2, quarter pada /4)
        return [q] * n

    def groups_units(self, policy: str = POLICY_QUARTER) -> List[float]:
        u = self.unit_quarters(policy)
        return [g / u for g in self.groups_quarters()]


def parse_meter(text: Optional[str], default: str = "4/4") -> Meter:
    """Mengurai teks sukat "7/8", "2+2+3/8", "C" (common), "cut"."""
    if not text:
        text = default
    t = text.strip().lower()
    if t in ("c", "common"):
        return Meter("4", 4)
    if t in ("cut", "c|", "alla breve"):
        return Meter("2", 2)
    if "/" not in t:
        return parse_meter(default, "4/4") if text != default else Meter("4", 4)
    num, den = t.split("/", 1)
    try:
        den_i = int(den.strip())
        parts = [int(p) for p in num.split("+") if p.strip()]
        if den_i <= 0 or not parts or any(p <= 0 for p in parts):
            raise ValueError
    except ValueError:
        if text == default:
            return Meter("4", 4)
        return parse_meter(default, "4/4")
    return Meter("+".join(str(p) for p in parts), den_i)


def group_boundaries(groups: List[float]) -> List[float]:
    """Titik akhir kumulatif tiap kelompok, misal [1,1,1.5] -> [1,2,3.5]."""
    out = []
    acc = 0.0
    for g in groups:
        acc += g
        out.append(acc)
    return out


def group_index(rel_units: float, groups: List[float]) -> int:
    """Indeks kelompok ketuk untuk posisi relatif (0 = awal birama) dalam unit."""
    pos = rel_units + EPS
    acc = 0.0
    for i, g in enumerate(groups):
        acc += g
        if pos < acc:
            return i
    # Di luar kapasitas (birama meluap): lanjutkan dengan kelompok sebesar unit terakhir
    if not groups:
        return 0
    last = groups[-1] if groups[-1] > 0 else 1.0
    return len(groups) + int((pos - acc) / last)


def split_at_units(start_units: float, dur_units: float) -> List[Tuple[float, float]]:
    """Memotong rentang [start, start+dur) pada setiap batas unit.

    Hasilnya daftar (awal, panjang). Potongan yang dimulai tepat di batas unit
    dan panjangnya >= 1 unit dipecah lagi menjadi potongan-potongan 1 unit.
    """
    pieces: List[Tuple[float, float]] = []
    pos = start_units
    rem = dur_units
    guard = 0
    while rem > EPS and guard < 512:
        guard += 1
        # batas unit berikutnya setelah pos
        floor_pos = int(pos + EPS) if pos >= 0 else -int(-pos - EPS) - 1
        boundary = float(floor_pos) + 1.0
        take = boundary - pos
        if take <= EPS:
            take = 1.0
        take = min(rem, take)
        pieces.append((pos, take))
        pos += take
        rem -= take
    return pieces


def split_for_symbols(start_units: float, dur_units: float, groups_units: List[float]) -> List[Tuple[float, float]]:
    """Memotong satu nada/diam menjadi potongan-potongan simbol yang sadar kelompok ketuk.

    Aturan (menyatukan praktik Puji Syukur untuk x/4 dan praktik 6/8 "1 + ½ + 1 + ½"):
    * Potongan yang dimulai TEPAT di batas unit: ambil satu unit penuh (simbol polos) selama
      sisa >= 1 unit - simbol polos boleh melintasi batas kelompok karena tak berbalok.
      Sisa < 1 unit menjadi potongan sub-unit yang dipotong pada batas kelompok berikutnya.
    * Potongan yang dimulai di TENGAH unit: dipotong pada batas kelompok berikutnya (bukan batas
      unit). Pada x/4 kelompok = unit sehingga sinkop "1̅ 2̅ .̅ 3̅" tetap terpecah per ketuk;
      pada 6/8 seperempat yang mulai di not 1/8 ke-4 tetap satu simbol polos: "5 6̅ 5 6̅".
      Potongan >= 1 unit dari titik tengah dipecah rakus: unit-unit penuh lalu sisanya.
    """
    bounds = group_boundaries(groups_units) if groups_units else []
    pieces: List[Tuple[float, float]] = []
    pos = start_units
    rem = dur_units
    guard = 0

    def next_group_boundary(x: float) -> float:
        for b in bounds:
            if b > x + EPS:
                return b
        # di luar kapasitas: teruskan dengan kelompok sebesar kelompok terakhir
        last = groups_units[-1] if groups_units and groups_units[-1] > 0 else 1.0
        base = bounds[-1] if bounds else 0.0
        k = int((x - base) / last) + 1
        return base + k * last

    while rem > EPS and guard < 1024:
        guard += 1
        on_unit = abs(pos - round(pos)) < 0.02
        if on_unit:
            if rem >= 1.0 - 0.02:
                take = min(rem, 1.0)
            else:
                take = min(rem, next_group_boundary(pos) - pos)
        else:
            span = next_group_boundary(pos) - pos
            take = min(rem, span)
            if take >= 1.0 - 0.02:
                take = 1.0
        if take <= EPS:
            take = rem
        pieces.append((pos, take))
        pos += take
        rem -= take
    return pieces


def symbols_for_subunit(length_units: float, allow_dot: bool = True) -> List[Tuple[float, int, bool, bool]]:
    """Mengubah panjang sub-unit menjadi daftar simbol (panjang, balok, titik, baku).

    ``baku`` False berarti panjangnya tidak dapat diwakili nilai not biner
    (misal sisa tuplet yang tidak terdeteksi) dan hanya didekati.
    """
    for L, beams, dot in _STANDARD_SUBUNITS:
        if dot and not allow_dot:
            continue
        if abs(length_units - L) < 0.02:
            return [(L, beams, dot, True)]
    out: List[Tuple[float, int, bool, bool]] = []
    rem = length_units
    for L, beams in _BINARY_SUBUNITS:
        while rem >= L - 0.02:
            out.append((L, beams, False, True))
            rem -= L
    if rem > 0.02:
        # Sisa tak baku: dekati dengan balok sesuai besarnya
        beams = 1 if rem > 0.3 else (2 if rem > 0.15 else 3)
        out.append((rem, beams, False, False))
    return out


def beams_for_length(length_units: float) -> int:
    """Perkiraan jumlah balok untuk satu simbol tunggal sepanjang length_units."""
    if length_units >= 1.0 - 0.02:
        return 0
    if length_units > 0.5 - 0.02:
        return 1
    if length_units > 0.25 - 0.02:
        return 1 if length_units >= 0.4 else 2
    if length_units > 0.125 - 0.02:
        return 2
    return 3
