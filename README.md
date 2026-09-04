# OpenJianpu

[![CI](https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml/badge.svg)](https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Tests: 60+ Passed](https://img.shields.io/badge/tests-60%2B%20passed-brightgreen.svg)](tests/)
[![Language: Indonesian](https://img.shields.io/badge/docs-Bahasa%20Indonesia-green.svg)](README.id.md)

**OpenJianpu** is a high-performance, standalone vector typesetting engine and converter that transforms **MusicXML** and Western sheet music directly into publication-grade **Numbered Musical Notation** (*Jianpu / 简谱 / Not Angka*).

Designed specifically for choral ensembles (SATB), vocal arrangements, and liturgical hymnals (*Puji Syukur, Madah Bakti, Kidung Jemaat, lagumisa.web.id*), OpenJianpu produces crisp, typography-grade vector PDFs in milliseconds—**completely independent of LilyPond, MuseScore, or JVM runtimes**.

---

## 📖 Table of Contents
- [Why OpenJianpu?](#-why-openjianpu)
- [Key Engineering Innovations](#-key-engineering-innovations)
- [Pipeline Architecture](#-pipeline-architecture)
- [Installation](#-installation)
- [CLI Reference & Usage](#-cli-reference--usage)
  - [1. Direct Conversion (`convert`)](#1-convert-musicxml-to-pdf)
  - [2. Rhythmic Beat Auditing (`check`)](#2-audit-rhythm-and-meter-consistency)
  - [3. Intermediate JSON Pipeline (`xml2json` & `render`)](#3-two-way-json-interchange)
  - [4. External Lyric Alignment (`--lyrics-file`)](#4-external-lyric-alignment---lyrics-file)
- [Notation Conventions & Specimen Standards](#-notation-conventions--standards)
- [Python API](#-python-api)
- [Corpus Benchmark & Verification](#-corpus-benchmark--verification)
- [License](#-license)

---

## 💡 Why OpenJianpu?

Numbered musical notation (1 to 7 corresponding to movable-Do scale degrees) is sung and read by hundreds of millions of choristers, vocalists, and students across Southeast Asia (Indonesia), East Asia (China, Taiwan), and global choral institutions.

However, modern notation software (Sibelius, Finale, Dorico, MuseScore) fundamentally treats sheet music through Western five-line staves. Past attempts to automate conversion have suffered from critical flaws:
1. **Heavy Toolchain Bloat**: Preprocessors like `jianpu-ly` rely on full GNU LilyPond installations, requiring 10–30 seconds per score and consuming hundreds of megabytes of disk space.
2. **Choral Voice Collapse**: Most converters fail on standard choral scores where 4 voices (SATB) are condensed into two closed staves (Soprano/Alto on treble, Tenor/Bass on bass), merging voices into unreadable chords or losing voice identities.
3. **Silent Corruption on OMR**: MusicXML scanned from OMR tools (Audiveris, SmartScore) frequently contains rhythm defects (dust specks read as dots, phantom rests, unbracketed triplets). Naive converters silently corrupt durations or break barlines.
4. **Mangled Lyric Hyphenation**: Multi-syllable lyrics in Asian and Western languages lose their hyphenation or stick together without word spaces.

**OpenJianpu was built to solve these challenges with mathematical rigor**:
- **0.4s compilation** per score directly via pure Python and PyCairo vector primitives.
- **Zero silent corruption**: Rhythm is mathematically audited against time signatures; unambiguous defects are deterministically fixed, and remaining source errors are transparently flagged on the printed PDF (`! m27`).
- **PUEBI & Multilingual linguistic rules**: Intelligent syllable hyphenation and sticky-word splitting.

---

## 🚀 Key Engineering Innovations

### 1. Standalone Vector Engraving Engine (PyCairo)
- **Zero LilyPond / LaTeX dependencies**: Renders directly to vector PDF using high-precision Cairo paths.
- **Dynamic Collision Avoidance**: Multi-pass lyric layout with elastic font scaling (from 9.5pt down to 6.5pt) to ensure syllables never overlap or breach measure boundaries.
- **Publication Ornaments**: Native rendering of octave dots (above/below numerals), accidental slashes, duration beams, curved melisma ties, dynamic hairpins (`cresc.`, `dim.`), fermatas, repeat barlines, and numbered voltas (kamar 1 & 2).

### 2. Intelligent SATB Choral Routing & Divisi Splitting
- **Closed Score Separation**: Automatically identifies two-stave choral setups and routes voices into independent Soprano, Alto, Tenor, and Bass lines based on staff clefs, note pitch medians, and voice numbers.
- **Divisi Detection**: Voices containing polyphonic chords on $\ge 20\%$ of measures are automatically factored into distinct split parts (e.g. S1/S2 or S/A).
- **Accidental Chord Parsing**: Occasional chord clusters take the lowest pitch for Basses and highest pitch for upper voices, correctly inheriting root note durations.

### 3. Metric Engine & Single Source of Truth (`meter.py`)
- **Strict Metric Grouping**: Sukat and time signatures dictate exact beam partitions (e.g., $7/8 = 2+2+3$, $9/8 = 3+3+3$, $6/8 = 3+3$).
- **Sub-Beat Beamed Extension Dots & Rests**: Dots and rests belonging to fractional sub-beats are grouped under beams (e.g. `3 .̅ 3̅` or `0̅ 3̅`), adhering to authentic hymnal printing conventions (*Puji Syukur 347b & 390b*).
- **Compound Meter Support**: Default `--beat-unit quarter` groups 6/8 into 2 compound dotted-quarter beats ($\overline{1\ 2\ 3}\ \overline{4\ 5\ 6}$), while `--beat-unit denominator` serves slow 6-beat adagio measures.

### 4. Deterministic Error Recovery & Visual Diagnostic
When processing MusicXML from OCR/OMR, OpenJianpu applies strict, non-speculative repairs:
- **Trailing Phantom Rests**: Automatically prunes unvoiced rests at the end of a measure if and only if removing them exactly equals the meter's capacity.
- **Unbracketed 1/8 Triplets**: Automatically recovers triplets when 3 consecutive eighth notes exceed the measure by exactly 1 eighth note and the candidate group is unique.
- **Transparent Barline Warning (`! m<n>`)**: If source notes remain rhythmically overflowing, OpenJianpu **refuses to guess or alter pitches**. Instead, it renders the score gracefully and imprints a clear diagnostic flag `! m27` above the barline, alerting choir directors during rehearsals.

### 5. PUEBI & Multilingual Syllable Engine
- **Grammar-Aware Syllabification**: Integrates formal Indonesian orthography rules (PUEBI: `V-V`, `V-KV`, `VK-KV`, `VK-KKV` with inseparable digraphs `ng`, `ny`, `sy`, `kh`, `gh`).
- **OMR Sticky-Word Repair (`tambal_lirik.py`)**: Uses vacant notes as exact arithmetic verifiers to redistribute merged words without guessing (99.1% precision).
- **CamelCase Boundary Splitting**: Automatically unglues concatenated text like `keHadiratMu` $\rightarrow$ `ke Hadirat-Mu` and `padaNya` $\rightarrow$ `pada-Nya`.

---

## 🛠️ Pipeline Architecture

```
                                 ┌────────────────────────────────┐
                                 │   MusicXML / MXL / Sheet PDF   │
                                 └───────────────┬────────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │   xml_parser & degreelib     │
                                  │   - Movable-Do Pitch Mapper  │
                                  │   - Closed-Score SATB Router │
                                  │   - Divisi Chord Extractor   │
                                  └──────────────┬───────────────┘
                                                 │
                        ┌────────────────────────┴────────────────────────┐
                        ▼                                                 ▼
         ┌──────────────────────────────┐                  ┌──────────────────────────────┐
         │     Rhythm & Meter Audit     │                  │   PUEBI Syllable Engine      │
         │   - Phantom Rest Pruning     │                  │   - Sticky Word Splitting    │
         │   - Unbracketed Triplet Fix  │                  │   - CamelCase Boundary Fix   │
         │   - Barline Flagging (! mX)  │                  │   - Optional --lyrics-file   │
         └──────────────┬───────────────┘                  └──────────────┬───────────────┘
                        │                                                 │
                        └────────────────────────┬────────────────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │   NotAngkaScore JSON Model   │
                                  └──────────────┬───────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │    PyCairo Vector Engine     │
                                  │   - Layout & System Break    │
                                  │   - Anti-Collision Lyrics    │
                                  │   - Beams, Ties, Ornaments   │
                                  └──────────────┬───────────────┘
                                                 │
                                                 ▼
                                  ┌──────────────────────────────┐
                                  │  Publication-Grade PDF       │
                                  └──────────────────────────────┘
```

---

## 📦 Installation

### 1. Prerequisites
OpenJianpu requires the `cairo` graphics library and standard Liberation fonts:

- **Ubuntu / Debian**:
  ```bash
  sudo apt-get update
  sudo apt-get install -y libcairo2-dev pkg-config fonts-liberation
  ```
- **Fedora / RHEL**:
  ```bash
  sudo dnf install cairo-devel pkgconf-pkg-config liberation-sans-fonts
  ```
- **macOS** (Homebrew):
  ```bash
  brew install cairo pkg-config
  ```
- **Windows**:
  Standard wheels for `pycairo` are automatically provided by `pip`.

### 2. Install OpenJianpu
Clone the repository and install in editable/development or standard mode:
```bash
git clone https://github.com/Alvnvnc/OpenJianpu.git
cd OpenJianpu
pip install .
```

To install development dependencies (for running tests):
```bash
pip install .[dev]
```

---

## 💻 CLI Reference & Usage

OpenJianpu provides the `openjianpu` CLI (with `notangka` available as an identical alias).

### 1. Convert MusicXML to PDF
Convert any standard `.musicxml`, `.xml`, or compressed `.mxl` score:
```bash
openjianpu convert hymn.musicxml -o hymn_numbered.pdf
```

#### Key Options:
| Flag | Description | Default |
|---|---|---|
| `-o, --output` | Target PDF file path | `<input>_notangka.pdf` |
| `--title` | Override score title | Extracted from MusicXML |
| `--composer` | Override composer name | Extracted from MusicXML |
| `--lyricist` | Override lyricist/poet name | Extracted from MusicXML |
| `--beat-unit` | Beat unit policy: `quarter` or `denominator` | `quarter` |
| `--lyrics-file` | Path to clean external text file to map lyrics | `None` |
| `--no-tambal-lirik` | Disable automatic PUEBI sticky-word splitting | `False` (enabled) |
| `--save-json` | Also save the intermediate JSON schema | `None` |

### 2. Audit Rhythm and Meter Consistency
Inspect whether measure note sums match time signature capacities:
```bash
openjianpu check hymn.musicxml -v
```
*Sample Output:*
```text
Sukat awal 4/4, satuan ketuk: quarter
m1    4/4      kap 4     penuh
m2    4/4      kap 4     LEBIH S=4.5; tak baku S:1@4/0.5
Ringkasan: 2 birama · 8 suara-birama · 7 penuh · 0 kurang · 1 LEBIH · 1 simbol tak baku
Status: GAGAL (ada birama meluap atau simbol tak baku)
```

### 3. Two-Way JSON Interchange
You can decouple score extraction from PDF rendering. This allows manual editing or programmatic score transformations:
```bash
# Step 1: Extract MusicXML to human-readable JSON
openjianpu xml2json hymn.musicxml -o hymn.json

# Step 2: Edit hymn.json if needed, then render
openjianpu render hymn.json -o hymn_final.pdf
```

### 4. External Lyric Alignment (`--lyrics-file`)
If the source MusicXML has severely mangled lyrics, provide a clean text file (`syair.txt`):
```text
# General line applies to all vocal parts
Ha-le-lu-ya, pu-ji-lah Tu-han

# Voice-specific lines:
S: Kha-las dan mu-li-a
A 2: Bait ke-dua khu-sus al-to

# Special tokens:
# '_' is a melisma (note without a syllable)
# '|' is an optional visual barline divider
```
Then run:
```bash
openjianpu convert hymn.musicxml --lyrics-file syair.txt -o hymn.pdf
```

---

## 🎼 Notation Conventions & Standards

OpenJianpu adheres to international *Jianpu* guidelines and Indonesian liturgical standards (*PML Yogyakarta, Yamuger, lagumisa.web.id*):

| Element | Engraving Style | Description |
|---|---|---|
| **Pitches** | `1 2 3 4 5 6 7` | Scale degrees relative to key tonic ($1 = \text{Do}$) |
| **Rest** | `0` | Silent pause; sub-beat rests take beams (`0̅`) |
| **Octave Shift** | `1̇` / `1̣` | Dots placed vertically above (high) or below (low) |
| **Accidentals** | `1/` (kres), `7\` (mol) | Diagonal slash through numeral indicating chromatic alteration |
| **Duration Dots** | `1 .` / `3 .̅` | Prolongation dots; sub-beat dots inherit beam lines |
| **Beams** | $\overline{1\ 2}$, $\overline{\overline{1\ 2}}$ | Horizontal lines above numerals denoting eighth and sixteenth notes |
| **Compound 6/8** | $\overline{1\ 2\ 3}\quad \overline{4\ 5\ 6}$ | Grouped in 3-eighth bundles (2 compound beats per measure) |
| **Defective Flag** | `! m27` | Red/amber indicator above barline when measure durations overflow |

---

## 🐍 Python API

Integrate OpenJianpu directly into your Python pipelines or web applications:

```python
from openjianpu import (
    parse_musicxml_to_score,
    NotAngkaRenderer,
    check_score,
    apply_lyrics_file
)

# 1. Parse MusicXML to intermediate score model
score = parse_musicxml_to_score("anthem.musicxml", beat_unit="quarter")

# 2. Optionally apply clean lyrics
# apply_lyrics_file(score, "clean_lyrics.txt")

# 3. Perform rhythm and metric audit
report = check_score(score)
print(f"Measures: {len(score.measures)}, Overflows: {report.n_over}")

# 4. Render to vector PDF
renderer = NotAngkaRenderer(score, "anthem_notangka.pdf")
renderer.render()
print("Successfully generated vector PDF.")
```

---

## 📊 Corpus Benchmark & Verification

OpenJianpu was hardened against an extensive empirical dataset:
- **259 real-world choral MusicXML scores** parsed and engraved with **0 crashes / tracebacks**.
- **67 automated regression tests** covering accidentals, cross-measure voice routing, pickup measures (anacrusis), tuplets, and font scaling.
- **Rhythm Recovery Audit**: In a benchmark of 1,075 overflowing voice-measures from OCR:
  - **123 phantom rests** safely eliminated.
  - **59 unbracketed triplets** unambiguously restored.
  - **93 net reduction in overflow defects** without altering a single sung note.

---

## 🤝 Contributing

Contributions from the global music technology, choral, and open-source communities are warmly welcomed!
1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.

Developed by **Alvin Vincent** & the open-source choral community.
