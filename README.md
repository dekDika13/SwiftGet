# SwiftGet

Download manager untuk Windows, macOS, dan Linux: mengambil alih unduhan dari browser, mengunduh video dan audio (pilih resolusi & format),
mengunduh seluruh playlist, dan merapikan hasil unduhan dalam kategori.

---

## 1. Mengunduh aplikasi

Buka halaman **[Releases](https://github.com/dekDika13/SwiftGet/releases)**, pilih versi terbaru (paling atas), lalu unduh file sesuai perangkatmu
dari bagian **Assets**:

| Perangkat | File yang diunduh |
|---|---|
| **Windows** (disarankan) | `SwiftGet-Setup-<versi>.exe` |
| Windows tanpa instalasi | `SwiftGet-<versi>-windows-portable.zip` |
| **Mac Intel** | `SwiftGet-<versi>-macos-x86_64.dmg` |
| **Mac Apple Silicon** (M1, M2, M3, M4) | `SwiftGet-<versi>-macos-arm64.dmg` |
| **Linux** | `SwiftGet-<versi>-linux-x86_64.tar.gz` |

Tidak yakin Mac kamu Intel atau Apple Silicon? Klik logo Apple › *About This Mac*: tertulis "Chip Apple M…" berarti Apple Silicon, "Intel" berarti Intel.

### Memasang di Windows
1. Jalankan `SwiftGet-Setup-….exe`. Jika muncul **"Windows protected your PC"**, klik **More info › Run anyway** (muncul karena aplikasi belum
   memakai sertifikat berbayar; aplikasinya sendiri aman).
2. Ikuti wizard. Ada pilihan **"Start SwiftGet when I sign in"** (jalan otomatis di latar belakang saat login) dan shortcut desktop.
3. Buka dari Start Menu. Versi portable: ekstrak zip, jalankan `SwiftGet.exe` (jangan pisahkan dari folder `_internal`).

### Memasang di macOS
1. Buka file `.dmg`, lalu **seret SwiftGet ke Applications**.
2. Pertama kali dibuka, macOS bisa menolak karena developer belum dikenal. Klik kanan SwiftGet › **Open** › Open. Jika masih ditolak, jalankan di Terminal:
   `xattr -cr /Applications/SwiftGet.app`

### Memasang di Linux
Ekstrak `tar.gz`, lalu jalankan `SwiftGet/SwiftGet` dari file manager atau terminal.

FFmpeg (untuk menggabung video/audio resolusi tinggi dan konversi MP3) **sudah termasuk**, tidak perlu dipasang terpisah.

---

## 2. Cara pakai

### Menambah unduhan
Tekan **Tambah URL** (atau `Ctrl/Cmd + N`), tempel tautan, tunggu analisis otomatis, lalu **Mulai unduh**. SwiftGet mengenali sendiri apakah tautan itu:
- **file biasa** (zip, exe, dmg, pdf, …) termasuk dari Google Drive, MediaFire, Dropbox, OneDrive, GitHub, Pixeldrain, SourceForge,
- **video/audio** (YouTube, TikTok, X, Instagram, Vimeo, dan ribuan situs lain),
- **halaman berisi banyak file**: kamu tinggal mencentang yang diinginkan.

Bisa juga: menempel banyak URL sekaligus (satu per baris), menyeret tautan ke jendela, atau menyalin tautan (SwiftGet menampilkan notifikasi "URL terdeteksi", klik untuk menambahkan).

### Video dan audio
- **Resolusi & format:** pilih di kartu video (MP4, MKV, WebM) atau tab **Audio** (MP3, M4A, Opus, FLAC, WAV).
- **Kompatibilitas:** *Kompatibel (H.264 + AAC)* dapat diputar di pemutar bawaan Mac, iPhone, dan Windows. *Kualitas asli (VP9/AV1)* tanpa konversi,
  paling bagus dan hemat ukuran, tetapi biasanya hanya terputar di VLC/IINA. Resolusi di atas 1080p (1440p/4K) hanya tersedia dalam VP9/AV1, jadi pada mode kompatibel
  videonya dikonversi dulu ke H.264 (lebih lama).
- **Mengganti resolusi/format belakangan:** klik kanan video di daftar › **Ubah resolusi / format…**
- **Koneksi:** video memakai 1 koneksi (lebih aman dari penolakan YouTube); file biasa memakai 8.

### Playlist
Jika tautan adalah playlist (atau video di dalam playlist), muncul pilihan **"Unduh seluruh playlist"**:
- **Nama folder playlist** terisi otomatis dari judul playlist dan bisa kamu ubah sebelum mengunduh.
- Di daftar unduhan, playlist tampil sebagai **satu baris** (nama playlist, jumlah video, progres gabungan). **Klik dua kali** (atau klik kanan › *Lihat isi playlist*)
  untuk membuka popup berisi tiap video: kamu bisa **jeda, lanjutkan, ubah resolusi, atau hapus video tertentu dari daftar**.
- Nama file tidak diberi nomor urut. Jika ada judul yang persis sama dalam satu playlist, yang berikutnya otomatis diberi angka di belakang: `Judul (1).mp4`.
- Jika nama playlist yang sama sudah ada, muncul pilihan: **ganti nama, timpa, lihat playlist lama, atau batal**.

### Jika file/video yang sama sudah pernah diunduh
Muncul peringatan dengan pilihan: **simpan dengan nomor** (`Judul (1)`), **ganti file lama**, **buka folder file sebelumnya**, atau batal.

### Mengelola unduhan
- Sidebar kiri: filter status (Sedang berjalan, Antrean, Dijeda, Selesai, Gagal) dan kategori (Video, Musik, Dokumen, Arsip, Program, Gambar), dengan penghitung. Cari lewat kotak pencarian (`Ctrl/Cmd + F`).
- File otomatis masuk subfolder kategori di `Downloads/SwiftGet/`.
- Klik kanan unduhan: jeda/lanjutkan, naik/turun prioritas, **Properti** (ubah jumlah koneksi, folder tujuan, dan nama file, termasuk untuk unduhan yang gagal atau sudah selesai), unduh ulang, salin tautan, hapus.
- Unduhan yang terputus bisa dilanjutkan (resume), bahkan setelah aplikasi ditutup. Ada batas kecepatan, jadwal mulai, dan verifikasi checksum.

### Jalur alternatif untuk situs yang membatasi kecepatan (opsional, nonaktif secara default)
Sebagian situs file hosting (misalnya MediaFire) menurunkan kecepatan per **alamat IP** setelah kamu mengunduh banyak, sehingga tinggal ±100 KB/s.
Jika kamu punya proxy atau VPN sendiri (HTTP/HTTPS/SOCKS5), SwiftGet bisa mengirim unduhan situs tertentu lewat jalur itu:
- Aktifkan di **Pengaturan › Jaringan › Jalur alternatif**, isi **Daftar jalur** (satu per baris; tulis `direct` untuk jalur tanpa proxy), dan **Situs yang memakai jalur**.
- Bila unduhan terlalu lambat (batas bisa diatur) atau jalurnya gagal/diblokir, SwiftGet **pindah ke jalur berikutnya otomatis dan melanjutkan dari byte terakhir** (tanpa mengunduh ulang).
- Tombol **Tes jalur** menampilkan alamat IP keluar tiap jalur.

Yang perlu diketahui: SwiftGet **tidak menyediakan proxy** dan **tidak memalsukan identitas atau alamat IP**; batas dari situs tetap berlaku di jalur mana pun,
dan file tetap harus melewati internetmu sehingga fitur ini **tidak menghemat bandwidth**. Mega tidak didukung (filenya terenkripsi dan kuotanya per IP).
Pastikan pemakaiannya sesuai syarat layanan situs dan penyedia proxy/VPN-mu. Kalau yang kamu butuhkan hanya kecepatan, menunggu reset kuota, atau akun premium situs itu, tetap yang paling pasti.

### Berjalan di latar belakang & jalan otomatis saat login
- Menutup jendela hanya menyembunyikannya ke system tray / menu bar; unduhan terus berjalan. Keluar sepenuhnya lewat menu tray › **Keluar**.
- **Jalan otomatis saat login:** aktifkan di **Pengaturan › Umum › "Jalankan SwiftGet saat login"** (juga ditawarkan saat pertama kali dibuka dan di installer Windows).
  Aplikasi lalu berjalan **diam-diam di latar belakang** tanpa membuka jendela, sehingga extension browser langsung bisa dipakai. Klik ikon aplikasi kapan saja untuk membuka jendelanya.
  Bisa dimatikan lagi di Pengaturan yang sama. Berlaku di Windows, macOS, dan Linux.

---

## 3. Memasang extension browser

Extension menangkap unduhan dari browser (diarahkan ke SwiftGet), menampilkan tombol **Unduh** di atas video, dan menambah menu klik kanan.
Didukung: **Chrome, Edge, Brave, Opera, Vivaldi, Firefox**. (Safari tidak memakai extension: salin tautannya, SwiftGet akan mendeteksinya, atau tempel ke aplikasi.)

1. Buka SwiftGet › **Pengaturan › Browser**, lalu klik tombol browsermu (Chrome, Edge, Brave, atau Firefox).
   SwiftGet menyiapkan folder `SwiftGet Extension` di folder Home-mu, menyalin lokasinya ke clipboard, dan membuka halaman extensions browser.
2. Di halaman extensions:
   - **Chrome / Edge / Brave:** aktifkan **Developer mode** → **Load unpacked** → pilih folder `SwiftGet Extension`.
   - **Firefox:** **Load Temporary Add-on…** → pilih file `manifest.json` di folder tersebut (Firefox melupakannya saat browser ditutup; lihat catatan di bawah).
3. SwiftGet langsung menampilkan **"Izinkan extension terhubung?"**. Klik **Ya**. Selesai, tidak perlu menyalin token.

Pastikan SwiftGet sedang berjalan (di latar belakang pun cukup). Jika popup extension menunjukkan "Belum terhubung", klik **Hubungkan ke SwiftGet**.

Menggunakan extension:
- **Unduhan biasa:** klik tautan unduhan seperti biasa, dan otomatis dialihkan ke SwiftGet.
- **Video:** arahkan kursor ke video, klik tombol **Unduh** yang muncul; atau klik kanan halaman › *Unduh video halaman ini dengan SwiftGet*.
- **Stream yang terdeteksi:** klik ikon extension untuk melihat daftar media di tab yang sedang dibuka.
- **Gambar ("Save image as…") dibiarkan ditangani browser** agar tidak gagal di situs yang memblokir unduhan dari luar browser (mis. anti-hotlink WordPress). Bisa diaktifkan di Opsi extension.
- **Dialog "Simpan sebagai…" bawaan browser** tidak diganggu: SwiftGet menunggu kamu memilih folder, lalu menyimpan ke folder pilihanmu.
- Jika SwiftGet tidak berjalan, browser mengunduh seperti biasa (tidak ada yang rusak).

---

## 4. Fitur

- Unduhan multi-koneksi (hingga 32), jeda/lanjut, resume setelah aplikasi ditutup, antrean dengan prioritas, batas kecepatan, jadwal mulai
- Pengunduh video & audio untuk ribuan situs: pilih resolusi, format, kompatibilitas H.264/AAC, subtitle, metadata
- Playlist sebagai satu baris dengan popup isi playlist, folder bernama, penanganan nama kembar
- Peringatan duplikat (nomor / ganti / buka folder / batal) untuk file, video, dan playlist
- Pengenal tautan otomatis dan resolver Google Drive, MediaFire, Dropbox, OneDrive, GitHub, Pixeldrain, SourceForge
- Manajemen hasil: kategori otomatis, filter, pencarian, riwayat permanen, properti per unduhan, buka file / folder
- Extension browser dengan pairing otomatis, tombol di atas video, deteksi stream
- System tray, notifikasi, deteksi URL di clipboard, jalan otomatis saat login di latar belakang, aksi setelah antrean selesai (tutup / sleep / matikan)
- Tema Glass (gelap/terang), Gelap, dan Terang

## 5. Batasan

- **Konten DRM** (Netflix, Disney+, Spotify, dll.) tidak bisa diunduh.
- **Kecepatan** tidak bisa melebihi kecepatan internetmu; banyak koneksi hanya membantu jika server membatasi per koneksi.
- **Google Drive:** pesan "kuota habis / too many users" adalah batas dari Google. Folder Drive belum didukung (unduh file satu per satu).
- **HTTP 403 ("butuh login/izin"):** SwiftGet otomatis mencoba beberapa cara (tanpa header Range, Referer situs asal, header ala browser). Jika file memang butuh login, unduh lewat browser dengan extension aktif agar sesi login ikut terkirim.
- **Belum didukung:** Mega, Terabox, torrent/magnet, FTP. Situs dengan captcha atau timer: unduh lewat browser dengan extension aktif (kamu menyelesaikan captcha, SwiftGet menangkap hasilnya).
- **Firefox:** extension yang dipasang manual bersifat sementara dan hilang saat browser ditutup, kecuali versi yang sudah ditandatangani (dari toko Firefox).
- **YouTube sering mengubah sistemnya.** Jika unduhan video gagal, perbarui yt-dlp di **Pengaturan › Video & Audio › Perbarui yt-dlp** atau pasang versi SwiftGet terbaru.
- Mengunduh dari beberapa platform bisa melanggar syarat layanan mereka. Unduh hanya konten yang memang boleh kamu unduh.
- Aplikasi belum ditandatangani secara digital, sehingga Windows/macOS menampilkan peringatan saat pertama kali dibuka (lihat bagian 1).

## 6. Masalah umum

| Masalah | Solusi |
|---|---|
| Video tidak bisa diputar di QuickTime/iPhone | Unduh dengan Kompatibilitas = **H.264 + AAC**; untuk file lama klik kanan › Unduh ulang |
| YouTube: "page needs to be reloaded" / 403 | Coba lagi; perbarui yt-dlp; turunkan koneksi video menjadi 1 (klik kanan › Properti) |
| Extension: "Aplikasi tidak aktif" | Jalankan SwiftGet (atau aktifkan jalan otomatis saat login) |
| Extension: "Belum terhubung" | Klik ikon extension › **Hubungkan ke SwiftGet**, lalu **Ya** di aplikasi |
| Jendela tidak muncul setelah login | Itu normal (berjalan di latar belakang); klik ikon di system tray / menu bar |
| Dialog "Simpan sebagai" di macOS macet | Perbaikan ada di versi terbaru (extension tidak lagi menyentuh unduhan sebelum folder dipilih). Pasang ulang/muat ulang extension dari folder `SwiftGet Extension` yang baru |
| HTTP 403 pada gambar/file tertentu | Perbarui aplikasi dan extension; gambar kini ditangani browser secara default. Bila masih 403, file butuh login: unduh lewat browser |
| Kecepatan turun jadi ±100 KB/s di MediaFire dsb. | Itu pembatasan per IP dari situs. Tunggu reset, gunakan akun premium, atau (opsional) pakai Jalur alternatif dengan proxy/VPN milikmu |
| Port 6277 dipakai aplikasi lain | Ubah port di Pengaturan › Browser |

Catatan pengembang, cara membangun, dan detail teknis ada di [`OWNER.md`](OWNER.md).
