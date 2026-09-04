# OpenJianpu

[![CI](https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml/badge.svg)](https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Language: Indonesian](https://img.shields.io/badge/lang-Bahasa%20Indonesia-green.svg)](README.id.md)

**OpenJianpu** is a high-performance, standalone vector engine that converts **MusicXML** and Western sheet music directly into publication-grade **Numbered Musical Notation** (*Jianpu / 简谱 / Not Angka*). 

Engineered specifically for vocal, choral (SATB), and liturgical arrangements, OpenJianpu renders sharp vector PDFs using PyCairo in milliseconds—**completely independent of LilyPond**.

---

## Highlights

- **⚡ Standalone Vector Engraving**: Pure Python + PyCairo vector rendering engine. Sub-second conversion time (<0.5s per score) producing publication-quality vector PDFs.
- **🎼 Full Choral & SATB Support**: Automatic system breaking, voice separation (Soprano, Alto, Tenor, Bass), closed/open score staff splitting, and polyphonic chord division.
- **⏱️ Deterministic Meter & Beat Auditing**:
  - Comprehensive time signature engine supporting simple (2/4, 3/4, 4/4) and compound meters (6/8, 9/8, 12/8).
  - High-confidence deterministic error recovery: automatically prunes trailing phantom rests and restores unambiguous unbracketed 1/8 triplets.
  - Safe failure policy: defective measures with overflow durations are explicitly flagged (`! m27`) in the output PDF to prevent silent corruption during rehearsals.
- **📝 Intelligent Multilingual & PUEBI Lyric Engine**:
  - Automatic OMR sticky-syllable repair based on syllable counting and PUEBI rules.
  - Orthographic boundary splitting for camelCase concatenations (e.g. `keHadiratMu` → `ke Hadirat-Mu`).
  - `--lyrics-file` option: align clean lyrics syllable-by-syllable to singing notes.
- **🔍 Two-Way JSON Interchange**: Seamlessly export scores to an intermediate JSON format (`openjianpu xml2json`) and render back to PDF (`openjianpu render`), enabling programmatic and web editor integrations.

---

## Installation

### 1. System Dependencies
OpenJianpu requires the `cairo` graphics library and standard Liberation fonts:

- **Ubuntu / Debian**:
  ```bash
  sudo apt-get update
  sudo apt-get install -y libcairo2-dev pkg-config fonts-liberation
  ```
- **macOS** (Homebrew):
  ```bash
  brew install cairo pkg-config
  ```
- **Windows**:
  Pre-built wheels for `pycairo` are automatically installed via `pip`.

### 2. Python Package
Install directly from GitHub or source:
```bash
git clone https://github.com/Alvnvnc/OpenJianpu.git
cd OpenJianpu
pip install .
```

*(PyPI release coming soon: `pip install openjianpu`)*

---

## Quick Start (CLI)

OpenJianpu provides a unified command-line tool `openjianpu` (with `notangka` available as an alias):

### 1. Convert MusicXML to Numbered Notation PDF
```bash
openjianpu convert score.musicxml -o score_notangka.pdf
```
*Options:*
- `--save-json score.json`: Save intermediate JSON schema.
- `--title "Custom Title"`: Override score title.
- `--lyrics-file lyrics.txt`: Apply clean external lyric text.
- `--beat-unit {quarter,denominator}`: Select beat unit policy (default: `quarter`).

### 2. Audit Rhythm & Time Signatures
Inspect measure capacity and check for overflowing or defective notes:
```bash
openjianpu check score.musicxml -v
```

### 3. Intermediate JSON Pipeline
```bash
# Extract MusicXML to clean JSON
openjianpu xml2json score.musicxml -o score.json

# Render JSON to vector PDF
openjianpu render score.json -o output.pdf
```

---

## Notation Conventions

OpenJianpu adheres to international *Jianpu* principles and Indonesian choral standards (*PML Yogyakarta, Yamuger, lagumisa.web.id*):

| Element | Representation | Description |
|---|---|---|
| **Pitches** | `1 2 3 4 5 6 7` | Movable-Do scale degrees (Do, Re, Mi, Fa, Sol, La, Si) |
| **Rests** | `0` | Silent beats / pauses |
| **Octaves** | `1̇` (dot above), `1̣` (dot below) | Dots positioned precisely above/below numerals |
| **Duration Beams** | $\overline{1\ 2}$, $\overline{\overline{1\ 2}}$ | Horizontal beams denoting eighth (1/8) and sixteenth (1/16) notes |
| **Compound Meter (6/8)** | $\overline{1\ 2\ 3}\quad \overline{4\ 5\ 6}$ | Grouped in 3-eighth bundles (2 compound beats per measure) |
| **Defective Measures** | `! m27` | Visual diagnostic callout placed on barline when source data overflows |

---

## Python API

You can also use OpenJianpu as a Python library:

```python
from openjianpu import parse_musicxml_to_score, NotAngkaRenderer, check_score

# 1. Parse MusicXML
score = parse_musicxml_to_score("hymn.musicxml")

# 2. Audit rhythm
report = check_score(score)
if not report.ok:
    print(f"Warning: {report.n_over} overflowing measures detected.")

# 3. Render directly to vector PDF
renderer = NotAngkaRenderer(score, "output.pdf")
renderer.render()
```

---

## Architecture

```
OpenJianpu/
├── src/openjianpu/
│   ├── schema.py        # Abstract score data model (JSON-serializable)
│   ├── meter.py         # Time signature, metric grouping & compound beats
│   ├── degreelib.py     # Chromatic scale degree mapping & key transpositions
│   ├── layout.py        # System block distribution and automatic breaking
│   ├── xml_parser.py    # MusicXML parsing, voice routing & error repair
│   ├── lyrics.py        # Syllable alignment and custom text injection
│   ├── silabel.py       # PUEBI-compliant Indonesian syllable hyphenation
│   ├── tambal_lirik.py  # OMR glued-word recovery
│   ├── renderer.py      # PyCairo vector PDF typesetting engine
│   ├── checker.py       # Beat auditing and validation diagnostic
│   └── cli.py           # Command-line interface
└── tests/
    └── test_cli.py      # Regression & unit test suite (60+ tests)
```

---

## Testing

Run the test suite with `pytest`:
```bash
pytest
```

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

Developed with passion by **Alvin Vincent** and the open-source choral community.
