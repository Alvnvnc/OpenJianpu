"""Pustaka bersama batik-partitur: baca MusicXML dan ubah pitch jadi scale degree.

Hanya memakai stdlib. Tidak ada langkah vision di sini - seluruh kebenaran
berasal dari representasi simbolik MusicXML.
"""

import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

SCHEMA_VERSION = 2

# ---------------------------------------------------------------- konfigurasi

DEFAULT_CONFIG = {
    "mode": "reengrave",
    "tonic_policy": "from_score",
    "manual_tonic": None,
    "minor_policy": "la_based",
    "target_staves": [],
    "notation_style": "degree_labels",
    "rest_symbol": "0",
    # Bunyi tanpa nada (tepuk tangan, hentak kaki). jianpu-ly menyebutnya
    # "percussion beat" dan menuliskannya x; kepala not silang di partitur asal.
    "unpitched_symbol": "x",
    "accidental_style": "slash",
    "octave_style": "dots",
    "octave_anchor": "minimal_dots",
    "label_font_size": -1,
    "confidence_threshold": 0.92,
    "include_instruments": False,
    "language": "id",
    "omr_source": "auto",
}

OMR_SOFTWARE = re.compile(r"audiveris|oemer|photoscore|smartscore|sharpeye|capella-scan|\bomr\b", re.I)


def is_omr_source(root, cfg):
    """Apakah MusicXML ini hasil OMR - dari config, atau dari <encoding><software>.

    Penalti keyakinan tuplet (0,9 < ambang 0,92) dibuat karena Audiveris sering
    salah membaca tuplet; pada ekspor program notasi atau bacaan glif
    (pdf_to_musicxml.py) tuplet itu pasti, dan 144 item review pada satu
    partitur Sibelius semuanya derau. Sumber yang tidak menyebut perangkat
    lunaknya dianggap simbolik: yang dituntut review adalah yang terbukti
    rawan, bukan yang tidak diketahui.
    """
    pilihan = cfg.get("omr_source", "auto")
    if pilihan in (True, False):
        return pilihan
    for node in root.iter():
        if strip_ns(node.tag) == "software" and node.text and OMR_SOFTWARE.search(node.text):
            return True
    return False


def load_config(path=None):
    cfg = dict(DEFAULT_CONFIG)
    if path:
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
        unknown = sorted(set(user) - set(DEFAULT_CONFIG) - {"source", "$schema"})
        if unknown:
            raise ValueError("field config tidak dikenal: " + ", ".join(unknown))
        cfg.update({k: v for k, v in user.items() if k in DEFAULT_CONFIG})
    return cfg


# ------------------------------------------------------------------ teori nada

STEP_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
STEP_DIATONIC = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}
DIATONIC_STEP = {v: k for k, v in STEP_DIATONIC.items()}
MAJOR_OFFSETS = [0, 2, 4, 5, 7, 9, 11]

# fifths -7..+7
MAJOR_TONICS = ["Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#"]
MINOR_TONICS = ["Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#", "G#", "D#", "A#"]

ALTER_NAME = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}


def parse_pitch_name(name):
    """'Bb' -> ('B', -1). Menerima b/# dan unicode musik."""
    name = name.strip().replace("♭", "b").replace("♯", "#").replace("♮", "")
    if not name or name[0].upper() not in STEP_PC:
        raise ValueError("nama nada tidak valid: %r" % name)
    step = name[0].upper()
    alter = 0
    for ch in name[1:]:
        if ch == "b":
            alter -= 1
        elif ch == "#":
            alter += 1
        elif ch in "-s":
            continue
        else:
            raise ValueError("nama nada tidak valid: %r" % name)
    return step, alter


def pitch_name(step, alter):
    return step + ALTER_NAME.get(alter, "?%+d" % alter)


def pitch_class(step, alter):
    return (STEP_PC[step] + alter) % 12


def diatonic_index(step, octave):
    """Indeks diatonis absolut: naik 1 tiap huruf, 7 tiap oktaf."""
    return octave * 7 + STEP_DIATONIC[step]


def midi_number(step, alter, octave):
    return (octave + 1) * 12 + STEP_PC[step] + alter


def tonic_from_fifths(fifths, mode, minor_policy):
    """Tonic aktif ('1' dalam not angka) dari tanda kunci.

    Praktik not angka Indonesia memakai la-based minor: lagu minor tetap
    memakai do dari tangga nada mayor sejajar, sehingga tonik minor jadi 6.
    """
    idx = int(fifths) + 7
    if not 0 <= idx < len(MAJOR_TONICS):
        raise ValueError("fifths di luar jangkauan: %s" % fifths)
    if (mode or "major").lower() == "minor" and minor_policy == "do_based":
        return parse_pitch_name(MINOR_TONICS[idx])
    return parse_pitch_name(MAJOR_TONICS[idx])


def degree_of(step, alter, tonic_step, tonic_alter):
    """Pitch tertulis -> (degree 1-7, accidental, chromatic delta).

    Derivasi berbasis huruf: degree ditentukan ejaan not, bukan bunyi MIDI,
    sehingga F# dan Gb pada Do=C menghasilkan #4 dan b5, bukan angka yang sama.
    """
    degree = (STEP_DIATONIC[step] - STEP_DIATONIC[tonic_step]) % 7 + 1
    expected = MAJOR_OFFSETS[degree - 1]
    actual = (pitch_class(step, alter) - pitch_class(tonic_step, tonic_alter)) % 12
    delta = ((actual - expected) + 6) % 12 - 6
    if delta not in ALTER_NAME:
        raise ValueError("alterasi ekstrem pada %s: %+d" % (pitch_name(step, alter), delta))
    return degree, ALTER_NAME[delta], delta


def octave_offset(step, octave, tonic_step, tonic_ref_index):
    """Berapa oktaf not ini di atas/di bawah oktaf acuan suara ini."""
    rel = diatonic_index(step, octave) - tonic_ref_index
    return rel // 7


def plain_token(degree, accidental, offset, is_rest=False, rest_symbol="0"):
    """Bentuk teks datar untuk diff test: 5, #4, b7, 1' (oktaf naik), 5, (turun)."""
    if is_rest:
        return rest_symbol
    marks = "'" * offset if offset > 0 else "," * -offset
    return "%s%d%s" % (accidental, degree, marks)


# --------------------------------------------------------------- muat berkas

def read_musicxml(path):
    """Kembalikan root <score-partwise>. Menerima .musicxml/.xml/.mxl."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            inner = None
            if "META-INF/container.xml" in zf.namelist():
                container = ET.fromstring(zf.read("META-INF/container.xml"))
                node = container.find(".//rootfile")
                if node is not None:
                    inner = node.get("full-path")
            if inner is None:
                candidates = [n for n in zf.namelist()
                              if n.lower().endswith((".xml", ".musicxml")) and not n.startswith("META-INF")]
                if not candidates:
                    raise ValueError("arsip .mxl tidak berisi MusicXML")
                inner = candidates[0]
            data = zf.read(inner)
    else:
        with open(path, "rb") as fh:
            data = fh.read()

    root = ET.fromstring(data)
    tag = strip_ns(root.tag)
    if tag == "score-timewise":
        raise ValueError("score-timewise belum didukung; konversi ke score-partwise dulu")
    if tag != "score-partwise":
        raise ValueError("akar bukan score-partwise melainkan <%s>" % tag)
    strip_all_ns(root)
    return root


def strip_ns(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def strip_all_ns(elem):
    for node in elem.iter():
        node.tag = strip_ns(node.tag)


def part_names(root):
    names = {}
    for sp in root.findall("./part-list/score-part"):
        pid = sp.get("id")
        node = sp.find("part-name")
        abbrev = sp.find("part-abbreviation")
        label = (node.text or "").strip() if node is not None and node.text else ""
        if not label and abbrev is not None and abbrev.text:
            label = abbrev.text.strip()
        names[pid] = label or pid
    return names


def part_abbreviations(root):
    """{part_id: singkatan} dari <part-abbreviation>.

    Dipakai sebagai nama pendek pada sistem kedua dan seterusnya. Tanpa ini,
    nama suara hilang begitu partitur lebih dari satu sistem - penyanyi
    kehilangan penanda barisnya persis saat halaman jadi padat.
    """
    out = {}
    for sp in root.findall("./part-list/score-part"):
        node = sp.find("part-abbreviation")
        if node is not None and node.text and node.text.strip():
            out[sp.get("id")] = node.text.strip()
    return out


def text_int(elem, tag, default=None):
    node = elem.find(tag)
    if node is None or node.text is None or not node.text.strip():
        return default
    return int(float(node.text.strip()))


# ------------------------------------------------------------- iterasi not

# ------------------------------------------------- data ritme, lirik, barline
#
# Field-field di bawah ini hanya dipakai notation_style=full_cipher. Pada
# degree_labels ritme datang dari musicxml2ly, sehingga anotasi cukup memasok
# angka. Begitu staf hilang, tidak ada lagi yang tahu ritme kecuali anotasi ini.

# type MusicXML -> (penyebut nilai not, pembilang selalu 1)
NOTE_TYPE_DENOM = {
    "maxima": 1 / 8, "long": 1 / 4, "breve": 1 / 2,
    "whole": 1, "half": 2, "quarter": 4, "eighth": 8,
    "16th": 16, "32nd": 32, "64th": 64, "128th": 128,
    "256th": 256, "512th": 512, "1024th": 1024,
}


def read_lyrics(note):
    """Semua <lyric> pada satu not, satu entri per bait.

    Elision (dua suku kata pada satu not) ditulis MusicXML sebagai beberapa
    <text> yang diselang <elision> DI DALAM satu <lyric>. Anak-anaknya dibaca
    berurutan supaya pemisahnya ikut terbawa: menggabung <text> saja mengubah
    "sih" + "Mu" jadi "sihMu" - PDF-nya sah, liriknya salah cetak, dan tidak ada
    yang error. Isi <elision> adalah karakter pemisah yang diminta partitur;
    kosong berarti spasi.

    <syllabic> yang menentukan tanda hubung adalah yang TERAKHIR: pada elision
    keping terakhirlah yang menyambung ke not berikutnya.
    """
    out = []
    for lyric in note.findall("lyric"):
        parts, syllabic, elision = [], "single", False
        for child in lyric:
            tag = strip_ns(child.tag)
            if tag == "text":
                parts.append(child.text or "")
            elif tag == "elision":
                elision = True
                parts.append((child.text or "").strip() or " ")
            elif tag == "syllabic":
                if child.text and child.text.strip():
                    syllabic = child.text.strip().lower()
        number = lyric.get("number") or lyric.get("name") or "1"
        # <lyric number="verse1"> dipakai sebagian penerbit; ambil digitnya.
        digits = "".join(ch for ch in str(number) if ch.isdigit())
        out.append({
            "verse": int(digits) if digits else 1,
            "text": ("".join(parts)).strip(),
            "syllabic": syllabic,
            "extend": lyric.find("extend") is not None,
            "elision": elision,
        })
    return out


def read_slurs(note):
    """Tipe slur pada not ini: start/stop/continue. Penanda melisma untuk lirik."""
    return [s.get("type") for s in note.findall("./notations/slur") if s.get("type")]


def read_tuplet_bracket(note):
    """'start'/'stop' dari <notations><tuplet>, penanda batas kelompok tuplet.

    <time-modification> hanya menyebut rasionya, jadi tiga triol berurutan tidak
    bisa dibedakan dari satu tuplet sembilan not - dan tercetak sebagai satu
    kurung berangka 3. Batas kelompoknya hanya ada di sini.
    """
    for node in note.findall("./notations/tuplet"):
        kind = node.get("type")
        if kind in ("start", "stop"):
            return kind
    return None


def read_time_modification(note):
    """(actual, normal) dari <time-modification>, atau (None, None)."""
    tm = note.find("time-modification")
    if tm is None:
        return None, None
    return text_int(tm, "actual-notes"), text_int(tm, "normal-notes")


def measure_barlines(root):
    """{(part_id, nomor birama): gaya barline kanan}. Hanya barline non-biasa."""
    styles = {}
    for part in root.findall("./part"):
        pid = part.get("id")
        for measure in part.findall("./measure"):
            number = measure.get("number") or "?"
            for bar in measure.findall("barline"):
                if (bar.get("location") or "right") != "right":
                    continue
                node = bar.find("bar-style")
                repeat = bar.find("repeat")
                if repeat is not None:
                    styles[(pid, number)] = "repeat-" + (repeat.get("direction") or "backward")
                elif node is not None and node.text:
                    styles[(pid, number)] = node.text.strip()
    return styles


class NoteEvent(dict):
    """Satu kejadian not/istirahat dengan posisi musikalnya."""


def iter_note_events(root):
    """Hasilkan NoteEvent berurutan per part, dengan onset dalam divisions.

    Menangani <backup>/<forward> untuk polifoni, <chord/> untuk not serempak,
    serta perubahan <divisions>, <key>, dan <time> di tengah karya.
    """
    names = part_names(root)
    for part in root.findall("./part"):
        pid = part.get("id")
        state = {
            "divisions": 1,
            "fifths": None,
            "mode": "major",
            "beats": 4,
            "beat_type": 4,
        }
        for measure_index, measure in enumerate(part.findall("./measure")):
            number = measure.get("number") or "?"
            implicit = (measure.get("implicit") or "no").lower() == "yes"
            cursor = 0
            last_onset = 0
            for child in measure:
                tag = child.tag
                if tag == "attributes":
                    apply_attributes(child, state)
                elif tag == "backup":
                    cursor -= text_int(child, "duration", 0) or 0
                elif tag == "forward":
                    cursor += text_int(child, "duration", 0) or 0
                elif tag == "note":
                    ev = build_event(child, state, pid, names.get(pid, pid),
                                     number, implicit, cursor, last_onset,
                                     measure_index)
                    yield ev
                    if ev["chord"]:
                        pass  # not serempak: onset sama, kursor tidak maju
                    else:
                        last_onset = cursor
                        cursor += ev["duration"]


def apply_attributes(attrs, state):
    div = text_int(attrs, "divisions")
    if div:
        state["divisions"] = div
    key = attrs.find("key")
    if key is not None:
        fifths = text_int(key, "fifths")
        if fifths is not None:
            state["fifths"] = fifths
        mode = key.find("mode")
        state["mode"] = (mode.text or "major").strip().lower() if mode is not None and mode.text else "major"
    time = attrs.find("time")
    if time is not None:
        beats = time.find("beats")
        beat_type = time.find("beat-type")
        if beats is not None and beats.text:
            # Pembilang majemuk seperti "2+2+3" dijumlahkan, bukan dipotong ke bagian pertama
            state["beats"] = sum(int(p) for p in beats.text.strip().split("+") if p.strip())
        if beat_type is not None and beat_type.text:
            state["beat_type"] = int(beat_type.text.strip())
        if beats is not None and beats.text and beat_type is not None and beat_type.text:
            state["time_text"] = f"{beats.text.strip()}/{beat_type.text.strip()}"
    clef = attrs.find("clef")
    if clef is not None:
        sign = clef.find("sign")
        if sign is not None and sign.text:
            state["clef_sign"] = sign.text.strip().upper()
        oct_ch = clef.find("clef-octave-change")
        if oct_ch is not None and oct_ch.text:
            try:
                state["clef_octave_change"] = int(oct_ch.text.strip())
            except ValueError:
                state["clef_octave_change"] = 0


def build_event(note, state, part_id, part_name, measure, implicit, cursor, last_onset,
                measure_index=0):
    is_chord = note.find("chord") is not None
    is_grace = note.find("grace") is not None
    is_cue = note.find("cue") is not None
    rest_node = note.find("rest")
    is_rest = rest_node is not None
    is_measure_rest = is_rest and (rest_node.get("measure") or "").strip().lower() == "yes"
    duration = 0 if is_grace else (text_int(note, "duration", 0) or 0)

    voice = note.find("voice")
    staff = note.find("staff")
    pitch = note.find("pitch")
    # Bunyi tanpa nada (tepuk tangan, hentak kaki, perkusi tubuh): MusicXML
    # menulisnya <unpitched>, dan display-step/display-octave di dalamnya
    # adalah PENEMPATAN di staf, bukan tinggi nada. Tidak boleh jadi angka.
    unpitched = note.find("unpitched")

    type_node = note.find("type")
    note_type = (type_node.text or "").strip().lower() \
        if type_node is not None and type_node.text else None
    tuplet_actual, tuplet_normal = read_time_modification(note)

    tie_state = None
    ties = {t.get("type") for t in note.findall("tie")}
    ties |= {t.get("type") for t in note.findall("./notations/tied")}
    if "stop" in ties and "start" in ties:
        tie_state = "continue"
    elif "stop" in ties:
        tie_state = "stop"
    elif "start" in ties:
        tie_state = "start"

    ev = NoteEvent({
        "part_id": part_id,
        "part_name": part_name,
        "measure": measure,
        # Posisi birama dalam part. Nomor birama TIDAK unik: bagian berulang
        # memakai ulang nomor, kadang berdampingan. Pengelompokan harus pakai ini.
        "measure_index": measure_index,
        "time_sig": state.get("time_text"),
        "fermata": note.find("./notations/fermata") is not None,
        "implicit_measure": implicit,
        "voice": (voice.text or "1").strip() if voice is not None and voice.text else "1",
        "staff": int(staff.text.strip()) if staff is not None and staff.text else 1,
        "onset": last_onset if is_chord else cursor,
        "duration": duration,
        "divisions": state["divisions"],
        "beats": state["beats"],
        "beat_type": state["beat_type"],
        "fifths": state["fifths"],
        "key_mode": state["mode"],
        "chord": is_chord,
        "grace": is_grace,
        "cue": is_cue,
        "rest": is_rest,
        "measure_rest": is_measure_rest,
        "clef_sign": state.get("clef_sign", "G"),
        "clef_octave_change": state.get("clef_octave_change", 0),
        "unpitched": unpitched is not None and pitch is None,
        "tie_state": tie_state,
        "tuplet": note.find("./time-modification") is not None,
        "has_lyric": note.find("lyric") is not None,
        # --- dipakai full_cipher: ritme dan lirik yang tak dipakai degree_labels
        "note_type": note_type,
        "dots": len(note.findall("dot")),
        "lyrics": read_lyrics(note),
        "slurs": read_slurs(note),
        "tuplet_actual": tuplet_actual,
        "tuplet_normal": tuplet_normal,
        "tuplet_bracket": read_tuplet_bracket(note),
    })

    if pitch is not None:
        step = (pitch.find("step").text or "C").strip().upper()
        alter_node = pitch.find("alter")
        alter = int(float(alter_node.text.strip())) if alter_node is not None and alter_node.text else 0
        octave = text_int(pitch, "octave", 4)
        ev["step"] = step
        ev["alter"] = alter
        ev["octave"] = octave
        ev["pitch_written"] = "%s%d" % (pitch_name(step, alter), octave)
        ev["midi"] = midi_number(step, alter, octave)
    else:
        ev["step"] = ev["alter"] = ev["octave"] = None
        ev["pitch_written"] = None
        ev["midi"] = None
    return ev


# Pemisah nama part gabungan pada partitur rapat: "Sopran/Alto", "Tenor & Bas".
# Tanda hubung sengaja TIDAK dipakai - "Mezzo-Sopran" adalah satu nama.
NAME_SPLIT = re.compile(r"\s*(?:/|&|\+|,|\bdan\b|\band\b)\s*", re.I)


def split_compound(label, count):
    """'Sopran/Alto' + 2 lane -> ['Sopran', 'Alto']. Tidak cocok -> None."""
    if not label or count < 2:
        return None
    pieces = [p.strip() for p in NAME_SPLIT.split(label) if p.strip()]
    return pieces if len(pieces) == count else None


def lane_names(payload):
    """Nama per lane (part_id, staff, voice), urut kemunculan seperti emit_jianpu.

    SATB rapat menaruh dua suara pada satu staf, jadi satu <part> memasok dua
    lane. Nama part-nya pun gabungan ("Sopran/Alto"), dan itulah satu-satunya
    petunjuk suara yang ada di berkas. Kalau jumlah kepingnya sama dengan jumlah
    lane, keping ke-i dipakai untuk lane ke-i.

    Pemetaan itu hanya dipakai bila nada rata-rata lane MENURUN sesuai urutan -
    konvensi MusicXML menaruh suara atas lebih dulu. Kalau tidak, nama tidak
    dipecah dan sebuah catatan review dikeluarkan: label suara yang salah
    percaya diri lebih berbahaya daripada label generik, karena orang akan
    menyanyikan baris yang bukan bagiannya tanpa tahu.

    Balikan: (daftar (lane_key, nama_panjang, nama_pendek), daftar catatan).
    """
    order, by_part = [], {}
    for ev in payload.get("events") or []:
        key = (ev["part_id"], ev["staff"], ev["voice"])
        if key not in by_part:
            order.append(key)
            by_part[key] = []
        if not ev.get("rest") and ev.get("pitch_sounding") is not None:
            by_part[key].append(ev["pitch_sounding"])

    parts = {p["id"]: p for p in payload.get("parts") or []}
    lanes_of = {}
    for key in order:
        lanes_of.setdefault(key[0], []).append(key)

    out, notes = [], []
    for part_id, keys in lanes_of.items():
        info = parts.get(part_id) or {}
        full = info.get("name") or part_id
        abbrev = info.get("abbreviation")
        if len(keys) == 1:
            out.append((keys[0], full, abbrev or full))
            continue
        longs = split_compound(full, len(keys))
        if longs:
            means = [sum(by_part[k]) / len(by_part[k]) if by_part[k] else None
                     for k in keys]
            known = [m for m in means if m is not None]
            if len(known) == len(means) and any(
                    a <= b for a, b in zip(known, known[1:])):
                notes.append(
                    "part %s: nama '%s' tidak dipecah - suara pertama tidak lebih "
                    "tinggi dari suara berikutnya, jadi urutan namanya tidak bisa "
                    "dipastikan" % (full, full))
                longs = None
        shorts = split_compound(abbrev, len(keys)) if longs else None
        for index, key in enumerate(keys):
            if longs:
                out.append((key, longs[index], (shorts or longs)[index]))
            else:
                label = "%s %d" % (full, index + 1)
                out.append((key, label, label))
    ordinal = {key: i for i, key in enumerate(order)}
    out.sort(key=lambda row: ordinal[row[0]])
    return out, notes


def measure_capacity(divisions, beats, beat_type):
    """Panjang satu birama penuh dalam divisions."""
    return divisions * 4 * beats / beat_type


def fail(message):
    sys.stderr.write("batik-partitur: %s\n" % message)
    raise SystemExit(2)


def write_json(path, payload):
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
