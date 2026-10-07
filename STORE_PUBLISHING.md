# Menerbitkan extension agar terpasang sekali klik

Browser sengaja memblokir pemasangan extension otomatis dari luar toko (Chrome/Edge di Windows dan macOS hanya mau memasang
dari toko resmi, kecuali PC dikelola kantor). Jalan yang profesional dan resmi adalah **menerbitkan extension di toko**.
Setelah terbit, pengguna cukup klik "Tambahkan", dan SwiftGet otomatis meminta izin pairing.

Buat paketnya: `python packaging/pack_extension.py` (atau ambil artifact `SwiftGet-extension` dari GitHub Actions).

| Toko | Biaya | Paket | Catatan |
|---|---|---|---|
| Chrome Web Store (juga dipakai Brave, Opera, Vivaldi, Arc) | $5 sekali | `swiftget-chrome-edge.zip` | https://chrome.google.com/webstore/devconsole |
| Microsoft Edge Add-ons | gratis | `swiftget-chrome-edge.zip` | https://partner.microsoft.com/dashboard/microsoftedge |
| Firefox (addons.mozilla.org) | gratis | `swiftget-firefox.zip` | https://addons.mozilla.org/developers/ . "Listed" untuk toko publik, atau "Unlisted" untuk ditandatangani lalu dibagikan sendiri |

Setelah diterbitkan, isi URL halaman tokonya di `swiftget/config.py` pada `EXT_STORE`. Tombol Chrome/Edge/Brave/Firefox di
Pengaturan › Browser langsung membuka halaman toko.

## Teks pengajuan (bisa disalin)

**Tujuan tunggal:** Mengambil alih unduhan browser dan mengirim tautan unduhan atau video halaman ke aplikasi desktop SwiftGet
(download manager) yang berjalan di komputer pengguna.

**Alasan izin `<all_urls>` / host permissions:** Mendeteksi tautan unduhan dan elemen video di halaman mana pun, membaca cookie
situs yang sama agar unduhan yang membutuhkan login tetap berhasil, dan berkomunikasi dengan aplikasi lokal di 127.0.0.1.
**`downloads`:** menjeda lalu membatalkan unduhan bawaan browser setelah dialihkan ke SwiftGet.
**`webRequest`:** mendeteksi alamat stream media (HLS/DASH/MP4) pada tab aktif. **`cookies`:** meneruskan sesi login ke aplikasi.
**`contextMenus`, `storage`, `tabs`:** menu klik kanan, menyimpan pengaturan, dan membaca URL tab aktif.

**Privasi:** Extension tidak mengirim data ke server mana pun. Semua komunikasi hanya ke aplikasi SwiftGet di `127.0.0.1` pada komputer
pengguna. Perlu halaman kebijakan privasi (URL) yang menyatakan hal ini; GitHub Pages atau README di repositori cukup.

## Peringatan jujur
Toko-toko cenderung menolak extension yang menonjolkan "pengunduh video YouTube". Tulis deskripsi dan tangkapan layar yang
berfokus pada **download manager** (mengambil alih unduhan file, antrean, resume), jangan menjual fitur unduh YouTube di
halaman tokonya. Proses tinjauan biasanya beberapa hari sampai beberapa minggu.
