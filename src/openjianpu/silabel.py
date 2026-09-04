#!/usr/bin/env python3
"""Pemenggalan suku kata bahasa Indonesia, untuk menambal lirik hasil OMR.

Kenapa ini ada. Pada jalur produk utuh, 23% suku kata terbaca benar tetapi jatuh
di not yang salah: OMR menggabung suku kata bertanda hubung jadi satu token
("Ka-sih-Mu" -> "KasihMu"), lalu not-not sesudahnya kehilangan liriknya dan
seluruh baris bergeser. Untuk mengembalikannya, token gabungan itu harus dipenggal
lagi - dan bahasa Indonesia adalah kasus terbaik untuk itu: aturannya hampir
seluruhnya bisa dituliskan.

Aturan PUEBI yang dipakai:

  V-V      dua vokal berurutan dipisah          sa-at, ni-at, ku-a-sa
  V-KV     satu konsonan di antara vokal        ba-pak, ka-sih, de-ngan
  VK-KV    dua konsonan                         man-di, ber-kat, Ap-ril
  VK-KKV   tiga konsonan                        in-stru-men
  digraf   ng ny sy kh tidak pernah dipisah     ba-nyak, sung-guh

Diftong `ai au oi` DI AKHIR KATA tidak dipisah (pan-tai, pu-lau), tetapi
"main" tetap ma-in. Ejaannya sendiri tidak menentukan - itu sifat kata, bukan
sifat huruf. Karena itu fungsi `candidates()` mengembalikan BEBERAPA pemenggalan,
dan yang memilih adalah jumlah serangan nada, bukan tebakan di sini.

  python3 silabel.py kasihmu berkat sunggguh
"""
import sys

VOWELS = set("aeiouAEIOU")
DIGRAPHS = ("ng", "ny", "sy", "kh", "gh")
DIPHTHONGS = ("ai", "au", "oi", "ei")


def units(word):
    """Kata -> daftar unit (satu vokal, atau satu konsonan/digraf)."""
    out, i = [], 0
    while i < len(word):
        two = word[i:i + 2].lower()
        if two in DIGRAPHS:
            out.append(word[i:i + 2])
            i += 2
        else:
            out.append(word[i])
            i += 1
    return out


def is_vowel(unit):
    return len(unit) == 1 and unit in VOWELS


def split_points(unit_list, keep_final_diphthong):
    """Indeks unit tempat suku kata baru dimulai."""
    starts = [0]
    i = 0
    while i < len(unit_list):
        if not is_vowel(unit_list[i]):
            i += 1
            continue
        # cari konsonan berikutnya sesudah vokal ini
        j = i + 1
        while j < len(unit_list) and not is_vowel(unit_list[j]):
            j += 1
        # j menunjuk vokal berikutnya (atau ujung kata)
        consonants = j - i - 1
        if j >= len(unit_list):
            break
        if consonants == 0:
            # V-V, kecuali diftong di akhir kata
            pair = (unit_list[i] + unit_list[j]).lower()
            final = j == len(unit_list) - 1
            if keep_final_diphthong and final and pair in DIPHTHONGS:
                break
            starts.append(j)
        elif consonants == 1:
            starts.append(j - 1)          # V-KV
        else:
            starts.append(i + 2)          # VK-KV dan VK-KKV
        i = j
    return starts


def syllabify(word, keep_final_diphthong=True):
    """Satu pemenggalan. Kata tanpa vokal dikembalikan apa adanya."""
    core = word
    if not any(ch in VOWELS for ch in core):
        return [word]
    unit_list = units(core)
    starts = split_points(unit_list, keep_final_diphthong)
    out = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(unit_list)
        out.append("".join(unit_list[start:end]))
    return [piece for piece in out if piece]


def candidates(word):
    """Semua pemenggalan yang masuk akal, terpanjang dulu.

    Perbedaannya cuma perlakuan diftong akhir, dan itu memang tidak bisa
    diputuskan dari ejaan. Pemilihnya jumlah serangan nada.
    """
    seen, out = set(), []
    for keep in (True, False):
        pieces = tuple(syllabify(word, keep))
        if pieces not in seen:
            seen.add(pieces)
            out.append(list(pieces))
    out.sort(key=len)
    return out


if __name__ == "__main__":
    for w in sys.argv[1:]:
        print("%-14s %s" % (w, "  |  ".join("-".join(c) for c in candidates(w))))
