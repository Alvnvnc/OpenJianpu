"""
OpenJianpu: High-performance, standalone vector engine converting MusicXML and sheet music
into Numbered Musical Notation (Not Angka / Jianpu).
"""

__version__ = "0.1.0"

from .schema import (
    NotAngkaScore,
    Measure,
    MeasureVoice,
    NoteItem,
    ScoreMeta,
    SystemBlockConfig,
    DynamicMark,
)
from .xml_parser import parse_musicxml_to_score
from .renderer import NotAngkaRenderer
from .checker import check_score, format_report, CheckReport
from .meter import parse_meter, Meter, POLICY_QUARTER, POLICY_DENOMINATOR, POLICIES
from .lyrics import apply_lyrics_file

__all__ = [
    "__version__",
    "NotAngkaScore",
    "Measure",
    "MeasureVoice",
    "NoteItem",
    "ScoreMeta",
    "SystemBlockConfig",
    "DynamicMark",
    "parse_musicxml_to_score",
    "NotAngkaRenderer",
    "check_score",
    "format_report",
    "CheckReport",
    "parse_meter",
    "Meter",
    "POLICY_QUARTER",
    "POLICY_DENOMINATOR",
    "POLICIES",
    "apply_lyrics_file",
]
