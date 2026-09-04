# OpenJianpu (Bahasa Indonesia)

[English Version](README.md) | **Bahasa Indonesia**

**OpenJianpu** adalah mesin konversi dan penata huruf (*engraving engine*) vektor mandiri yang mengubah partitur **MusicXML** dan not balok menjadi **Not Angka** (*Jianpu / 简谱*) berstandar penerbitan tinggi.

Dirancang khusus untuk paduan suara (SATB), musik liturgi (gaya *Puji Syukur*, *Madah Bakti*, *Kidung Jemaat*, dan *lagumisa.web.id*), OpenJianpu merender PDF vektor tajam secara instan menggunakan PyCairo—**100% mandiri tanpa membutuhkan instalasi LilyPond**.

---

## Keunggulan Utama

- **⚡ Mesin Render Vektor Mandiri (PyCairo)**: Mengonversi partitur dalam waktu kurang dari 0,5 detik langsung menjadi PDF vektor resolusi tinggi. Tidak membutuhkan LilyPond.
- **🎼 Tata Letak Paduan Suara SATB Otomatis**: Pemisahan sistem otomatis, penataan suara Sopran, Alto, Tenor, Bass (baik paranada terbuka maupun tertutup), dan pembagian divisi akor otomatis.
- **⏱️ Pembacaan Ketukan & Audit Irama Sadar-Sukat**:
  - Mendukung sukat sederhana (2/4, 3/4, 4/4) maupun sukat majemuk (6/8, 9/8, 12/8).
  - Pemulihan deterministik aman: membuang tanda diam hantu (*phantom rests*) di ujung birama dan memulihkan triol 1/8 tak berkurung jika kandidatnya tunggal.
  - Penanda transparan: birama yang isinya melebihi sukat diberi penanda `! m27` di atas garis birama agar cacat sumber terlihat jelas saat latihan paduan suara dan tidak mengalami manipulasi diam-diam (*silent corruption*).
- **📝 Penanganan Lirik Cerdas & Kaidah PUEBI**:
  - Pemecahan suku kata otomatis pada MusicXML hasil OMR menggunakan aturan pemenggalan PUEBI (`silabel.py` dan `tambal_lirik.py`).
  - Pemisahan batas huruf kecil ke kapital (misal `keHadiratMu` $\rightarrow$ `ke Hadirat-Mu`).
  - Fitur `--lyrics-file`: menempelkan teks syair bersih suku kata demi suku kata secara presisi ke not bersuara.
- **🔍 Format Antara JSON Dua Arah**: Mendukung ekspor ke skema JSON (`xml2json`) dan cetak ulang ke PDF (`render`), memudahkan integrasi dengan aplikasi web atau penyuntingan manual.

---

## Instalasi

### 1. Dependensi Sistem
OpenJianpu memerlukan pustaka grafis `cairo` dan fon standar Liberation:

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
  Pustaka `pycairo` terinstal otomatis melalui wheel `pip`.

### 2. Pemasangan Pustaka Python
Klon repositori dan pasang secara lokal:
```bash
git clone https://github.com/Alvnvnc/OpenJianpu.git
cd OpenJianpu
pip install .
```

---

## Panduan Penggunaan CLI

Perintah utama adalah `openjianpu` (perintah `notangka` juga tersedia sebagai alias):

### 1. Konversi MusicXML ke PDF Not Angka Langsung
```bash
openjianpu convert lagu.musicxml -o lagu_notangka.pdf
```
*Opsi Tambahan:*
- `--save-json lagu.json`: Menyimpan representasi JSON perantara.
- `--title "Judul Lagu"`: Menimpa judul partitur.
- `--lyrics-file syair.txt`: Menempelkan teks lirik bersih eksternal.
- `--beat-unit {quarter,denominator}`: Menentukan satuan ketuk cetak (bawaan: `quarter`).

### 2. Audit Ketukan dan Birama (Audit Check)
Memeriksa apakah kapasitas tiap birama di MusicXML sesuai dengan sukatnya:
```bash
openjianpu check lagu.musicxml -v
```

### 3. Alur JSON Perantara
```bash
# Ekstrak MusicXML ke JSON bersih
openjianpu xml2json lagu.musicxml -o lagu.json

# Render JSON kembali ke PDF
openjianpu render lagu.json -o lagu.pdf
```

---

## Konvensi Cetak Not Angka Indonesia

OpenJianpu mengikuti konvensi baku not angka Indonesia (mengacu pada standar **Pusat Musik Liturgi / PML Yogyakarta**, **Yamuger**, dan **lagumisa.web.id**):

| Elemen | Simbol / Notasi | Keterangan |
|---|---|---|
| **Tinggi Nada** | `1 2 3 4 5 6 7` | Solmisasi relatif (*Do, Re, Mi, Fa, Sol, La, Si*) |
| **Tanda Diam** | `0` | Berhenti bernyanyi / jeda ketukan |
| **Titik Oktaf** | `1̇` (atas), `1̣` (bawah) | Titik di atas/bawah angka untuk membedakan oktaf |
| **Garis Balok** | $\overline{1\ 2}$, $\overline{\overline{1\ 2}}$ | Garis horizontal di atas angka bernilai not 1/8 dan 1/16 |
| **Sukat Majemuk (6/8)** | $\overline{1\ 2\ 3}\quad \overline{4\ 5\ 6}$ | Disatukan dalam kelompok 3 not 1/8 (2 ketuk majemuk per birama) |
| **Birama Meluap** | `! m27` | Penanda visual di atas garis birama bila durasi sumber melebihi sukat |

---

## Contoh Format Berkas Lirik (`--lyrics-file`)

Format berkas lirik teks bersih (`syair.txt`):
```text
# Baris komentar dan baris kosong diabaikan
# Tanpa awalan: berlaku serentak untuk semua suara
Ma-lam ku-dus, su-nyi se-nyap

# Awalan suara khusus
S: Ha-nya sop-ran yang me-nya-nyi-kan ba-ris i-ni
2: Bait ke-dua di-tu-lis de-ngan a-wal-an nomor
A 2: Bait ke-dua khu-sus al-to

# Karakter khusus:
# '_' adalah melisma (not tanpa suku kata)
# '|' diabaikan (dapat dipakai sebagai pemisah birama visual)
```

---

## Penggunaan via Python API

OpenJianpu dapat diimpor langsung sebagai pustaka Python di dalam skrip atau backend web:

```python
from openjianpu import parse_musicxml_to_score, NotAngkaRenderer, check_score

# 1. Baca partitur MusicXML
score = parse_musicxml_to_score("partitur.musicxml")

# 2. Audit irama
report = check_score(score)
if not report.ok:
    print(f"Peringatan: terdapat {report.n_over} birama yang meluap.")

# 3. Render ke PDF Vektor
renderer = NotAngkaRenderer(score, "keluaran.pdf")
renderer.render()
```

---

## Pengujian Mandiri

Jalankan seluruh rangkaian uji otomatis (*regression tests*):
```bash
pytest
```

---

## Lisensi

Repositori ini dirilis di bawah lisensi terbuka **MIT License** - lihat berkas [LICENSE](LICENSE) untuk ketentuan lengkap.

Dibuat oleh **Alvin Vincent** bersama komunitas paduan suara & musik liturgi Indonesia.
