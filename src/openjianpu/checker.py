"""
Pemeriksa ketukan (beat audit) untuk NotAngkaScore.

Menjawab pertanyaan "apakah pembacaan ketukan partitur ini benar?" secara terukur:
* tiap pasangan (birama, suara) dijumlahkan durasinya dan dibandingkan dengan
  kapasitas birama menurut sukat (atau kapasitas nyata birama gantung);
* simbol sub-ketuk yang tidak dapat diwakili nilai not biner ditandai "tak baku";
* pergantian sukat dan birama gantung dilaporkan agar mudah dicek mata.

Dipakai oleh ``notangka_cli.py check`` dan oleh uji otomatis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .schema import NotAngkaScore, Measure
from .meter import parse_meter, POLICY_QUARTER, EPS

TOL = 0.03
_STANDARD_LENGTHS = (1.0, 0.75, 0.5, 0.375, 0.25, 0.1875, 0.125)


@dataclass
class VoiceFill:
    voice: str
    total: float
    capacity: float

    @property
    def status(self) -> str:
        if self.total > self.capacity + TOL:
            return "lebih"
        if self.total < self.capacity - TOL:
            return "kurang"
        return "penuh"


@dataclass
class MeasureAudit:
    number: int
    time_signature: str
    capacity: float
    is_partial: bool
    fills: List[VoiceFill] = field(default_factory=list)
    nonstandard: List[str] = field(default_factory=list)  # deskripsi simbol tak baku

    @property
    def over(self) -> List[VoiceFill]:
        return [f for f in self.fills if f.status == "lebih"]

    @property
    def under(self) -> List[VoiceFill]:
        return [f for f in self.fills if f.status == "kurang"]


@dataclass
class CheckReport:
    beat_unit: str
    initial_time_signature: str
    measures: List[MeasureAudit] = field(default_factory=list)
    meter_changes: List[str] = field(default_factory=list)   # "m3 7/8"
    repairs: List[str] = field(default_factory=list)
    partial_measures: List[str] = field(default_factory=list)  # "m0 (kap 1.0)"

    @property
    def voice_measures(self) -> int:
        return sum(len(m.fills) for m in self.measures)

    @property
    def n_full(self) -> int:
        return sum(1 for m in self.measures for f in m.fills if f.status == "penuh")

    @property
    def n_over(self) -> int:
        return sum(len(m.over) for m in self.measures)

    @property
    def n_under(self) -> int:
        return sum(len(m.under) for m in self.measures)

    @property
    def n_nonstandard(self) -> int:
        return sum(len(m.nonstandard) for m in self.measures)

    @property
    def ok(self) -> bool:
        return self.n_over == 0 and self.n_nonstandard == 0


def _measure_capacity(score: NotAngkaScore, m: Measure, policy: str) -> float:
    if m.capacity_beats:
        return float(m.capacity_beats)
    return parse_meter(m.time_signature or score.meta.time_signature or "4/4").capacity_units(policy)


def check_score(score: NotAngkaScore) -> CheckReport:
    policy = getattr(score.meta, "beat_unit", POLICY_QUARTER) or POLICY_QUARTER
    report = CheckReport(beat_unit=policy, initial_time_signature=score.meta.time_signature or "4/4",
                         repairs=list(getattr(score, "repairs", []) or []))
    prev_label = parse_meter(score.meta.time_signature or "4/4").label

    for m in score.measures:
        ts = m.time_signature or score.meta.time_signature or "4/4"
        cap = _measure_capacity(score, m, policy)
        audit = MeasureAudit(
            number=m.number, time_signature=ts, capacity=cap,
            is_partial=bool(m.capacity_beats)
        )
        label = parse_meter(ts).label
        if label != prev_label:
            report.meter_changes.append(f"m{m.number} {ts}")
            prev_label = label
        if m.capacity_beats:
            report.partial_measures.append(f"m{m.number} (kap {m.capacity_beats:g} dari {parse_meter(ts).capacity_units(policy):g})")

        for vname, v in m.voices.items():
            if not v.notes:
                continue
            total = sum((n.duration_beats or 0.0) for n in v.notes)
            audit.fills.append(VoiceFill(voice=vname, total=total, capacity=cap))
            for n in v.notes:
                if n.tuplet:
                    continue
                d = n.duration_beats or 0.0
                if d <= EPS:
                    continue
                if d >= 1.0 - TOL:
                    # simbol polos berdurasi ≥ 1 unit: hanya sah bila 0 birama penuh atau titik/angka 1 unit
                    if abs(d - round(d)) > TOL and not (len(v.notes) == 1 and n.text == "0"):
                        audit.nonstandard.append(f"{vname}:{n.text}@{n.beat:g}/{d:g}")
                    continue
                if not any(abs(d - L) < TOL for L in _STANDARD_LENGTHS):
                    audit.nonstandard.append(f"{vname}:{n.text}@{n.beat:g}/{d:g}")
        report.measures.append(audit)

    return report


def format_report(report: CheckReport, verbose: bool = False) -> str:
    lines: List[str] = []
    lines.append(f"Sukat awal {report.initial_time_signature}, satuan ketuk: {report.beat_unit}")
    for r in report.repairs:
        lines.append("Perbaikan otomatis: " + r)
    if report.meter_changes:
        lines.append("Pergantian sukat: " + ", ".join(report.meter_changes))
    if report.partial_measures:
        lines.append("Birama gantung/penggenap: " + ", ".join(report.partial_measures))

    for m in report.measures:
        problems = []
        if m.over:
            problems.append("LEBIH " + " ".join(f"{f.voice}={f.total:g}" for f in m.over))
        if m.under:
            problems.append("kurang " + " ".join(f"{f.voice}={f.total:g}" for f in m.under))
        if m.nonstandard:
            problems.append("tak baku " + " ".join(m.nonstandard))
        if problems or verbose:
            status = "; ".join(problems) if problems else "penuh"
            lines.append(f"m{m.number:<4} {m.time_signature:<8} kap {m.capacity:<5g} {status}")

    lines.append(
        f"Ringkasan: {len(report.measures)} birama · {report.voice_measures} suara-birama · "
        f"{report.n_full} penuh · {report.n_under} kurang · {report.n_over} LEBIH · "
        f"{report.n_nonstandard} simbol tak baku"
    )
    lines.append("Status: " + ("OK" if report.ok else "GAGAL (ada birama meluap atau simbol tak baku)"))
    return "\n".join(lines)
