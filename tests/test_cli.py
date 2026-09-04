import os
import json
import subprocess
import sys
import pytest

here = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(here)
src_dir = os.path.join(repo_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
scripts_dir = os.path.join(src_dir, "openjianpu")

from openjianpu.schema import (
    NotAngkaScore, ScoreMeta, TempoMeta, Measure, MeasureVoice,
    NoteItem, DynamicMark, SystemBlockConfig
)
from openjianpu.xml_parser import to_indonesian_pitch, parse_musicxml_to_score
from openjianpu.renderer import NotAngkaRenderer


class TestNotAngkaSchema:
    def test_json_roundtrip(self):
        meta = ScoreMeta(
            title="Lagu Uji Coba",
            tonic_label="Do=Bes",
            time_signature="4/4",
            tempo=TempoMeta(bpm=84),
            composer="Komposer Uji"
        )
        notes = [
            NoteItem(text="1", octave=0, beams=0),
            NoteItem(text="2", octave=1, beams=1),
            NoteItem(text="3", accidental="kres", dot=True),
            NoteItem(text="0", beams=0)
        ]
        m1 = Measure(
            number=1,
            voices={"S": MeasureVoice(voice_name="S", notes=notes)},
            lyrics={"SA": "La la la"},
            dynamics=[DynamicMark(beat=1.0, text="mf")]
        )
        sys_cfg = SystemBlockConfig(measure_indices=[1], block_type="satb_paired")
        score = NotAngkaScore(meta=meta, measures=[m1], systems=[sys_cfg])

        json_str = score.to_json()
        restored = NotAngkaScore.from_json(json_str)

        assert restored.meta.title == "Lagu Uji Coba"
        assert restored.meta.tonic_label == "Do=Bes"
        assert restored.meta.tempo.bpm == 84
        assert len(restored.measures) == 1
        assert len(restored.measures[0].voices["S"].notes) == 4
        assert restored.measures[0].voices["S"].notes[2].accidental == "kres"
        assert restored.measures[0].lyrics["SA"] == "La la la"
        assert restored.systems[0].block_type == "satb_paired"


class TestNotAngkaParser:
    def test_indonesian_pitch_names(self):
        assert to_indonesian_pitch("Bb") == "Bes"
        assert to_indonesian_pitch("Eb") == "Es"
        assert to_indonesian_pitch("Gb") == "Ges"
        assert to_indonesian_pitch("Db") == "Des"
        assert to_indonesian_pitch("Ab") == "As"
        assert to_indonesian_pitch("F#") == "Fis"
        assert to_indonesian_pitch("C#") == "Cis"
        assert to_indonesian_pitch("G#") == "Gis"
        assert to_indonesian_pitch("C") == "C"
        assert to_indonesian_pitch("G") == "G"

    def test_parse_sample_musicxml(self):
        xml_file = os.path.join(repo_root, "out/glif/test_r.musicxml")
        if not os.path.exists(xml_file):
            pytest.skip("Berkas test_r.musicxml tidak ditemukan")

        score = parse_musicxml_to_score(xml_file)
        assert score.meta.title == "Rek Ayo Rek"
        assert score.meta.tonic_label == "Do=G"
        assert score.meta.time_signature == "4/4"
        assert len(score.measures) == 40
        assert "S" in score.measures[0].voices
        assert score.systems[0].block_type == "satb_paired"

    def test_voice_block_type_detection_solo(self, tmp_path):
        meta = ScoreMeta(title="Solo")
        m1 = Measure(number=1, voices={"S": MeasureVoice(voice_name="S", notes=[NoteItem(text="1")])})
        score = NotAngkaScore(meta=meta, measures=[m1], systems=[SystemBlockConfig(measure_indices=[1], block_type="single_solo")])
        pdf_out = str(tmp_path / "solo.pdf")
        renderer = NotAngkaRenderer(score, pdf_out)
        renderer.render()
        assert os.path.exists(pdf_out)
        assert os.path.getsize(pdf_out) > 0

    def test_voice_block_type_detection_sa_duet(self, tmp_path):
        meta = ScoreMeta(title="Duet SA")
        m1 = Measure(
            number=1,
            voices={
                "S": MeasureVoice(voice_name="S", notes=[NoteItem(text="1")]),
                "A": MeasureVoice(voice_name="A", notes=[NoteItem(text="3")])
            }
        )
        score = NotAngkaScore(meta=meta, measures=[m1], systems=[SystemBlockConfig(measure_indices=[1], block_type="sa_duet")])
        pdf_out = str(tmp_path / "duet.pdf")
        renderer = NotAngkaRenderer(score, pdf_out)
        renderer.render()
        assert os.path.exists(pdf_out)
        assert os.path.getsize(pdf_out) > 0


class TestNotAngkaRenderer:
    def test_pdf_header_and_validity(self, tmp_path):
        json_file = os.path.join(repo_root, "out/glif/The_Lord_Bless_You_Score.json")
        if not os.path.exists(json_file):
            pytest.skip("Berkas acuan The_Lord_Bless_You_Score.json tidak ditemukan")

        with open(json_file, "r", encoding="utf-8") as f:
            score = NotAngkaScore.from_json(f.read())

        out_pdf = str(tmp_path / "rendered_tlby.pdf")
        renderer = NotAngkaRenderer(score, out_pdf)
        renderer.render()

        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 5000  # Dokumen berisi beberapa halaman/elemen
        with open(out_pdf, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"


class TestNotAngkaCLI:
    def test_cli_version(self):
        cli_path = os.path.join(scripts_dir, "cli.py")
        res = subprocess.run([sys.executable, cli_path, "--version"], capture_output=True, text=True)
        assert res.returncode == 0
        assert "openjianpu 0.1.0" in (res.stdout + res.stderr)

    def test_cli_render_success(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        json_file = os.path.join(repo_root, "out/glif/The_Lord_Bless_You_Score.json")
        if not os.path.exists(json_file):
            pytest.skip("JSON acuan tidak ditemukan")

        out_pdf = str(tmp_path / "cli_out.pdf")
        res = subprocess.run([sys.executable, cli_path, "render", json_file, "-o", out_pdf], capture_output=True, text=True)
        assert res.returncode == 0
        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 0

    def test_cli_render_missing_file(self):
        cli_path = os.path.join(scripts_dir, "cli.py")
        res = subprocess.run([sys.executable, cli_path, "render", "/path/tidak/ada.json"], capture_output=True, text=True)
        assert res.returncode == 1
        assert "tidak ditemukan" in res.stderr

    def test_cli_convert_success(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        xml_file = os.path.join(repo_root, "out/glif/test_r.musicxml")
        if not os.path.exists(xml_file):
            pytest.skip("MusicXML tidak ditemukan")

        out_pdf = str(tmp_path / "cli_convert.pdf")
        save_json = str(tmp_path / "cli_convert.json")
        res = subprocess.run(
            [sys.executable, cli_path, "convert", xml_file, "-o", out_pdf, "--save-json", save_json],
            capture_output=True, text=True
        )
        assert res.returncode == 0
        assert os.path.exists(out_pdf)
        assert os.path.exists(save_json)
        assert os.path.getsize(out_pdf) > 0
        assert os.path.getsize(save_json) > 0

    def test_cli_convert_the_lord_bless_you(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        xml_file = os.path.join(repo_root, "out/hasil_notangka/The_Lord_Bless_You.musicxml")
        if not os.path.exists(xml_file):
            pytest.skip("The_Lord_Bless_You.musicxml tidak ditemukan")

        out_pdf = str(tmp_path / "tlby_convert.pdf")
        res = subprocess.run(
            [sys.executable, cli_path, "convert", xml_file, "-o", out_pdf],
            capture_output=True, text=True
        )
        assert res.returncode == 0
        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 0

    def test_cli_convert_remember_me(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        xml_file = os.path.join(repo_root, "out/glif/Remember_Me_-_Kuriakos_Elias_Chavara.musicxml")
        if not os.path.exists(xml_file):
            pytest.skip("Remember_Me MusicXML tidak ditemukan")

        out_pdf = str(tmp_path / "remember_me_convert.pdf")
        save_json = str(tmp_path / "remember_me_convert.json")
        res = subprocess.run(
            [sys.executable, cli_path, "convert", xml_file, "-o", out_pdf, "--save-json", save_json],
            capture_output=True, text=True
        )
        assert res.returncode == 0
        assert os.path.exists(out_pdf)
        assert os.path.exists(save_json)
        assert os.path.getsize(out_pdf) > 10000
        assert os.path.getsize(save_json) > 10000

    def test_cli_convert_direct_pdf(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        pdf_file = os.path.join(repo_root, "korpus-psmits/pdf/Remember_Me_-_Kuriakos_Elias_Chavara.pdf")
        if not os.path.exists(pdf_file):
            pytest.skip("PDF sumber tidak ditemukan")

        out_pdf = str(tmp_path / "remember_me_direct_from_pdf.pdf")
        res = subprocess.run(
            [sys.executable, cli_path, "convert", pdf_file, "-o", out_pdf, "--subtitle", 'From "Coco"'],
            capture_output=True, text=True
        )
        assert res.returncode == 0
        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 10000

    def test_cli_convert_missing_file(self):
        cli_path = os.path.join(scripts_dir, "cli.py")
        res = subprocess.run([sys.executable, cli_path, "convert", "/path/tidak/ada.xml"], capture_output=True, text=True)
        assert res.returncode == 1
        assert "tidak ditemukan" in res.stderr

    def test_cli_corrupted_json(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        bad_json = str(tmp_path / "bad.json")
        with open(bad_json, "w") as f:
            f.write("{ ini bukan json valid }")

        res = subprocess.run([sys.executable, cli_path, "render", bad_json], capture_output=True, text=True)
        assert res.returncode == 1
        assert "gagal membaca/mem-parse JSON" in res.stderr

    def test_cli_corrupted_xml(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        bad_xml = str(tmp_path / "bad.xml")
        with open(bad_xml, "w") as f:
            f.write("<not-valid-xml")

        res = subprocess.run([sys.executable, cli_path, "convert", bad_xml], capture_output=True, text=True)
        assert res.returncode == 1
        assert "Error saat mem-parse berkas MusicXML" in res.stderr

    def test_cli_xml2json_success(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        xml_file = os.path.join(repo_root, "out/glif/test_r.musicxml")
        if not os.path.exists(xml_file):
            pytest.skip("MusicXML tidak ditemukan")

        out_json = str(tmp_path / "cli_export.json")
        res = subprocess.run([sys.executable, cli_path, "xml2json", xml_file, "-o", out_json], capture_output=True, text=True)
        assert res.returncode == 0
        assert os.path.exists(out_json)
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["meta"]["title"] == "Rek Ayo Rek"

    def test_auto_healing_missing_beams(self):
        notes = [
            NoteItem(text="3", dot=True, beams=0), # 1.5 ketuk
            NoteItem(text="3", dot=False, beams=0), # harus otomatis disembuhkan jadi 1 balok
            NoteItem(text="2", beams=1),
            NoteItem(text="3", beams=1),
        ]
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Healing", tonic_label="Do=C", time_signature="4/4"),
            measures=[Measure(number=1, voices={"S": MeasureVoice(voice_name="S", notes=notes)})]
        )
        r = NotAngkaRenderer(score, "/dev/null")
        r._heal_notes(notes)
        assert notes[1].beams == 1, "Not ke-2 harus otomatis sembuh memiliki beams=1"
        assert notes[1].duration_beats == 0.5

    def test_triplet_and_dot_spacing_rendering(self, tmp_path):
        triplet_notes = [
            NoteItem(text="1", octave=1, beams=1, tuplet="3", beat=1.0, duration_beats=1/3),
            NoteItem(text="2", octave=1, beams=1, tuplet="3", beat=1.333, duration_beats=1/3),
            NoteItem(text="3", octave=1, beams=1, tuplet="3", beat=1.667, duration_beats=1/3),
            NoteItem(text=".", beat=2.0, duration_beats=1.0),
            NoteItem(text="5", dot=True, beat=3.0, duration_beats=1.5),
            NoteItem(text="6", beams=1, beat=4.5, duration_beats=0.5),
        ]
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Triplet", tonic_label="Do=F", time_signature="4/4"),
            measures=[Measure(number=1, voices={"S": MeasureVoice(voice_name="S", notes=triplet_notes)})]
        )
        out_pdf = str(tmp_path / "triplet.pdf")
        r = NotAngkaRenderer(score, out_pdf)
        r.render()
        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 1000

    def test_dynamic_measure_width_and_lyric_density(self):
        # Birama 1: hanya 1 not panjang
        m1_notes = [NoteItem(text="1", beat=1.0), NoteItem(text=".", beat=2.0), NoteItem(text=".", beat=3.0), NoteItem(text=".", beat=4.0)]
        # Birama 2: rapat 8 not dengan lirik
        m2_notes = [
            NoteItem(text="1", beat=1.0, lyric="Rek"),
            NoteItem(text="2", beat=1.5, lyric="a-"),
            NoteItem(text="3", beat=2.0, lyric="yo"),
            NoteItem(text="4", beat=2.5, lyric="rek"),
            NoteItem(text="5", beat=3.0, lyric="mla-"),
            NoteItem(text="6", beat=3.5, lyric="ku"),
            NoteItem(text="7", beat=4.0, lyric="mla-"),
            NoteItem(text="1", beat=4.5, lyric="ku"),
        ]
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Density", tonic_label="Do=C", time_signature="4/4"),
            measures=[
                Measure(number=1, voices={"S": MeasureVoice(voice_name="S", notes=m1_notes)}),
                Measure(number=2, voices={"S": MeasureVoice(voice_name="S", notes=m2_notes)})
            ]
        )
        r = NotAngkaRenderer(score, "/dev/null")
        widths = r._calculate_measure_widths(score.measures)
        assert len(widths) == 2
        assert widths[1] > widths[0], "Birama dengan lirik padat harus mendapatkan alokasi lebar lebih besar secara dinamis"

    def test_unpitched_whisper_and_multi_divisi_noche(self):
        """Memverifikasi bahwa partitur polifoni kompleks (Noche) terpetakan ke 16 suara dan menangani bisikan vokal 'x'."""
        xml_path = "out/test_noche.musicxml"
        if not os.path.exists(xml_path):
            pytest.skip("File out/test_noche.musicxml belum ada")

        from openjianpu.xml_parser import parse_musicxml_to_score, detect_voice_mapping
        import xml.etree.ElementTree as ET

        root = ET.parse(xml_path).getroot()
        mapping = detect_voice_mapping(root)
        
        # Harus memetakan ke 16 suara kanonikal S1-S4, A1-A4, T1-T4, B1-B4
        unique_voices = set(mapping.values())
        expected_voices = {
            "S1", "S2", "S3", "S4",
            "A1", "A2", "A3", "A4",
            "T1", "T2", "T3", "T4",
            "B1", "B2", "B3", "B4"
        }
        assert unique_voices == expected_voices, f"Mapping harus tepat 16 suara (pecahan lintas halaman digabung): {sorted(unique_voices)}"

        # Parse skor lengkap
        score = parse_musicxml_to_score(xml_path)
        assert len(score.measures) == 77
        assert score.systems[0].block_type == "general_multivoice"

        # Cek nada bisikan pada bar 52 (tenor / bass membisikkan 's')
        m52 = score.measures[51] # 0-indexed index 51 adalah bar 52
        has_whisper = False
        for v in m52.voices.values():
            for n in v.notes:
                if n.text == "x" and n.lyric == "s":
                    has_whisper = True
                    break
        assert has_whisper, "Nada bisikan 'x' dengan lirik 's' harus terdeteksi di bar 52"

    def test_general_multivoice_pdf_rendering(self, tmp_path):
        """Memverifikasi perenderan sistem multi-suara general_multivoice ke PDF vektor valid."""
        from openjianpu.schema import NotAngkaScore, ScoreMeta, Measure, MeasureVoice, NoteItem, SystemBlockConfig
        from openjianpu.renderer import NotAngkaRenderer

        # Buat skor tiruan 8 suara SSAATTBB
        voices_list = ["S1", "S2", "A1", "A2", "T1", "T2", "B1", "B2"]
        m_voices = {}
        for v in voices_list:
            m_voices[v] = MeasureVoice(
                voice_name=v,
                notes=[
                    NoteItem(text="1", beat=1.0, duration_beats=1.0, lyric="Glo-"),
                    NoteItem(text="3", beat=2.0, duration_beats=1.0, lyric="ri-"),
                    NoteItem(text="5", beat=3.0, duration_beats=1.0, lyric="a,"),
                    NoteItem(text="0", beat=4.0, duration_beats=1.0)
                ]
            )

        m = Measure(number=1, voices=m_voices)
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Octet", composer="Composer", lyricist="Poet"),
            measures=[m],
            systems=[SystemBlockConfig(measure_indices=[1], block_type="general_multivoice", voices=voices_list)]
        )

        out_pdf = str(tmp_path / "test_octet.pdf")
        r = NotAngkaRenderer(score, out_pdf)
        r.render()

        assert os.path.exists(out_pdf)
        assert os.path.getsize(out_pdf) > 2000
        with open(out_pdf, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"

    def test_whole_measure_rest_centered(self):
        """Memverifikasi bahwa istirahat 1 birama penuh (0 tunggal) diposisikan persis di tengah birama."""
        from openjianpu.schema import NotAngkaScore, ScoreMeta, Measure, MeasureVoice, NoteItem
        from openjianpu.renderer import NotAngkaRenderer

        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Rest", time_signature="7/8"),
            measures=[Measure(number=1, time_signature="7/8", voices={"S": MeasureVoice("S", [NoteItem(text="0", duration_beats=3.5)])})]
        )
        r = NotAngkaRenderer(score, "/dev/null")
        m = score.measures[0]
        notes = m.voices["S"].notes
        pos = r._compute_note_positions(notes, m_x=100.0, m_w=150.0, m=m)
        assert len(pos) == 1
        expected_center = 100.0 + (150.0 - 7.0) / 2.0
        assert abs(pos[0] - expected_center) < 1e-4

    def test_beam_clearance_and_height_consistency(self):
        """Memverifikasi bahwa kelompok balok menjaga clearance di atas titik oktaf dan konsisten."""
        from openjianpu.schema import NotAngkaScore, ScoreMeta, Measure, MeasureVoice, NoteItem
        from openjianpu.renderer import NotAngkaRenderer

        notes = [
            NoteItem(text="1", octave=1, beams=1, beat=1.0, duration_beats=0.5),
            NoteItem(text="2", octave=1, beams=1, beat=1.5, duration_beats=0.5),
            NoteItem(text="3", octave=0, beams=1, beat=2.0, duration_beats=0.5),
            NoteItem(text="4", octave=0, beams=1, beat=2.5, duration_beats=0.5),
        ]
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Beam"),
            measures=[Measure(number=1, voices={"S": MeasureVoice("S", notes)})]
        )
        r = NotAngkaRenderer(score, "/dev/null")
        positions = r._compute_note_positions(notes, m_x=50.0, m_w=100.0)
        assert len(positions) == 4
        # Pastikan tidak ada exception saat menggambar beams
        r._draw_beams(notes, positions, base_y=100.0, m=score.measures[0])

    def test_tuplet_bracket_geometry_and_rendering(self, tmp_path):
        """Memverifikasi bahwa kurung triplet berbusur digambar dengan benar."""
        from openjianpu.schema import NotAngkaScore, ScoreMeta, Measure, MeasureVoice, NoteItem
        from openjianpu.renderer import NotAngkaRenderer

        notes = [
            NoteItem(text="6", tuplet="3", beat=1.0, duration_beats=2/3),
            NoteItem(text="6", tuplet="3", beat=1.667, duration_beats=2/3),
            NoteItem(text="7", tuplet="3", beat=2.333, duration_beats=2/3),
        ]
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Triplet Bracket"),
            measures=[Measure(number=1, voices={"S": MeasureVoice("S", notes)})]
        )
        pdf_out = str(tmp_path / "tup_test.pdf")
        r = NotAngkaRenderer(score, pdf_out)
        r.render()
        assert os.path.exists(pdf_out)
        assert os.path.getsize(pdf_out) > 500

    def test_extension_dot_beams_follow_duration(self):
        """Titik perpanjangan satu ketuk penuh tak berbalok; titik setengah ketuk berbalok satu
        (Puji Syukur 347b: "3 .̅ 3̅" untuk seperempat bertitik + seperdelapan)."""
        from openjianpu.schema import NoteItem
        from openjianpu.renderer import NotAngkaRenderer
        from openjianpu.schema import NotAngkaScore, ScoreMeta, Measure, MeasureVoice

        notes = [
            NoteItem(text="3", beat=1.0, duration_beats=1.0),
            NoteItem(text=".", beams=1, beat=2.0, duration_beats=1.0),   # titik satu ketuk penuh, balok keliru
            NoteItem(text="4", beat=3.0, duration_beats=1.0),
            NoteItem(text=".", beams=0, beat=4.0, duration_beats=0.5),   # titik setengah ketuk tanpa balok (keliru)
            NoteItem(text="5", beams=1, beat=4.5, duration_beats=0.5),
        ]
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Dot Beams"),
            measures=[Measure(number=1, voices={"S": MeasureVoice("S", notes)})]
        )
        r = NotAngkaRenderer(score, "/dev/null")
        r._heal_notes(notes)
        assert notes[1].beams == 0, "Titik satu ketuk penuh WAJIB tanpa balok"
        assert notes[3].beams == 1, "Titik setengah ketuk WAJIB berbalok satu"
        groups = r._beam_groups(notes, score.measures[0])
        assert groups == [[3, 4]], f"Titik dan not 1/8 pada ketukan yang sama harus satu balok: {groups}"

    def test_meter_7_8_grouping_2_2_3(self, tmp_path):
        """Memverifikasi bahwa balok tujuh not 1/8 pada birama 7/8 terbagi 2+2+3."""
        from openjianpu.schema import NotAngkaScore, ScoreMeta, Measure, MeasureVoice, NoteItem
        from openjianpu.renderer import NotAngkaRenderer

        # 7 not 1/8 dalam birama 7/8
        notes = [
            NoteItem(text="1", beams=1, beat=1.0, duration_beats=0.5),
            NoteItem(text="7", beams=1, beat=1.5, duration_beats=0.5),
            NoteItem(text="1", beams=1, beat=2.0, duration_beats=0.5),
            NoteItem(text="1", beams=1, beat=2.5, duration_beats=0.5),
            NoteItem(text="7", beams=1, beat=3.0, duration_beats=0.5),
            NoteItem(text="2", beams=1, beat=3.5, duration_beats=0.5),
            NoteItem(text="7", beams=1, beat=4.0, duration_beats=0.5),
        ]
        m1 = Measure(number=1, time_signature="7/8", voices={"T": MeasureVoice("T", notes)})
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test 7/8", time_signature="7/8"),
            measures=[m1]
        )
        pdf_out = str(tmp_path / "test_7_8.pdf")
        r = NotAngkaRenderer(score, pdf_out)
        assert r._beam_groups(notes, m1) == [[0, 1], [2, 3], [4, 5, 6]]
        r.render()
        assert os.path.exists(pdf_out)
        assert os.path.getsize(pdf_out) > 500

    def test_triplet_notes_have_no_horizontal_beam_lines(self, tmp_path):
        """Memverifikasi bahwa kelompok triplet tidak digambar dengan garis balok datar (beams=0)."""
        from openjianpu.schema import NotAngkaScore, ScoreMeta, Measure, MeasureVoice, NoteItem
        from openjianpu.renderer import NotAngkaRenderer

        # Triplet 3 not dan 2 not 1/8 biasa dalam 1 birama
        tup_notes = [
            NoteItem(text="1", tuplet="3", beams=1, beat=1.0, duration_beats=1/3),
            NoteItem(text="2", tuplet="3", beams=1, beat=1.333, duration_beats=1/3),
            NoteItem(text="3", tuplet="3", beams=1, beat=1.667, duration_beats=1/3),
            NoteItem(text="4", beams=1, beat=2.0, duration_beats=0.5),
            NoteItem(text="5", beams=1, beat=2.5, duration_beats=0.5),
        ]
        score = NotAngkaScore(
            meta=ScoreMeta(title="Test Triplet No Beam"),
            measures=[Measure(number=1, voices={"S": MeasureVoice("S", tup_notes)})]
        )
        r = NotAngkaRenderer(score, "/dev/null")
        r._heal_notes(tup_notes)

        # 1. Triplet notes harus memiliki beams = 0
        assert tup_notes[0].beams == 0, "Not triplet 1 harus memiliki beams=0"
        assert tup_notes[1].beams == 0, "Not triplet 2 harus memiliki beams=0"
        assert tup_notes[2].beams == 0, "Not triplet 3 harus memiliki beams=0"

        # 2. Not non-triplet 1/8 tetap memiliki beams = 1
        assert tup_notes[3].beams == 1, "Not ke-4 (1/8 non-triplet) tetap beams=1"
        assert tup_notes[4].beams == 1, "Not ke-5 (1/8 non-triplet) tetap beams=1"

        # 3. Render ke PDF berjalan lancar
        pdf_out = str(tmp_path / "tup_no_beam.pdf")
        r_pdf = NotAngkaRenderer(score, pdf_out)
        r_pdf.render()
        assert os.path.exists(pdf_out)
        assert os.path.getsize(pdf_out) > 500






# ---------------------------------------------------------------------------
# Pembacaan ketukan lintas sukat (meter-aware beat reading)
# ---------------------------------------------------------------------------

def _note_xml(n: dict, divisions: int) -> str:
    """Membangun satu elemen <note> MusicXML dari kamus ringkas."""
    parts = ["<note>"]
    if n.get("rest"):
        parts.append("<rest/>" if not n.get("measure_rest") else '<rest measure="yes"/>')
    else:
        parts.append(f"<pitch><step>{n.get('step', 'C')}</step><octave>{n.get('octave', 4)}</octave></pitch>")
    parts.append(f"<duration>{n['dur']}</duration>")
    if n.get("tie"):
        parts.append(f'<tie type="{n["tie"]}"/>')
    parts.append("<voice>1</voice>")
    if n.get("type"):
        parts.append(f"<type>{n['type']}</type>")
    for _ in range(n.get("dots", 0)):
        parts.append("<dot/>")
    if n.get("lyric"):
        parts.append(f"<lyric><syllabic>single</syllabic><text>{n['lyric']}</text></lyric>")
    parts.append("</note>")
    return "".join(parts)


def _mxml(measures, part_name="Soprano", divisions=4, key_fifths=0):
    """measures: daftar (time_signature|None, implicit(bool), [note dict, ...])."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<score-partwise version="3.1"><part-list><score-part id="P1">',
           f'<part-name>{part_name}</part-name></score-part></part-list><part id="P1">']
    for i, (ts, implicit, notes) in enumerate(measures):
        attrs = f' implicit="yes"' if implicit else ""
        out.append(f'<measure number="{i if implicit and i == 0 else i + 1}"{attrs}>')
        if i == 0 or ts:
            out.append("<attributes>")
            if i == 0:
                out.append(f"<divisions>{divisions}</divisions><key><fifths>{key_fifths}</fifths><mode>major</mode></key>")
            if ts:
                num, den = ts.split("/")
                out.append(f"<time><beats>{num}</beats><beat-type>{den}</beat-type></time>")
            if i == 0:
                out.append("<clef><sign>G</sign><line>2</line></clef>")
            out.append("</attributes>")
        for n in notes:
            out.append(_note_xml(n, divisions))
        out.append("</measure>")
    out.append("</part></score-partwise>")
    return "\n".join(out)


def _parse_xml_str(tmp_path, xml_str, name="uji.musicxml", **kw):
    p = tmp_path / name
    p.write_text(xml_str, encoding="utf-8")
    return parse_musicxml_to_score(str(p), **kw)


def _sym(notes):
    """Ringkasan simbol: teks, balok, durasi."""
    return [(n.text, n.beams, round(n.duration_beats, 3)) for n in notes]


class TestMeterModel:
    def test_parse_meter_and_capacity(self):
        from openjianpu.meter import parse_meter
        assert parse_meter("4/4").capacity_units() == 4.0
        assert parse_meter("7/8").capacity_units() == 3.5
        assert parse_meter("9/8").capacity_units() == 4.5
        assert parse_meter("2/2").capacity_units() == 4.0
        assert parse_meter("1/4").capacity_units() == 1.0
        assert parse_meter("2+2+3/8").capacity_units() == 3.5
        assert parse_meter("2+2+3/8").label == "2+2+3/8"
        assert parse_meter("C").label == "4/4"
        assert parse_meter("rusak").label == "4/4"
        # kebijakan penyebut: satu simbol = nilai penyebut
        assert parse_meter("7/8").capacity_units("denominator") == 7.0
        assert parse_meter("2/2").capacity_units("denominator") == 2.0

    def test_beat_groups(self):
        from openjianpu.meter import parse_meter, group_index
        assert parse_meter("7/8").groups_units() == [1.0, 1.0, 1.5]
        assert parse_meter("9/8").groups_units() == [1.5, 1.5, 1.5]
        assert parse_meter("6/8").groups_units() == [1.5, 1.5]
        assert parse_meter("5/8").groups_units() == [1.5, 1.0]
        assert parse_meter("3+2+2/8").groups_units() == [1.5, 1.0, 1.0]
        assert parse_meter("2/2").groups_units() == [2.0, 2.0]
        assert parse_meter("3/4").groups_units() == [1.0, 1.0, 1.0]
        assert parse_meter("7/8").groups_units("denominator") == [2.0, 2.0, 3.0]
        g = parse_meter("7/8").groups_units()
        assert [group_index(x, g) for x in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0)] == [0, 0, 1, 1, 2, 2, 2]

    def test_split_and_subunit_symbols(self):
        from openjianpu.meter import split_at_units, symbols_for_subunit
        assert split_at_units(0.0, 1.5) == [(0.0, 1.0), (1.0, 0.5)]
        assert split_at_units(0.5, 1.0) == [(0.5, 0.5), (1.0, 0.5)]
        assert split_at_units(0.5, 2.0) == [(0.5, 0.5), (1.0, 1.0), (2.0, 0.5)]
        assert [(L, b, d) for L, b, d, _ in symbols_for_subunit(0.5)] == [(0.5, 1, False)]
        assert [(L, b, d) for L, b, d, _ in symbols_for_subunit(0.75)] == [(0.75, 1, True)]
        assert [(L, b, d) for L, b, d, _ in symbols_for_subunit(0.75, allow_dot=False)] == [(0.5, 1, False), (0.25, 2, False)]
        assert [(L, b, d) for L, b, d, _ in symbols_for_subunit(0.25)] == [(0.25, 2, False)]


class TestBeatReadingAcrossMeters:
    def test_dotted_quarter_plus_eighth_matches_puji_syukur_347b(self, tmp_path):
        """2/4: seperempat bertitik + seperdelapan -> "3 .̅ 3̅" (titik dan not 1/8 satu balok)."""
        xml = _mxml([("2/4", False, [
            dict(step="E", dur=6, type="quarter", dots=1, lyric="Tu-"),
            dict(step="E", dur=2, type="eighth", lyric="han"),
        ])])
        sc = _parse_xml_str(tmp_path, xml)
        notes = sc.measures[0].voices["S"].notes
        assert _sym(notes) == [("3", 0, 1.0), (".", 1, 0.5), ("3", 1, 0.5)]
        assert [n.beat for n in notes] == [1.0, 2.0, 2.5]
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._beam_groups(notes, sc.measures[0]) == [[1, 2]]

    def test_syncopated_quarter_is_split_at_beat_boundary(self, tmp_path):
        """4/4: 1/8, 1/4, 1/8, 1/2 -> "1̅ 2̅ .̅ 3̅ 4 ." : balok tidak pernah melintasi ketukan."""
        xml = _mxml([("4/4", False, [
            dict(step="C", dur=2, type="eighth"),
            dict(step="D", dur=4, type="quarter"),
            dict(step="E", dur=2, type="eighth"),
            dict(step="F", dur=8, type="half"),
        ])])
        sc = _parse_xml_str(tmp_path, xml)
        notes = sc.measures[0].voices["S"].notes
        assert _sym(notes) == [("1", 1, 0.5), ("2", 1, 0.5), (".", 1, 0.5), ("3", 1, 0.5), ("4", 0, 1.0), (".", 0, 1.0)]
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._beam_groups(notes, sc.measures[0]) == [[0, 1], [2, 3]]

    def test_7_8_seven_eighths_quarter_policy_and_denominator_policy(self, tmp_path):
        eighths = [dict(step=s, dur=2, type="eighth") for s in "CDEFGAB"]
        xml = _mxml([("7/8", False, eighths)])
        sc = _parse_xml_str(tmp_path, xml)
        notes = sc.measures[0].voices["S"].notes
        assert [n.beams for n in notes] == [1] * 7
        assert sum(n.duration_beats for n in notes) == 3.5
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._beam_groups(notes, sc.measures[0]) == [[0, 1], [2, 3], [4, 5, 6]]

        sc2 = _parse_xml_str(tmp_path, xml, name="uji2.musicxml", beat_unit="denominator")
        notes2 = sc2.measures[0].voices["S"].notes
        assert sc2.meta.beat_unit == "denominator"
        assert [n.beams for n in notes2] == [0] * 7, "Pada kebijakan penyebut, not 1/8 di 7/8 adalah simbol polos"
        assert sum(n.duration_beats for n in notes2) == 7.0
        r2 = NotAngkaRenderer(sc2, "/dev/null")
        assert r2._get_measure_total_beats(sc2.measures[0]) == 7.0

    def test_fractional_rests_are_not_rounded(self, tmp_path):
        """7/8 dan 9/8: tanda diam 1,5 ketuk menjadi "0 0̅", bukan dua nol penuh (round(1.5) == 2)."""
        xml = _mxml([
            ("7/8", False, [dict(rest=True, dur=6, type="quarter", dots=1), dict(step="A", dur=2, type="eighth"),
                            dict(step="A", dur=4, type="quarter"), dict(step="A", dur=2, type="eighth")]),
            ("9/8", False, [dict(rest=True, dur=6, type="quarter", dots=1), dict(rest=True, dur=2, type="eighth"),
                            dict(step="C", dur=4, type="quarter"), dict(step="C", dur=4, type="quarter"), dict(step="C", dur=2, type="eighth")]),
        ])
        sc = _parse_xml_str(tmp_path, xml)
        n1 = sc.measures[0].voices["S"].notes
        assert _sym(n1) == [("0", 0, 1.0), ("0", 1, 0.5), ("6", 1, 0.5), ("6", 0, 1.0), ("6", 1, 0.5)]
        assert [n.beat for n in n1] == [1.0, 2.0, 2.5, 3.0, 4.0]
        assert abs(sum(n.duration_beats for n in n1) - 3.5) < 1e-9
        n2 = sc.measures[1].voices["S"].notes
        assert _sym(n2) == [("0", 0, 1.0), ("0", 1, 0.5), ("0", 1, 0.5), ("1", 0, 1.0), ("1", 0, 1.0), ("1", 1, 0.5)]
        assert [n.beat for n in n2] == [1.0, 2.0, 2.5, 3.0, 4.0, 5.0]
        assert abs(sum(n.duration_beats for n in n2) - 4.5) < 1e-9
        r = NotAngkaRenderer(sc, "/dev/null")
        # 9/8 = 3+3+3 not 1/8: batas kelompok pada 1,5 dan 3,0 ketuk, sehingga "0̅"@2 (kelompok 1)
        # dan "0̅"@2,5 (kelompok 2) TIDAK disatukan baloknya; "1̅"@5 berdiri sendiri.
        assert r._beam_groups(n2, sc.measures[1]) == [[1], [2], [5]]

    def test_quarter_crossing_a_group_boundary_is_split(self, tmp_path):
        """7/8 (2+2+3): seperempat yang melintasi batas kelompok dipecah "6̅ .̅"; yang berada
        di dalam kelompok 3 not 1/8 tetap satu simbol polos."""
        xml = _mxml([("7/8", False, [dict(rest=True, dur=6, type="quarter", dots=1),
                                     dict(step="A", dur=4, type="quarter"), dict(step="A", dur=4, type="quarter")])])
        sc = _parse_xml_str(tmp_path, xml)
        n1 = sc.measures[0].voices["S"].notes
        assert _sym(n1) == [("0", 0, 1.0), ("0", 1, 0.5), ("6", 1, 0.5), (".", 1, 0.5), ("6", 0, 1.0)]
        assert [n.beat for n in n1] == [1.0, 2.0, 2.5, 3.0, 3.5]
        assert abs(sum(n.duration_beats for n in n1) - 3.5) < 1e-9

    def test_6_8_quarter_policy_follows_one_plus_half_convention(self, tmp_path):
        """6/8 dengan satuan seperempat: 1/4 1/8 1/4 1/8 -> "5 6̅ 5 6̅" (1 + ½ + 1 + ½);
        1/2 bertitik -> "5 . ."; 1/4 bertitik + 1/4 bertitik -> "5 .̅ 5 .̅"."""
        xml = _mxml([
            ("6/8", False, [dict(step="G", dur=4, type="quarter"), dict(step="A", dur=2, type="eighth"),
                            dict(step="G", dur=4, type="quarter"), dict(step="A", dur=2, type="eighth")]),
            (None, False, [dict(step="G", dur=12, type="half", dots=1)]),
            (None, False, [dict(step="G", dur=6, type="quarter", dots=1), dict(step="G", dur=6, type="quarter", dots=1)]),
            (None, False, [dict(step=s, dur=2, type="eighth") for s in "CDEFGA"]),
        ])
        sc = _parse_xml_str(tmp_path, xml)
        ms = sc.measures
        assert _sym(ms[0].voices["S"].notes) == [("5", 0, 1.0), ("6", 1, 0.5), ("5", 0, 1.0), ("6", 1, 0.5)]
        assert [n.beat for n in ms[0].voices["S"].notes] == [1.0, 2.0, 2.5, 3.5]
        assert _sym(ms[1].voices["S"].notes) == [("5", 0, 1.0), (".", 0, 1.0), (".", 0, 1.0)]
        assert _sym(ms[2].voices["S"].notes) == [("5", 0, 1.0), (".", 1, 0.5), ("5", 0, 1.0), (".", 1, 0.5)]
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._beam_groups(ms[3].voices["S"].notes, ms[3]) == [[0, 1, 2], [3, 4, 5]]
        from openjianpu.checker import check_score
        assert check_score(sc).ok

    def test_cli_check_subcommand(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        xml = _mxml([("3/4", False, [dict(step="C", dur=4, type="quarter"), dict(step="D", dur=4, type="quarter"), dict(step="E", dur=4, type="quarter")]),
                     ("2/4", False, [dict(step="C", dur=4, type="quarter"), dict(step="D", dur=4, type="quarter")])])
        p = tmp_path / "cek.musicxml"
        p.write_text(xml, encoding="utf-8")
        res = subprocess.run([sys.executable, cli_path, "check", str(p)], capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr
        assert "Pergantian sukat: m2 2/4" in res.stdout
        assert "Status: OK" in res.stdout
        # birama meluap -> kode keluar 2
        bad = _mxml([("2/4", False, [dict(step="C", dur=4, type="quarter"), dict(step="D", dur=4, type="quarter"), dict(step="E", dur=4, type="quarter")])])
        pb = tmp_path / "meluap.musicxml"
        pb.write_text(bad, encoding="utf-8")
        res = subprocess.run([sys.executable, cli_path, "check", str(pb)], capture_output=True, text=True)
        assert res.returncode == 2
        assert "LEBIH" in res.stdout

    def test_tied_note_continuation_keeps_fractional_value(self, tmp_path):
        """Nada 1/4 disambung (tie) ke 1/8 pada birama berikutnya -> titik berbalok, bukan titik penuh."""
        xml = _mxml([
            ("2/4", False, [dict(step="G", dur=4, type="quarter"), dict(step="G", dur=4, type="quarter", tie="start")]),
            (None, False, [dict(step="G", dur=2, type="eighth", tie="stop"), dict(step="A", dur=2, type="eighth"), dict(step="B", dur=4, type="quarter")]),
        ])
        sc = _parse_xml_str(tmp_path, xml)
        n2 = sc.measures[1].voices["S"].notes
        assert _sym(n2) == [(".", 1, 0.5), ("6", 1, 0.5), ("7", 0, 1.0)]
        assert sc.measures[0].voices["S"].notes[-1].tie is True

    def test_composite_numerator_2_2_3(self, tmp_path):
        eighths = [dict(step=s, dur=2, type="eighth") for s in "CDEFGAB"]
        xml = _mxml([("2+2+3/8", False, eighths)])
        sc = _parse_xml_str(tmp_path, xml)
        m = sc.measures[0]
        assert m.time_signature == "2+2+3/8"
        assert sc.meta.time_signature == "2+2+3/8"
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._get_measure_total_beats(m) == 3.5
        assert r._beam_groups(m.voices["S"].notes, m) == [[0, 1], [2, 3], [4, 5, 6]]

    def test_pickup_measure_gets_its_real_capacity(self, tmp_path):
        """Birama gantung (implicit) satu ketuk pada 4/4 -> kapasitas 1, not rapat ke garis birama."""
        xml = _mxml([
            ("4/4", True, [dict(step="G", dur=2, type="eighth"), dict(step="A", dur=2, type="eighth")]),
            (None, False, [dict(step="C", dur=4, type="quarter", octave=5), dict(step="B", dur=4, type="quarter"), dict(step="A", dur=8, type="half")]),
        ])
        sc = _parse_xml_str(tmp_path, xml)
        m0, m1 = sc.measures[0], sc.measures[1]
        assert m0.capacity_beats == 1.0
        assert m1.capacity_beats is None
        assert [n.beat for n in m0.voices["S"].notes] == [1.0, 1.5]
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._get_measure_total_beats(m0) == 1.0
        assert r._beam_groups(m0.voices["S"].notes, m0) == [[0, 1]]
        from openjianpu.checker import check_score
        rep = check_score(sc)
        assert rep.ok and rep.n_full == 2
        assert rep.partial_measures and rep.partial_measures[0].startswith("m0")

    def test_lone_eighth_keeps_its_beam(self):
        """Not 1/8 tunggal (misal gantung "5̅ |") tetap berbendera; tanpa bendera ia terbaca seperempat."""
        notes = [NoteItem(text="5", beams=1, beat=1.0, duration_beats=0.5)]
        m = Measure(number=0, time_signature="4/4", capacity_beats=0.5, voices={"S": MeasureVoice("S", notes)})
        sc = NotAngkaScore(meta=ScoreMeta(title="Gantung"), measures=[m])
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._beam_groups(notes, m) == [[0]]

    def test_measure_grid_is_shared_by_all_voices(self):
        """Grid ketukan dihitung sekali per birama: suara yang meluap tidak boleh menggeser suara lain."""
        s_notes = [NoteItem(text="1", beat=1.0, duration_beats=1.0), NoteItem(text="2", beat=2.0, duration_beats=1.0)]
        a_notes = [NoteItem(text="3", beat=1.0, duration_beats=1.0), NoteItem(text="4", beat=2.0, duration_beats=1.0), NoteItem(text="5", beat=3.0, duration_beats=1.0)]
        m = Measure(number=1, time_signature="2/4", voices={"S": MeasureVoice("S", s_notes), "A": MeasureVoice("A", a_notes)})
        sc = NotAngkaScore(meta=ScoreMeta(title="Grid", time_signature="2/4"), measures=[m])
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._get_measure_total_beats(m, s_notes) == r._get_measure_total_beats(m, a_notes) == 3.0
        ps = r._compute_note_positions(s_notes, 100.0, 200.0, m)
        pa = r._compute_note_positions(a_notes, 100.0, 200.0, m)
        assert abs(ps[0] - pa[0]) < 1e-6 and abs(ps[1] - pa[1]) < 1e-6

    def test_meter_change_label_shown_in_every_block_type(self, tmp_path):
        """Label pergantian sukat (4/4 -> 2/4) tercetak di blok solo, SA, dan SATB, bukan hanya multi-suara."""
        import shutil
        if not shutil.which("pdftotext"):
            pytest.skip("pdftotext tidak tersedia")
        def mk(block_type, voices):
            ms = []
            for k, ts in enumerate(("4/4", "2/4", "2/4", "4/4")):
                vs = {v: MeasureVoice(v, [NoteItem(text="1", beat=1.0, duration_beats=1.0), NoteItem(text="2", beat=2.0, duration_beats=1.0)]) for v in voices}
                ms.append(Measure(number=k + 1, time_signature=ts, voices=vs))
            sc = NotAngkaScore(meta=ScoreMeta(title="Sukat", time_signature="4/4"), measures=ms,
                               systems=[SystemBlockConfig(measure_indices=[1, 2, 3, 4], block_type=block_type, voices=voices)])
            r = NotAngkaRenderer(sc, "/dev/null")
            assert r._meter_change_label(ms[0]) is None
            assert r._meter_change_label(ms[1]) == "2/4"
            assert r._meter_change_label(ms[2]) is None
            assert r._meter_change_label(ms[3]) == "4/4"
            out = str(tmp_path / f"{block_type}.pdf")
            NotAngkaRenderer(sc, out).render()
            txt = subprocess.run(["pdftotext", out, "-"], capture_output=True, text=True).stdout
            assert txt.count("2/4") >= 1 and txt.count("4/4") >= 2, f"{block_type}: label sukat tidak tercetak"
        mk("single_solo", ["S"])
        mk("sa_duet", ["S", "A"])
        mk("satb_paired", ["S", "A", "T", "B"])
        mk("general_multivoice", ["S1", "S2", "A1", "A2"])

    def test_noche_meter_changes_are_read_exactly(self):
        """Noche: seluruh birama 3/4, 7/8, 9/8, 1/4 (bukan 2/2 yang sumbernya cacat) terisi tepat."""
        xml_path = os.path.join(repo_root, "out/test_noche.musicxml")
        if not os.path.exists(xml_path):
            pytest.skip("File out/test_noche.musicxml belum ada")
        from openjianpu.checker import check_score
        sc = parse_musicxml_to_score(xml_path)
        rep = check_score(sc)
        assert rep.meter_changes[:6] == ["m3 7/8", "m4 9/8", "m5 7/8", "m6 9/8", "m7 1/4", "m8 7/8"]
        assert rep.n_nonstandard == 0
        problems = [m for m in rep.measures if (m.over or m.under) and m.time_signature not in ("2/2",)]
        # m71 (2/4) meluap karena sumber MusicXML-nya sendiri memuat 2,5 ketuk
        problems = [m for m in problems if m.number != 71]
        assert problems == [], [(m.number, m.time_signature, [f.voice for f in m.over + m.under]) for m in problems]
        assert rep.n_full >= 0.94 * rep.voice_measures


# ---------------------------------------------------------------------------
# Penguatan: pemetaan suara, modulasi, bait, birama diam, dinamika, garis birama
# ---------------------------------------------------------------------------

def _mxml_parts(parts, measures_per_part, divisions=4, key_fifths=0, ts="4/4", extra_part_xml=None):
    """parts: daftar (id, nama[, midi_program]); measures_per_part: {id: [ [note dict...], ... ]}."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<score-partwise version="3.1"><part-list>']
    for p in parts:
        pid, name = p[0], p[1]
        out.append(f'<score-part id="{pid}"><part-name>{name}</part-name>')
        if len(p) > 2:
            out.append(f'<midi-instrument id="{pid}-I1"><midi-program>{p[2]}</midi-program></midi-instrument>')
        out.append('</score-part>')
    out.append('</part-list>')
    for p in parts:
        pid = p[0]
        out.append(f'<part id="{pid}">')
        for i, notes in enumerate(measures_per_part[pid]):
            out.append(f'<measure number="{i + 1}">')
            if i == 0:
                num, den = ts.split("/")
                clef = extra_part_xml.get(pid, "<clef><sign>G</sign><line>2</line></clef>") if extra_part_xml else "<clef><sign>G</sign><line>2</line></clef>"
                out.append(f"<attributes><divisions>{divisions}</divisions><key><fifths>{key_fifths}</fifths></key>"
                           f"<time><beats>{num}</beats><beat-type>{den}</beat-type></time>{clef}</attributes>")
            for n in notes:
                if isinstance(n, str):
                    out.append(n)  # XML mentah (direction, barline, attributes)
                else:
                    out.append(_note_xml(n, divisions))
            out.append('</measure>')
        out.append('</part>')
    out.append('</score-partwise>')
    return "\n".join(out)


def _q(step, octave=4, lyric=None, **kw):
    d = dict(step=step, octave=octave, dur=4, type="quarter")
    if lyric:
        d["lyric"] = lyric
    d.update(kw)
    return d


class TestHardeningVoiceMapping:
    def test_instrument_parts_are_dropped_and_generic_names_inferred(self, tmp_path):
        from openjianpu.xml_parser import detect_voice_mapping
        import xml.etree.ElementTree as ET
        parts = [("P1", "Staf 1"), ("P2", "Staf 2"), ("P3", "Staf 3"), ("P4", "Staf 4"), ("P5", "Piano", 1), ("P6", "Bass Guitar")]
        mp = {
            "P1": [[_q("C", 5), _q("D", 5), _q("E", 5), _q("C", 5)]],
            "P2": [[_q("E", 4), _q("F", 4), _q("G", 4), _q("E", 4)]],
            "P3": [[_q("G", 3), _q("A", 3), _q("B", 3), _q("G", 3)]],
            "P4": [[_q("C", 3), _q("D", 3), _q("E", 3), _q("C", 3)]],
            "P5": [[_q("C", 4), _q("D", 4), _q("E", 4), _q("C", 4)]],
            "P6": [[_q("C", 2), _q("D", 2), _q("E", 2), _q("C", 2)]],
        }
        clefs = {"P3": '<clef><sign>G</sign><line>2</line><clef-octave-change>-1</clef-octave-change></clef>',
                 "P4": '<clef><sign>F</sign><line>4</line></clef>', "P6": '<clef><sign>F</sign><line>4</line></clef>'}
        xml = _mxml_parts(parts, mp, extra_part_xml=clefs)
        root = ET.fromstring(xml)
        m = detect_voice_mapping(root)
        assert m == {"P1": "S", "P2": "A", "P3": "T", "P4": "B"}, m

    def test_named_families_numbering_and_merging(self, tmp_path):
        from openjianpu.xml_parser import detect_voice_mapping
        import xml.etree.ElementTree as ET
        parts = [("P1", "Soprano 1"), ("P2", "Soprano 2"), ("P3", "Alto 2"), ("P4", "Alto"), ("P5", "Mezzo-soprano"), ("P6", "Bajo"), ("P7", "Bassoon"), ("P8", "Soprano")]
        rest = dict(rest=True, dur=16, type="whole")
        mp = {pid: [[_q("C", 5)], [_q("C", 5)]] for pid, _ in [(p[0], 0) for p in parts]}
        mp["P8"] = [[rest], [_q("C", 5)]]   # "Soprano" tanpa nomor: pecahan S1 yang berbunyi di birama lain
        mp["P1"] = [[_q("C", 5)], [rest]]
        xml = _mxml_parts(parts, mp)
        m = detect_voice_mapping(ET.fromstring(xml))
        assert m["P1"] == "S1" and m["P2"] == "S2" and m["P8"] == "S1", m
        assert m["P3"] == "A2" and m["P4"] == "A1", m
        assert m["P5"] == "MS" and m["P6"] == "B", m
        assert "P7" not in m, "Bassoon adalah alat musik"

    def test_software_name_is_not_a_composer(self, tmp_path):
        xml = _mxml([("4/4", False, [_q("C"), _q("D"), _q("E"), _q("F")])])
        xml = xml.replace("<part-list>", "<identification><creator type=\"composer\">Music21</creator></identification><part-list>")
        sc = _parse_xml_str(tmp_path, xml)
        assert sc.meta.composer == ""

    def test_junk_omr_credits_are_skipped_in_favor_of_credit_words(self, tmp_path):
        xml = _mxml([("4/4", False, [_q("C"), _q("D"), _q("E"), _q("F")])])
        xml = xml.replace("<part-list>", (
            '<identification><creator type="composer">2nd time to</creator><creator type="composer">BRIDGE</creator>'
            '<creator type="lyricist">28 Em</creator></identification>'
            '<credit><credit-words>Licensed to Alouisia Choir</credit-words></credit>'
            '<credit><credit-words>Composed by Michael Masser</credit-words></credit>'
            '<credit><credit-words>SATB arrangement by Dinar Primasti</credit-words></credit>'
            '<part-list>'))
        sc = _parse_xml_str(tmp_path, xml)
        assert sc.meta.composer == "Composed by Michael Masser"
        assert sc.meta.arranger == "SATB arrangement by Dinar Primasti"
        assert sc.meta.lyricist == ""
        assert sc.meta.subtitle == ""


class TestHardeningContent:
    def test_modulation_changes_degrees_and_prints_label(self, tmp_path):
        """C mayor -> G mayor di birama 2: nada G menjadi 1 (bukan 5) dan label Do=G tercetak."""
        xml = _mxml([("4/4", False, [_q("G"), _q("A"), _q("B"), _q("C", 5)]),
                     (None, False, [_q("G"), _q("A"), _q("B"), _q("C", 5)])])
        xml = xml.replace('<measure number="2">', '<measure number="2"><attributes><key><fifths>1</fifths></key></attributes>')
        sc = _parse_xml_str(tmp_path, xml)
        m1, m2 = sc.measures
        assert [n.text for n in m1.voices["S"].notes] == ["5", "6", "7", "1"]
        assert [n.text for n in m2.voices["S"].notes] == ["1", "2", "3", "4"]
        assert m1.tonic_label == "Do=C" and m2.tonic_label == "Do=G"
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._tonic_change_label(m1) is None
        assert r._tonic_change_label(m2) == "Do=G"

    def test_multiple_verses_are_kept_and_rendered(self, tmp_path):
        notes = [_q("C", lyric="Pu-"), _q("D", lyric="ji"), _q("E", lyric="Tu-"), _q("F", lyric="han")]
        xml = _mxml([("4/4", False, notes)])
        # sisipkan bait 2 pada setiap not
        for a, b in (("Pu-", "Ma-"), ("ji", "ri"), ("Tu-", "nya-"), ("han", "nyi")):
            xml = xml.replace(f"<lyric><syllabic>single</syllabic><text>{a}</text></lyric>",
                              f'<lyric number="1"><syllabic>single</syllabic><text>{a}</text></lyric><lyric number="2"><syllabic>single</syllabic><text>{b}</text></lyric>')
        sc = _parse_xml_str(tmp_path, xml)
        ns = sc.measures[0].voices["S"].notes
        assert [n.lyric for n in ns] == ["Pu-", "ji", "Tu-", "han"]
        assert [n.verses for n in ns] == [["Ma-"], ["ri"], ["nya-"], ["nyi"]]
        r = NotAngkaRenderer(sc, "/dev/null")
        assert r._extra_verses(sc.measures, ["S"]) == 1
        out = str(tmp_path / "bait.pdf")
        NotAngkaRenderer(sc, out).render()
        import shutil
        if shutil.which("pdftotext"):
            txt = subprocess.run(["pdftotext", out, "-"], capture_output=True, text=True).stdout
            assert "nyi" in txt and "han" in txt

    def test_lyric_ligatures_and_artifacts_are_cleaned(self):
        from openjianpu.xml_parser import clean_lyric_text
        assert clean_lyric_text("diﬀ-") == "diff-"
        assert clean_lyric_text("ﬁne") == "fine"
        assert clean_lyric_text("=") == ""
        assert clean_lyric_text("dumabiyyu@gmail.comdum") == ""
        assert clean_lyric_text("dum abiyyu@gmail.com dum") == "dum  dum"
        assert clean_lyric_text("ka mi") == "ka mi"

    def test_consecutive_all_rest_measures_collapse(self, tmp_path):
        rest = dict(rest=True, dur=16, type="whole", measure_rest=True)
        xml = _mxml([("4/4", False, [rest]), (None, False, [rest]), (None, False, [rest]),
                     (None, False, [_q("C"), _q("D"), _q("E"), _q("F")])])
        sc = _parse_xml_str(tmp_path, xml)
        assert sc.measures[0].multi_rest == 3
        assert sc.systems[0].measure_indices == [1, 4], sc.systems[0].measure_indices
        out = str(tmp_path / "multirest.pdf")
        NotAngkaRenderer(sc, out).render()
        import shutil
        if shutil.which("pdftotext"):
            txt = subprocess.run(["pdftotext", out, "-"], capture_output=True, text=True).stdout
            assert "3 birama" in txt

    def test_dynamics_hairpins_and_barlines_are_extracted(self, tmp_path):
        dyn = '<direction placement="below"><direction-type><dynamics><mf/></dynamics></direction-type></direction>'
        wedge_on = '<direction><direction-type><wedge type="crescendo"/></direction-type></direction>'
        wedge_off = '<direction><direction-type><wedge type="stop"/></direction-type></direction>'
        words = '<direction><direction-type><words>rit.</words></direction-type></direction>'
        m1 = [dyn, _q("C"), _q("D"), wedge_on, _q("E"), _q("F"), wedge_off]
        m2 = ['<barline location="left"><bar-style>heavy-light</bar-style><repeat direction="forward"/></barline>',
              _q("C"), words, _q("D"), _q("E"), _q("F"),
              '<barline location="right"><bar-style>light-heavy</bar-style><ending number="1" type="start"/><repeat direction="backward"/></barline>']
        m3 = [_q("C"), _q("D"), _q("E"), _q("F"), '<barline location="right"><bar-style>light-light</bar-style></barline>']
        m4 = [_q("C"), _q("D"), _q("E"), _q("F")]
        xml = _mxml_parts([("P1", "Soprano")], {"P1": [m1, m2, m3, m4]})
        sc = _parse_xml_str(tmp_path, xml)
        ms = sc.measures
        d1 = ms[0].dynamics
        assert [(d.text, d.beat) for d in d1 if not d.is_hairpin] == [("mf", 1.0)]
        hp = [d for d in d1 if d.is_hairpin]
        assert len(hp) == 1 and hp[0].hairpin_type == "cresc" and hp[0].beat == 3.0
        assert abs(hp[0].hairpin_end_beat - 5.0) < 0.01
        assert [(d.text, d.beat) for d in ms[1].dynamics] == [("rit.", 2.0)]
        assert ms[1].barline_left == "repeat_start" and ms[1].barline_type == "repeat_end" and ms[1].ending == "1."
        assert ms[2].barline_type == "double"
        assert ms[3].barline_type == "final"
        out = str(tmp_path / "dyn.pdf")
        NotAngkaRenderer(sc, out).render()
        assert os.path.getsize(out) > 500

    def test_fermata_is_read(self, tmp_path):
        xml = _mxml([("4/4", False, [_q("C"), _q("D"), _q("E"), _q("F")])])
        xml = xml.replace("<type>quarter</type></note>", "<type>quarter</type><notations><fermata/></notations></note>", 1)
        sc = _parse_xml_str(tmp_path, xml)
        assert sc.measures[0].voices["S"].notes[0].fermata is True

    def test_system_chunking_shrinks_for_dense_measures(self, tmp_path):
        dense = [dict(step=s, dur=1, type="16th", lyric="ta-") for s in "CDEFGABC" * 2]
        sparse = [_q("C"), _q("D"), _q("E"), _q("F")]
        sc_dense = _parse_xml_str(tmp_path, _mxml([("4/4", False, dense)] * 6), name="padat.musicxml")
        sc_sparse = _parse_xml_str(tmp_path, _mxml([("4/4", False, sparse)] * 6), name="lega.musicxml")
        assert len(sc_sparse.systems[0].measure_indices) == 4   # batas 16,5 ketuk per sistem pada 4/4
        assert len(sc_dense.systems[0].measure_indices) == 1

    def test_per_system_block_type_follows_sounding_voices(self, tmp_path):
        rest = dict(rest=True, dur=16, type="whole", measure_rest=True)
        satb = [_q("C", 5), _q("D", 5), _q("E", 5), _q("F", 5)]
        parts = [("P1", "Solo"), ("P2", "Soprano"), ("P3", "Alto"), ("P4", "Tenor"), ("P5", "Bass")]
        mp = {"P1": [satb, [rest], [rest], [rest], [rest], [rest]],
              "P2": [[rest], satb, satb, satb, satb, satb], "P3": [[rest], satb, satb, satb, satb, satb],
              "P4": [[rest], satb, satb, satb, satb, satb], "P5": [[rest], satb, satb, satb, satb, satb]}
        sc = _parse_xml_str(tmp_path, _mxml_parts(parts, mp))
        types = [(s.block_type, s.voices) for s in sc.systems]
        assert types[0][0] == "general_multivoice" and "Solo" in types[0][1]
        assert types[-1] == ("satb_paired", ["S", "A", "T", "B"]), types


class TestHardeningDivisi:
    def test_chord_divisi_splits_into_two_voices(self, tmp_path):
        """Part Sopran yang menulis divisi sebagai akor pada >= 20% birama dipecah S1 (atas) / S2 (bawah)."""
        def chord_measure(top, bottom):
            m = []
            for _ in range(4):
                m.append(dict(step=top, octave=5, dur=4, type="quarter"))
                m.append("<note><chord/><pitch><step>%s</step><octave>4</octave></pitch><duration>4</duration><voice>1</voice><type>quarter</type></note>" % bottom)
            return m
        parts = [("P1", "Soprano"), ("P2", "Alto"), ("P3", "Tenor"), ("P4", "Bass")]
        plain = [_q("C", 5), _q("D", 5), _q("E", 5), _q("F", 5)]
        mp = {"P1": [chord_measure("E", "C")] * 5 + [plain],
              "P2": [plain] * 6, "P3": [plain] * 6, "P4": [plain] * 6}
        sc = _parse_xml_str(tmp_path, _mxml_parts(parts, mp))
        vs = {v for m in sc.measures for v in m.voices}
        assert vs == {"S1", "S2", "A", "T", "B"}, vs
        m1 = sc.measures[0]
        assert [n.text for n in m1.voices["S1"].notes] == ["3"] * 4
        assert [n.text for n in m1.voices["S2"].notes] == ["1"] * 4
        # birama tanpa akor: kedua suara mendapat nada yang sama (unisono)
        m6 = sc.measures[5]
        assert [n.text for n in m6.voices["S1"].notes] == [n.text for n in m6.voices["S2"].notes] == ["1", "2", "3", "4"]
        from openjianpu.checker import check_score
        assert check_score(sc).n_over == 0

    def test_closed_score_two_staves_become_satb(self, tmp_path):
        """Satu part 'Choir' dua staf, akor SA di staf 1 dan TB di staf 2 -> S, A, T, B."""
        def note(step, octv, staff, chord=False):
            return ("<note>" + ("<chord/>" if chord else "") + f"<pitch><step>{step}</step><octave>{octv}</octave></pitch>"
                    f"<duration>4</duration><voice>{1 if staff == 1 else 2}</voice><type>quarter</type><staff>{staff}</staff></note>")
        measures = []
        for _ in range(6):
            m = []
            for _ in range(4):
                m += [note("E", 5, 1), note("C", 5, 1, chord=True)]
            m.append("<backup><duration>16</duration></backup>")
            for _ in range(4):
                m += [note("G", 3, 2), note("C", 3, 2, chord=True)]
            measures.append(m)
        clefs = {"P1": '<staves>2</staves><clef number="1"><sign>G</sign><line>2</line></clef><clef number="2"><sign>F</sign><line>4</line></clef>'}
        sc = _parse_xml_str(tmp_path, _mxml_parts([("P1", "Choir")], {"P1": measures}, extra_part_xml=clefs))
        vs = {v for m in sc.measures for v in m.voices}
        assert vs == {"S", "A", "T", "B"}, vs
        m1 = sc.measures[0]
        assert [n.text for n in m1.voices["S"].notes] == ["3"] * 4
        assert [n.text for n in m1.voices["A"].notes] == ["1"] * 4
        assert [n.text for n in m1.voices["T"].notes] == ["5"] * 4
        assert [n.text for n in m1.voices["B"].notes] == ["1"] * 4
        assert sc.systems[0].block_type == "satb_paired"

    def test_convert_warns_about_source_overflow(self, tmp_path):
        cli_path = os.path.join(scripts_dir, "cli.py")
        bad = _mxml([("2/4", False, [_q("C"), _q("D"), _q("E")]), (None, False, [_q("C"), _q("D")])])
        pb = tmp_path / "meluap.musicxml"
        pb.write_text(bad, encoding="utf-8")
        out = str(tmp_path / "meluap.pdf")
        res = subprocess.run([sys.executable, cli_path, "convert", str(pb), "-o", out], capture_output=True, text=True)
        assert res.returncode == 0 and os.path.exists(out)
        assert "Peringatan" in res.stderr and "m1" in res.stderr


class TestLimitationFixes:
    def test_phantom_trailing_rest_is_pruned(self, tmp_path):
        """2/4: dua seperempat + diam 1/8 hantu di ujung -> diam dibuang, birama pas, tercatat sebagai perbaikan."""
        xml = _mxml([("2/4", False, [_q("C"), _q("D"), dict(rest=True, dur=2, type="eighth")]),
                     (None, False, [_q("E"), _q("F")])])
        sc = _parse_xml_str(tmp_path, xml)
        assert [n.text for n in sc.measures[0].voices["S"].notes] == ["1", "2"]
        assert any("diam hantu" in r for r in sc.repairs), sc.repairs
        from openjianpu.checker import check_score
        assert check_score(sc).n_over == 0

    def test_unbracketed_eighth_triplet_is_recovered(self, tmp_path):
        """4/4: 1/4 1/4 1/4 + tiga 1/8 (kelebihan persis 1/8) -> tiga 1/8 itu triol; kandidat tunggal."""
        xml = _mxml([("4/4", False, [_q("C"), _q("D"), _q("E"),
                                     dict(step="F", dur=2, type="eighth"), dict(step="G", dur=2, type="eighth"), dict(step="A", dur=2, type="eighth")])])
        sc = _parse_xml_str(tmp_path, xml)
        ns = sc.measures[0].voices["S"].notes
        assert [n.tuplet for n in ns] == [None, None, None, "3", "3", "3"]
        assert abs(sum(n.duration_beats for n in ns) - 4.0) < 1e-6
        assert any("triol" in r for r in sc.repairs)

    def test_ambiguous_overflow_is_left_alone(self, tmp_path):
        """4/4 dengan sembilan 1/8: banyak kandidat triol -> tidak ditebak, tetap dilaporkan LEBIH."""
        xml = _mxml([("4/4", False, [dict(step=s, dur=2, type="eighth") for s in "CDEFGABCD"])])
        sc = _parse_xml_str(tmp_path, xml)
        assert sc.repairs == []
        from openjianpu.checker import check_score
        assert check_score(sc).n_over == 1

    def test_overflow_marker_printed_in_pdf(self, tmp_path):
        import shutil
        if not shutil.which("pdftotext"):
            pytest.skip("pdftotext tidak tersedia")
        xml = _mxml([("2/4", False, [_q("C"), _q("D"), _q("E")]), (None, False, [_q("C"), _q("D")])])
        sc = _parse_xml_str(tmp_path, xml)
        out = str(tmp_path / "tanda.pdf")
        NotAngkaRenderer(sc, out).render()
        txt = subprocess.run(["pdftotext", out, "-"], capture_output=True, text=True).stdout
        assert "! m1" in txt and "! m2" not in txt

    def test_glued_lyric_token_is_split_to_preceding_empty_notes(self, tmp_path):
        """"tutup" pada not ke-2 dengan not ke-1 kosong -> "tu-" "tup" (lirik/tambal_lirik, PUEBI)."""
        if not os.path.exists(os.path.join(src_dir, "openjianpu", "tambal_lirik.py")):
            pytest.skip("lirik/tambal_lirik.py tidak ada")
        xml = _mxml([("4/4", False, [_q("C"), _q("D", lyric="tutup"), _q("E", lyric="ma-"), _q("F", lyric="ta")])])
        sc = _parse_xml_str(tmp_path, xml)
        assert [n.lyric for n in sc.measures[0].voices["S"].notes] == ["tu-", "tup", "ma-", "ta"]
        assert any("lirik" in r for r in sc.repairs)
        sc2 = _parse_xml_str(tmp_path, xml, name="tanpa.musicxml", tambal_lirik=False)
        assert [n.lyric for n in sc2.measures[0].voices["S"].notes] == [None, "tutup", "ma-", "ta"]

    def test_camelcase_glued_lyrics_are_split(self):
        from openjianpu.xml_parser import clean_lyric_text
        assert clean_lyric_text("keHadiratMu") == "ke Hadirat-Mu"
        assert clean_lyric_text("padaNya") == "pada-Nya"
        assert clean_lyric_text("Tuhan") == "Tuhan"
        assert clean_lyric_text("AllahBapa") == "Allah Bapa"

    def test_lyrics_file_tokenize_and_apply(self, tmp_path):
        from openjianpu.lyrics import tokenize_lyrics, apply_lyrics_file
        assert tokenize_lyrics("Ma-lam ku-dus, _ se-nyap") == ["Ma-", "lam", "ku-", "dus,", None, "se-", "nyap"]
        xml = _mxml([("4/4", False, [_q("C", lyric="xx"), _q("D"), _q("E"), _q("F")]),
                     (None, False, [dict(rest=True, dur=4, type="quarter"), _q("G"), _q("A"), _q("B")])])
        sc = _parse_xml_str(tmp_path, xml, tambal_lirik=False)
        lf = tmp_path / "syair.txt"
        lf.write_text("# bait 1\nMa-lam ku-dus, _ su-nyi\n2: Bait ke-dua ma-lam\n", encoding="utf-8")
        applied = apply_lyrics_file(sc, str(lf))
        assert applied == {"S": 12}, applied
        n1 = sc.measures[0].voices["S"].notes
        n2 = sc.measures[1].voices["S"].notes
        assert [n.lyric for n in n1] == ["Ma-", "lam", "ku-", "dus,"]
        assert [n.lyric for n in n2] == [None, None, "su-", "nyi"]        # diam dilewati, "_" melisma
        # "Bait" memang dua suku kata menurut PUEBI (ba-it); kata tanpa tanda hubung dipenggal otomatis
        assert [n.verses for n in n1] == [["Ba-"], ["it"], ["ke-"], ["dua"]]

    def test_e2e_sample_chorus_fixture(self, tmp_path):
        fixture_path = os.path.join(here, "fixtures", "sample_chorus.musicxml")
        assert os.path.exists(fixture_path), "sample_chorus.musicxml fixture must exist"

        out_pdf = str(tmp_path / "sample.pdf")
        out_json = str(tmp_path / "sample.json")
        cli_entry = os.path.join(src_dir, "openjianpu", "cli.py")

        # 1. Convert MusicXML -> PDF + JSON
        res = subprocess.run([
            sys.executable, cli_entry, "convert", fixture_path,
            "-o", out_pdf, "--save-json", out_json
        ], capture_output=True, text=True)
        assert res.returncode == 0, f"Convert failed: {res.stderr}"
        assert os.path.exists(out_pdf) and os.path.getsize(out_pdf) > 0
        assert os.path.exists(out_json) and os.path.getsize(out_json) > 0

        # 2. Check audit
        res_check = subprocess.run([
            sys.executable, cli_entry, "check", fixture_path
        ], capture_output=True, text=True)
        assert res_check.returncode == 0
        assert "Status: OK" in res_check.stdout

        # 3. Render JSON -> PDF
        out_pdf2 = str(tmp_path / "from_json.pdf")
        res_render = subprocess.run([
            sys.executable, cli_entry, "render", out_json, "-o", out_pdf2
        ], capture_output=True, text=True)
        assert res_render.returncode == 0
        assert os.path.exists(out_pdf2) and os.path.getsize(out_pdf2) > 0

