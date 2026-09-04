"""
Parser MusicXML ke NotAngkaScore.
Membaca partitur MusicXML (hasil ekstraksi PDF / software notasi)
dan mengubahnya menjadi struktur data standar NotAngkaScore.
"""

import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from .schema import (
    NotAngkaScore, ScoreMeta, TempoMeta, Measure, MeasureVoice,
    NoteItem, DynamicMark, SystemBlockConfig
)
from .meter import (
    Meter, parse_meter, split_for_symbols, symbols_for_subunit, beams_for_length,
    POLICY_QUARTER, POLICIES, EPS as METER_EPS
)
from .layout import estimate_measure_width, SYSTEM_USABLE_WIDTH

# Impor degreelib bila ada di PATH atau batik-partitur-skill
try:
    from . import degreelib
except ImportError:
    try:
        import degreelib
    except ImportError:
        # Coba tambahkan path batik-partitur-skill
        skill_scripts = "/home/alvn/Documents/playground/batik-partitur-skill/scripts"
        if os.path.exists(skill_scripts) and skill_scripts not in sys.path:
            sys.path.insert(0, skill_scripts)
        import degreelib


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


INDONESIAN_PITCH_NAMES = {
    "Cb": "Ces",
    "Gb": "Ges",
    "Db": "Des",
    "Ab": "As",
    "Eb": "Es",
    "Bb": "Bes",
    "F#": "Fis",
    "C#": "Cis",
    "G#": "Gis",
    "D#": "Dis",
    "A#": "Ais",
}


def looks_like_junk_credit(txt: str) -> bool:
    """Teks kredit yang bukan nama orang: nomor birama, simbol akor, penanda bagian (BRIDGE),
    petunjuk pemain (2nd time to), lisensi, durasi, nama perangkat lunak."""
    import re
    t = (txt or "").strip()
    low = t.lower()
    if len(t) < 3:
        return True
    if low in SOFTWARE_NAMES:
        return True
    if re.match(r"^\d", t):
        return True
    if re.match(r"^[A-G][#b]?(maj|min|m|dim|aug|sus|add)?\d*(/[A-G][#b]?)?$", t):
        return True
    if t.isupper() and len(t.split()) <= 2 and any(k in low for k in ("bridge", "chorus", "verse", "coda", "intro", "refrain", "outro", "reff", "solo", "tutti")):
        return True
    if any(k in low for k in ("time to", "licensed", "duration", "copyright", "©", "www.", "http", "all rights", "page ")):
        return True
    return False


import re as _re
import unicodedata as _ud
_RE_EMAIL = _re.compile(r"\S+@\S+\.\S+")
_RE_CAMEL = _re.compile(r"([a-z])([A-Z][a-z])")
_RE_CAMEL_CLITIC = _re.compile(r"([a-z])((?:Mu|Nya|Ku|Kau)(?=[^a-z]|$))")
_RE_URL = _re.compile(r"(https?://|www\.)\S+")


def clean_lyric_text(txt: str) -> str:
    """Normalisasi teks lirik dari ekstraksi PDF: ligatur (ﬀ, ﬁ), spasi keras, karakter kendali."""
    if not txt:
        return ""
    t = txt if txt.isascii() else _ud.normalize("NFKC", txt)
    if not t.isascii():
        t = t.replace("\u00a0", " ").replace("\u2019", "'").replace("\u2018", "'")
        t = "".join(ch for ch in t if _ud.category(ch)[0] != "C")
    if len(t) > 6 and _RE_CAMEL.search(t):
        # "keHadiratMu" -> "ke Hadirat-Mu": batas huruf kecil->kapital adalah batas kata yang hilang spasinya
        t = _RE_CAMEL_CLITIC.sub(r"\1-\2", t)
        t = _RE_CAMEL.sub(r"\1 \2", t)
    if "@" in t:
        t = _RE_EMAIL.sub("", t)          # alamat email dari footer PDF yang ikut terbaca
    if "http" in t or "www." in t:
        t = _RE_URL.sub("", t)            # URL
    t = t.strip()
    if t and not any(ch.isalpha() for ch in t) and t not in ("-", "_", "'"):
        return ""  # artefak seperti "=", "|", "3-" (nomor birama / simbol akor yang terbaca sebagai lirik)
    return t


def to_indonesian_pitch(pitch_str: str) -> str:
    return INDONESIAN_PITCH_NAMES.get(pitch_str, pitch_str)


FAMILY_ORDER = {"Solo": 0, "U": 1, "Fem": 2, "S": 3, "MS": 4, "A": 5, "Male": 6, "T": 7, "Bar": 8, "B": 9, "Other": 10}


def voice_family(v: str) -> str:
    """Keluarga suara dari nama suara kanonikal (S1 -> S, MS2 -> MS, Solo 2 -> Solo)."""
    import re
    m = re.match(r"^([A-Za-z]+)", v.strip())
    fam = m.group(1) if m else v
    return fam if fam in FAMILY_ORDER else "Other"


def voice_sort_key(v: str) -> Tuple[int, int, str]:
    """Kunci pengurutan kanonikal suara partitur vokal/paduan suara."""
    import re
    fam = voice_family(v)
    m = re.search(r"(\d+)", v)
    num = int(m.group(1)) if m else 0
    return (FAMILY_ORDER.get(fam, 10), num, v)


# Kata kunci part instrumental (bukan suara manusia) -> tidak dicetak dalam not angka paduan suara
INSTRUMENT_KEYWORDS = (
    "piano", "pno", "keyboard", "keys", "organ", "orgel", "guitar", "gitar", "ukulele", "drum", "percus",
    "perkusi", "flute", "flauto", "piccolo", "oboe", "clarinet", "klarinet", "bassoon", "fagot", "horn",
    "trumpet", "trompet", "trombone", "tuba", "violin", "viola", "cello", "contrabass", "double bass",
    "string bass", "electric bass", "bass guitar", "acoustic bass", "strings", "synth", "softsynth",
    "smartmusic", "electric", "electr", "hand clap", "clap", "finger snap", "snap", "wood block", "shaker",
    "tambour", "harp", "sax", "marimba", "xylo", "glocken", "timpani", "cymbal", "kick", "snare", "accordion",
    "recorder", "kecapi", "gamelan", "angklung", "kolintang", "suling", "kendang", "gong", "midi", "click",
    "metronome", "bell", "vibraphone", "celesta", "harmonium", "ensemble", "orchestra", "orkestra",
)
VOCAL_MIDI_PROGRAMS = {53, 54, 55, 86}  # Choir Aahs, Voice Oohs, Synth Voice, Lead 6 (voice)
GENERIC_NAME_PATTERNS = ("staf", "staff", "part", "suara", "voice", "vocal", "vokal", "musicxml part", "p")
SOFTWARE_NAMES = ("music21", "musescore", "sibelius", "finale", "dorico", "encore", "lilypond", "capella", "noteflight", "flat.io")


def _classify_part_name(pname: str) -> Tuple[str, Optional[int], bool]:
    """(keluarga, nomor divisi, generik?) dari nama part.

    Keluarga: Solo, U (unisono/umat), Fem, S, MS, A, Male, T, Bar, B, atau "?" bila nama generik
    (Staf 1, Voice, Part 2, "4") sehingga harus ditebak dari kunci dan wilayah nada.
    Nomor pada nama generik adalah nomor staf, bukan nomor divisi, sehingga diabaikan.
    """
    import re
    low = pname.strip().lower()
    low_cmp = re.sub(r"[\.\-_]+", " ", low)
    m_num = re.search(r"(\d+)", low)
    num = int(m_num.group(1)) if m_num else None
    if num is None:
        roman_map = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}
        for tok in re.split(r"\s+", low_cmp):
            if tok in roman_map:
                num = roman_map[tok]
                break

    def has(*keys):
        return any(k in low_cmp for k in keys)

    if has("solo") or re.match(r"^so\.?\s*[sat]?\.?$", low):
        return "Solo", num, False
    if has("unison", "unis", "umat", "tutti", "all voices"):
        return "U", num, False
    if has("mezzo") or low_cmp.startswith("ms"):
        return "MS", num, False
    if has("sopran", "soprano", "cantus", "descant", "treble", "sop"):
        return "S", num, False
    if has("contralt", "alto", "alt"):
        return "A", num, False
    if has("bariton", "barito", "bar ") or low_cmp in ("bar", "bar."):
        return "Bar", num, False
    if has("tenor", "ten "):
        return "T", num, False
    if has("bass", "bas ", "bajo", "basso", "baixo") or low_cmp in ("bas", "b"):
        return "B", num, False
    if has("female", "women", "wanita", "perempuan", "ladies"):
        return "Fem", num, False
    if has("male", "men", "pria", "laki"):
        return "Male", num, False
    if has("choir", "chorus", "koor", "paduan"):
        return "?", None, True
    if re.match(r"^s\.?\s*\d*$", low_cmp) or re.match(r"^ss\.?\s*\d*$", low_cmp):
        return "S", num, False
    if re.match(r"^a\.?\s*\d*$", low_cmp):
        return "A", num, False
    if re.match(r"^t\.?\s*\d*$", low_cmp):
        return "T", num, False
    if re.match(r"^b\.?\s*\d*$", low_cmp):
        return "B", num, False
    return "?", None, True


_VOCAL_BASS_NAME = None


def _is_instrument_part(pname: str, instrument_names: List[str], midi_programs: List[int]) -> bool:
    """Part instrumental bila nama part / nama instrumennya memuat kata kunci alat musik.

    Kata "bass" ambigu: "Bass", "Bass 2", "Bajo", "Basso" adalah suara manusia; "Bassoon",
    "Bass guitar", "Acoustic bass", "Bass akustik", "Contrabass" adalah alat musik.
    Nama generik (Staf 1, Voice) dengan program MIDI non-vokal juga dianggap alat musik.
    """
    import re
    fam, _, generic = _classify_part_name(pname)
    for nm in [pname] + list(instrument_names):
        low = (nm or "").strip().lower()
        if not low:
            continue
        if re.fullmatch(r"(bass|basso|bajo|baixo|bas|b)\.?\s*(\d+|i{1,3}|iv)?\.?", low):
            continue  # suara bas manusia
        if any(k in low for k in ("bass guitar", "bass gitar", "string bass", "electric bass", "acoustic bass",
                                   "bass akustik", "bas akustik", "double bass", "contrabass", "bassoon",
                                   "bass drum", "bass clarinet", "bass trombone", "upright bass", "bass elektrik")):
            return True
        if any(k in low for k in INSTRUMENT_KEYWORDS):
            # nama vokal eksplisit yang kebetulan memuat kata kunci (misal "Suara Alto" memuat "alt"?) tidak ada;
            # kata kunci "electr"/"synth" dll. hanya muncul pada alat musik
            return True
    if generic and midi_programs and not any(p in VOCAL_MIDI_PROGRAMS for p in midi_programs):
        return True
    return False


def detect_voice_mapping(root: ET.Element) -> Dict[str, str]:
    """
    Memetakan <score-part> id ke nama suara kanonikal Not Angka secara dinamis:
    - part instrumental (piano, flute, perkusi, ...) dibuang;
    - nama generik (Staf 1, Voice, Part 2) ditebak keluarganya dari kunci (G, G8vb, F) dan median nada,
      lalu dikoreksi relatif: bila belum ada S di skor, part treble tertinggi menjadi S, dst.;
    - part disjoin bernama sama yang tidak pernah berbunyi bersamaan (pecahan lintas halaman)
      digabung menjadi satu suara;
    - divisi dinomori (S1, S2, ...) dan nama tunggal dirapikan (S1 -> S bila cuma satu Sopran).
    Part yang tidak ada dalam hasil pemetaan tidak dicetak.
    """
    import re
    import statistics
    part_headers = root.findall(".//score-part")
    if not part_headers:
        return {}

    STEP_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    part_map = parts_by_id(root)
    all_parts = []
    for order, sp in enumerate(part_headers):
        pid = sp.get("id")
        pname_el = sp.find("part-name")
        pname = pname_el.text.strip() if pname_el is not None and pname_el.text else ""
        if not pname:
            ab = sp.find("part-abbreviation")
            pname = ab.text.strip() if ab is not None and ab.text else (pid or "")
        instr_names = [(si.findtext("instrument-name") or "").strip() for si in sp.findall("score-instrument")]
        midi_progs = []
        for mi in sp.findall("midi-instrument"):
            try:
                midi_progs.append(int((mi.findtext("midi-program") or "").strip()))
            except ValueError:
                pass

        p_el = part_map.get(pid)
        # Statistik per staf: partitur tertutup (SA di staf 1, TB di staf 2) dipecah per staf
        staff_stats: Dict[int, dict] = {}
        clefs: Dict[int, Tuple[str, int]] = {}
        if p_el is not None:
            for m in p_el.findall("measure"):
                mnum = m.get("number")
                for clef in m.findall("attributes/clef"):
                    try:
                        cno = int((clef.get("number") or "1").strip())
                    except ValueError:
                        cno = 1
                    if cno not in clefs:
                        sign = (clef.findtext("sign") or "G").strip().upper()
                        try:
                            oc = int((clef.findtext("clef-octave-change") or "0").strip())
                        except ValueError:
                            oc = 0
                        clefs[cno] = (sign, oc)
                sounding_staves = set()
                for n in m.findall("note"):
                    if n.find("rest") is not None or n.find("grace") is not None:
                        continue
                    try:
                        stf = int((n.findtext("staff") or "1").strip())
                    except ValueError:
                        stf = 1
                    st = staff_stats.setdefault(stf, {"pitches": [], "active_m": set()})
                    sounding_staves.add(stf)
                    pt = n.find("pitch")
                    if pt is not None:
                        try:
                            step = (pt.findtext("step") or "C").strip().upper()
                            octv = int((pt.findtext("octave") or "4").strip())
                            alt = float((pt.findtext("alter") or "0").strip() or 0)
                            # <pitch> MusicXML sudah nada bunyi (clef-octave-change tidak perlu ditambahkan)
                            st["pitches"].append(12 * (octv + 1) + STEP_SEMITONE.get(step, 0) + alt)
                        except ValueError:
                            pass
                for stf in sounding_staves:
                    try:
                        staff_stats[stf]["active_m"].add(int(mnum))
                    except (ValueError, TypeError):
                        pass

        fam, num, generic = _classify_part_name(pname)
        is_instr = _is_instrument_part(pname, instr_names, midi_progs)
        staves = sorted(staff_stats.keys()) or [1]
        total_active = len(set().union(*[st["active_m"] for st in staff_stats.values()])) if staff_stats else 0
        # Staf tambahan yang benar-benar bersuara menjadi sub-part sendiri (kunci "P1#2")
        multi = [stf for stf in staves if len(staff_stats.get(stf, {}).get("active_m", ())) >= max(2, 0.2 * total_active)]
        if len(multi) < 2:
            multi = [staves[0]]
        for k, stf in enumerate(multi):
            st = staff_stats.get(stf, {"pitches": [], "active_m": set()})
            key = pid if stf == staves[0] else f"{pid}#{stf}"
            clef_sign, clef_oct = clefs.get(stf, clefs.get(1, ("G", 0)))
            all_parts.append({
                "pid": key, "pname": pname if len(multi) == 1 else f"{pname} staf {stf}",
                "family": fam if (len(multi) == 1) else "?",
                "num": num if len(multi) == 1 else None,
                "generic": generic or len(multi) > 1,
                "active_m": st["active_m"], "order": order * 10 + k,
                "median": statistics.median(st["pitches"]) if st["pitches"] else None,
                "clef": clef_sign, "clef_oct": clef_oct,
                "instrument": is_instr,
            })

    part_info = [p for p in all_parts if not p["instrument"]]
    if not part_info:
        # Tidak ada part vokal terdeteksi (misal partitur melodi piano): pakai semua part sebagai suara
        part_info = all_parts
        for p in part_info:
            p["family"], p["generic"] = "?", True

    # --- Tebak keluarga part generik dari kunci + median nada, lalu koreksi relatif ---
    def bass_group(p) -> bool:
        return p["clef"] == "F" or (p["clef"] == "G" and p["clef_oct"] < 0) or (p["median"] is not None and p["median"] < 58)

    named_fams = {p["family"] for p in part_info if p["family"] != "?"}
    generic_parts = [p for p in part_info if p["family"] == "?"]
    for p in generic_parts:
        med = p["median"]
        if med is None:
            p["family"] = "S"
        elif bass_group(p):
            if p["clef"] == "G" and p["clef_oct"] < 0:
                p["family"] = "T"
            else:
                p["family"] = "T" if med >= 57 else "B"
        else:
            p["family"] = "S" if med >= 68 else "A"

    treble = [p for p in generic_parts if p["median"] is not None and not bass_group(p)]
    bass = [p for p in generic_parts if p["median"] is not None and bass_group(p)]
    for grp, hi_fam, lo_fam in ((treble, "S", "A"), (bass, "T", "B")):
        if len(grp) >= 2:
            grp_sorted = sorted(grp, key=lambda q: (-q["median"], q["order"]))
            fams = {q["family"] for q in grp} | (named_fams & {hi_fam, lo_fam})
            if hi_fam not in fams:
                grp_sorted[0]["family"] = hi_fam
            if lo_fam not in fams and len(grp_sorted) >= 2:
                grp_sorted[-1]["family"] = lo_fam

    # --- Bentuk slot per keluarga ---
    mapping: Dict[str, str] = {}
    by_fam: Dict[str, List[dict]] = {}
    for p in sorted(part_info, key=lambda q: q["order"]):
        by_fam.setdefault(p["family"], []).append(p)

    def norm_name(pn: str) -> str:
        return re.sub(r"[\s\.\-_]+", " ", pn.strip().lower())

    for fam, plist in by_fam.items():
        slots: List[dict] = []
        for p in plist:
            act = p["active_m"]
            target_num = None if p["generic"] else p["num"]
            matched = None
            for sl in slots:
                if sl["active_m"] & act:
                    continue  # berbunyi bersamaan: pasti suara berbeda
                if fam in ("Solo", "U", "Fem", "Male"):
                    # Solois berbeda bisa saja tak pernah berbunyi bersamaan: gabung hanya bila namanya sama
                    if norm_name(sl["pname"]) == norm_name(p["pname"]):
                        matched = sl
                        break
                elif target_num is None or sl["id"] == target_num:
                    # Divisi paduan suara: pecahan lintas halaman sering berganti nama
                    # ("Soprano" -> "S3", "Contralto 1" -> "C 1"); nomor sama + tidak tumpang tindih = suara sama
                    matched = sl
                    break
            if matched is not None:
                matched["pids"].append(p["pid"])
                matched["active_m"].update(act)
            else:
                existing = {sl["id"] for sl in slots}
                if target_num is not None and target_num not in existing:
                    new_id = target_num
                else:
                    new_id = 1
                    while new_id in existing:
                        new_id += 1
                slots.append({"id": new_id, "pids": [p["pid"]], "active_m": set(act), "pname": p["pname"], "generic": p["generic"]})

        single = len(slots) == 1
        for sl in slots:
            if single:
                vname = fam
            elif fam == "Solo":
                vname = f"{fam} {sl['id']}"
            else:
                vname = f"{fam}{sl['id']}"
            for pid in sl["pids"]:
                mapping[pid] = vname

    return mapping


def tambal_lirik_root(root: ET.Element) -> Tuple[int, int]:
    """Memanggil tambal_lirik.tambal(root) bila modulnya ada; (0, 0) bila tidak."""
    try:
        from .tambal_lirik import tambal
        return tambal(root)
    except (ImportError, ValueError):
        pass
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (here, os.path.join(here, "..", "..", "lirik"), os.path.join(here, "..", "lirik"), os.path.join(here, "lirik")):
        path = os.path.join(cand, "tambal_lirik.py")
        if os.path.exists(path):
            try:
                if cand not in sys.path:
                    sys.path.insert(0, cand)
                spec = importlib.util.spec_from_file_location("tambal_lirik", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.tambal(root)
            except Exception:
                return (0, 0)
    return (0, 0)


def repair_overflow(events: List[dict], capacity_q: float, label: str, repairs: List[str]) -> List[dict]:
    """Perbaikan deterministik untuk satu suara-birama yang isinya melebihi sukat.

    Hanya dua kasus yang terbukti tidak mengubah apa yang dinyanyikan / bisa diverifikasi eksak:
    1. Tanda diam hantu di UJUNG birama: membuangnya membuat jumlah durasi persis = kapasitas.
    2. Triol tak berkurung: tiga not berurutan sama nilainya (d) dan kelebihannya persis d,
       sehingga 3d -> 2d membuat birama pas. Hanya bila kandidatnya tunggal.
    Selebihnya dibiarkan (dilaporkan sebagai LEBIH oleh `check`).
    """
    if not events:
        return events
    divs = max(events[0].get("divisions", 1), 1)
    total = sum(e["duration"] for e in events) / divs
    excess = total - capacity_q
    if excess <= 0.02:
        return events
    evs = list(events)
    # 1. diam hantu di ujung birama
    dropped = 0
    while evs and evs[-1].get("rest") and not evs[-1].get("measure_rest"):
        d = evs[-1]["duration"] / divs
        if excess - d >= -0.02:
            evs.pop()
            excess -= d
            dropped += 1
        else:
            break
    if dropped:
        repairs.append(f"{label}: {dropped} tanda diam hantu di ujung birama dibuang")
    if excess <= 0.02:
        return evs
    # 2. triol tak berkurung
    cands = []
    for i in range(len(evs) - 2):
        trio = evs[i:i + 3]
        if any(e.get("tuplet") or e.get("grace") or e.get("chord") for e in trio):
            continue
        d = trio[0]["duration"]
        # hanya not pendek (1/8 atau lebih kecil): kurung triol yang luput OMR ada pada not berbalok
        if d / divs >= 0.99:
            continue
        if all(abs(e["duration"] - d) < 1e-9 for e in trio) and abs(excess - d / divs) < 0.02:
            cands.append(i)
    if len(cands) == 1:
        i = cands[0]
        d = evs[i]["duration"]
        for k in range(3):
            e = evs[i + k]
            e["duration"] = e["duration"] * 2.0 / 3.0
            e["tuplet"] = True
            e["tuplet_actual"] = 3
            e["tuplet_normal"] = 2
            e["onset"] = evs[i]["onset"] + k * e["duration"]
        for e in evs[i + 3:]:
            e["onset"] = e["onset"] - d
        repairs.append(f"{label}: tiga not senilai dijadikan triol (kelebihan persis satu not)")
    return evs


def parts_by_id(root: ET.Element) -> Dict[str, ET.Element]:
    """{part_id: <part>} dibangun sekali; menghindari pemindaian seluruh dokumen per part."""
    return {p.get("id"): p for p in root.findall("./part")} or {p.get("id"): p for p in root.iter("part")}


def sub_part_key(part_id: str, staff: int) -> str:
    """Kunci sub-part: part_id untuk staf pertama, 'P1#2' untuk staf kedua, dst."""
    return part_id if int(staff or 1) <= 1 else f"{part_id}#{int(staff)}"


def detect_divisi_chords(root: ET.Element, mapping: Dict[str, str]) -> Dict[str, Tuple[str, str]]:
    """Suara vokal yang menulis divisi sebagai akor (dua not setangkai) dipecah menjadi dua suara.

    Keputusan diambil per SUARA cetak (gabungan semua sub-part yang memetakan ke nama itu):
    akor pada >= 4 birama dan >= 20% birama bersuara. Nama hasil pecahan:
    * partitur tertutup: S tanpa A -> (S, A); A tanpa S -> (S, A); T tanpa B -> (T, B); B tanpa T -> (T, B);
    * selain itu nomor divisi berikutnya: S -> (S1, S2), S1 -> (S1, S2), A2 -> (A2, A3).
    Semua sub-part yang memetakan ke suara itu diperbarui agar penamaan tetap konsisten.
    """
    import re
    if not mapping:
        return {}
    fam_nums: Dict[str, set] = {}
    for v in mapping.values():
        m = re.match(r"^([A-Za-z]+)\s*(\d*)$", v)
        if m:
            fam_nums.setdefault(m.group(1), set()).add(int(m.group(2)) if m.group(2) else 1)

    by_vname: Dict[str, List[str]] = {}
    for key, vname in mapping.items():
        by_vname.setdefault(vname, []).append(key)

    part_map = parts_by_id(root)

    def chord_stats(key: str) -> Tuple[int, int]:
        pid, _, stf = key.partition("#")
        stf_no = int(stf) if stf else 1
        p_el = part_map.get(pid)
        if p_el is None:
            return 0, 0
        active = chord_measures = 0
        for m in p_el.findall("measure"):
            n_sound = n_chord = 0
            for n in m.findall("note"):
                if n.find("rest") is not None or n.find("grace") is not None:
                    continue
                try:
                    if int((n.findtext("staff") or "1").strip()) != stf_no:
                        continue
                except ValueError:
                    pass
                n_sound += 1
                if n.find("chord") is not None:
                    n_chord += 1
            if n_sound:
                active += 1
                if n_chord:
                    chord_measures += 1
        return active, chord_measures

    divisi: Dict[str, Tuple[str, str]] = {}
    for vname, keys in by_vname.items():
        fam = voice_family(vname)
        if fam in ("Solo", "U", "Other", "Fem", "Male"):
            continue
        active = chord_measures = 0
        for key in keys:
            a, c = chord_stats(key)
            active += a
            chord_measures += c
        if not (active and chord_measures >= 4 and chord_measures >= 0.2 * active):
            continue
        if fam == "S" and "A" not in fam_nums and "MS" not in fam_nums:
            upper, lower = vname, "A"
            fam_nums.setdefault("A", set()).add(1)
        elif fam == "A" and "S" not in fam_nums and "MS" not in fam_nums:
            upper, lower = "S", vname
            fam_nums.setdefault("S", set()).add(1)
        elif fam == "T" and "B" not in fam_nums and "Bar" not in fam_nums:
            upper, lower = vname, "B"
            fam_nums.setdefault("B", set()).add(1)
        elif fam == "B" and "T" not in fam_nums and "Bar" not in fam_nums:
            upper, lower = "T", vname
            fam_nums.setdefault("T", set()).add(1)
        else:
            nums = fam_nums.setdefault(fam, {1})
            m_num = re.match(r"^[A-Za-z]+\s*(\d+)$", vname)
            up_no = int(m_num.group(1)) if m_num else 1
            nums.add(up_no)
            low_no = up_no + 1
            while low_no in nums:
                low_no += 1
            nums.add(low_no)
            upper = f"{fam}{up_no}"
            lower = f"{fam}{low_no}"
        for key in keys:
            mapping[key] = upper
            divisi[key] = (upper, lower)
    return divisi


def _walk_measure_offsets(m_elem: ET.Element, divisions: int):
    """Menghasilkan (elemen, offset_divisions, divisions) untuk tiap anak birama, mengikuti kursor
    <note>/<backup>/<forward> seperti MusicXML mendefinisikannya."""
    cursor = 0
    divs = divisions
    for ch in m_elem:
        tag = strip_ns(ch.tag)
        if tag == "attributes":
            d = ch.find("divisions")
            if d is not None and d.text:
                try:
                    divs = int(d.text.strip())
                except ValueError:
                    pass
            yield ch, cursor, divs
        elif tag == "backup":
            try:
                cursor -= int((ch.findtext("duration") or "0").strip())
            except ValueError:
                pass
        elif tag == "forward":
            try:
                cursor += int((ch.findtext("duration") or "0").strip())
            except ValueError:
                pass
        elif tag == "note":
            yield ch, cursor, divs
            if ch.find("chord") is None and ch.find("grace") is None:
                try:
                    cursor += int((ch.findtext("duration") or "0").strip())
                except ValueError:
                    pass
        else:
            yield ch, cursor, divs


TEMPO_WORDS = ("andant", "allegr", "moderat", "adagi", "lent", "larg", "prest", "vivac", "grave", "con moto",
               "slow", "fast", "ballad", "swing", "tempo", "rubato", "maestoso", "animato", "tranquil", "dolce",
               "sedang", "lambat", "cepat", "khidmat", "riang", "agung")

EXPRESSION_WORDS = ("cresc", "decresc", "dim", "rit", "rall", "accel", "a tempo", "tempo", "dolce", "legato",
                    "marcato", "espress", "poco", "molto", "sub", "sempre", "piu", "meno", "rubato", "fermata",
                    "sfz", "solo", "tutti", "hum", "ooh", "aah", "whisper", "bisik", "spoken")


def extract_directions(root: ET.Element, part_ids: List[str]) -> Dict[str, Dict[int, List[Tuple[float, str, str]]]]:
    """Dinamika, hairpin, dan kata ekspresi per part per birama.

    Hasil: {pid: {measure_number: [(offset_quarters, kind, text), ...]}} dengan kind
    "dynamic" (p, mf, f, ...), "wedge_start_cresc", "wedge_start_decresc", "wedge_stop", "words".
    """
    out: Dict[str, Dict[int, List[Tuple[float, str, str]]]] = {}
    part_map = parts_by_id(root)
    for pid in part_ids:
        p_el = part_map.get(pid)
        if p_el is None:
            continue
        divs = 1
        per_m: Dict[int, List[Tuple[float, str, str]]] = {}
        for m_idx, m_elem in enumerate(p_el.findall("measure")):
            try:
                mnum = int(m_elem.get("number"))
            except (TypeError, ValueError):
                mnum = m_idx + 1
            for ch, cursor, divs in _walk_measure_offsets(m_elem, divs):
                if strip_ns(ch.tag) != "direction":
                    continue
                off = cursor
                off_el = ch.find("offset")
                if off_el is not None and off_el.text:
                    try:
                        off += int(float(off_el.text.strip()))
                    except ValueError:
                        pass
                off_q = off / max(divs, 1)
                for dt in ch.findall("direction-type"):
                    for child in dt:
                        tag = strip_ns(child.tag)
                        if tag == "dynamics":
                            for d in child:
                                dname = strip_ns(d.tag)
                                if dname == "other-dynamics":
                                    dname = (d.text or "").strip()
                                if dname:
                                    per_m.setdefault(mnum, []).append((off_q, "dynamic", dname))
                        elif tag == "wedge":
                            wt = (child.get("type") or "").lower()
                            if wt in ("crescendo", "diminuendo"):
                                per_m.setdefault(mnum, []).append((off_q, "wedge_start_" + ("cresc" if wt == "crescendo" else "decresc"), ""))
                            elif wt == "stop":
                                per_m.setdefault(mnum, []).append((off_q, "wedge_stop", ""))
                        elif tag == "words":
                            txt = (child.text or "").strip()
                            low = txt.lower()
                            if txt and len(txt) <= 28 and any(k in low for k in EXPRESSION_WORDS) and not any(c.isdigit() for c in txt):
                                per_m.setdefault(mnum, []).append((off_q, "words", txt))
        out[pid] = per_m
    return out


def extract_barlines(root: ET.Element) -> Dict[int, Dict[str, str]]:
    """{measure_number: {"right": ..., "left": ..., "ending": ...}} dari <barline> semua part (yang pertama menang)."""
    out: Dict[int, Dict[str, str]] = {}
    for p_el in root.findall(".//part"):
        for m_idx, m_elem in enumerate(p_el.findall("measure")):
            try:
                mnum = int(m_elem.get("number"))
            except (TypeError, ValueError):
                mnum = m_idx + 1
            info = out.setdefault(mnum, {})
            for bl in m_elem.findall("barline"):
                loc = (bl.get("location") or "right").lower()
                style = (bl.findtext("bar-style") or "").strip().lower()
                rep_el = bl.find("repeat")
                end_el = bl.find("ending")
                if end_el is not None and (end_el.get("type") or "start").lower() == "start" and "ending" not in info:
                    num = (end_el.get("number") or "").strip()
                    txt = (end_el.text or "").strip()
                    info["ending"] = txt or (f"{num}." if num else "1.")
                if loc == "left":
                    if rep_el is not None and (rep_el.get("direction") or "").lower() == "forward":
                        info.setdefault("left", "repeat_start")
                    elif style in ("light-light", "heavy-light") and "left" not in info:
                        info["left"] = "double"
                else:
                    if rep_el is not None and (rep_el.get("direction") or "").lower() == "backward":
                        info.setdefault("right", "repeat_end")
                    elif style == "light-light":
                        info.setdefault("right", "double")
                    elif style in ("light-heavy", "heavy", "heavy-heavy"):
                        info.setdefault("right", "final")
    return out


def parse_musicxml_to_score(
    xml_path: str,
    title: Optional[str] = None,
    composer: Optional[str] = None,
    arranger: Optional[str] = None,
    subtitle: Optional[str] = None,
    lyricist: Optional[str] = None,
    beat_unit: str = POLICY_QUARTER,
    tambal_lirik: bool = True
) -> NotAngkaScore:
    """Mengubah file MusicXML menjadi NotAngkaScore.

    ``beat_unit`` menentukan satuan ketuk cetak (lihat notangka.meter):
    "quarter" (bawaan, praktik Puji Syukur/lagumisa) atau "denominator".
    ``tambal_lirik`` memecah kembali token lirik yang digumpalkan OMR ke not-not kosong
    di depannya memakai pemenggal PUEBI (lirik/tambal_lirik.py) - hanya bila jumlah suku
    katanya PERSIS mengisi lubang, jadi tidak menebak.
    """
    root = degreelib.read_musicxml(xml_path)
    repairs: List[str] = []
    if tambal_lirik:
        n_tok, n_syl = tambal_lirik_root(root)
        if n_tok:
            repairs.append(f"lirik: {n_tok} token lengket dipecah menjadi {n_syl} suku kata tambahan (PUEBI)")

    # 1. Ekstrak Metadata
    meta = ScoreMeta()

    raw_title = ""
    if title:
        raw_title = title
    else:
        work_title = root.find(".//work/work-title")
        movement_title = root.find(".//movement-title")
        if work_title is not None and work_title.text:
            raw_title = work_title.text.strip()
        elif movement_title is not None and movement_title.text:
            raw_title = movement_title.text.strip()
        else:
            base = os.path.splitext(os.path.basename(xml_path))[0]
            raw_title = base

    # Bersihkan underscore
    raw_title = raw_title.replace("_", " ").strip()

    # Ekstrak Komposer & Arranger dari tag resmi
    if composer:
        meta.composer = composer
    else:
        for composer_node in root.findall(".//creator[@type='composer']"):
            cand = (composer_node.text or "").strip()
            if cand and not looks_like_junk_credit(cand):
                meta.composer = cand
                break

    if arranger:
        meta.arranger = arranger
    else:
        for arranger_node in root.findall(".//creator[@type='arranger']"):
            cand = (arranger_node.text or "").strip()
            if cand and not looks_like_junk_credit(cand):
                meta.arranger = cand
                break

    if lyricist:
        meta.lyricist = lyricist
    else:
        for lyricist_node in root.findall(".//creator[@type='lyricist']"):
            cand = (lyricist_node.text or "").strip()
            if cand and not looks_like_junk_credit(cand):
                meta.lyricist = cand
                break

    if subtitle:
        meta.subtitle = subtitle

    # Pindai tag credit-words untuk title, subtitle, composer, arranger, lyricist
    for credit in root.findall(".//credit"):
        for cw in credit.findall(".//credit-words"):
            txt = (cw.text or "").strip()
            if not txt:
                continue
            txt_low = txt.lower()
            if looks_like_junk_credit(txt) and not any(k in txt_low for k in ("music by", "composed by", "words by", "arr")):
                continue
            if ("arr." in txt_low or "arrang" in txt_low) and not meta.arranger:
                meta.arranger = txt
            elif ("music by" in txt_low or "composed by" in txt_low) and not meta.composer:
                meta.composer = txt
            elif ("words by" in txt_low or "text by" in txt_low or "puisi" in txt_low or "syair" in txt_low or "lyric" in txt_low) and not meta.lyricist:
                meta.lyricist = txt
            elif ("from " in txt_low or "satb" in txt_low) and not meta.subtitle:
                meta.subtitle = txt

    # Jika nama judul mengandung pemisah " - " (misal: "Remember Me - Kuriakos Elias Chavara")
    if " - " in raw_title:
        parts = raw_title.split(" - ", 1)
        meta.title = parts[0].strip()
        second_part = parts[1].strip()
        if not meta.arranger and not meta.composer:
            if any(term in second_part.lower() for term in ["arr", "satb", "choir"]):
                meta.arranger = second_part
            else:
                meta.arranger = f"Arr. {second_part}"
    else:
        if raw_title.islower():
            meta.title = raw_title.title()
        else:
            meta.title = raw_title

    # Cari Key Signature awal
    fifths = 0
    mode = "major"
    first_key = root.find(".//key")
    if first_key is not None:
        f_node = first_key.find("fifths")
        m_node = first_key.find("mode")
        if f_node is not None and f_node.text:
            fifths = int(f_node.text)
        if m_node is not None and m_node.text:
            mode = m_node.text

    tonic_step, tonic_alter = degreelib.tonic_from_fifths(fifths, mode, "la_based")
    raw_tonic_name = degreelib.pitch_name(tonic_step, tonic_alter)
    tonic_name = to_indonesian_pitch(raw_tonic_name)
    meta.tonic_label = f"Do={tonic_name}"
    initial_fifths, initial_mode = fifths, mode

    tonic_cache: Dict[Tuple[int, str], Tuple[str, int, str]] = {}

    def tonic_for(ev) -> Tuple[str, int, str]:
        """(step, alter, label 'Do=X') untuk kunci yang berlaku pada event ini - mendukung modulasi."""
        f = ev.get("fifths")
        f = initial_fifths if f is None else int(f)
        md = (ev.get("key_mode") or initial_mode or "major")
        key = (f, md)
        if key not in tonic_cache:
            try:
                st, al = degreelib.tonic_from_fifths(f, md, "la_based")
            except ValueError:
                st, al = tonic_step, tonic_alter
            tonic_cache[key] = (st, al, f"Do={to_indonesian_pitch(degreelib.pitch_name(st, al))}")
        return tonic_cache[key]

    # Sukat awal & kebijakan satuan ketuk
    if beat_unit not in POLICIES:
        beat_unit = POLICY_QUARTER
    meta.beat_unit = beat_unit
    time_node = root.find(".//time")
    if time_node is not None:
        beats = time_node.find("beats")
        beat_type = time_node.find("beat-type")
        if beats is not None and beat_type is not None and beats.text and beat_type.text:
            meta.time_signature = parse_meter(f"{beats.text.strip()}/{beat_type.text.strip()}").label

    # Tempo: <per-minute> (metronom), lalu <sound tempo="">; kata tempo dari <words> birama pertama.
    # Bila sumber tidak menyebut tempo, tidak dicetak (bukan angka bawaan yang mengada-ada).
    tempo_node = root.find(".//per-minute")
    if tempo_node is not None and tempo_node.text:
        try:
            meta.tempo.bpm = int(round(float(tempo_node.text)))
            bu = root.find(".//metronome/beat-unit")
            if bu is not None and bu.text:
                meta.tempo.beat_unit = {"quarter": "4", "eighth": "8", "half": "2", "quarter.": "4."}.get(bu.text.strip(), "4")
        except ValueError:
            pass
    if meta.tempo.bpm is None:
        snd = root.find(".//sound[@tempo]")
        if snd is not None:
            try:
                meta.tempo.bpm = int(round(float(snd.get("tempo"))))
            except (TypeError, ValueError):
                pass
    first_part_el = root.find(".//part")
    if first_part_el is not None:
        m0 = first_part_el.find("measure")
        if m0 is not None:
            for w in m0.findall(".//direction-type/words"):
                txt = (w.text or "").strip()
                low = txt.lower()
                if txt and len(txt) <= 32 and not any(ch.isdigit() for ch in txt) and any(k in low for k in TEMPO_WORDS):
                    meta.tempo.text = txt
                    break

    # 2. Proses Part-Part dan Birama secara Dinamis
    standard_parts = detect_voice_mapping(root)
    divisi_map = detect_divisi_chords(root, standard_parts)

    def ev_key(ev) -> str:
        return sub_part_key(ev["part_id"], ev.get("staff", 1) or 1)

    def ev_midi(ev) -> float:
        step_semi = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
        return 12 * (int(ev.get("octave") or 4) + 1) + step_semi.get(str(ev.get("step") or "C").upper(), 0) + float(ev.get("alter") or 0)

    measures_dict: Dict[int, Measure] = {}

    # Gunakan degreelib.iter_note_events untuk pembacaan durasi dan polifoni yang kokoh.
    # Setiap event membawa "time_sig" (sukat yang berlaku pada biramanya), sehingga
    # perubahan sukat di tengah lagu (3/4 -> 7/8 -> 9/8 -> 2/2 ...) terbaca per event.
    events = list(degreelib.iter_note_events(root))

    def ev_measure_number(ev) -> int:
        try:
            return int(ev["measure"])
        except (ValueError, TypeError):
            return ev["measure_index"] + 1

    def ev_meter(ev) -> Meter:
        return parse_meter(ev.get("time_sig") or meta.time_signature or "4/4")

    # Kelompokkan event per (mnum, vname, pid) untuk menyaring tanda diam dummy dari part disjoin
    parts_per_mv: Dict[Tuple[int, str], Dict[str, List[dict]]] = {}
    for ev in events:
        key = ev_key(ev)
        vname = standard_parts.get(key)
        if vname is None:
            continue  # part instrumental / staf tidak dicetak
        mnum = ev_measure_number(ev)
        parts_per_mv.setdefault((mnum, vname), {}).setdefault(key, []).append(ev)

    # Untuk tiap (mnum, vname), seleksi event yang valid:
    # 1. Jika ada part yang memiliki nada sounding (not rest), ambil part-part yang sounding.
    # 2. Jika seluruh part hanya memuat tanda diam (rest), ambil SATU part saja agar tidak duplikasi.
    filtered_events = []
    for (mnum, vname) in sorted(parts_per_mv.keys(), key=lambda k: (k[0], voice_sort_key(k[1]))):
        p_dict = parts_per_mv[(mnum, vname)]
        sounding_pids = [pid for pid, evs in p_dict.items() if any(not e.get("rest") for e in evs)]
        if sounding_pids:
            for pid in sounding_pids:
                filtered_events.extend(p_dict[pid])
        else:
            first_pid = list(p_dict.keys())[0]
            filtered_events.extend(p_dict[first_pid])

    # Suara utama per (part, birama): suara bernomor TERKECIL pada staf terkecil.
    # Ini menggantikan aturan lama "voice <= 1" yang meloloskan voice 0 DAN voice 1
    # sekaligus (berkas ground-truth tertentu menomori suara dari 0) sehingga tanda diam
    # kedua suara menumpuk dan birama tampak meluap dua kali lipat.
    primary_voice: Dict[Tuple[str, int], int] = {}
    for ev in filtered_events:
        if ev.get("grace"):
            continue
        try:
            vno = int(ev.get("voice", 1))
        except (TypeError, ValueError):
            vno = 1
        key = (ev_key(ev), ev_measure_number(ev))
        if key not in primary_voice or vno < primary_voice[key]:
            primary_voice[key] = vno

    def is_primary_event(ev) -> bool:
        """Event yang ikut membentuk ketukan cetak: bukan chord lanjutan, grace, atau suara sekunder
        (suara utama = nomor suara terkecil pada staf itu)."""
        if ev.get("chord") or ev.get("grace"):
            return False
        try:
            vno = int(ev.get("voice", 1))
        except (TypeError, ValueError):
            vno = 1
        key = (ev_key(ev), ev_measure_number(ev))
        return vno == primary_voice.get(key, vno)

    # --- Pra-pindai: isi nyata tiap birama (dalam not seperempat) untuk mendeteksi
    #     birama gantung (pickup/anacrusis) dan birama penggenap di akhir lagu.
    content_q: Dict[int, float] = {}
    implicit_measures = set()
    meter_by_measure: Dict[int, Meter] = {}
    for ev in filtered_events:
        if not is_primary_event(ev):
            continue
        mnum = ev_measure_number(ev)
        divs = max(ev["divisions"], 1)
        end_q = (ev["onset"] + ev["duration"]) / divs
        content_q[mnum] = max(content_q.get(mnum, 0.0), end_q)
        if ev.get("implicit_measure"):
            implicit_measures.add(mnum)
        if mnum not in meter_by_measure:
            meter_by_measure[mnum] = ev_meter(ev)

    all_mnums = sorted(content_q.keys())
    first_mnum = all_mnums[0] if all_mnums else None
    last_mnum = all_mnums[-1] if all_mnums else None

    # offset_q: pergeseran onset agar birama gantung rapat ke garis birama berikutnya
    # capacity_units: kapasitas nyata birama parsial (dalam unit)
    offset_q: Dict[int, float] = {}
    partial_capacity: Dict[int, float] = {}
    for mnum in all_mnums:
        mt = meter_by_measure[mnum]
        cap_q = mt.capacity_quarters()
        cq = content_q[mnum]
        is_partial = cq > METER_EPS and cq < cap_q - 0.02
        if not is_partial:
            continue
        if mnum in implicit_measures or mnum == first_mnum:
            offset_q[mnum] = cap_q - cq
            partial_capacity[mnum] = cq / mt.unit_quarters(beat_unit)
        elif mnum == last_mnum:
            partial_capacity[mnum] = cq / mt.unit_quarters(beat_unit)

    def emit_symbols(
        notes_list: List[NoteItem], first_text: str, cont_text: str,
        onset_u: float, dur_u: float, offset_u: float, *,
        octave: int = 0, accidental: Optional[str] = None, lyric: Optional[str] = None,
        tie_last: bool = False, tuplet: Optional[str] = None, allow_dot_first: bool = True,
        fixed_beams: Optional[int] = None, groups_units: Optional[List[float]] = None,
        verses: Optional[List[Optional[str]]] = None, fermata: bool = False
    ):
        """Menguraikan satu event berdurasi dur_u (unit) menjadi simbol-simbol Not Angka.

        Kaidah (Puji Syukur / lagumisa):
        * potongan tepat satu unit -> simbol polos (angka pada potongan pertama, lalu titik);
        * potongan sub-unit -> simbol berbalok: 1/2 unit satu balok, 1/4 unit dua balok,
          termasuk pada titik perpanjangan dan tanda diam (PS 347b: "3 .̅ 3̅", PS 390b: "0̅3̅");
        * potongan dipotong pada batas unit/kelompok ketuk (lihat meter.split_for_symbols)
          sehingga balok tak pernah melintasi ketukan.
        """
        if tuplet is not None:
            # Tuplet dicetak sebagai satu simbol; kurung ╭─3─╮ (bukan balok) yang menandai nilainya.
            beams = 0 if tuplet == "3" else beams_for_length(dur_u)
            notes_list.append(NoteItem(
                text=first_text, octave=octave, accidental=accidental, beams=beams,
                beat=1.0 + onset_u - offset_u, duration_beats=dur_u,
                lyric=lyric, tie=tie_last, tuplet=tuplet, verses=verses, fermata=fermata
            ))
            return

        pieces = split_for_symbols(onset_u, dur_u, groups_units or [1.0])
        symbols: List[Tuple[float, float, int, bool]] = []  # (awal, panjang, balok, titik)
        for k, (p_start, p_len) in enumerate(pieces):
            if p_len >= 1.0 - 0.02:
                symbols.append((p_start, 1.0, 0, False))
                continue
            allow_dot = allow_dot_first and k == 0 and first_text not in ("0",)
            sub_pos = p_start
            for L, beams, dot, _exact in symbols_for_subunit(p_len, allow_dot=allow_dot):
                symbols.append((sub_pos, L, beams, dot))
                sub_pos += L

        for k, (p_start, p_len, beams, dot) in enumerate(symbols):
            is_first = (k == 0)
            is_last = (k == len(symbols) - 1)
            notes_list.append(NoteItem(
                text=first_text if is_first else cont_text,
                octave=octave if is_first else 0,
                accidental=accidental if is_first else None,
                beams=fixed_beams if fixed_beams is not None else beams,
                dot=dot,
                beat=1.0 + p_start - offset_u,
                duration_beats=p_len,
                lyric=lyric if is_first else None,
                verses=verses if is_first else None,
                fermata=fermata if is_first else False,
                tie=tie_last if is_last else False,
                tuplet=None
            ))

    # Kelompokkan event menjadi (not dasar, [not akor]) per onset, lalu arahkan ke suara cetak:
    # * sub-part berdivisi akor: not tertinggi -> suara atas, not terendah -> suara bawah;
    # * sub-part biasa dengan akor sesekali: keluarga B mengambil not terendah, lainnya tertinggi.
    chord_groups: List[Tuple[dict, List[dict]]] = []
    for ev in filtered_events:
        if ev.get("grace"):
            continue
        key = ev_key(ev)
        if key not in standard_parts:
            continue
        if ev.get("chord"):
            if chord_groups:
                base = chord_groups[-1][0]
                if (base["part_id"] == ev["part_id"] and ev_measure_number(base) == ev_measure_number(ev)
                        and (base.get("staff", 1) or 1) == (ev.get("staff", 1) or 1) and base.get("voice") == ev.get("voice")):
                    chord_groups[-1][1].append(ev)
            continue
        if not is_primary_event(ev):
            continue
        chord_groups.append((ev, []))

    routed_events: List[Tuple[str, dict, dict]] = []  # (nama suara, event nada, event dasar untuk lirik)
    for base, chords in chord_groups:
        key = ev_key(base)
        vname = standard_parts[key]
        pitched = [e for e in [base] + chords if e.get("step") is not None and not e.get("rest")]
        if len(pitched) >= 2:
            # Not akor setangkai selalu senilai not dasarnya; durasi hasil ekstraksi PDF bisa melenceng
            pitched = [e if e is base else dict(e, duration=base["duration"], note_type=base.get("note_type"),
                                                 dots=base.get("dots", 0), onset=base["onset"]) for e in pitched]
            pitched.sort(key=ev_midi, reverse=True)
        if key in divisi_map:
            upper, lower = divisi_map[key]
            if len(pitched) >= 2:
                routed_events.append((upper, pitched[0], base))
                routed_events.append((lower, pitched[-1], base))
            else:
                routed_events.append((upper, base, base))
                routed_events.append((lower, base, base))
        elif len(pitched) >= 2:
            pick = pitched[-1] if voice_family(vname) in ("B", "Bar") else pitched[0]
            routed_events.append((vname, pick, base))
        else:
            routed_events.append((vname, base, base))

    # Perbaikan deterministik birama meluap (per suara-birama)
    per_vm: Dict[Tuple[str, int], List[Tuple[str, dict, dict]]] = {}
    order: List[Tuple[str, int]] = []
    for item in routed_events:
        k = (item[0], ev_measure_number(item[1]))
        if k not in per_vm:
            per_vm[k] = []
            order.append(k)
        per_vm[k].append(item)
    repaired: List[Tuple[str, dict, dict]] = []
    for k in order:
        items = per_vm[k]
        vname_k, mnum_k = k
        mt_k = meter_by_measure.get(mnum_k) or ev_meter(items[0][1])
        if mnum_k in partial_capacity:
            repaired.extend(items)
            continue
        before = [it[1] for it in items]
        after = repair_overflow(before, mt_k.capacity_quarters(), f"m{mnum_k} {vname_k}", repairs)
        keep = {id(e) for e in after}
        repaired.extend(it for it in items if id(it[1]) in keep)
    routed_events = repaired

    # Proses event yang telah diarahkan
    for vname, ev, lyric_ev in routed_events:
        pid = ev["part_id"]
        mnum = ev_measure_number(ev)
        mt = meter_by_measure.get(mnum) or ev_meter(ev)
        unit_q = mt.unit_quarters(beat_unit)
        cap_units = mt.capacity_units(beat_unit)
        groups_u = mt.groups_units(beat_unit)

        ev_tonic_step, ev_tonic_alter, ev_tonic_label = tonic_for(ev)
        if mnum not in measures_dict:
            measures_dict[mnum] = Measure(
                number=mnum,
                time_signature=mt.label,
                capacity_beats=partial_capacity.get(mnum),
                tonic_label=ev_tonic_label
            )
        m_obj = measures_dict[mnum]

        if vname not in m_obj.voices:
            m_obj.voices[vname] = MeasureVoice(voice_name=vname, notes=[])
        notes_out = m_obj.voices[vname].notes

        divs = max(ev["divisions"], 1)
        off_q = offset_q.get(mnum, 0.0)
        dur_u = (ev["duration"] / divs) / unit_q
        onset_u = ((ev["onset"] / divs) + off_q) / unit_q
        offset_u = off_q / unit_q

        # Ekstrak lirik per suku kata: bait 1 -> lyric, bait 2.. -> verses
        syl = None
        verses: Optional[List[Optional[str]]] = None
        lyr_src = lyric_ev.get("lyrics") or ev.get("lyrics")
        if lyr_src:
            by_verse: Dict[int, str] = {}
            for l in lyr_src:
                txt = clean_lyric_text(l.get("text") or "")
                if not txt:
                    continue
                if l.get("syllabic") in ("begin", "middle"):
                    txt += "-"
                vno = int(l.get("verse") or 1)
                if vno not in by_verse:
                    by_verse[vno] = txt
            if by_verse:
                vmin = min(by_verse)
                syl = by_verse.get(1) or by_verse.get(vmin)
                extra = [by_verse.get(k) for k in range(2, max(by_verse) + 1)] if max(by_verse) >= 2 else []
                if 1 not in by_verse and vmin in by_verse:
                    extra = [by_verse.get(k) for k in range(2, max(by_verse) + 1) if k != vmin]
                if any(extra):
                    verses = extra

        # Deteksi tuplet: triplet -> "3" (kurung berbusur), tuplet lain -> kode angkanya
        t_act = ev.get("tuplet_actual")
        has_tmod = bool(ev.get("tuplet")) or ev.get("tuplet_bracket") in ("start", "continue")
        tuplet_code = None
        if has_tmod:
            tuplet_code = "3" if t_act in (3, None) else str(t_act)

        # Kasus 1: Tanda Diam (Rest)
        if ev.get("rest"):
            measure_cap = partial_capacity.get(mnum, cap_units)
            is_whole_rest = (
                ev.get("measure_rest")
                or dur_u >= measure_cap - 0.08
                or (abs(onset_u - offset_u) < 0.02 and dur_u >= measure_cap * 0.85)
            )
            if is_whole_rest:
                notes_out.append(NoteItem(text="0", octave=0, beat=1.0, duration_beats=measure_cap))
                continue
            emit_symbols(notes_out, "0", "0", onset_u, dur_u, offset_u,
                         tuplet=tuplet_code, allow_dot_first=False, groups_units=groups_u,
                         fermata=bool(ev.get("fermata")))
            continue

        # Kasus 2: Nada Tak Bernada / Bisikan / Efek Vokal Perkusif (Unpitched) -> simbol 'x'
        tie_flag = (ev.get("tie_state") in ("start", "continue"))
        if ev.get("unpitched") or ev.get("step") is None:
            emit_symbols(notes_out, "x", ".", onset_u, dur_u, offset_u,
                         lyric=syl, tie_last=tie_flag, tuplet=tuplet_code, groups_units=groups_u,
                         verses=verses, fermata=bool(ev.get("fermata")))
            continue

        # Kasus 3: Nada Bernada
        deg, acc_name, delta = degreelib.degree_of(ev["step"], ev["alter"], ev_tonic_step, ev_tonic_alter)
        acc_code = "kres" if delta > 0 else ("mol" if delta < 0 else None)
        # Tentukan oktaf referensi:
        # Sopran & Alto = 4, Bas = 3.
        # Tenor: jika ditulis di Kunci G (treble clef) tanpa oktaf sounding (-1),
        # not-not tertulisnya berada pada oktaf 4-5 (seperti Sopran), sehingga ref_oct = 4
        # agar tidak menghasilkan 2 titik oktaf atas palsu yang menabrak garis balok.
        if vname.startswith("S") or vname.startswith("A"):
            ref_oct = 4
        elif vname.startswith("B"):
            ref_oct = 3
        elif vname.startswith("T"):
            if ev.get("clef_sign") == "G" and ev.get("clef_octave_change", 0) != -1:
                ref_oct = 4
            elif ev.get("octave", 3) >= 4:
                ref_oct = 4
            else:
                ref_oct = 3
        else:
            ref_oct = 4 if ev.get("octave", 3) >= 4 else 3
        oct_diff = degreelib.octave_offset(ev["step"], ev["octave"], ev_tonic_step, degreelib.diatonic_index(ev_tonic_step, ref_oct))

        # Nada perpanjangan legatura (tie stop / continue tanpa suku kata baru):
        # tidak mengulang angka, seluruh potongannya ditulis titik (.) dengan balok sesuai nilainya.
        if ev.get("tie_state") in ("stop", "continue") and not syl:
            emit_symbols(notes_out, ".", ".", onset_u, dur_u, offset_u,
                         tie_last=(ev.get("tie_state") == "continue"),
                         tuplet=tuplet_code, allow_dot_first=False, groups_units=groups_u)
            continue

        emit_symbols(notes_out, str(deg), ".", onset_u, dur_u, offset_u,
                     octave=oct_diff, accidental=acc_code, lyric=syl,
                     tie_last=tie_flag, tuplet=tuplet_code, groups_units=groups_u,
                     verses=verses, fermata=bool(ev.get("fermata")))

    # 2b. Garis birama (ganda, penutup, ulangan) dan kamar ulangan
    for mnum, info in extract_barlines(root).items():
        m_obj = measures_dict.get(mnum)
        if m_obj is None:
            continue
        if info.get("right"):
            m_obj.barline_type = info["right"]
        if info.get("left"):
            m_obj.barline_left = info["left"]
        if info.get("ending"):
            m_obj.ending = info["ending"]

    # 2c. Dinamika, hairpin, kata ekspresi: gabungan semua part cetak, tanpa duplikat
    printed_pids = sorted({k.partition("#")[0] for k in standard_parts.keys()})
    directions = extract_directions(root, printed_pids)
    for pid in printed_pids:
        open_wedge: Optional[Tuple[int, DynamicMark]] = None
        for mnum in sorted(directions.get(pid, {}).keys()):
            m_obj = measures_dict.get(mnum)
            if m_obj is None:
                continue
            mt = meter_by_measure.get(mnum) or parse_meter(m_obj.time_signature or meta.time_signature)
            unit_q = mt.unit_quarters(beat_unit)
            cap_u = partial_capacity.get(mnum, mt.capacity_units(beat_unit))
            off_u = offset_q.get(mnum, 0.0) / unit_q
            for off_q, kind, text in directions[pid][mnum]:
                beat = round(1.0 + off_q / unit_q + off_u - off_u, 3)
                beat = max(1.0, min(beat, cap_u + 0.999))
                if kind == "wedge_stop":
                    if open_wedge is not None:
                        w_m, w_mark = open_wedge
                        if w_m == mnum:
                            w_mark.hairpin_end_beat = max(beat, w_mark.beat + 0.5)
                        open_wedge = None
                    continue
                existing = m_obj.dynamics
                if kind == "dynamic" or kind == "words":
                    if any(abs(d.beat - beat) < 0.26 and d.text == text and not d.is_hairpin for d in existing):
                        continue
                    existing.append(DynamicMark(beat=beat, text=text))
                elif kind.startswith("wedge_start_"):
                    htype = kind.split("_")[-1]
                    if any(abs(d.beat - beat) < 0.26 and d.is_hairpin and d.hairpin_type == htype for d in existing):
                        open_wedge = None
                        continue
                    mark = DynamicMark(beat=beat, text="", is_hairpin=True, hairpin_type=htype,
                                       hairpin_end_beat=cap_u + 1.0)
                    existing.append(mark)
                    open_wedge = (mnum, mark)
        # hairpin yang tidak ditutup dalam birama yang sama dibiarkan sampai akhir biramanya

    # 3. Kumpulkan Teks Lirik Gabungan untuk Kompatibilitas
    all_measures = [measures_dict[k] for k in sorted(measures_dict.keys())]
    for m in all_measures:
        for vname in ("S", "A", "T", "B"):
            v = m.voices.get(vname)
            if v and v.notes:
                words = [n.lyric for n in v.notes if n.lyric]
                if words:
                    m.lyrics[vname] = " ".join(words)

        # Lirik bersama SA dan TB
        m.lyrics["SA"] = m.lyrics.get("S") or m.lyrics.get("A", "")
        m.lyrics["TB"] = m.lyrics.get("T") or m.lyrics.get("B", "")

    # Tanda birama akhir
    if all_measures:
        all_measures[-1].barline_type = "final"

    # 4. Birama diam beruntun (semua suara cetak diam) -> satu birama dengan hitungan (multi-rest)
    def measure_all_rest(m: Measure) -> bool:
        if m.dynamics:
            return False
        vs = [v for v in m.voices.values() if v.notes]
        if not vs:
            return True
        return all(all(n.text == "0" and not n.lyric for n in v.notes) for v in vs)

    hidden_measures = set()
    i = 0
    while i < len(all_measures):
        if measure_all_rest(all_measures[i]) and all_measures[i].capacity_beats is None:
            j = i
            while (j + 1 < len(all_measures) and measure_all_rest(all_measures[j + 1])
                   and all_measures[j + 1].capacity_beats is None
                   and (all_measures[j + 1].time_signature == all_measures[i].time_signature)):
                j += 1
            run = j - i + 1
            if run >= 2:
                all_measures[i].multi_rest = run
                for k in range(i + 1, j + 1):
                    hidden_measures.add(all_measures[k].number)
            i = j + 1
        else:
            i += 1

    # 5. Susun Sistem secara Dinamis: tipe blok dan suara dipilih PER SISTEM
    all_sounding_voices = set()
    for m in all_measures:
        for v, mv in m.voices.items():
            if any(n.text != "0" for n in mv.notes):
                all_sounding_voices.add(v)
    all_ordered_voices = sorted(list(all_sounding_voices), key=voice_sort_key)
    printable = [m for m in all_measures if m.number not in hidden_measures]

    systems = []
    i = 0
    while i < len(printable):
        cur_chunk = []
        cur_beats = 0.0
        cur_width = 0.0
        while i < len(printable):
            m_cand = printable[i]
            if m_cand.capacity_beats is not None:
                b_cnt = m_cand.capacity_beats
            else:
                b_cnt = parse_meter(m_cand.time_signature or meta.time_signature or "4/4").capacity_units(beat_unit)
            if m_cand.multi_rest > 1:
                b_cnt = 2.0
            max_chunk_meas = 4 if len(all_sounding_voices) > 4 else 5
            max_chunk_beats = 14.5 if len(all_sounding_voices) > 4 else 16.5
            # Perkiraan lebar alami birama (pt): birama padat not/lirik memaksa sistem lebih pendek
            w_need = estimate_measure_width(m_cand, b_cnt)
            if cur_chunk and (cur_beats + b_cnt > max_chunk_beats or len(cur_chunk) >= max_chunk_meas
                              or cur_width + w_need > SYSTEM_USABLE_WIDTH * 1.6):
                break
            cur_chunk.append(m_cand.number)
            cur_beats += b_cnt
            cur_width += w_need
            i += 1

        sys_measures = [m for m in printable if m.number in cur_chunk]
        sys_voices_set = set()
        for m in sys_measures:
            for v, mv in m.voices.items():
                if any(n.text != "0" for n in mv.notes):
                    sys_voices_set.add(v)
        sys_voices = sorted(list(sys_voices_set), key=voice_sort_key)

        if not sys_voices:
            # sistem yang seluruhnya diam (misal multi-rest): pakai suara pertama yang ada
            fallback = all_ordered_voices[:1] or ["S"]
            systems.append(SystemBlockConfig(measure_indices=cur_chunk, block_type="single_solo", voices=fallback))
            continue
        vset = set(sys_voices)
        if len(sys_voices) == 1:
            blk_type, system_voices = "single_solo", sys_voices
        elif vset <= {"S", "A"}:
            blk_type, system_voices = "sa_duet", ["S", "A"]
        elif {"S", "A"} <= vset <= {"S", "A", "T", "B"}:
            blk_type, system_voices = "satb_paired", ["S", "A", "T", "B"]
        else:
            blk_type, system_voices = "general_multivoice", sys_voices

        systems.append(SystemBlockConfig(measure_indices=cur_chunk, block_type=blk_type, voices=system_voices))

    return NotAngkaScore(meta=meta, measures=all_measures, systems=systems, repairs=repairs)
