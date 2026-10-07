# SwiftGet — Download Manager Lintas Platform

Aplikasi desktop (Python + Qt) untuk mengelola unduhan seperti Internet Download Manager, lengkap dengan **extension browser**,
**pengunduh video/audio** (pilih resolusi & format), dan **manajemen hasil unduhan** (kategori, riwayat, pencarian, antrean).
Berjalan di macOS, Windows, dan Linux.

> **Status pengujian jujur:** mesin unduhan (multi-koneksi, pause/resume, checksum, nama unik, server extension) sudah diuji otomatis
> (`python -m tests.test_engine`). Antarmuka Qt dan extension ditulis lengkap, tetapi belum diuji di layar nyata. Kalau ada tampilan yang
> janggal saat pertama kali dijalankan, laporkan dan akan mudah diperbaiki.

---

## Fitur

**Mesin unduhan**
- Multi-koneksi hingga 32 per file (file dipecah jadi *chunk*, ditarik paralel, dengan penyeimbangan beban otomatis)
- Pause / lanjut, **resume bahkan setelah aplikasi ditutup**, deteksi file berubah di server (ETag/Last-Modified)
- **Deteksi duplikat:** kalau URL/video yang sama sudah ada di daftar atau filenya sudah ada di disk, muncul dialog dengan pilihan
  *simpan dengan nomor* (`Judul (1).mp4`), *ganti file lama* (timpa), *buka folder file sebelumnya*, atau batal. Berlaku untuk file biasa dan video.
- Retry otomatis dengan jeda bertahap, pengecekan ruang disk, nama file unik otomatis (`file (1).zip`)
- Batas kecepatan global, jumlah unduhan bersamaan, prioritas antrean (naik/turun)
- Jadwal mulai (pilih tanggal & jam), verifikasi **checksum** (SHA-256 / SHA-1 / MD5)

**Pengenal tautan otomatis (Analisis URL)**
- File langsung (zip, exe, dmg, iso, pdf, dll.)
- **Resolver file hosting:** Google Drive (termasuk file besar bertoken konfirmasi, Docs/Sheets/Slides → PDF/XLSX/PPTX), MediaFire, Dropbox, OneDrive/SharePoint, GitHub (blob → raw), Pixeldrain, SourceForge
- **Video & audio (yt-dlp, 1000+ situs):** pilih resolusi (perkiraan ukuran ditampilkan), format video (MP4/MKV/WebM), audio saja (MP3, M4A, Opus, FLAC, WAV, atau asli), playlist, subtitle, metadata, cover
- Halaman berisi banyak file → dipindai, lalu kamu centang mana yang mau diunduh

**Manajemen hasil unduhan**
- Subfolder kategori otomatis: Video, Musik, Dokumen, Arsip, Program, Gambar, Lainnya
- Sidebar filter (status & kategori) dengan penghitung, pencarian instan, urut kolom
- Riwayat permanen (SQLite), panel detail dengan peta segmen, buka file / tampilkan di folder
- Hapus dari daftar *atau* beserta file, unduh ulang, bersihkan yang selesai

**Kenyamanan**
- System tray + notifikasi, deteksi URL yang disalin ke clipboard, seret & lepas tautan ke jendela
- Tindakan setelah antrean selesai: tutup aplikasi / sleep / matikan komputer (dengan hitung mundur pembatalan)
- Tema **Glass** (gelap/terang, gaya Liquid Glass Tahoe), plus tema Gelap & Terang klasik; grafik kecepatan, info disk
- **Properti per unduhan** (klik kanan): ubah jumlah koneksi, folder tujuan, dan nama file kapan saja, termasuk untuk unduhan yang gagal
  atau sudah selesai (file dipindahkan). Unduhan aktif dijeda sebentar lalu otomatis dilanjutkan.

**Extension browser (Chrome, Edge, Brave, Opera, Vivaldi, Arc, Firefox)**
- Mengambil alih unduhan browser (dengan cookies & referer ikut terkirim, jadi situs yang butuh login tetap bisa)
- Tombol **Unduh** melayang di atas setiap video
- Menu klik kanan: *Unduh dengan SwiftGet* (tautan), *Unduh media* (video/audio), *Unduh video halaman ini*
- Popup menampilkan stream HLS/DASH/MP4 yang terdeteksi di tab
- Jika aplikasi tidak aktif, unduhan otomatis dilanjutkan browser seperti biasa
- **Safari:** tidak memakai extension. Salin URL → SwiftGet mendeteksinya dari clipboard (notifikasi → klik), atau tempel/seret ke aplikasi

---

## Instalasi (macOS Intel / Windows / Linux)

Butuh **Python 3.10+** (disarankan 3.12).

```bash
cd swiftget
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # membaca pyproject.toml (sama dengan: pip install -e .)
python run.py                      # atau: python -m swiftget  /  swiftget
```

**FFmpeg** (untuk menggabung video+audio resolusi tinggi dan konversi MP3). **Tidak perlu Homebrew.** `pip install -r requirements.txt`
sudah memasang paket `imageio-ffmpeg` yang membawa binary FFmpeg (termasuk Mac Intel), dan SwiftGet memakainya otomatis.
Urutan pencarian: path di Pengaturan › Video → FFmpeg di PATH → `/usr/local/bin`, `/opt/homebrew/bin` → binary dari `imageio-ffmpeg`.

Alternatif jika mau FFmpeg sendiri: unduh binary statis (macOS Intel: https://evermeet.cx/ffmpeg/, Windows: https://www.gyan.dev/ffmpeg/builds/),
lalu pilih filenya di **Pengaturan › Video & Audio › Lokasi FFmpeg**. Pengguna Linux: `sudo apt install ffmpeg`.

Tanpa FFmpeg video tetap bisa diunduh, tetapi hanya format gabungan (biasanya sampai 720p) dan tanpa konversi audio.

---

## Memasang extension browser

**Tersambung otomatis, tanpa salin-tempel token.** Cukup:

1. Buka **Pengaturan › Browser** dan klik tombol browsermu (Chrome, Edge, Brave, atau Firefox). SwiftGet menyiapkan folder
   `~/SwiftGet Extension`, menyalin path-nya ke clipboard, dan membuka halaman extensions browser.
2. Di halaman itu: aktifkan **Developer mode** → **Load unpacked** → pilih folder tadi. (Firefox: *Load Temporary Add-on* → `manifest.json`.)
3. SwiftGet langsung menampilkan **"Izinkan extension terhubung?"**. Klik **Ya**. Selesai.

Saat pertama kali membuka SwiftGet, aplikasi juga menawarkan langkah ini. Tombol *Putuskan semua extension* di tab yang sama mencabut semua izin.

**Pemasangan sekali klik** (tanpa Developer mode) hanya mungkin lewat toko resmi, karena Chrome/Edge memblokir pemasangan otomatis dari luar
toko. Panduan menerbitkan ke Chrome Web Store, Edge Add-ons, dan Firefox Add-ons ada di [`STORE_PUBLISHING.md`](STORE_PUBLISHING.md).
Begitu terbit, isi URL toko di `EXT_STORE` (`swiftget/config.py`) dan tombol di Pengaturan langsung membuka halaman toko.

Agar extension selalu terhubung, aktifkan **Jalankan SwiftGet saat login** (Pengaturan › Umum; installer Windows juga menawarkannya).
Bila SwiftGet tidak berjalan, unduhan otomatis dilanjutkan oleh browser seperti biasa.

Chrome mungkin menampilkan peringatan kuning soal `background.scripts`; itu normal karena satu manifest dipakai untuk Chrome dan Firefox.
Paket khusus toko (manifest bersih per browser) dibuat dengan `python packaging/pack_extension.py`.

---

## Cara pakai

- **Tambah unduhan:** `Ctrl/Cmd + N` atau tombol **Tambah URL**. Tempel URL, tunggu analisis otomatis, lalu **Mulai unduh**.
  Tempel banyak URL (satu per baris) untuk menambah semuanya sekaligus.
- **Video:** setelah analisis muncul kartu video. Pilih tab *Video* (resolusi + format) atau *Audio* (MP3/M4A/…).
  Pilihan **Kompatibilitas** (default): hasil **H.264 + AAC dalam MP4**, bisa diputar di QuickTime, iPhone, dan Windows. Resolusi yang hanya
  tersedia dalam VP9/AV1 (mis. 1440p/4K di YouTube) otomatis dikonversi ke H.264 setelah diunduh (lebih lama). Pilih *Kualitas maksimum*
  kalau kamu memakai VLC dan mau file asli tanpa konversi.
- **Ganti resolusi/format dari daftar:** klik kanan sebuah video › *Ubah resolusi / format…*. Pilih Video/Audio, resolusi, format, dan
  kompatibilitas; tombol *Muat resolusi asli dari video* menampilkan resolusi yang benar-benar tersedia beserta perkiraan ukuran.
  Untuk unduhan yang belum selesai, pengaturan baru langsung dipakai. Untuk yang sudah selesai, hasilnya ditambahkan sebagai unduhan
  baru (file lama tetap ada). Nama file video memuat resolusinya, mis. `Judul [1080p].mp4`.
- **Kompatibel vs kualitas asli:** pilih di kartu video atau jadikan bawaan di Pengaturan › Video & Audio › *Mode video bawaan*.
  *Kompatibel* = H.264 + AAC (bisa diputar di QuickTime, iPhone, Windows). Di YouTube, H.264 hanya sampai 1080p; untuk 1440p/4K
  videonya dikonversi ulang ke H.264 (butuh waktu dan ada sedikit penurunan kualitas). *Kualitas asli* = VP9/AV1 apa adanya, paling
  bagus dan hemat ukuran, tapi sering gagal diputar di QuickTime/iPhone, cocok untuk VLC/IINA.
- **Koneksi:** file biasa memakai 8 koneksi, **video (YouTube dll.) memakai 1 koneksi** karena banyak situs menolak koneksi paralel.
  Bisa diubah di dialog tambah unduhan, di Pengaturan, atau per unduhan lewat klik kanan › *Properti*.
- **Dari browser:** klik unduhan seperti biasa (otomatis ditangkap), atau tekan tombol Unduh di atas video.
- **Kelola:** klik kanan sebuah unduhan untuk jeda/lanjut, prioritas, unduh ulang, salin tautan, atau hapus. Klik dua kali untuk membuka file.
- **Filter:** sidebar kiri (Sedang berjalan, Antrean, Selesai, Gagal, dan tiap kategori). Cari dengan `Ctrl/Cmd + F`.
- **Tutup jendela** = sembunyi ke tray. Keluar sungguhan lewat menu tray → *Keluar*.

Data (pengaturan + riwayat) tersimpan di:
`~/Library/Application Support/SwiftGet` (macOS) · `%APPDATA%\SwiftGet` (Windows) · `~/.config/SwiftGet` (Linux).

---

## Tampilan Glass (Tahoe)

Liquid Glass asli (pembiasan cahaya dan efek lensa) adalah komponen native Apple (`NSGlassEffectView`) yang tidak bisa digambar oleh Qt.
SwiftGet memberi dua tingkat:

1. **Tema Glass (semua OS, default):** latar aurora lembut, panel melayang berbingkai tipis semi-transparan, sudut sangat bulat,
   tombol kapsul. Pilih lewat tombol *Tema* (berputar Glass gelap → Glass terang → Gelap → Terang) atau Pengaturan › Umum.
2. **Efek kaca native macOS (eksperimental, opsional):** `pip install -r requirements-mac.txt`, lalu aktifkan
   *Efek kaca native macOS* di Pengaturan › Umum dan mulai ulang. Di macOS 26 memakai `NSGlassEffectView` (Liquid Glass asli) bila ada,
   selain itu blur `NSVisualEffectView`. Belum teruji; bila jendela jadi aneh, hapus `"native_glass": true` dari `settings.json`.

---

## Struktur proyek

```
pyproject.toml             identitas proyek: versi, dependensi, entry point (sumber versi tunggal)
run.py                     peluncur tipis (isi aplikasi ada di swiftget/app.py)
swiftget/
  config.py                pengaturan, kategori
  engine.py                mesin multi-koneksi (FileJob) + yt-dlp (MediaJob)
  resolvers.py             plugin per situs (Drive, MediaFire, …)
  analyzer.py              analisis URL → file / media / daftar tautan
  manager.py               antrean, jadwal, prioritas, riwayat
  server.py                server lokal 127.0.0.1 untuk extension
  ui/                      jendela, dialog, tabel kustom, tema, ikon
extension/                 extension browser (Manifest V3, pairing otomatis)
STORE_PUBLISHING.md        panduan menerbitkan extension ke toko
tests/test_engine.py       tes otomatis engine
packaging/                 build.py, make_icons.py
.github/workflows/         build otomatis macOS/Windows/Linux
```

### Menambah resolver situs baru

Satu fungsi saja di `swiftget/resolvers.py`:

```python
@resolver("NamaSitus", r"namasitus\.com/file/")
def namasitus(net, url):
    html = net.get(url).text
    direct = re.search(r'href="(https://cdn[^"]+)"', html).group(1)
    return Resolved(direct, referer=url)
```

---

## Membangun aplikasi (installer)

Hasil build **bukan** folder `.exe + _internal` mentah, melainkan paket siap bagikan:

| OS | Hasil di `dist/release/` |
|---|---|
| Windows | `SwiftGet-Setup-<versi>.exe` (installer: Start Menu, shortcut desktop, uninstaller, opsi jalan saat login) + `…-windows-portable.zip` |
| macOS | `SwiftGet-<versi>-macos-<arsitektur>.dmg` (seret ke Applications) |
| Linux | `SwiftGet-<versi>-linux-<arsitektur>.tar.gz` |

Folder `_internal` tetap ada (itu cara kerja PyInstaller), tetapi dengan installer ia tersimpan rapi di folder instalasi dan tidak terlihat pengguna.

**Lokal:** `pip install -r requirements-dev.txt` lalu `python packaging/build.py` (jalankan di OS target; Windows butuh
[Inno Setup 6](https://jrsoftware.org/isdl.php) agar installer terbentuk, tanpa itu hanya zip portabel).

**Otomatis lewat GitHub Actions** (disarankan, bisa bangun semua OS tanpa perangkatnya). Build & rilis hanya terjadi kalau **angka
`version` di `pyproject.toml` berubah**:

| Yang kamu push | Hasil |
|---|---|
| Perubahan file lain saja (kode, README, dll.) | workflow **tidak jalan** sama sekali |
| `pyproject.toml` diubah, tapi bukan versinya (mis. dependensi) | workflow jalan sebentar, lalu semua job **dilewati** |
| Angka `version` di `pyproject.toml` berubah | **build 4 OS + Release otomatis** (tag `v<versi>`) |

Cara merilis versi baru:
1. Ubah baris `version = "1.2.1"` di `pyproject.toml`, mis. menjadi `"1.2.2"`.
2. `git add . && git commit -m "Rilis 1.2.2" && git push`
3. Tunggu ±10-15 menit. Hasilnya muncul di halaman **Releases** dengan tag `v1.2.2` (dibuat otomatis), berisi installer Windows, `.dmg` Mac Intel
   dan Apple Silicon, paket Linux, dan paket extension. Memantau prosesnya: tab *Actions*.

### Alur build (yang terjadi di balik layar)
```
push → GitHub cek: pyproject.toml ikut berubah?   tidak → selesai (tidak ada yang jalan)
          │ ya
          ▼
  job "version"   baca version sekarang & version di commit sebelumnya → berubah? tidak → semua job dilewati
          │ ya (validasi format 1.2.3)
          ▼
  ┌─ job "app" (paralel, 4 mesin) ──────────────────────┐   job "extension"
  │ Windows │ Mac Intel │ Mac Apple Silicon │ Linux     │   (zip untuk toko extension)
  │ pasang dependensi dari pyproject.toml ([dev])       │
  │ tes engine → PyInstaller → kemas (installer/dmg/tar)│
  └──────────────────────────────────────────────────────┘
          ▼
  job "release"   kumpulkan semua file → buat tag v<versi> → buat/perbarui Release → lampirkan file
```
Walau satu OS gagal, file dari OS lain tetap dilampirkan. Tombol *Run workflow* di tab Actions membangun ulang versi yang tertulis di
`pyproject.toml` tanpa mengubah apa pun. Mendorong ulang versi yang sama memperbarui file di Release itu. Jika job `release` gagal dengan
error izin (403), buka repositori › *Settings › Actions › General › Workflow permissions* › pilih *Read and write permissions*.

### Fungsi `pyproject.toml`
File ini adalah "kartu identitas" proyek (standar PEP 621) dan dipakai di banyak tempat sekaligus:

| Bagian | Gunanya |
|---|---|
| `[project] version` | **Satu-satunya sumber versi.** Dibaca aplikasi (pojok kanan bawah), `build.py` (nama file hasil build, info `.exe`), dan workflow (tag Release) |
| `[project] dependencies` | Daftar pustaka yang dipasang oleh `pip install -r requirements.txt` (isinya hanya `-e .`) |
| `[project.optional-dependencies]` | `dev` (PyInstaller, Pillow untuk build) dan `mac` (efek kaca native); dipasang lewat `pip install -e ".[dev]"` |
| `[project] name, description, readme, urls, classifiers` | Metadata proyek (tampil di GitHub/PyPI dan alat Python lain) |
| `requires-python` | Versi Python minimum (3.10) |
| `[project.gui-scripts]` | Membuat perintah `swiftget` yang membuka aplikasi setelah `pip install .`; bisa juga `python -m swiftget` |
| `[build-system]` + `[tool.setuptools…]` | Cara pip membangun paket (hanya folder `swiftget/`, bukan `extension`, `tests`, dll.) |

Menambah pustaka baru cukup menambahkannya ke `dependencies`; jangan menulis versi di tempat lain.

**Peringatan keamanan OS (wajar untuk aplikasi tanpa tanda tangan):**
- Windows SmartScreen menampilkan *"Windows protected your PC"* → klik *More info › Run anyway*. Menghilangkannya butuh sertifikat code signing
  (berbayar; proyek open source bisa mengajukan gratis lewat SignPath Foundation).
- macOS menolak membuka aplikasi dari developer tak dikenal → klik kanan aplikasi › *Open*, atau jalankan
  `xattr -cr /Applications/SwiftGet.app`. Menghilangkannya butuh Apple Developer Account (signing + notarization).

Tes engine: `python -m tests.test_engine`

---

## Batasan yang perlu kamu tahu

- **DRM** (Netflix, Disney+, Spotify, dll.) tidak bisa diunduh.
- **Kecepatan** tidak bisa melewati bandwidth internetmu. Multi-koneksi membantu bila server membatasi per koneksi; bila tidak, hasilnya setara browser.
- **Google Drive:** kuota "too many users" adalah batas dari Google. Folder belum didukung (unduh file satu per satu).
- **Mega, Terabox, torrent/magnet, FTP:** belum didukung di versi ini. Situs dengan captcha/timer sebaiknya diunduh lewat browser + extension (kamu menyelesaikan captcha, SwiftGet menangkap link finalnya).
- **yt-dlp** perlu rutin diperbarui karena situs sering berubah: *Pengaturan › Video & Audio › Perbarui yt-dlp*.
- Mengunduh dari beberapa platform bisa melanggar syarat layanan mereka, dan Chrome Web Store sering menolak extension downloader video. Untuk pemakaian pribadi, pasang manual seperti di atas. Unduh hanya file yang memang boleh kamu unduh, dan waspadai malware pada file dari hosting acak (gunakan kolom *checksum* bila penyedia memberikannya).
- Batas kecepatan berlaku langsung untuk file biasa; untuk video (yt-dlp) berlaku saat unduhan dimulai.

## Pemecahan masalah

| Masalah | Solusi |
|---|---|
| Extension: "Aplikasi tidak aktif" | Pastikan SwiftGet berjalan & port sama di extension dan Pengaturan › Browser |
| Extension: "Token salah" | Buka popup extension › *Hubungkan ke SwiftGet* (token diperbarui otomatis) |
| "Port dipakai aplikasi lain" | Ganti port di Pengaturan › Browser, lalu samakan di extension |
| Video hanya 360p/720p atau tidak ada MP3 | `pip install imageio-ffmpeg` (atau pilih path FFmpeg di Pengaturan), lalu restart SwiftGet |
| Video YouTube gagal | Perbarui yt-dlp; untuk konten berlogin pilih *Ambil cookies dari* browser kamu |
| macOS: `yt-dlp` tak bisa baca cookies Safari | Beri SwiftGet/Terminal izin *Full Disk Access* |
| Video tidak bisa diputar di QuickTime/iPhone | Unduh dengan Kompatibilitas = H.264 + AAC (default). Untuk file lama berformat VP9/Opus: klik kanan › Unduh ulang |
| Unduhan YouTube ditolak/gagal | Pastikan koneksi video = 1 (klik kanan › Properti), perbarui yt-dlp, dan coba *Ambil cookies dari* browser |
| YouTube: `HTTP Error 403: Forbidden` | SwiftGet otomatis mencoba jalur klien alternatif. Bila tetap gagal: perbarui yt-dlp, set koneksi video = 1, dan coba *Ambil cookies dari* browser. yt-dlp versi baru kadang butuh runtime JavaScript (Deno atau Node.js) untuk YouTube; cek catatan rilis yt-dlp |
| Dialog "Tambah unduhan" tidak muncul saat aplikasi di tray | Sudah diperbaiki di v1.2.1: dialog tampil sebagai jendela mandiri di depan. Bila masih tertutup, pastikan SwiftGet versi terbaru berjalan |
| Windows: "Windows protected your PC" | Normal untuk aplikasi tanpa code signing: *More info › Run anyway* |
| Extension: "Belum terhubung" | Pastikan SwiftGet berjalan, buka popup extension › *Hubungkan ke SwiftGet*, lalu klik *Ya* di aplikasi |
| Tampilan font kecil/besar | Ubah skala di pengaturan sistem; ukuran teks diatur di `theme.py` (`font-size`) |
