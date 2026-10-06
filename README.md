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
pip install -r requirements.txt
python run.py
```

**FFmpeg** (untuk menggabung video+audio resolusi tinggi dan konversi MP3). **Tidak perlu Homebrew.** `pip install -r requirements.txt`
sudah memasang paket `imageio-ffmpeg` yang membawa binary FFmpeg (termasuk Mac Intel), dan SwiftGet memakainya otomatis.
Urutan pencarian: path di Pengaturan › Video → FFmpeg di PATH → `/usr/local/bin`, `/opt/homebrew/bin` → binary dari `imageio-ffmpeg`.

Alternatif jika mau FFmpeg sendiri: unduh binary statis (macOS Intel: https://evermeet.cx/ffmpeg/, Windows: https://www.gyan.dev/ffmpeg/builds/),
lalu pilih filenya di **Pengaturan › Video & Audio › Lokasi FFmpeg**. Pengguna Linux: `sudo apt install ffmpeg`.

Tanpa FFmpeg video tetap bisa diunduh, tetapi hanya format gabungan (biasanya sampai 720p) dan tanpa konversi audio.

---

## Memasang extension browser

1. Di SwiftGet buka **Pengaturan › Browser**, klik **Salin** pada token.
2. Pasang extension dari folder `extension/`:

| Browser | Langkah |
|---|---|
| **Chrome / Brave / Opera / Vivaldi** | buka `chrome://extensions` → aktifkan *Developer mode* → **Load unpacked** → pilih folder `extension` |
| **Edge** | buka `edge://extensions` → *Developer mode* → **Load unpacked** |
| **Firefox** | buka `about:debugging#/runtime/this-firefox` → **Load Temporary Add-on** → pilih `extension/manifest.json`. Lalu di *Add-ons Manager › SwiftGet › Permissions* izinkan akses ke semua situs. (Sifatnya sementara sampai extension ditandatangani lewat addons.mozilla.org.) |
| **Safari** | tidak ada extension, lihat bagian fitur di atas |

3. Klik ikon SwiftGet → **Pengaturan**, tempel token, klik **Tes koneksi**. Harus muncul "Terhubung ✓".

Chrome mungkin menampilkan peringatan kuning soal `background.scripts` atau `browser_specific_settings`; itu normal, karena satu manifest dipakai untuk Chrome dan Firefox.

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
run.py                     titik masuk
swiftget/
  config.py                pengaturan, kategori
  engine.py                mesin multi-koneksi (FileJob) + yt-dlp (MediaJob)
  resolvers.py             plugin per situs (Drive, MediaFire, …)
  analyzer.py              analisis URL → file / media / daftar tautan
  manager.py               antrean, jadwal, prioritas, riwayat
  server.py                server lokal 127.0.0.1 untuk extension
  ui/                      jendela, dialog, tabel kustom, tema, ikon
extension/                 extension browser (Manifest V3)
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

## Membangun aplikasi mandiri

```bash
pip install -r requirements-dev.txt
python packaging/build.py          # hasil di dist/
```
PyInstaller harus dijalankan di OS target (Mac untuk `.app`, Windows untuk `.exe`). Workflow GitHub Actions di `.github/workflows/build.yml`
membangun keempat target (Mac Intel, Mac Apple Silicon, Windows, Linux) sekaligus tanpa perlu punya semua perangkatnya.
Agar `.app` tidak diblokir Gatekeeper di Mac lain perlu *code signing + notarization* (Apple Developer Account).

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
| Extension: "Token salah" | Salin ulang token dari aplikasi ke Opsi extension |
| "Port dipakai aplikasi lain" | Ganti port di Pengaturan › Browser, lalu samakan di extension |
| Video hanya 360p/720p atau tidak ada MP3 | `pip install imageio-ffmpeg` (atau pilih path FFmpeg di Pengaturan), lalu restart SwiftGet |
| Video YouTube gagal | Perbarui yt-dlp; untuk konten berlogin pilih *Ambil cookies dari* browser kamu |
| macOS: `yt-dlp` tak bisa baca cookies Safari | Beri SwiftGet/Terminal izin *Full Disk Access* |
| Video tidak bisa diputar di QuickTime/iPhone | Unduh dengan Kompatibilitas = H.264 + AAC (default). Untuk file lama berformat VP9/Opus: klik kanan › Unduh ulang |
| Unduhan YouTube ditolak/gagal | Pastikan koneksi video = 1 (klik kanan › Properti), perbarui yt-dlp, dan coba *Ambil cookies dari* browser |
| YouTube: `HTTP Error 403: Forbidden` | SwiftGet otomatis mencoba jalur klien alternatif. Bila tetap gagal: perbarui yt-dlp, set koneksi video = 1, dan coba *Ambil cookies dari* browser. yt-dlp versi baru kadang butuh runtime JavaScript (Deno atau Node.js) untuk YouTube; cek catatan rilis yt-dlp |
| Tampilan font kecil/besar | Ubah skala di pengaturan sistem; ukuran teks diatur di `theme.py` (`font-size`) |
