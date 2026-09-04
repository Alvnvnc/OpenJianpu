#!/usr/bin/env python3
"""
CLI Tool Not Angka Mandiri (Batik Partitur).
Mengonversi MusicXML atau JSON langsung menjadi PDF Vektor Not Angka murni
berstandar tinggi (gaya lagumisa.web.id) tanpa LilyPond.
"""

import argparse
import os
import sys

try:
    from .schema import NotAngkaScore
    from .renderer import NotAngkaRenderer
    from .xml_parser import parse_musicxml_to_score
    from .checker import check_score, format_report
    from .lyrics import apply_lyrics_file
    from .meter import POLICIES, POLICY_QUARTER
    from . import __version__
except (ImportError, ValueError):
    from openjianpu.schema import NotAngkaScore
    from openjianpu.renderer import NotAngkaRenderer
    from openjianpu.xml_parser import parse_musicxml_to_score
    from openjianpu.checker import check_score, format_report
    from openjianpu.lyrics import apply_lyrics_file
    from openjianpu.meter import POLICIES, POLICY_QUARTER
    __version__ = "0.1.0"



def cmd_render(args):
    """Render file JSON ke PDF."""
    if not os.path.exists(args.input_json):
        print(f"Error: berkas {args.input_json} tidak ditemukan.", file=sys.stderr)
        return 1

    try:
        with open(args.input_json, "r", encoding="utf-8") as f:
            score = NotAngkaScore.from_json(f.read())
    except Exception as e:
        print(f"Error: gagal membaca/mem-parse JSON: {e}", file=sys.stderr)
        return 1

    out_pdf = args.output or os.path.splitext(args.input_json)[0] + ".pdf"
    try:
        renderer = NotAngkaRenderer(score, out_pdf)
        renderer.render()
    except Exception as e:
        print(f"Error saat merender PDF: {e}", file=sys.stderr)
        return 1

    print(f"Sukses! PDF Vektor Not Angka dihasilkan -> {out_pdf}")
    return 0


def cmd_convert(args):
    """Konversi file MusicXML atau PDF balok ke PDF Not Angka langsung."""
    input_file = args.input_file
    if not os.path.exists(input_file):
        print(f"Error: berkas {input_file} tidak ditemukan.", file=sys.stderr)
        return 1

    xml_to_process = input_file
    tmp_xml = None

    # Jika input adalah PDF balok:
    if input_file.lower().endswith(".pdf"):
        print(f"Mendeteksi input PDF balok: {input_file}")
        import tempfile
        import subprocess

        # Cari skrip pdf_to_musicxml
        pdf_tool = os.path.join(here, "pdf_to_musicxml.py")
        if not os.path.exists(pdf_tool):
            skill_pdf_tool = "/home/alvn/Documents/playground/batik-partitur-skill/scripts/pdf_to_musicxml.py"
            if os.path.exists(skill_pdf_tool):
                pdf_tool = skill_pdf_tool

        if not os.path.exists(pdf_tool):
            print("Error: skrip ekstraksi PDF pdf_to_musicxml.py tidak ditemukan.", file=sys.stderr)
            return 1

        tmp_handle = tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False)
        tmp_xml = tmp_handle.name
        tmp_handle.close()

        cmd = [sys.executable, pdf_tool, input_file, "-o", tmp_xml]
        if args.title:
            cmd.extend(["--title", args.title])

        print("Mengekstrak notasi dan font musik dari glif PDF...")
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(tmp_xml) or os.path.getsize(tmp_xml) == 0:
            print(f"Gagal mengekstrak notasi dari PDF: {res.stderr or res.stdout}", file=sys.stderr)
            if os.path.exists(tmp_xml):
                os.remove(tmp_xml)
            return 1

        print("Ekstraksi PDF berhasil.")
        xml_to_process = tmp_xml

        # Deteksi metadata judul, komposer, lirik dari teks PDF jika tidak ditentukan argumen CLI
        pdf_title = getattr(args, "title", None)
        pdf_composer = getattr(args, "composer", None)
        pdf_arranger = getattr(args, "arranger", None)
        pdf_lyricist = getattr(args, "lyricist", None)

        try:
            import pypdf
            reader = pypdf.PdfReader(input_file)
            if reader.pages:
                page0 = reader.pages[0]
                ph = float(page0.mediabox.height)
                pw = float(page0.mediabox.width)
                texts_top = []

                def visitor(text, cm, tm, font_dict, font_size):
                    t = text.strip()
                    # Ambil teks di 12% bagian paling atas halaman (header judul/komposer/lyricist)
                    if t and tm[5] > ph * 0.88:
                        texts_top.append((t, tm[4], tm[5]))

                page0.extract_text(visitor_text=visitor)
                for t, tx, ty in texts_top:
                    if not any(c.isalpha() for c in t):
                        continue
                    if pw * 0.28 <= tx <= pw * 0.72 and not pdf_title:
                        pdf_title = t
                    elif tx > pw * 0.65 and not pdf_composer:
                        pdf_composer = t
                    elif tx < pw * 0.35 and not pdf_lyricist:
                        pdf_lyricist = t
        except Exception:
            pass

    try:
        score = parse_musicxml_to_score(
            xml_to_process,
            title=pdf_title if input_file.lower().endswith(".pdf") else args.title,
            composer=pdf_composer if input_file.lower().endswith(".pdf") else args.composer,
            arranger=pdf_arranger if input_file.lower().endswith(".pdf") else args.arranger,
            subtitle=args.subtitle,
            lyricist=pdf_lyricist if input_file.lower().endswith(".pdf") else getattr(args, "lyricist", None),
            beat_unit=getattr(args, "beat_unit", POLICY_QUARTER) or POLICY_QUARTER,
            tambal_lirik=not getattr(args, "no_tambal_lirik", False)
        )
    except Exception as e:
        print(f"Error saat mem-parse berkas MusicXML: {e}", file=sys.stderr)
        if tmp_xml and os.path.exists(tmp_xml):
            os.remove(tmp_xml)
        return 1

    # Lirik dari berkas teks bersih (menimpa lirik sumber)
    if getattr(args, "lyrics_file", None):
        if not os.path.exists(args.lyrics_file):
            print(f"Error: berkas lirik {args.lyrics_file} tidak ditemukan.", file=sys.stderr)
            return 1
        applied = apply_lyrics_file(score, args.lyrics_file)
        print("Lirik dari berkas ditempelkan: " + ", ".join(f"{v}={n}" for v, n in applied.items()))

    # Audit ketukan singkat: birama yang isinya melebihi sukat berarti sumber MusicXML-nya cacat
    try:
        report = check_score(score)
        for r_txt in score.repairs:
            print("Perbaikan otomatis: " + r_txt)
        if report.n_over or report.n_nonstandard:
            over_ms = sorted({m.number for m in report.measures if m.over})
            shown = ", ".join(f"m{k}" for k in over_ms[:8]) + (" ..." if len(over_ms) > 8 else "")
            print(f"Peringatan: {report.n_over} suara-birama meluap ({shown}); "
                  f"{report.n_nonstandard} simbol tak baku. Periksa dengan: notangka_cli.py check {os.path.basename(input_file)}",
                  file=sys.stderr)
        if report.meter_changes:
            print(f"Pergantian sukat: {', '.join(report.meter_changes[:12])}{' ...' if len(report.meter_changes) > 12 else ''}")
    except Exception:
        pass

    # Simpan JSON jika diminta
    if args.save_json:
        try:
            with open(args.save_json, "w", encoding="utf-8") as f:
                f.write(score.to_json())
            print(f"JSON perantara disimpan -> {args.save_json}")
        except Exception as e:
            print(f"Peringatan: gagal menyimpan JSON perantara: {e}", file=sys.stderr)

    out_pdf = args.output or os.path.splitext(input_file)[0] + "_notangka.pdf"
    try:
        renderer = NotAngkaRenderer(score, out_pdf)
        renderer.render()
    except Exception as e:
        print(f"Error saat merender PDF: {e}", file=sys.stderr)
        if tmp_xml and os.path.exists(tmp_xml):
            os.remove(tmp_xml)
        return 1
    finally:
        if tmp_xml and os.path.exists(tmp_xml):
            os.remove(tmp_xml)

    print(f"Sukses! Konversi ke PDF Not Angka berhasil -> {out_pdf}")
    return 0


def cmd_xml2json(args):
    """Ekspor MusicXML ke JSON standar Not Angka."""
    if not os.path.exists(args.input_xml):
        print(f"Error: berkas {args.input_xml} tidak ditemukan.", file=sys.stderr)
        return 1

    try:
        score = parse_musicxml_to_score(
            args.input_xml,
            title=args.title,
            composer=args.composer,
            arranger=args.arranger,
            subtitle=args.subtitle,
            lyricist=getattr(args, "lyricist", None),
            beat_unit=getattr(args, "beat_unit", POLICY_QUARTER) or POLICY_QUARTER,
            tambal_lirik=not getattr(args, "no_tambal_lirik", False)
        )
        if getattr(args, "lyrics_file", None):
            apply_lyrics_file(score, args.lyrics_file)
    except Exception as e:
        print(f"Error saat mem-parse berkas MusicXML: {e}", file=sys.stderr)
        return 1

    out_json = args.output or os.path.splitext(args.input_xml)[0] + ".json"
    try:
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(score.to_json())
    except Exception as e:
        print(f"Error saat menulis berkas JSON: {e}", file=sys.stderr)
        return 1

    print(f"Sukses! JSON Not Angka disimpan -> {out_json}")
    return 0


def cmd_check(args):
    """Audit ketukan: bandingkan isi tiap suara-birama dengan kapasitas sukatnya."""
    src = args.input_file
    if not os.path.exists(src):
        print(f"Error: berkas {src} tidak ditemukan.", file=sys.stderr)
        return 1
    try:
        if src.lower().endswith(".json"):
            with open(src, "r", encoding="utf-8") as f:
                score = NotAngkaScore.from_json(f.read())
        else:
            score = parse_musicxml_to_score(src, beat_unit=args.beat_unit or POLICY_QUARTER)
    except Exception as e:
        print(f"Error saat membaca berkas: {e}", file=sys.stderr)
        return 1

    report = check_score(score)
    print(format_report(report, verbose=args.verbose))
    return 0 if report.ok else 2


def main():
    parser = argparse.ArgumentParser(
        prog="openjianpu",
        description="OpenJianpu: High-performance, standalone engine converting MusicXML & sheet music to Numbered Musical Notation (Not Angka / Jianpu)"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: render (JSON -> PDF)
    p_render = subparsers.add_parser("render", help="Render file notangka.json ke PDF")
    p_render.add_argument("input_json", help="Path ke berkas JSON Not Angka")
    p_render.add_argument("-o", "--output", help="Path berkas PDF keluaran")

    # Subcommand: convert (MusicXML atau PDF -> PDF Not Angka)
    p_convert = subparsers.add_parser("convert", help="Konversi MusicXML atau PDF balok ke PDF Not Angka")
    p_convert.add_argument("input_file", help="Path ke berkas MusicXML (.musicxml/.xml/.mxl) atau PDF balok (.pdf)")
    p_convert.add_argument("-o", "--output", help="Path berkas PDF keluaran")
    p_convert.add_argument("--title", help="Judul partitur kustom")
    p_convert.add_argument("--composer", help="Nama komposer kustom")
    p_convert.add_argument("--arranger", help="Nama arranger kustom")
    p_convert.add_argument("--lyricist", help="Nama penulis lirik / syair kustom")
    p_convert.add_argument("--subtitle", help="Subjudul kustom (misal: 'From Coco')")
    p_convert.add_argument("--save-json", help="Simpan juga representasi JSON perantara")
    p_convert.add_argument("--beat-unit", choices=list(POLICIES), default=POLICY_QUARTER,
                           help="Satuan ketuk cetak: quarter (bawaan, gaya Puji Syukur/lagumisa) atau denominator (penyebut sukat)")
    p_convert.add_argument("--lyrics-file", help="Berkas teks syair bersih untuk menimpa lirik sumber (lihat notangka/lyrics.py)")
    p_convert.add_argument("--no-tambal-lirik", action="store_true", help="Jangan pecah token lirik lengket dengan pemenggal PUEBI")

    # Subcommand: xml2json (MusicXML -> JSON)
    p_xml2json = subparsers.add_parser("xml2json", help="Ekstrak MusicXML ke skema JSON Not Angka")
    p_xml2json.add_argument("input_xml", help="Path ke berkas MusicXML")
    p_xml2json.add_argument("-o", "--output", help="Path berkas JSON keluaran")
    p_xml2json.add_argument("--title", help="Judul partitur kustom")
    p_xml2json.add_argument("--composer", help="Nama komposer kustom")
    p_xml2json.add_argument("--arranger", help="Nama arranger kustom")
    p_xml2json.add_argument("--lyricist", help="Nama penulis lirik / syair kustom")
    p_xml2json.add_argument("--subtitle", help="Subjudul kustom")
    p_xml2json.add_argument("--beat-unit", choices=list(POLICIES), default=POLICY_QUARTER,
                            help="Satuan ketuk cetak: quarter (bawaan) atau denominator")
    p_xml2json.add_argument("--lyrics-file", help="Berkas teks syair bersih untuk menimpa lirik sumber")
    p_xml2json.add_argument("--no-tambal-lirik", action="store_true", help="Jangan pecah token lirik lengket dengan pemenggal PUEBI")

    # Subcommand: check (audit ketukan MusicXML / JSON)
    p_check = subparsers.add_parser("check", help="Audit ketukan: isi tiap suara-birama vs kapasitas sukat")
    p_check.add_argument("input_file", help="Path ke berkas MusicXML atau JSON Not Angka")
    p_check.add_argument("--beat-unit", choices=list(POLICIES), default=POLICY_QUARTER,
                         help="Satuan ketuk cetak: quarter (bawaan) atau denominator")
    p_check.add_argument("-v", "--verbose", action="store_true", help="Tampilkan semua birama, bukan hanya yang bermasalah")

    args = parser.parse_args()
    if args.command == "render":
        return cmd_render(args)
    elif args.command == "convert":
        return cmd_convert(args)
    elif args.command == "xml2json":
        return cmd_xml2json(args)
    elif args.command == "check":
        return cmd_check(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
