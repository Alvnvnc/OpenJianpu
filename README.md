<p align="center">
  <h1 align="center">OpenJianpu</h1>
  <p align="center"><b>The open-source, high-performance vector typesetting engine for Numbered Musical Notation (Jianpu / 简谱 / Not Angka).</b></p>
</p>

<p align="center">
  <a href="https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml"><img alt="CI Build" src="https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <a href="https://www.python.org/"><img alt="Python: 3.9+" src="https://img.shields.io/badge/python-3.9+-blue.svg"></a>
  <a href="tests/"><img alt="Tests" src="https://img.shields.io/badge/tests-60%2B%20passed-brightgreen.svg"></a>
  <a href="https://github.com/Alvnvnc/OpenJianpu/releases"><img alt="Release" src="https://img.shields.io/badge/release-v0.1.0-orange.svg"></a>
</p>

<p align="center">
  <b>English</b> |
  <a href="README.id.md">Bahasa Indonesia</a>
</p>

```
  Western Sheet Music / MusicXML                        OpenJianpu Vector PDF
 ┌──────────────────────────────┐                      ┌──────────────────────────────┐
 │   𝄞 4 𝅘𝅥   𝅘𝅥   𝅗𝅥            │      OpenJianpu      │   1=F  4/4                   │
 │     4 ♩   ♩   𝅗              │   ───────────────►   │   | 1   3   5   . |          │
 │       Hal-le - lu            │     (< 0.5 sec)      │     Hal-le - lu    -         │
 └──────────────────────────────┘                      └──────────────────────────────┘
```

**OpenJianpu** converts **MusicXML**, compressed `.mxl`, and Western sheet music directly into publication-grade **Numbered Musical Notation** (*Jianpu / Not Angka*). 

Engineered specifically for SATB choirs, vocal ensembles, and church hymnals, OpenJianpu renders crisp, vector PDFs in sub-second time using PyCairo—**completely independent of GNU LilyPond, MuseScore, or JVM runtimes**.

---

## ⚡ Quick Start

### Installation

```bash
# System dependencies (Ubuntu / Debian)
sudo apt-get update && sudo apt-get install -y libcairo2-dev pkg-config fonts-liberation

# macOS (Homebrew)
brew install cairo pkg-config

# Install OpenJianpu
pip install git+https://github.com/Alvnvnc/OpenJianpu.git
```

### 1-Line Usage

```bash
# Convert any MusicXML score directly to a vector PDF
openjianpu convert score.musicxml -o output.pdf

# Audit rhythm, metric capacity, and barline consistency
openjianpu check score.musicxml -v
```

---

## 🎯 Why OpenJianpu?

Numbered musical notation (where digits `1` through `7` represent movable-Do scale degrees) is the primary musical language for hundreds of millions of singers across Asia (China, Taiwan, Indonesia, Singapore) and global vocal ensembles.

However, Western engraving suites (Sibelius, Finale, Dorico, MuseScore) fundamentally treat notation through five-line staves. Previous automated converters suffered from critical barriers:

1. **Heavy Toolchain Overhead**: Tools like `jianpu-ly` require a full GNU LilyPond environment, consuming hundreds of megabytes and taking 15–30 seconds per compile.
2. **Choral Voice Collapse**: Conventional converters fail when 4 choral voices (SATB) are condensed into two closed staves (Treble: Soprano/Alto, Bass: Tenor/Bass), merging lines into unreadable chords or losing vocal assignments.
3. **Silent Rhythmic Corruption**: MusicXML originating from Optical Music Recognition (OMR) frequently contains scanning artifacts (dust specks recognized as dots, missing tuplet brackets, phantom rests). Guessing notes blindly leads to silent corruption during choir rehearsals.
4. **Mangled Lyrics**: Syllables from non-English or hyphenated texts frequently lose syllable boundaries or stick together without word spaces.

**OpenJianpu solves all four problems through purpose-built engineering**:
- **Blazing Fast**: Compiles in **< 0.5s** per score via pure Python and PyCairo vector geometry.
- **Zero Silent Corruption**: Strict metric auditing against time signatures. Deterministic fixes are applied only when mathematically unambiguous; remaining defects are visually flagged (`! m27`) on the printed PDF.
- **Smart Closed-Score Routing**: Automatically splits 2-staff SATB hymns into 4 independent vocal lines.
- **Linguistic Syllable Alignment**: Built-in grammar-based syllable hyphenation and sticky-word splitting.

---

## ✨ Features

- **🚀 Standalone Vector Typesetting**: Direct-to-PDF vector output without LilyPond, LaTeX, or external typesetting binaries.
- **👥 Automatic SATB Choral Routing**:
  - Automatically splits 2-stave choral scores into independent Soprano, Alto, Tenor, and Bass systems.
  - Detects divisi chords ($\ge 20\%$ of measures) and splits them into separate parallel voices (S1/S2 or S/A).
  - Handles occasional chords cleanly (assigning lowest pitch to Bass and highest to upper voices).
- **⏱️ Deterministic Rhythmic Engine (`meter.py`)**:
  - Strict metric grouping for simple (2/4, 3/4, 4/4, 2/2) and compound meters (6/8, 9/8, 12/8, 7/8).
  - Beamed sub-beat prolongation dots and rests (e.g. `3 .̅ 3̅` and `0̅ 3̅`), adhering to printed hymnal standards.
  - Dual 6/8 meter policies: `--beat-unit quarter` (2 compound dotted-quarter beats: $\overline{1\ 2\ 3}\ \overline{4\ 5\ 6}$) or `--beat-unit denominator` (6 simple beats).
- **🛡️ Safe Error Recovery & Visual Barline Diagnostics**:
  - Automatically prunes trailing phantom rests when removing them makes measure duration exactly equal capacity.
  - Automatically restores unambiguous unbracketed 1/8 triplets.
  - Displays a diagnostic flag `! m<number>` above the barline for uncorrected source errors instead of silently guessing pitches.
- **📝 Intelligent Syllable Engine**:
  - Syllabification engine handling multi-syllable word division and digraph preservation (`ng`, `ny`, `sy`, `kh`).
  - Automatic CamelCase splitting (`praiseTheLord` → `praise The Lord`).
  - Custom lyric override via `--lyrics-file` with melisma support (`_`).
- **🔄 Two-Way JSON Architecture**:
  - Decouple parsing and rendering: export MusicXML to a clean JSON schema (`xml2json`), inspect or edit, and render back to PDF (`render`).

---

## 💻 CLI Reference

OpenJianpu provides the `openjianpu` command (with `notangka` available as an identical alias).

```
usage: openjianpu [-h] [--version] {convert,check,xml2json,render} ...
```

### 1. `convert` — MusicXML to Numbered Notation PDF
```bash
openjianpu convert input.musicxml -o output.pdf [OPTIONS]
```

| Option | Description | Default |
|---|---|---|
| `-o, --output` | Output PDF file path | `<input>_notangka.pdf` |
| `--title` | Override score title | Extracted from MusicXML |
| `--composer` | Override composer name | Extracted from MusicXML |
| `--arranger` | Override arranger name | Extracted from MusicXML |
| `--lyricist` | Override lyricist name | Extracted from MusicXML |
| `--subtitle` | Custom subtitle | Extracted from MusicXML |
| `--beat-unit` | Beat unit policy: `quarter` or `denominator` | `quarter` |
| `--lyrics-file` | Path to clean external lyric file | `None` |
| `--no-tambal-lirik` | Disable automatic sticky-syllable splitting | `False` (enabled) |
| `--save-json` | Save intermediate JSON schema | `None` |

### 2. `check` — Rhythmic & Metric Consistency Audit
Audit note durations against measure capacity across all vocal lines:
```bash
openjianpu check input.musicxml -v
```

*Example Audit Output:*
```text
Initial meter: 4/4, beat unit: quarter
m1    4/4      cap 4.0   full
m2    4/4      cap 4.0   OVERFLOW S=4.5; non-standard S:1@4/0.5
Summary: 2 measures · 8 voice-measures · 7 full · 0 under · 1 OVERFLOW
Status: FAILED (overflowing measures or non-standard symbols detected)
```

### 3. `xml2json` — Extract to Structured JSON
```bash
openjianpu xml2json input.musicxml -o score.json
```

### 4. `render` — Render JSON to Vector PDF
```bash
openjianpu render score.json -o score.pdf
```

---

## 🎼 Notation Reference & Standards

| Musical Element | Visual Output | Description |
|---|---|---|
| **Pitches** | `1 2 3 4 5 6 7` | Scale degrees relative to key tonic ($1 = \text{Do}$) |
| **Rest** | `0` | Silent beat; sub-beat rests take beams (`0̅`) |
| **Octave Shift** | `1̇` / `1̣` | Dots placed vertically above (higher octave) or below (lower octave) |
| **Accidentals** | `1/` (sharp), `7\` (flat) | Diagonal slash through numeral indicating chromatic semitone shift |
| **Duration Dots** | `1 .` / `3 .̅` | Prolongation dot; sub-beat dots inherit beam lines |
| **Beams** | $\overline{1\ 2}$, $\overline{\overline{1\ 2}}$ | Horizontal lines above numerals denoting eighth and sixteenth notes |
| **Compound 6/8** | $\overline{1\ 2\ 3}\quad \overline{4\ 5\ 6}$ | Grouped in 3-eighth bundles (2 compound beats per measure) |
| **Repeat Barlines** | `|:   :|` | Standard forward and backward section repeat signs |
| **Voltas** | `┌ 1. ──┐  ┌ 2. ──┐` | 1st and 2nd alternate endings |
| **Melisma** | `(1  2)` | Curved slurs connecting notes sung on a single syllable |
| **Defective Flag** | `! m27` | Diagnostic indicator printed above barline on overflowing measures |

---

## 📝 Custom Lyric File Syntax (`--lyrics-file`)

When processing damaged OMR files with broken text, provide a clean text file (`lyrics.txt`):

```text
# Lines without prefixes apply to all singing voices:
Hal-le-lu-jah, praise the Lord on high

# Voice-specific prefixes:
S: On-ly so-pran-os sing this line
2: Se-cond verse text goes here
A 2: Al-to on-ly for verse two

# Special tokens:
# '_' marks a melisma (note without a syllable)
# '|' is an optional barline separator
```

Apply it during conversion:
```bash
openjianpu convert score.musicxml --lyrics-file lyrics.txt -o score.pdf
```

---

## 🐍 Python API

Integrate OpenJianpu into custom Python applications, web services, or music pipelines:

```python
from openjianpu import (
    parse_musicxml_to_score,
    NotAngkaRenderer,
    check_score,
)

# 1. Parse MusicXML into the intermediate score model
score = parse_musicxml_to_score("anthem.musicxml", beat_unit="quarter")

# 2. Audit rhythmic consistency
report = check_score(score)
if not report.ok:
    print(f"Audit warning: {report.n_over} overflowing measures detected.")

# 3. Render directly to vector PDF
renderer = NotAngkaRenderer(score, "anthem_numbered.pdf")
renderer.render()
print("Generated publication-ready vector PDF.")
```

---

## 📊 Corpus Benchmark & Verification

OpenJianpu has been validated against an empirical choral dataset:
- **259 real-world choral MusicXML scores** parsed and typeset with **0 crashes / tracebacks**.
- **60+ regression tests** covering accidentals, cross-measure voice routing, pickup measures (anacrusis), tuplets, and font scaling.
- **Rhythm Recovery Benchmark** (on 1,075 overflowing voice-measures from OCR):
  - **123 phantom rests** safely eliminated.
  - **59 unbracketed triplets** unambiguously restored.
  - **93 net reduction in overflow defects** without altering a single sung note.

---

## 🤝 Contributing

Contributions from the international music technology and choral communities are welcome!
1. Fork the repository (`https://github.com/Alvnvnc/OpenJianpu/fork`).
2. Create your feature branch (`git checkout -b feature/NewFeature`).
3. Commit your changes (`git commit -m 'feat: Add NewFeature'`).
4. Push to the branch (`git push origin feature/NewFeature`).
5. Open a Pull Request.

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

Developed with passion by **Alvin Vincent** and the open-source choral community.
