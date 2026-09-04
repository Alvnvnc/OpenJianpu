#!/usr/bin/env python3
"""M6 - pecah kembali suku kata yang digumpalkan OMR, lalu isikan ke not kosong.

Bukan kesalahan OCR. Pada kerapatan cetak buku nyanyian, LilyPond dan mesin
cetak lain MEMBUANG tanda hubung antar suku kata, jadi halamannya memang
bertuliskan `tutup`, bukan `tu-tup`. Audiveris membacanya dengan benar - sebagai
satu kata - dan not-not yang seharusnya menampung suku kata sebelumnya jadi
kosong:

  OMR    (istirahat)  Ter   -     tutup  -     mata  ku  na
  acuan  (istirahat)  Ter   tu    tup    ma    ta    ku  na

Not-nya tidak hilang; Audiveris membacanya semua. Yang hilang cuma pembagian
suku katanya, dan itu bisa dikembalikan tanpa melihat gambar lagi.

**Verifikatornya gratis dan eksak, sama seperti M5 pada ritme:** jumlah not
kosong tepat sebelum token itu menentukan berapa suku kata yang harus keluar
darinya. Kalau `tutup` didahului satu not kosong, ia wajib pecah jadi dua - dan
`silabel.py` hanya menawarkan `tu-tup`. Tidak ada yang ditebak.

Diam ketika ambigu: kalau tidak ada pemenggalan PUEBI yang panjangnya persis
mengisi lubangnya, atau ada lebih dari satu yang muat, tokennya dibiarkan.

  python3 lirik/tambal_lirik.py masuk.musicxml keluar.musicxml
"""
import argparse
import collections
import os
import sys
import xml.etree.ElementTree as ET

try:
    from .silabel import candidates, syllabify
except (ImportError, ValueError):
    from silabel import candidates, syllabify

# Suku kata pecahan mewarisi kedudukan token asalnya di dalam kata.
LANJUT = {"single": ("begin", "middle", "end"),
          "begin": ("begin", "middle", "middle"),
          "end": ("middle", "middle", "end"),
          "middle": ("middle", "middle", "middle")}


def _teks(el):
    return "".join(t.text or "" for t in el.findall("text")).strip()


def _lane(note):
    return ((note.findtext("staff") or "1").strip(),
            (note.findtext("voice") or "1").strip())


def kandidat_pecahan(teks, jumlah):
    """Pemenggalan PUEBI yang panjangnya PERSIS `jumlah`; None kalau tak tunggal.

    Dua penjagaan, dan keduanya GRATIS - diukur pada 217 pemecahan, keduanya
    membuang kesalahan tanpa kehilangan satu perbaikan pun:

      panjang kata >= 3   `Ia` memang dua suku kata menurut PUEBI (i-a), tetapi
                          kata sependek itu praktis tidak pernah kehilangan
                          tanda hubung - ia memang dicetak utuh di satu not.
      diftong akhir utuh  `hei` -> `he-i` memecah diftong `ei` di ujung kata.
                          `candidates()` menawarkan pemenggalan itu karena
                          ejaan saja tidak bisa memutuskan, tetapi kalau
                          pemenggalan yang mempertahankan diftong lebih pendek,
                          yang lebih panjang hampir selalu salah.

    Ketepatan: tanpa penjagaan 97,7%; dengan keduanya 99,1% pada jumlah
    perbaikan yang sama persis (212). Menaikkan ambang ke 4 huruf menambah
    ketepatan jadi 99,5% tetapi membuang 16 perbaikan yang benar - tidak
    diambil, karena pemecahan yang terlewat cuma tidak memperbaiki, sedangkan
    tukarannya di sini terlalu mahal.
    """
    if jumlah < 2:
        return None
    inti = teks.strip()
    depan = inti[:len(inti) - len(inti.lstrip("-"))]
    belakang = inti[len(inti.rstrip("-")):]
    kata = inti.strip("-")
    if not kata.isalpha() or len(kata) < 3:
        return None
    cocok = [c for c in candidates(kata) if len(c) == jumlah]
    if len(cocok) != 1:
        return None
    if len(cocok[0]) > len(syllabify(kata, keep_final_diphthong=True)):
        return None
    pecah = list(cocok[0])
    pecah[0] = depan + pecah[0]
    pecah[-1] = pecah[-1] + belakang
    return pecah


def tambal(root):
    """Kembalikan (jumlah token dipecah, jumlah suku kata baru)."""
    dipecah = suku = 0
    for part in root.findall("part"):
        urut = collections.defaultdict(list)          # lane -> [note berurutan]
        for measure in part.findall("measure"):
            for note in measure.findall("note"):
                if note.find("chord") is not None or note.find("grace") is not None:
                    continue
                urut[_lane(note)].append(note)
        for notes in urut.values():
            bait = set()
            for note in notes:
                for ly in note.findall("lyric"):
                    bait.add(ly.get("number") or "1")
            for nomor in sorted(bait):
                dipecah_, suku_ = _tambal_bait(notes, nomor)
                dipecah += dipecah_
                suku += suku_
    return dipecah, suku


def _tambal_bait(notes, nomor):
    dipecah = suku = 0
    # Not yang bisa menampung suku kata: bukan istirahat. Istirahat memutus
    # rentetan - suku kata tidak boleh melompatinya.
    for i, note in enumerate(notes):
        ly = next((x for x in note.findall("lyric")
                   if (x.get("number") or "1") == nomor), None)
        if ly is None:
            continue
        teks = _teks(ly)
        if not teks or teks == "_":
            continue
        # hitung not kosong yang bisa dinyanyikan, tepat sebelum not ini
        kosong = []
        j = i - 1
        while j >= 0:
            n = notes[j]
            if n.find("rest") is not None:
                break
            if any((x.get("number") or "1") == nomor for x in n.findall("lyric")):
                break
            kosong.append(n)
            j -= 1
        if not kosong:
            continue
        kosong.reverse()
        pecah = kandidat_pecahan(teks, len(kosong) + 1)
        if pecah is None:
            continue
        awal, tengah, akhir = LANJUT.get(
            (ly.findtext("syllabic") or "single").strip(), LANJUT["single"])
        for k, (n, potongan) in enumerate(zip(kosong, pecah[:-1])):
            baru = ET.Element("lyric", {"number": nomor})
            ET.SubElement(baru, "syllabic").text = awal if k == 0 else tengah
            ET.SubElement(baru, "text").text = potongan
            n.append(baru)
            suku += 1
        for t in ly.findall("text"):
            ly.remove(t)
        syl = ly.find("syllabic")
        if syl is None:
            syl = ET.Element("syllabic")
            ly.insert(0, syl)
        syl.text = akhir
        ET.SubElement(ly, "text").text = pecah[-1]
        dipecah += 1
    return dipecah, suku


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("masukan")
    ap.add_argument("keluaran")
    args = ap.parse_args()
    tree = ET.parse(args.masukan)
    dipecah, suku = tambal(tree.getroot())
    tree.write(args.keluaran, encoding="UTF-8", xml_declaration=True)
    print("%d token digumpalkan dipecah; %d suku kata dikembalikan ke not kosong"
          % (dipecah, suku), file=sys.stderr)


if __name__ == "__main__":
    main()
