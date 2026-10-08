# OWNER.md — Catatan lengkap pemilik proyek SwiftGet

Dokumen ini untuk **pemilik/maintainer**: gambaran produk, keputusan desain, cara kerja teknis, cara merilis, cara merawat, dan hal-hal yang
belum teruji. Panduan pengguna ada di [`README.md`](README.md).

**Daftar isi**
1. [Ringkasan produk](#1-ringkasan-produk)
2. [Status pengujian (jujur)](#2-status-pengujian-jujur)
3. [Peta proyek](#3-peta-proyek)
4. [Cara kerja teknis](#4-cara-kerja-teknis)
5. [Extension browser](#5-extension-browser)
6. [Keamanan & privasi](#6-keamanan--privasi)
7. [Build & rilis](#7-build--rilis)
8. [Tugas rutin pemilik](#8-tugas-rutin-pemilik)
9. [Menerbitkan extension ke toko](#9-menerbitkan-extension-ke-toko)
10. [Masalah yang diketahui & risiko](#10-masalah-yang-diketahui--risiko)
11. [Checklist uji manual sebelum rilis](#11-checklist-uji-manual-sebelum-rilis)
12. [Pemecahan masalah (untuk pemilik)](#12-pemecahan-masalah-untuk-pemilik)
13. [Ide pengembangan berikutnya](#13-ide-pengembangan-berikutnya)
14. [Glosarium](#14-glosarium)

---

## 1. Ringkasan produk

**Apa:** download manager lintas platform (Windows, macOS, Linux) ala Internet Download Manager, ditulis dengan Python + Qt (PySide6).

**Tiga komponen yang saling bicara:**
```
[Extension browser (JavaScript)] ⇄ server lokal 127.0.0.1:6277 ⇄ [Aplikasi desktop (Python/Qt)]
   menangkap unduhan, tombol di video                           mesin unduh, antrean, UI, riwayat
```

**Kemampuan utama:** unduhan multi-koneksi dengan resume; resolver file hosting; pengunduh video/audio (yt-dlp) dengan pilihan resolusi/format dan
mode kompatibel H.264/AAC; playlist (induk + isi); peringatan duplikat; kategori & riwayat; extension dengan pairing otomatis; jalan otomatis
saat login di latar belakang; tema Glass.

**Keputusan desain penting (dan alasannya)**

| Keputusan | Alasan |
|---|---|
| Python + PySide6 | Satu basis kode untuk 3 OS, tampilan bagus, ekosistem yt-dlp berbahasa Python |
| yt-dlp untuk video | Mendukung ribuan situs; memelihara ekstraktor sendiri tidak realistis |
| Server lokal (bukan Native Messaging) | Jauh lebih mudah dibuat dan di-debug; diamankan dengan token + pairing + cek Origin |
| Satu manifest extension untuk Chrome & Firefox | Mengurangi pemeliharaan; paket toko dibersihkan per browser oleh `packaging/pack_extension.py` |
| Safari tanpa extension | Butuh Xcode + Apple Developer Account ($99/tahun) dan API unduhannya terbatas; solusinya clipboard/tempel URL |
| Playlist = 1 tugas induk + N tugas anak | Memakai ulang seluruh mesin media (jeda, resume, retry, properti) per video, tanpa mesin khusus |
| Cookie browser tidak dikirim untuk YouTube | Cookie dari tab yang terbuka cepat berputar dan membuat YouTube menjawab "page needs to be reloaded"; juga lebih aman bagi akun pengguna |
| `pyproject.toml` sebagai satu-satunya sumber versi | Standar Python; dibaca aplikasi, skrip build, dan CI |
| Installer (Inno Setup) untuk Windows, DMG untuk macOS | Folder `.exe + _internal` mentah terlihat tidak profesional; `_internal` tersembunyi di folder instalasi |

---

## 2. Status pengujian (jujur)

**Diuji otomatis** (`python -m tests.test_engine`, dijalankan juga di CI sebelum build):
multi-koneksi + resume + jeda, server tanpa Range, penolakan halaman HTML, checksum benar/salah, nama file unik, server extension (token, Origin, Host),
pairing (setuju/tolak/bukan-extension), ubah koneksi/lokasi/nama saat berjalan dan setelah selesai, ubah opsi media, cookie sementara untuk yt-dlp,
pemilih format H.264/AAC, deteksi duplikat (daftar + disk), mode ganti & nomor, penomoran video (dengan yt-dlp tiruan), seluruh logika playlist
(induk+isi, nama kembar, agregasi status, jeda/lanjut massal, hapus, nama playlist sama, induk kosong hilang otomatis).

Ditambah: tangga 403 (anti-hotlink, Range diblokir), jalur alternatif (daftar jalur, penyamaran kredensial di UI, pindah jalur karena proxy mati dan karena melambat dengan lanjut dari byte terakhir), dan logika intercept extension dengan API tiruan.

**Tidak pernah dijalankan oleh pembuatnya (hanya ditulis dan dicek sintaks / dijalankan terhadap tiruan):**
- tampilan Qt secara visual di semua OS (pemilik sempat menguji di macOS Intel dan Windows 11 + Chrome/Edge; perbaikan dari temuan itu sudah dimasukkan)
- extension di browser sungguhan selain yang pernah dicoba pemilik (Chrome, Edge); Firefox, Brave, Opera, Vivaldi belum
- build PyInstaller / Inno Setup / DMG / tar.gz (build pertama di GitHub Actions kemungkinan butuh satu putaran perbaikan)
- alur nyata ke YouTube, Google Drive, MediaFire, dst. (sandbox pengembangan tidak punya internet)
- konversi H.264 (ffmpeg), efek kaca native macOS, jalan otomatis saat login di tiap OS, trik fokus Windows, klik ikon saat sudah berjalan (IPC)

Semua itu masuk ke [checklist uji manual](#11-checklist-uji-manual-sebelum-rilis).

---

## 3. Peta proyek

```
SwiftGet/
├── pyproject.toml            identitas proyek + SATU-SATUNYA tempat versi + dependensi + entry point
├── run.py                    peluncur tipis → swiftget.app.main()
├── README.md                 panduan pengguna          OWNER.md   dokumen ini
├── requirements*.txt         "-e ." / "-e .[dev]" / "-e .[mac]" (membaca pyproject.toml)
├── assets/                   icon.png / .ico / .icns
├── extension/                extension browser (Manifest V3)
├── packaging/                build.py, pack_extension.py, make_icons.py, windows/swiftget.iss
├── tests/test_engine.py      tes otomatis engine
├── .github/workflows/build.yml
└── swiftget/
    ├── app.py                titik masuk: satu-instans (QLockFile + IPC), mode --background
    ├── config.py             pengaturan (settings.json), kategori, versi (dibaca dari pyproject), URL toko extension, ekspor extension
    ├── util.py               format ukuran/waktu, nama file aman, klien HTTP (Net), deteksi YouTube
    ├── models.py             Task (dataclass) + DB (SQLite)
    ├── resolvers.py          plugin per situs: Google Drive, MediaFire, Dropbox, OneDrive, GitHub, Pixeldrain, SourceForge, Mega (pesan error)
    ├── engine.py             FileJob (multi-koneksi), MediaJob (yt-dlp), RateLimiter, probe, FFmpeg, cookie sementara
    ├── analyzer.py           analisis URL → file / media / daftar tautan; data playlist
    ├── manager.py            antrean, jadwal, prioritas, riwayat, duplikat, playlist induk/anak, ubah properti
    ├── server.py             server HTTP lokal untuk extension (/ping /pair /add /media)
    ├── autostart.py          jalan saat login (registry / LaunchAgent / .desktop)
    └── ui/
        ├── main_window.py    jendela utama, tray, pairing, onboarding, IPC
        ├── dialogs.py        Tambah unduhan, Properti, Pengaturan, dialog duplikat, sambutan, hitung mundur
        ├── playlist.py       popup isi playlist
        ├── table.py          model tabel, filter, delegate (nama/progres/status)
        ├── widgets.py        sidebar, grafik kecepatan, peta segmen, latar aurora
        ├── theme.py          palet + QSS (Glass gelap/terang, Gelap, Terang)
        ├── icons.py          ikon SVG bawaan; winutil.py (bring-to-front); mac_glass.py (efek native, eksperimental)
```

### Data pengguna di komputer

| Apa | Lokasi |
|---|---|
| Pengaturan, riwayat (SQLite), kunci instans | Windows `%APPDATA%\SwiftGet` · macOS `~/Library/Application Support/SwiftGet` · Linux `~/.config/SwiftGet` |
| Hasil unduhan | `~/Downloads/SwiftGet/<Kategori>/` (bisa diubah) |
| Salinan extension untuk dipasang | `~/SwiftGet Extension` (disegarkan otomatis tiap aplikasi dibuka) |
| File cookie sementara untuk yt-dlp | folder temp OS, `sg_cookies_*.txt`, dihapus setelah dipakai |
| Jalan saat login | Windows: registry `HKCU\…\Run\SwiftGet` · macOS: `~/Library/LaunchAgents/com.swiftget.app.plist` · Linux: `~/.config/autostart/swiftget.desktop` |

---

## 4. Cara kerja teknis

### 4.1 Tugas (`Task`) dan penyimpanan
Setiap unduhan adalah `Task` yang disimpan sebagai JSON di SQLite (`models.DB`). Jenisnya (`kind`): `file`, `media` (yt-dlp), dan `playlist` (induk).
Field runtime (`speed`, `eta`, `note`, `n_items`) tidak disimpan. Status: `queued, scheduled, preparing, downloading, processing, verifying, paused, completed, error`.
Saat aplikasi dibuka, tugas yang tadinya aktif dijadikan `paused` (pengguna melanjutkan manual).

### 4.2 Mesin file (`engine.FileJob`)
1. **Resolve** URL (resolver Drive/MediaFire/dll.) → URL langsung. 2. **Probe**: request `Range: bytes=0-0` untuk tahu ukuran, dukungan resume, nama, tipe.
3. Bagi file jadi *chunk* (≥1 MB, ≤64 MB, ± 4× jumlah koneksi), tulis ke `nama.part` (pra-alokasi). 4. N thread mengambil chunk berikutnya dari antrean (penyeimbangan beban),
tiap chunk dengan retry bertahap. 5. Selesai → `os.replace` ke nama akhir, verifikasi checksum bila diisi.
Resume: status tiap chunk (`[awal, akhir, terunduh]`) disimpan; saat lanjut, ETag/ukuran dicek, jika berubah mulai ulang. Server tanpa Range → 1 koneksi tanpa resume.
Batas kecepatan global (`RateLimiter`, token bucket). Halaman HTML ditolak (bukan file). Ruang disk dicek.

### 4.3 Mesin media (`engine.MediaJob`)
- Memakai `yt_dlp.YoutubeDL` di thread; jeda = melempar pembatalan dari hook progres (file `.part` dilanjutkan yt-dlp).
- **Format:** `build_format()`. Mode *kompatibel*: `bv*[vcodec^=avc1]+ba[ext=m4a]` (H.264+AAC), fallback bertingkat. Resolusi yang tidak punya H.264 (mis. 1440p/4K YouTube)
  diunduh VP9/AV1 lalu **dikonversi** ke H.264 (`libx264`, CRF 20) oleh `_transcode`. Mode *kualitas asli* tanpa konversi.
- **FFmpeg:** dicari berurutan: Pengaturan → PATH → lokasi umum → paket pip `imageio-ffmpeg` (ikut terpasang, tidak perlu Homebrew).
- **Nama file:** `Judul [1080p].mp4` (resolusi di nama agar beda resolusi tidak bentrok). Audio tanpa tag resolusi.
- **Duplikat:** `dup="number"` → bila `Judul [..].ext` sudah ada, cari `(1)`, `(2)`, … (`_numbered_template`, memakai satu ekstraksi tanpa unduh); `dup="replace"` → `overwrites=True`.
- **YouTube 403 / jalur klien:** bila gagal dengan 403, otomatis mencoba klien alternatif `android_vr` lalu `tv` (nama klien mengikuti yt-dlp dan bisa berubah).
- **Cookie:** cookie dari extension dikonversi ke file Netscape sementara (yt-dlp menolak cookie lewat header) dan **tidak dikirim untuk YouTube** (lihat tabel keputusan).
  Cookie dari browser untuk situs yang butuh login diatur lewat Pengaturan › Video & Audio › *Ambil cookies dari*.

### 4.4 Analisis URL (`analyzer`)
Urutan: situs media dikenal / `.m3u8`/`.mpd` → yt-dlp. Lainnya: resolver → probe. Jika HTML: coba yt-dlp (halaman berisi video) → pindai tautan (`scan_links`) → "tidak ada".
`fetch_media_info`: untuk YouTube tanpa cookie + retry klien alternatif; untuk situs lain bila gagal dicoba lagi tanpa cookie. URL video yang memuat `list=` juga diambil data
playlist-nya (`playlist_summary`: judul + daftar `entries` yang dipakai membuat tugas anak; video "[Private video]" / "[Deleted video]" dilewati).

### 4.5 Playlist (induk + anak)
- `Manager.add_playlist()` (atomik di bawah lock) membuat 1 tugas induk (`kind="playlist"`, `filename` = nama folder, `final_path` = folder) dan 1 tugas `media` per video
  dengan `parent_id` = id induk, disimpan di `<Video|Musik>/<nama folder>/`.
- Judul kembar dalam satu playlist diberi `media_opts["suffix"]=" (1)"` saat pembuatan (deterministik, tanpa balapan antar unduhan paralel). Tanpa nomor urut di depan nama.
- Induk **tidak punya job**; `_refresh_playlists()` (tiap 0,5 dtk) menghitung status (aktif > antre > gagal > jeda > selesai), progres rata-rata, kecepatan, ETA, catatan "n/N selesai · x gagal".
  Induk tanpa anak otomatis dihapus. Notifikasi selesai/gagal hanya untuk induk (anak tidak memicu notifikasi sendiri).
- Operasi pada induk (jeda, lanjut, unduh ulang, hapus) diteruskan ke semua anak. Hapus + file mencoba menghapus folder bila sudah kosong.
- UI: daftar utama hanya menampilkan tugas dengan `parent_id == 0` (`Proxy.parent_id`); popup `PlaylistDialog` memakai model/delegate yang sama dengan `parent_id = id induk`.
- Anak tunduk pada batas "unduhan bersamaan" (default 3), jadi playlist diunduh bertahap.
- Nama playlist sama → `find_playlist_duplicates()` (di daftar, berdasarkan folder, atau folder berisi di disk) → dialog: ganti nama / timpa / lihat playlist lama / batal.
  "Timpa" menghapus entri lama dari daftar dan mengunduh dengan `dup="replace"` (file bernama sama ditimpa; file lain di folder tidak disentuh).

### 4.6 Duplikat unduhan tunggal
`Manager.find_duplicates()`: URL yang sama di daftar (YouTube dinormalkan ke `yt:<id>`, video juga dibandingkan resolusi/format) **atau** file bernama sama di folder tujuan
**atau** (video) file berawalan judul serupa. Dialog: nomor / ganti / buka folder / batal. Pencocokan judul bersifat perkiraan.

### 4.7 Antrean & scheduler (`Manager._loop`)
Thread latar tiap 0,5 dtk: mengaktifkan tugas terjadwal, menjalankan antrean sesuai `max_concurrent` (hanya tugas non-playlist), menghitung agregat playlist, kecepatan global,
menyimpan progres tiap 3 dtk, memicu `queue_done`.

### 4.8 Jalan otomatis saat login & satu instans
- `autostart.enable(bool)` per OS; argumen `--background` membuat aplikasi hanya tampil di tray/menu bar. Status sebenarnya dibaca lewat `autostart.is_enabled()` dan
  disinkronkan ke pengaturan setiap aplikasi dibuka (installer Windows juga bisa mengaktifkannya lewat task "Start SwiftGet when I sign in").
- Pilihan tersedia di: Pengaturan › Umum, installer Windows, dan dialog sambutan saat pertama dibuka (untuk macOS `.dmg` & Linux `.tar.gz` yang tidak punya installer).
- **Satu instans:** `QLockFile`. Jika dibuka lagi saat sudah berjalan, instans kedua mengirim "show" lewat `QLocalSocket` ke instans pertama lalu keluar; jendela pertama muncul.
- Dialog "Tambah unduhan"/popup izin dari extension adalah jendela mandiri (tanpa induk) yang dibawa ke depan (`winutil.bring_to_front`, termasuk trik tombol Alt di Windows),
  sehingga muncul walau jendela utama tersembunyi.

### 4.9 Penanganan HTTP 403 saat mengunduh file
`engine.probe()` memakai tangga percobaan, dan header yang berhasil dipertahankan untuk seluruh unduhan: (1) header asli dari extension; (2) tanpa `Range` (sebagian WAF memblokirnya; unduhan lalu satu aliran tanpa resume);
(3) `Referer` = situs asal file (anti-hotlink WordPress/Cloudflare); (4) header ala browser (`Accept` gambar, `Sec-Fetch-*`). Hanya status 400/401/403/405/406/412 yang memicu percobaan berikutnya. Pesan galat menyebut bahwa semua cara sudah dicoba.
Referer juga diisi dari tab aktif oleh extension bila browser tidak memberikannya. Diuji dengan server tiruan anti-hotlink dan server yang memblokir Range.

### 4.10 Jalur alternatif (routing proxy per situs)
Opsional, `route_enabled=false` secara default. Pengaturan: `route_proxies` (satu per baris, `direct` = tanpa proxy, `socks5://…`/`http://…`; dukungan SOCKS lewat `requests[socks]`), `route_sites` (domain yang memakai jalur), `route_auto`, `route_slow_kbps`, `route_slow_secs`.
- `util.route_candidates()` memilih daftar jalur untuk URL; `Net(proxy=…)` memakai proxy itu. **Resolve halaman + probe + unduh semua lewat jalur yang sama** (tautan langsung banyak situs terikat IP).
- `FileJob` memantau kecepatan: bila di bawah ambang selama N detik (setelah pemanasan, sisa >1 MB, dan bukan karena batas kecepatan buatan pengguna), ia berhenti dengan alasan `rotate`; `Manager._run` menaikkan `route_idx` dan mengantre ulang. Chunk yang sudah terunduh dipertahankan, jadi **tidak ada data yang diunduh dua kali**.
- Kegagalan koneksi/proxy, atau HTTP 403/429/503 pada situs yang terdaftar, juga memicu pindah jalur. Batas: `2 × jumlah jalur − 1` pindah per unduhan, lalu error biasa.
- Berlaku untuk unduhan file dan analisis URL; unduhan video (yt-dlp) memakai proxy global saja.
- **Batasan nyata:** tidak ada pemalsuan IP/header (tidak akan berhasil dan menipu), tidak ada proxy bawaan, tidak ada rotasi akun. Bandwidth pengguna tetap terpakai penuh (file harus melewati koneksi pengguna). Mega tidak didukung. Diuji dengan jalur `direct`, proxy mati, dan server lambat; **belum diuji ke MediaFire/GoFile/Pixeldrain sungguhan**.

### 4.11 UI
- Tabel kustom (`table.py`): kolom Nama (ikon kategori, nama, sub-teks), Progres (bar), Status (titik berwarna). Baris playlist memakai ikon daftar dan sub-teks "Playlist · n/N selesai".
- Dialog Tambah unduhan: header & tombol tetap, **isi dalam `QScrollArea`** (memperbaiki tampilan menumpuk di layar pendek), ukuran awal dibatasi ke tinggi layar.
- Tema: palet di `theme.py` (token `@nama` pada QSS). Tema Glass = latar aurora (`widgets.Backdrop`) + panel semi-transparan; efek kaca native macOS (`mac_glass.py`) eksperimental dan nonaktif secara default.

---

## 5. Extension browser

**Berkas** (`extension/`): `manifest.json` (MV3; berisi `service_worker` *dan* `scripts` agar jalan di Chrome & Firefox, plus `browser_specific_settings`),
`background.js` (pairing, intercept unduhan, deteksi stream, menu klik kanan), `content.js` (tombol Unduh di atas video, Shadow DOM), `popup.*`, `options.*`, `ui.css`, `icons/`.

**Pairing otomatis (tanpa salin token):** extension `POST /pair` (tanpa token, Origin harus `chrome-extension://…`/`moz-extension://…`) → aplikasi menampilkan dialog "Izinkan?" → bila Ya, token dikirim
balik dan Origin disimpan di `paired_origins` (pairing berikutnya dari Origin yang sama langsung berhasil). Pairing dipicu saat extension dipasang, saat browser mulai, dan saat pengguna menekan
aksi yang butuh koneksi. Unduhan otomatis tidak pernah menunggu persetujuan (browser tetap mengunduh normal bila belum terhubung). "Putuskan semua extension" (Pengaturan › Browser) mengosongkan
`paired_origins` dan mengganti token.

**Intercept:** `downloads.onCreated` → (gambar dilewati kecuali opsi `interceptImages`) → **tunggu browser menentukan nama/lokasi file** (`waitFilename`) → jeda → kirim ke `/add` (URL, referer — cadangan dari tab aktif —, cookie, UA, nama, `saveDir`) → bila sukses, batalkan unduhan browser; bila aplikasi mati, lanjutkan di browser.
Menunggu nama file penting: menjeda/membatalkan unduhan saat dialog "Simpan sebagai…" masih terbuka membuat dialog bawaan macOS macet (tidak bisa disentuh). Bila pengguna menunggu >1,2 dtk (memilih folder sendiri), folder pilihannya dikirim sebagai `saveDir` dan dipakai aplikasi. Unduhan yang sudah selesai/gagal di browser sebelum dialihkan tidak digandakan. Logika ini diuji dengan API `downloads` tiruan di Node.

**Pemasangan oleh pengguna:** tombol Chrome/Edge/Brave/Firefox di Pengaturan › Browser menyalin extension ke `~/SwiftGet Extension`, membuka halaman extensions browser, menyalin path ke clipboard.
Pemasangan sekali klik hanya mungkin lewat toko (lihat bagian 9); isi `EXT_STORE` di `swiftget/config.py` setelah terbit.

**Izin:** `downloads` (jeda/batalkan unduhan browser), `webRequest` (deteksi stream), `cookies` (sesi login), `contextMenus`, `storage`, `tabs`, host `<all_urls>`.

---

## 6. Keamanan & privasi

- Server hanya mengikat **127.0.0.1**. Setiap request divalidasi: header `Host` harus `127.0.0.1`/`localhost`; `Origin` (bila ada) harus skema extension; rute `/add` & `/media`
  butuh header `X-SwiftGet-Token` (dibandingkan `secrets.compare_digest`); `/pair` hanya dari Origin extension dan butuh persetujuan pengguna. Halaman web biasa tidak bisa memerintah aplikasi.
- Token 24 byte acak disimpan di `settings.json` (tidak dienkripsi; hak akses file pengguna). Jangan dibagikan.
- Extension tidak mengirim data ke server mana pun selain `127.0.0.1`.
- Cookie hanya diteruskan ke aplikasi lokal; untuk yt-dlp dipakai lewat file sementara yang dihapus; **tidak dipakai untuk YouTube**.
- Aplikasi **belum ditandatangani** → peringatan SmartScreen (Windows) dan Gatekeeper (macOS). Sertifikat berbayar dibahas di bagian 8.
- Unduhan file dari hosting acak dapat berisi malware; sediakan kolom checksum, dan ingatkan pengguna.

---

## 7. Build & rilis

### 7.1 Sumber versi
`pyproject.toml` → `version = "X.Y.Z"` adalah **satu-satunya** tempat versi. Dibaca oleh aplikasi (pojok kanan bawah), `packaging/build.py` (nama file, info `.exe`), dan workflow (tag Release).
Saat di-build, `pyproject.toml` dibundel (`--add-data`) agar aplikasi hasil build tetap bisa membaca versinya.

### 7.2 Alur CI (`.github/workflows/build.yml`)
```
push yang mengubah pyproject.toml (branch main/master)  ← push lain TIDAK memicu apa pun
   └─ job "version"  : baca versi baru & versi di commit sebelumnya; sama → semua job dilewati; beda → lanjut (validasi format 1.2.3)
        ├─ job "app" (4 mesin paralel): Windows · Mac Intel (macos-15-intel) · Mac Apple Silicon (macos-latest) · Linux
        │     pip install ".[dev]" → python -m tests.test_engine → python packaging/build.py → upload artifact
        ├─ job "extension": python packaging/pack_extension.py → upload artifact
        └─ job "release": kumpulkan artifact → buat/perbarui Release bertag v<versi> → lampirkan semua file (tetap jalan walau satu OS gagal)
```
Tombol *Run workflow* membangun ulang versi yang ada. Mendorong versi yang sama memperbarui file di Release itu.
Izin: workflow memakai `GITHUB_TOKEN` dengan `contents: write` (tanpa secret tambahan). Bila job `release` gagal 403: Settings › Actions › General › Workflow permissions › *Read and write*.

### 7.3 Hasil build (di Release)
| File | Dibuat oleh |
|---|---|
| `SwiftGet-Setup-<v>.exe` | Inno Setup (`packaging/windows/swiftget.iss`), dipasang via `choco install innosetup` |
| `SwiftGet-<v>-windows-portable.zip` | zip folder PyInstaller (`SwiftGet.exe` + `_internal`) |
| `SwiftGet-<v>-macos-x86_64.dmg` / `-arm64.dmg` | `hdiutil` (aplikasi + tautan Applications), ad-hoc `codesign` |
| `SwiftGet-<v>-linux-x86_64.tar.gz` | tar folder PyInstaller |
| `swiftget-chrome-edge.zip`, `swiftget-firefox.zip` | `packaging/pack_extension.py` (manifest dibersihkan per browser) |
Ditambah "Source code" otomatis dari GitHub. `_internal` adalah cara kerja PyInstaller mode folder; mode satu-file ditolak karena startup lambat dan lebih sering ditandai antivirus.

### 7.4 Installer Windows
Pasang ke `%LOCALAPPDATA%\Programs\SwiftGet` (tanpa admin) atau `Program Files` (bila pengguna memilih untuk semua pengguna). Pilihan: shortcut desktop, **"Start SwiftGet when I sign in"** (menulis registry
`HKCU\…\Run` dengan `--background`; dihapus saat uninstall). Aplikasi diluncurkan di akhir instalasi. Bahasa installer: Inggris (bawaan Inno).

### 7.5 Menjalankan lokal
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt     # = pip install -e .
python run.py                       # atau: python -m swiftget  /  swiftget
pip install -r requirements-dev.txt && python packaging/build.py   # build lokal (di OS target)
python -m tests.test_engine
```

---

## 8. Tugas rutin pemilik

**Merilis versi baru:** ubah `version` di `pyproject.toml` → commit → push. ±10–15 menit kemudian Release muncul (`https://github.com/dekDika13/SwiftGet/releases`). Gunakan penomoran:
`MAJOR.MINOR.PATCH` (perbaikan kecil → PATCH, fitur baru → MINOR, perubahan besar → MAJOR).

**Branch utama bukan main/master:** ubah `branches:` di `build.yml`.

**Mengganti ikon:** ganti `assets/icon.png` (512×512), `assets/icon.ico` (Windows), `assets/icon.icns` (macOS), dan `extension/icons/16|32|48|128.png`; atau ubah `packaging/make_icons.py` lalu
jalankan `python packaging/make_icons.py`. Ikon di jendela/tray berasal dari `APP_SVG` di `swiftget/ui/icons.py`. Membuat `.icns` di Mac dari `icon1024.png`:
```bash
mkdir icon.iconset
for s in 16 32 128 256 512; do sips -z $s $s icon1024.png --out icon.iconset/icon_${s}x${s}.png; sips -z $((s*2)) $((s*2)) icon1024.png --out icon.iconset/icon_${s}x${s}@2x.png; done
iconutil -c icns icon.iconset && mv icon.icns assets/icon.icns
```
Setelah mengganti `.icns`, bila Dock masih menampilkan ikon lama: `killall Dock`.

**Menambah situs file hosting (resolver):** satu fungsi di `swiftget/resolvers.py`:
```python
@resolver("NamaSitus", r"namasitus\.com/file/")
def namasitus(net, url):
    html = net.get(url).text
    return Resolved(re.search(r'href="(https://cdn[^"]+)"', html).group(1), referer=url)
```
**Memperbarui yt-dlp:** pengguna: Pengaturan › Video & Audio › Perbarui yt-dlp. Pemilik: rilis versi baru (CI memasang yt-dlp terbaru karena `pyproject.toml` tidak mengunci versinya).
Pantau juga catatan rilis yt-dlp; YouTube beberapa kali mengubah persyaratan (token, runtime JavaScript) yang bisa merusak unduhan sampai yt-dlp diperbarui.

**Menghapus peringatan keamanan OS (opsional, berbayar):**
- Windows: sertifikat code signing (OV/EV), atau Azure Trusted Signing, atau program gratis **SignPath Foundation** untuk proyek open source.
- macOS: Apple Developer Account ($99/tahun) untuk signing + notarization (tambahkan langkah `codesign --options runtime` dan `xcrun notarytool` di CI).

**Mengubah port/token:** Pengaturan › Browser (port); *Putuskan semua extension* untuk mengganti token. Port harus sama dengan di extension (opsi extension).

**Menyetel batas default:** `DEFAULTS` di `swiftget/config.py` (koneksi 8 untuk file, 1 untuk media, bersamaan 3, dst.).

**Reset data pengguna saat uji:** hapus folder data (bagian 3). Jalankan ulang untuk melihat dialog sambutan lagi (`"onboarded": false` di `settings.json`).

---

## 9. Menerbitkan extension ke toko

Chrome/Edge memblokir pemasangan extension otomatis dari luar toko (kecuali PC dikelola kantor), jadi satu-satunya jalan agar pengguna cukup klik "Tambahkan" adalah toko resmi.
Paket dibuat otomatis oleh CI (`SwiftGet-extension`) atau `python packaging/pack_extension.py`.

| Toko | Biaya | Paket | Tautan |
|---|---|---|---|
| Chrome Web Store (juga untuk Brave, Opera, Vivaldi, Arc) | $5 sekali | `swiftget-chrome-edge.zip` | https://chrome.google.com/webstore/devconsole |
| Microsoft Edge Add-ons | gratis | `swiftget-chrome-edge.zip` | https://partner.microsoft.com/dashboard/microsoftedge |
| Firefox Add-ons (AMO) | gratis | `swiftget-firefox.zip` | https://addons.mozilla.org/developers/ ("Listed" = toko publik, "Unlisted" = ditandatangani lalu dibagikan sendiri) |

Setelah terbit, isi URL toko di `EXT_STORE` (`swiftget/config.py`); tombol di Pengaturan › Browser lalu langsung membuka halaman toko. Firefox hanya menyimpan extension permanen bila **ditandatangani** (lewat AMO).

**Teks pengajuan (salin):**
- *Tujuan tunggal:* Mengambil alih unduhan browser dan mengirim tautan unduhan atau video halaman ke aplikasi desktop SwiftGet (download manager) di komputer pengguna.
- *Alasan izin host `<all_urls>`:* mendeteksi tautan unduhan dan elemen video di halaman mana pun, membaca cookie situs yang sama agar unduhan yang butuh login berhasil, dan berkomunikasi dengan aplikasi lokal di 127.0.0.1.
  `downloads`: menjeda lalu membatalkan unduhan bawaan setelah dialihkan. `webRequest`: mendeteksi alamat stream media pada tab aktif. `cookies`: meneruskan sesi login ke aplikasi.
  `contextMenus`, `storage`, `tabs`: menu klik kanan, pengaturan, dan URL tab aktif.
- *Privasi:* Extension tidak mengirim data ke server mana pun. Semua komunikasi hanya ke aplikasi SwiftGet di `127.0.0.1` pada komputer pengguna. (Siapkan satu halaman kebijakan privasi berisi pernyataan ini; README di GitHub atau GitHub Pages cukup.)

**Peringatan:** toko cenderung menolak extension yang menonjolkan "pengunduh video YouTube". Tulis deskripsi dan tangkapan layar yang berfokus pada **download manager** (alihkan unduhan file, antrean, resume); jangan menjual unduh YouTube di
halaman toko. Tinjauan biasanya beberapa hari hingga beberapa minggu.

---

## 10. Masalah yang diketahui & risiko

**Hukum & kebijakan.** Mengunduh dari beberapa platform bisa melanggar syarat layanan mereka; DRM tidak bisa dan tidak akan didukung. Distribusi lewat toko resmi (App Store, Chrome Web Store) berisiko ditolak.
Pertimbangkan menambahkan pernyataan penafian di situs/README sesuai kebutuhan.

**Pemeliharaan yang tak terhindarkan.** yt-dlp dan situs hosting berubah terus; resolver (terutama MediaFire/Google Drive) dapat rusak tiba-tiba. Rencanakan rilis berkala.

**Teknis:**
- yt-dlp terbaru dapat memerlukan runtime JavaScript (Deno/Node.js) untuk YouTube; paket `yt-dlp-ejs` ikut terpasang tetapi runtime-nya belum terverifikasi di semua OS. Bila YouTube gagal serentak, periksa ini lebih dulu.
- Nama klien alternatif YouTube (`android_vr`, `tv`) bisa berubah/berhenti bekerja; hanya dipakai sebagai upaya terakhir saat 403.
- YouTube tidak memakai cookie dari extension. Video yang butuh login (usia/privat/member) hanya bisa lewat Pengaturan › *Ambil cookies dari* browser (di macOS untuk Safari butuh izin Full Disk Access).
- Deteksi duplikat video lewat kemiripan judul bersifat perkiraan; deteksi lewat URL lebih andal.
- Playlist diunduh sesuai batas "unduhan bersamaan" (3). "Timpa" playlist tidak menghapus file lain di folder.
- Progres induk playlist = rata-rata progres isi (ukuran total belum diketahui di awal), bukan jumlah byte.
- Properti (koneksi/lokasi/nama) untuk induk playlist tidak tersedia; ubah per video lewat popup isi playlist.
- Mengubah resolusi/format unduhan yang belum selesai memulai ulang unduhan itu; yang sudah selesai ditambahkan sebagai unduhan baru.
- Linux: system tray butuh dukungan lingkungan desktop (GNOME memerlukan ekstensi AppIndicator); Wayland dapat menolak "membawa jendela ke depan".
- macOS: mode latar belakang tetap menampilkan ikon di Dock; LaunchAgent dapat memicu notifikasi "item latar belakang" di macOS 13+. Efek kaca native: eksperimental.
- Windows: layar kecil/skala tinggi sempat membuat dialog menumpuk (sudah diperbaiki dengan area gulir); bila muncul lagi, laporkan ukuran layar dan skalanya.
- Firefox: pemasangan manual bersifat sementara; izin host harus diberikan manual di Add-ons Manager.
- Jalur alternatif belum diuji ke MediaFire/GoFile/Pixeldrain asli. Situs bisa membatasi per akun/cookie/browser fingerprint, bukan hanya IP, sehingga proxy belum tentu mengembalikan kecepatan. Dari sisi kebijakan: memutar jalur untuk menghindari batas situs bisa melanggar syarat layanan situs/penyedia proxy; fitur dibuat opsional, tanpa proxy bawaan, dan tanpa pemalsuan identitas.
- Mega tidak didukung (enkripsi sisi klien dan kuota per IP); GoFile memakai token situs yang berubah; belum ada resolver untuk GoFile/ACFile.
- Dialog "Simpan sebagai…" macOS: perbaikan (menunggu nama file) diuji hanya dengan API tiruan; verifikasi di Chrome/Edge macOS asli diperlukan.
- Tidak ada pembaruan otomatis aplikasi; pengguna mengunduh Release baru. (Ide: cek versi terbaru lewat GitHub API.)
- Tidak ada telemetri/laporan error otomatis.

---

## 11. Checklist uji manual sebelum rilis

Lakukan di tiap OS target (Windows 10/11, macOS Intel & Apple Silicon, satu distro Linux) pada hasil build **Release**, bukan hanya `python run.py`.

**Pemasangan:** installer Windows (tanpa admin; Start Menu; uninstall bersih; opsi login); DMG (seret, buka pertama dengan klik kanan › Open); tar.gz.
**Dasar:** versi di pojok kanan bawah = versi rilis; tambah URL file → unduh → jeda → lanjut → tutup & buka ulang → lanjut; hapus + file.
**Video:** YouTube 720p kompatibel → putar di pemutar bawaan OS; resolusi >1080p → konversi H.264 berhasil; audio MP3; ganti resolusi lewat klik kanan; video yang sama dua kali → dialog duplikat (nomor/ganti/buka folder/batal).
**Playlist:** playlist kecil (3–5 video) → satu baris di daftar; nama folder bisa diubah; popup isi: jeda/lanjut/hapus per video, ubah resolusi; judul kembar → `(1)`; tambah playlist bernama sama → dialog 4 pilihan.
**Extension (403 & dialog):** "Save image as…" gambar WordPress tidak lagi lewat SwiftGet (tidak 403); unduh file dengan "Ask where to save" aktif di Chrome/Edge macOS → dialog tidak macet dan file masuk ke folder pilihan; opsi "Ambil alih gambar" bila diaktifkan memakai Referer yang benar.
**Jalur alternatif:** aktifkan dengan daftar `direct` + satu proxy/VPN milik sendiri; Tes jalur menampilkan IP berbeda; unduhan besar berpindah jalur saat melambat dan lanjut tanpa mengulang.
**Extension:** pasang di Chrome & Edge (& Firefox); dialog izin muncul walau aplikasi di tray; klik unduhan di browser → dialihkan; tombol di atas video; popup extension (stream terdeteksi); aplikasi dimatikan → browser mengunduh normal.
**Latar belakang:** aktifkan "jalankan saat login" → restart/login ulang → aplikasi berjalan tanpa jendela; klik ikon → jendela muncul; matikan opsi → tidak jalan lagi. Dialog "Tambah unduhan" dari extension muncul di depan saat aplikasi di tray.
**Tampilan:** tema Glass/Gelap/Terang; layar kecil (1366×768, skala 125–150%): dialog Tambah unduhan tidak menumpuk (ada scroll); panah spinbox terlihat.

---

## 12. Pemecahan masalah (untuk pemilik)

| Gejala | Kemungkinan penyebab / langkah |
|---|---|
| Release tidak muncul | Versi di `pyproject.toml` tidak berubah (gerbang melewati build); atau job `release` 403 (izin workflow); lihat tab Actions › job `version` (log "versi sebelumnya/sekarang") |
| Job `app` merah di satu OS | Buka log job itu; file dari OS lain tetap dirilis. Penyebab umum: dependensi, PyInstaller hidden import, Inno Setup tidak terpasang (Windows hanya menghasilkan zip portable) |
| `Setup.exe` tidak ada | Langkah Inno Setup gagal / `choco install innosetup` gagal; periksa log |
| Tes CI gagal di Windows | Biasanya perbandingan path (`/` vs `\`): gunakan `os.path.normpath` |
| Aplikasi hasil build tidak mau jalan / crash saat unduh video | Windowed + yt-dlp menulis ke stderr (sudah ditangani di `app.py`); periksa `--collect-all yt_dlp_ejs imageio_ffmpeg` di `build.py` |
| Versi di aplikasi "0.0.0" | `pyproject.toml` tidak ikut terbundel / format `version = "…"` rusak |
| YouTube "page needs to be reloaded" | Cookie dikirim (seharusnya tidak untuk YouTube); perbarui yt-dlp; coba jalur klien alternatif |
| Extension "belum terhubung" | Aplikasi tidak berjalan, port berbeda, atau pairing ditolak; popup extension › Hubungkan; atau *Putuskan semua extension* lalu pairing ulang |
| 403 pada file tertentu | Cek apakah butuh login (unduh lewat browser dengan extension), dan lihat pesan galat: "sudah dicoba beberapa jenis header" berarti semua cara dicoba |
| Dialog "Simpan sebagai" browser macet | Extension lama; muat ulang extension dari `~/SwiftGet Extension` (versi baru menunggu nama file sebelum menyentuh unduhan) |
| Dialog dari extension tersembunyi di belakang browser | Windows menolak fokus: periksa `winutil.bring_to_front`; Linux Wayland tidak mengizinkan |
| macOS menolak membuka | `xattr -cr /Applications/SwiftGet.app` (atau signing + notarization) |

---

## 13. Ide pengembangan berikutnya

- Pembaruan otomatis (cek Release terbaru) · sertifikat signing · notarization macOS · terjemahan bahasa lain
- Native Messaging (pairing tanpa server lokal, bisa menyalakan aplikasi dari extension) · extension Safari (butuh Xcode + Developer Account)
- Mega, Terabox, torrent/magnet (aria2/libtorrent), FTP, folder Google Drive
- Pilih sebagian video sebelum mengunduh playlist (centang daftar) · Properti untuk induk playlist · urutan/prioritas dalam playlist
- Statistik penggunaan, pembersihan otomatis file lama, laporan error opsional
- Menambah `ruff`/`pytest` ke CI; tes UI otomatis (pytest-qt) agar tampilan ikut teruji

---

## 14. Glosarium

| Istilah | Arti sederhana |
|---|---|
| **Resume** | Melanjutkan unduhan dari bagian yang sudah selesai, bukan mengulang dari awal |
| **Multi-koneksi / chunk** | File dipotong jadi bagian-bagian yang diunduh bersamaan agar lebih cepat (bila server membatasi per koneksi) |
| **Resolver** | Modul kecil yang mengubah tautan halaman (Drive, MediaFire) menjadi tautan file langsung |
| **yt-dlp** | Pustaka sumber terbuka untuk mengunduh video/audio dari ribuan situs |
| **FFmpeg** | Alat untuk menggabung video+audio dan mengonversi format |
| **H.264 / AAC** | Kodek video/audio yang bisa diputar hampir di semua perangkat |
| **VP9 / AV1** | Kodek lebih efisien (kualitas tinggi, file kecil) tetapi tidak selalu bisa diputar di QuickTime/iPhone |
| **Pairing** | Proses menghubungkan extension ke aplikasi dengan persetujuan pengguna (menggantikan salin-tempel token) |
| **System tray / menu bar** | Area ikon kecil di dekat jam (Windows/Linux) atau di bar atas (macOS) tempat aplikasi tetap hidup di latar belakang |
| **PyInstaller** | Alat yang membungkus aplikasi Python + Python-nya menjadi aplikasi mandiri (folder `.exe` + `_internal`) |
| **Inno Setup** | Pembuat installer Windows (`Setup.exe`) |
| **Code signing / notarization** | Tanda tangan digital agar OS tidak menampilkan peringatan "developer tidak dikenal" |
| **CI (GitHub Actions)** | Robot di GitHub yang menjalankan tes dan build otomatis saat kondisi tertentu terpenuhi |
| **Induk / anak (playlist)** | Induk = satu baris playlist di daftar; anak = tiap video di dalamnya |
