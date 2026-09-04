# OpenJianpu Examples

This directory contains minimal, verified sample files to demonstrate OpenJianpu capabilities.

## Files
- `sample_chorus.musicxml`: A 4-part SATB chorus piece in 4/4 meter (key of F major / `Do=F`) with lyrics.
- `sample_lyrics.txt`: A sample external lyrics file demonstrating syllable mapping, voice isolation (`S:`, `A:`), and melisma syntax (`_`).

## Quick Run

Convert the sample score directly into a vector PDF:
```bash
openjianpu convert sample_chorus.musicxml -o sample_chorus.pdf
```

Audit the meter and rhythmic consistency:
```bash
openjianpu check sample_chorus.musicxml -v
```

Extract the structured intermediate JSON:
```bash
openjianpu xml2json sample_chorus.musicxml -o sample_chorus.json
```
