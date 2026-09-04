"""
Skema data standar Not Angka Indonesia (JSON / Python).
Menyimpan representasi partitur vokal/paduan suara yang mandiri dari format apapun.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
import json


@dataclass
class TempoMeta:
    bpm: Optional[int] = None   # None = sumber tidak menyebut tempo -> tidak dicetak
    beat_unit: str = "4"        # "4" untuk seperempat
    text: str = ""              # kata tempo, misal "Andante", "Moderato"


@dataclass
class ScoreMeta:
    title: str = "Judul Lagu"
    subtitle: str = ""              # contoh: 'From "Coco"' atau 'SATB div. a capella'
    tonic_label: str = "Do=C"      # contoh: "Do=Ges", "Do=D", "Do=F"
    time_signature: str = "4/4"     # "4/4", "3/4", "6/8", "2/4"
    tempo: TempoMeta = field(default_factory=TempoMeta)
    composer: str = ""              # contoh: "Words & Music by John Rutter"
    arranger: str = ""              # contoh: "Arr. John Leavitt"
    lyricist: str = ""              # contoh: "Juan Ramon Jimenez"
    beat_unit: str = "quarter"      # kebijakan satuan ketuk: "quarter" (PS/lagumisa) atau "denominator"


@dataclass
class NoteItem:
    """Satu entitas nada atau tanda diam/perpanjangan dalam birama."""
    text: str                       # "1", "2", "3", "4", "5", "6", "7", "0", atau "."
    octave: int = 0                 # -2, -1, 0, 1, 2 (titik oktaf bawah/atas)
    accidental: Optional[str] = None # "kres" (/) atau "mol" (\)
    beams: int = 0                  # 0 = not seperempat, 1 = garis tunggal (1/8), 2 = garis ganda (1/16)
    beam_type: Optional[str] = None # "start", "continue", "stop", "single"
    dot: bool = False               # titik nilai bawaan
    slur: Optional[str] = None      # "start", "stop"
    tie: bool = False               # tanda hubung / sambung
    fermata: bool = False           # tanda fermata di atas nada
    tuplet: Optional[str] = None    # "3" untuk triplet
    lyric: Optional[str] = None     # suku kata lirik bait 1 di bawah nada ini
    verses: Optional[List[Optional[str]]] = None # suku kata bait 2, 3, ... (indeks 0 = bait 2)
    beat: float = 1.0               # posisi awal dalam birama, satuan unit ketuk (1-indexed: 1.0, 1.5, 2.0)
    duration_beats: float = 1.0     # panjang simbol dalam unit ketuk (1.0 = satu simbol polos)


@dataclass
class DynamicMark:
    """Tanda ekspresi atau dinamika di atas baris not."""
    beat: float                     # posisi ketuk dalam birama (1-indexed, misal 1.0, 3.5)
    text: str                       # "p", "mp", "mf", "f", "cresc.", "dim.", "dolce e legato"
    is_hairpin: bool = False        # True jika hairpin
    hairpin_type: Optional[str] = None # "cresc" (<) atau "decresc" (>)
    hairpin_end_beat: Optional[float] = None


@dataclass
class MeasureVoice:
    """Konten sebuah suara dalam satu birama."""
    voice_name: str                 # "S", "A", "T", "B"
    notes: List[NoteItem] = field(default_factory=list)


@dataclass
class Measure:
    """Satu birama musik."""
    number: int
    voices: Dict[str, MeasureVoice] = field(default_factory=dict)
    lyrics: Dict[str, str] = field(default_factory=dict) # key: "SA" atau "TB" atau nama voice
    dynamics: List[DynamicMark] = field(default_factory=list)
    barline_type: str = "single"    # garis birama kanan: "single", "double", "final", "repeat_end"
    barline_left: Optional[str] = None # garis birama kiri: "repeat_start" atau "double"
    ending: Optional[str] = None       # teks kamar ulangan di awal birama, misal "1." / "2."
    time_signature: Optional[str] = None # misal "2/4", "4/4", "3/4", "2+2+3/8"
    capacity_beats: Optional[float] = None # kapasitas nyata (unit) untuk birama gantung/penggenap; None = ikut sukat
    tonic_label: Optional[str] = None    # "Do=X" yang berlaku di birama ini (modulasi); None = ikut meta
    multi_rest: int = 1                  # >1: birama ini mewakili n birama diam beruntun (birama berikutnya disembunyikan)


@dataclass
class SystemBlockConfig:
    """Konfigurasi satu sistem baris partitur."""
    measure_indices: List[int]      # daftar nomor birama dalam sistem ini
    block_type: str = "satb_paired" # "single_solo", "satb_paired", "unison", "general_multivoice"
    voices: Optional[List[str]] = None # daftar nama suara spesifik untuk sistem ini (misal S1, S2, A1, ...)


@dataclass
class NotAngkaScore:
    meta: ScoreMeta = field(default_factory=ScoreMeta)
    measures: List[Measure] = field(default_factory=list)
    systems: List[SystemBlockConfig] = field(default_factory=list)
    repairs: List[str] = field(default_factory=list)  # catatan perbaikan otomatis deterministik (diam hantu, triol)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NotAngkaScore":
        meta_d = d.get("meta", {})
        tempo_d = meta_d.get("tempo", {})
        bpm_raw = tempo_d.get("bpm")
        tempo = TempoMeta(
            bpm=int(bpm_raw) if bpm_raw not in (None, "", 0) else None,
            beat_unit=tempo_d.get("beat_unit", "4") or "4",
            text=tempo_d.get("text", "") or ""
        )
        meta = ScoreMeta(
            title=meta_d.get("title", ""),
            subtitle=meta_d.get("subtitle", ""),
            tonic_label=meta_d.get("tonic_label", "Do=C"),
            time_signature=meta_d.get("time_signature", "4/4"),
            tempo=tempo,
            composer=meta_d.get("composer", ""),
            arranger=meta_d.get("arranger", ""),
            lyricist=meta_d.get("lyricist", ""),
            beat_unit=meta_d.get("beat_unit", "quarter") or "quarter"
        )

        measures = []
        for m_d in d.get("measures", []):
            voices = {}
            for v_name, v_d in m_d.get("voices", {}).items():
                notes = []
                for n_d in v_d.get("notes", []):
                    notes.append(NoteItem(
                        text=n_d.get("text", "0"),
                        octave=int(n_d.get("octave") or 0),
                        accidental=n_d.get("accidental"),
                        beams=int(n_d.get("beams") or 0),
                        beam_type=n_d.get("beam_type"),
                        dot=bool(n_d.get("dot", False)),
                        slur=n_d.get("slur"),
                        tie=n_d.get("tie", False),
                        fermata=n_d.get("fermata", False),
                        tuplet=n_d.get("tuplet"),
                        lyric=n_d.get("lyric"),
                        verses=n_d.get("verses"),
                        beat=float(n_d.get("beat", 1.0)),
                        duration_beats=float(n_d.get("duration_beats", 1.0))
                    ))
                voices[v_name] = MeasureVoice(voice_name=v_name, notes=notes)

            dynamics = []
            for dyn_d in m_d.get("dynamics", []):
                dynamics.append(DynamicMark(
                    beat=dyn_d.get("beat", 1.0),
                    text=dyn_d.get("text", ""),
                    is_hairpin=dyn_d.get("is_hairpin", False),
                    hairpin_type=dyn_d.get("hairpin_type"),
                    hairpin_end_beat=dyn_d.get("hairpin_end_beat")
                ))

            measures.append(Measure(
                number=m_d.get("number", 1),
                voices=voices,
                lyrics=m_d.get("lyrics", {}),
                dynamics=dynamics,
                barline_type=m_d.get("barline_type", "single"),
                time_signature=m_d.get("time_signature"),
                capacity_beats=(float(m_d["capacity_beats"]) if m_d.get("capacity_beats") is not None else None),
                tonic_label=m_d.get("tonic_label"),
                multi_rest=int(m_d.get("multi_rest", 1) or 1),
                barline_left=m_d.get("barline_left"),
                ending=m_d.get("ending")
            ))

        systems = []
        for sys_d in d.get("systems", []):
            systems.append(SystemBlockConfig(
                measure_indices=sys_d.get("measure_indices", []),
                block_type=sys_d.get("block_type", "satb_paired"),
                voices=sys_d.get("voices")
            ))

        return cls(meta=meta, measures=measures, systems=systems, repairs=list(d.get("repairs", []) or []))

    @classmethod
    def from_json(cls, json_str: str) -> "NotAngkaScore":
        return cls.from_dict(json.loads(json_str))
