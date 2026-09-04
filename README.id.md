# OpenJianpu (Bahasa Indonesia)

[![CI](https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml/badge.svg)](https://github.com/Alvnvnc/OpenJianpu/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Tests: 60+ Passed](https://img.shields.io/badge/tests-60%2B%20passed-brightgreen.svg)](tests/)
[![English Docs](https://img.shields.io/badge/docs-English-blue.svg)](README.md)

[English Version](README.md) | **Bahasa Indonesia**

**OpenJianpu** adalah mesin penata huruf (*engraving engine*) dan pengonversi vektor mandiri berkinerja tinggi yang mengubah partitur **MusicXML** dan not balok menjadi **Not Angka** (*Jianpu / 简谱*) siap cetak berstandar penerbitan.

Dirancang khusus untuk kebutuhan paduan suara (SATB), aransemen vokal, dan buku nyanyian gereja (*Puji Syukur*, *Madah Bakti*, *Kidung Jemaat*, dan *lagumisa.web.id*), OpenJianpu merender PDF vektor resolusi tinggi dalam hitungan milidetik—**100% mandiri tanpa membutuhkan instalasi LilyPond, MuseScore, maupun Java/JVM**.

---

## 📖 Daftar Isi
- [Mengapa OpenJianpu Dibangun?](#-mengapa-openjianpu-dibangun)
- [Inovasi Rekayasa & Keunggulan](#-inovasi-rekayasa--keunggulan)
- [Arsitektur Alur Kerja](#-arsitektur-alur-kerja)
- [Instalasi](#-instalasi)
- [Panduan Pemakaian CLI](#-panduan-pemakaian-cli)
  - [1. Konversi Langsung (`convert`)](#1-konversi-musicxml-ke-pdf-not-angka)
  - [2. Audit Ketukan & Sukat (`check`)](#2-audit-ketukan-dan-sukat-check)
  - [3. Alur JSON Perantara (`xml2json` & `render`)](#3-alur-json-perantara-dua-arah)
  - [4. Penyelarasan Lirik Eksternal (`--lyrics-file`)](#4-penyelarasan-lirik-eksternal---lyrics-file)
- [Konvensi Cetak Not Angka Indonesia](#-konvensi-cetak-not-angka-indonesia)
- [Penggunaan via Python API](#-penggunaan-via-python-api)
- [Tolok Ukur Korpus & Verifikasi Empiris](#-tolok-ukur-korpus--verifikasi-empiris)
- [Lisensi](#-lisensi)

---

## 💡 Mengapa OpenJianpu Dibangun?

Not Angka adalah bahasa musik utama bagi jutaan anggota paduan suara, pemusik gereja, dan institusi pendidikan di Indonesia dan Asia. Namun, perangkat lunak notasi barat modern (Sibelius, Finale, MuseScore, Dorico) memperlakukan notasi angka sebagai anak tiri.

Upaya-upaya konversi otomatis sebelumnya selalu membentur empat tembok besar:
1. **Ketergantungan Berat ke LilyPond**: Alat seperti `jianpu-ly` membutuhkan instalasi penuh GNU LilyPond, memakan waktu 10–30 detik per partitur, dan rentan galat kompilasi eksternal.
2. **Keruntuhan Partitur Paduan Suara (*Closed Staves*)**: Paduan suara gereja lazim ditulis dalam 2 paranada (*treble* untuk Sopran-Alto, *bass* untuk Tenor-Bass). Konverter biasa menggabungkannya menjadi akor yang tidak terbaca atau kehilangan arah suara.
3. **Manipulasi Diam-Diam (*Silent Corruption*) pada Hasil OMR**: MusicXML hasil scan OMR (Audiveris, SmartScore) sering memiliki durasi cacat (debu terbaca titik, tanda diam hantu). Konverter yang berusaha menebak not justru merusak ritme yang dinyanyikan.
4. **Lirik yang Menggumpal Tanpa Spasi**: Suku kata lirik bahasa Indonesia sering kehilangan tanda hubung atau menempel menjadi satu kata tanpa spasi antarkata.

**OpenJianpu hadir menjawab masalah tersebut secara tuntas**:
- **Kompilasi super cepat (~0,4 detik per partitur)** berbasis PyCairo vektor murni.
- **Nol manipulasi diam-diam**: Ketukan diaudit secara matematis terhadap sukat. Galat yang pasti dibersihkan secara deterministik, sedangkan cacat sumber lainnya **ditandai secara transparan** (`! m27`) di atas garis birama PDF agar dirigen langsung mengetahuinya saat latihan.
- **PUEBI & Pemecah Suku Kata Otomatis**: Memecah kata majemuk yang lengket secara cerdas berdasarkan hitungan not bersuara.

---

## 🚀 Inovasi Rekayasa & Keunggulan

### 1. Mesin Render Vektor Mandiri (PyCairo)
- **Bebas LilyPond**: Menghasilkan garis balok, busur melisma, hairpin dinamika, dan angka beroktaf langsung ke PDF vektor tajam.
- **Algoritma Anti-Tabrakan Lirik**: Teks lirik dihitung dengan *forward-backward pass* dan penskalaan ukuran font dinamis (dari 9,5pt hingga 6,5pt) agar suku kata tidak pernah menabrak batas birama atau not di sampingnya.
- **Simbol Musik Lengkap**: Mendukung titik oktaf, garis miring kres/mol, busur melisma, dinamika (`p`, `f`, `mf`, hairpin `<` dan `>`), fermata, garis birama ganda/penutup, dan tanda kamar ulangan (1 & 2).

### 2. Pemisahan Jalur Suara SATB Otomatis
- **Pemisahan Paranada Tertutup (*Closed Score*)**: Membaca partitur dua staf dan secara cerdas memisahkannya menjadi 4 suara mandiri (Sopran, Alto, Tenor, Bass) berdasarkan kunci, median register nada, dan nomor suara.
- **Deteksi Divisi Akor**: Suara yang memuat akor polifonik pada $\ge 20\%$ birama otomatis dipecah menjadi suara paralel (misal S1/S2 atau S/A).
- **Penanganan Akor Sesekali**: Jika akor polifonik hanya muncul sesekali, keluarga Bass mengambil nada terendah dan suara atas mengambil nada tertinggi, dengan durasi not dasar yang diwariskan secara tepat.

### 3. Sukat & Satuan Ketuk Tunggal (`meter.py`)
- **Pembagian Kelompok Balok yang Presisi**: Sukat mengatur batas balok (*beam*), misal $7/8 = 2+2+3$, $9/8 = 3+3+3$, $6/8 = 3+3$. Garis balok tidak pernah menyeberang batas kelompok ketuk.
- **Titik Perpanjangan & Diam Sub-Ketuk Berbalok**: Titik dan tanda diam yang bernilai pecahan sub-ketuk ikut berbalok di atasnya (contoh: `3 .̅ 3̅` pada *Puji Syukur 347b*, `0̅ 3̅` pada *PS 390b*).
- **Sukat Majemuk /8 (PML & Yamuger)**: Opsi `--beat-unit quarter` (bawaan) memperlakukan 6/8 sebagai 2 ketukan majemuk bertitik ($\overline{1\ 2\ 3}\ \overline{4\ 5\ 6}$), sedangkan `--beat-unit denominator` melayani 6/8 tempo lambat (6 ketukan polos).

### 4. Pemulihan Deterministik & Penanda Cacat Transparan
- **Diam Hantu di Ujung Birama**: Membuang tanda diam palsu akibat OMR bila penghapusannya membuat jumlah durasi tepat sama dengan kapasitas birama.
- **Triol 1/8 Tak Berkurung**: Memulihkan notasi triol jika 3 not bernilai sama memiliki kelebihan tepat 1 not dan kelompoknya unik.
- **Penanda Birama Cacat (`! m<nomor>`)**: Bila ada birama yang tetap meluap dari sumbernya, OpenJianpu **tidak menebak nada**, melainkan mencetak `! m27` di atas garis birama PDF.

### 5. Mesin Lirik PUEBI & Pemecah Kata Lengket
- **Kaidah Fonotaktik PUEBI**: Mengintegrasikan aturan baku pemenggalan kata Indonesia (`V-V`, `V-KV`, `VK-KV`, `VK-KKV` dengan digraf `ng`, `ny`, `sy`, `kh`, `gh` yang tidak pernah dipisah).
- **Pemulihan Kata Lengket OMR (`tambal_lirik.py`)**: Menggunakan jumlah not kosong di depan token sebagai verifikator eksak untuk memecah kata majemuk (akurasi 99,1%).
- **Pemisahan CamelCase**: Memisahkan kata yang menempel akibat huruf kapital, misal `keHadiratMu` $\rightarrow$ `ke Hadirat-Mu` dan `padaNya` $\rightarrow$ `pada-Nya`.

---

## 🛠️ Arsitektur Alur Kerja

```
                               ┌────────────────────────────────┐
                               │   MusicXML / MXL / PDF Balok   │
                               └───────────────┬────────────────┘
                                               │
                                               ▼
                                ┌──────────────────────────────┐
                                │   xml_parser & degreelib     │
                                │   - Pemetaan Solmisasi Do=X  │
                                │   - Perutean SATB 4 Suara    │
                                │   - Pemecah Divisi Akor      │
                                └──────────────┬───────────────┘
                                               │
                      ┌────────────────────────┴────────────────────────┐
                      ▼                                                 ▼
       ┌──────────────────────────────┐                  ┌──────────────────────────────┐
       │      Audit Ketukan & Sukat   │                  │     Mesin Lirik PUEBI        │
       │   - Pembersihan Diam Hantu   │                  │   - Pemecah Kata Lengket     │
       │   - Pemulihan Triol 1/8      │                  │   - Pemisah Batas Huruf Besar│
       │   - Penanda Birama (! mX)    │                  │   - Opsi --lyrics-file       │
       └──────────────┬───────────────┘                  └──────────────┬───────────────┘
                      │                                                 │
                      └────────────────────────┬────────────────────────┘
                                               │
                                               ▼
                                ┌──────────────────────────────┐
                                │   Model JSON NotAngkaScore   │
                                └──────────────┬───────────────┘
                                               │
                                               ▼
                                ┌──────────────────────────────┐
                                │    Mesin Vektor PyCairo      │
                                │   - Tata Letak Birama/Sistem │
                                │   - Anti-Tabrakan Teks Lirik │
                                │   - Balok, Busur, Ornamen    │
                                └──────────────┬───────────────┘
                                               │
                                               ▼
                                ┌──────────────────────────────┐
                                │    PDF Not Angka Vektor      │
                                └──────────────────────────────┘
```

---

## 📦 Instalasi

### 1. Dependensi Sistem
OpenJianpu membutuhkan pustaka grafis `cairo` dan fon standar Liberation:

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
  Pustaka `pycairo` terinstal otomatis dalam bentuk wheel siap pakai melalui `pip`.

### 2. Memasang Paket Python
Klon repositori dan pasang ke lingkungan Python Anda:
```bash
git clone https://github.com/Alvnvnc/OpenJianpu.git
cd OpenJianpu
pip install .
```

---

## 💻 Panduan Pemakaian CLI

Perintah utama adalah `openjianpu` (perintah `notangka` juga aktif sebagai alias identik):

### 1. Konversi MusicXML ke PDF Not Angka
```bash
openjianpu convert lagu.musicxml -o lagu_notangka.pdf
```

#### Opsi-Opsi Penting:
| Parameter | Keterangan | Bawaan |
|---|---|---|
| `-o, --output` | Lokasi berkas PDF keluaran | `<nama_masukan>_notangka.pdf` |
| `--title` | Menimpa judul partitur | Diambil dari MusicXML |
| `--composer` | Menimpa nama komposer | Diambil dari MusicXML |
| `--lyricist` | Menimpa nama penulis syair/lirik | Diambil dari MusicXML |
| `--beat-unit` | Satuan ketuk cetak: `quarter` atau `denominator` | `quarter` |
| `--lyrics-file` | Berkas teks syair bersih untuk menimpa lirik | `None` |
| `--no-tambal-lirik` | Matikan pemecah kata lengket PUEBI | `False` (aktif) |
| `--save-json` | Simpan representasi data skema JSON | `None` |

### 2. Audit Ketukan dan Sukat (`check`)
Memeriksa apakah jumlah durasi not di tiap birama dan suara cocok dengan kapasitas sukatnya:
```bash
openjianpu check lagu.musicxml -v
```

### 3. Alur JSON Perantara Dua Arah
Anda dapat mengekstrak partitur ke format JSON bersih, menyuntingnya secara manual atau terprogram, lalu merendernya kembali ke PDF:
```bash
# 1. Ekstrak MusicXML ke JSON
openjianpu xml2json lagu.musicxml -o lagu.json

# 2. Render JSON kembali ke PDF
openjianpu render lagu.json -o hasil_akhir.pdf
```

### 4. Penyelarasan Lirik Eksternal (`--lyrics-file`)
Bila lirik pada berkas MusicXML sumber rusak parah, sediakan teks syair bersih (`syair.txt`):
```text
# Baris umum: berlaku serentak untuk semua suara
Ma-lam ku-dus, su-nyi se-nyap

# Khusus suara tertentu:
S: Kha-las dan mu-li-a
A 2: Bait ke-dua khu-sus al-to

# Simbol khusus:
# '_' adalah melisma (not tanpa suku kata)
# '|' pemisah visual birama (diabaikan)
```
Lalu jalankan:
```bash
openjianpu convert lagu.musicxml --lyrics-file syair.txt -o lagu.pdf
```

---

## 🎼 Konvensi Cetak Not Angka Indonesia

OpenJianpu mematuhi standar not angka Indonesia (mengacu pada kaidah cetak **Pusat Musik Liturgi / PML Yogyakarta**, **Yamuger**, dan **lagumisa.web.id**):

| Elemen | Notasi Cetak | Penjelasan |
|---|---|---|
| **Tinggi Nada** | `1 2 3 4 5 6 7` | Solmisasi relatif terhadap nada dasar (*Do, Re, Mi, Fa, Sol, La, Si*) |
| **Tanda Diam** | `0` | Diam / istirahat; diam sub-ketuk diberi balok (`0̅`) |
| **Titik Oktaf** | `1̇` / `1̣` | Titik tepat di atas (oktaf tinggi) atau di bawah (oktaf rendah) |
| **Kromatis** | `1/` (kres), `7\` (mol) | Garis miring memotong angka menunjukkan nada kromatis naik/turun |
| **Titik Nilai** | `1 .` / `3 .̅` | Titik perpanjangan nada; sub-ketuk mewarisi garis balok |
| **Garis Balok** | $\overline{1\ 2}$, $\overline{\overline{1\ 2}}$ | Garis horizontal di atas angka untuk not 1/8 dan 1/16 |
| **Sukat Majemuk (6/8)** | $\overline{1\ 2\ 3}\quad \overline{4\ 5\ 6}$ | Disatukan dalam kelompok 3 not 1/8 (2 ketuk majemuk per birama) |
| **Penanda Cacat** | `! m27` | Penanda visual di atas garis birama bila durasi sumber meluap |

---

## 🐍 Penggunaan via Python API

Gunakan OpenJianpu langsung di dalam proyek Python atau backend aplikasi web Anda:

```python
from openjianpu import (
    parse_musicxml_to_score,
    NotAngkaRenderer,
    check_score,
    apply_lyrics_file
)

# 1. Parse berkas MusicXML menjadi model skor data
score = parse_musicxml_to_score("misa.musicxml", beat_unit="quarter")

# 2. Audit irama & birama
report = check_score(score)
print(f"Total birama: {len(score.measures)}, Birama meluap: {report.n_over}")

# 3. Render langsung ke PDF vektor
renderer = NotAngkaRenderer(score, "misa_notangka.pdf")
renderer.render()
print("PDF Vektor Not Angka berhasil dihasilkan.")
```

---

## 📊 Tolok Ukur Korpus & Verifikasi Empiris

Keandalan OpenJianpu telah diuji secara menyeluruh pada korpus nyata:
- **259 partitur paduan suara MusicXML nyata** terkonversi dengan **0 kali crash / kegagalan**.
- **67 uji otomatis (*regression tests*)** mencakup kromatis, partitur tertutup dua paranada, birama gantung (*anacrusis*), triol, dan skala font adaptif.
- **Audit Pemulihan Irama**: Pada 1.075 suara-birama yang meluap dari hasil OMR:
  - **123 tanda diam hantu** berhasil dibersihkan secara aman.
  - **59 triol tak berkurung** berhasil dipulihkan secara deterministik.
  - **Penurunan 93 kasus cacat luapan** tanpa mengubah satu nada pun yang dinyanyikan.

---

## 📄 Lisensi

Proyek ini didistribusikan di bawah lisensi terbuka **MIT License** - lihat berkas [LICENSE](LICENSE) untuk ketentuan lengkap.

Dibuat dengan dedikasi oleh **Alvin Vincent** & komunitas musik paduan suara Indonesia.
