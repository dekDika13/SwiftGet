"""Dialog: Tambah Unduhan (analisis URL + pemilih format), Pengaturan, Hitung mundur."""
import os, subprocess, sys, time
from pathlib import Path

import requests
from shiboken6 import isValid
from PySide6.QtCore import QDateTime, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDateTimeEdit, QDialog, QFileDialog,
                               QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import autostart, config
from ..analyzer import MEDIA_HOSTS, Analysis, analyze, fetch_media_info
from ..config import categorize, export_extension
from ..engine import ffmpeg_path
from ..util import fmt_duration, fmt_size
from . import icons, theme
from .winutil import bring_to_front

_THREADS = set()


class Func(QThread):
    done = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        _THREADS.add(self)
        self.finished.connect(lambda: _THREADS.discard(self))

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:  # noqa
            self.done.emit(e)


def button(text, variant=None, icon=None):
    b = QPushButton(text)
    if variant:
        b.setProperty("variant", variant)
    if icon:
        b.setIcon(icons.icon(icon, "#ffffff" if variant == "primary" else theme.c("text"), theme.c("muted"), 16))
    return b


def muted(text="", wrap=True):
    l = QLabel(text)
    l.setObjectName("Muted")
    l.setWordWrap(wrap)
    return l


HINT, BUSY, FILE, MEDIA, LINKS, MSG = range(6)
DEFAULT_MEDIA = {"mode": "video", "container": "mp4", "compat": True, "h264": True}


class MediaOptions(QWidget):
    """Pemilih resolusi/format/kompatibilitas yang bisa dipakai ulang (dialog Properti)."""

    PRESETS = [(2160, False), (1440, False), (1080, True), (720, True), (480, True), (360, True)]

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        seg = QHBoxLayout()
        self.b_vid, self.b_aud = QPushButton("Video"), QPushButton("Audio")
        grp = QButtonGroup(self)
        for b in (self.b_vid, self.b_aud):
            b.setObjectName("Seg")
            b.setCheckable(True)
            grp.addButton(b)
            seg.addWidget(b)
        seg.addStretch()
        self.b_load = button("Muat resolusi asli dari video", "ghost", "refresh")
        seg.addWidget(self.b_load)
        l.addLayout(seg)
        self.vbox, self.abox = QWidget(), QWidget()
        vf, af = QFormLayout(self.vbox), QFormLayout(self.abox)
        for fl in (vf, af):
            fl.setContentsMargins(0, 4, 0, 0)
        self.q = QComboBox()
        self.c = QComboBox()
        for c in ("mp4", "mkv", "webm"):
            self.c.addItem(c.upper(), c)
        self.k = QComboBox()
        self.k.addItem("Kompatibel: H.264 + AAC (Mac, iPhone, Windows)", True)
        self.k.addItem("Kualitas asli: VP9/AV1, tanpa konversi (VLC/IINA)", False)
        vf.addRow("Resolusi", self.q)
        vf.addRow("Format", self.c)
        vf.addRow("Kompatibilitas", self.k)
        self.a = QComboBox()
        for n, c in (("MP3", "mp3"), ("M4A (AAC)", "m4a"), ("Opus", "opus"), ("FLAC (lossless)", "flac"),
                     ("WAV", "wav"), ("Asli, tanpa konversi", "best")):
            self.a.addItem(n, c)
        self.br = QComboBox()
        for b in ("320", "256", "192", "128"):
            self.br.addItem(f"{b} kbps", b)
        af.addRow("Format", self.a)
        af.addRow("Kualitas", self.br)
        l.addWidget(self.vbox)
        l.addWidget(self.abox)
        self.hint = muted()
        l.addWidget(self.hint)
        self.set_qualities([{"height": h, "size": 0, "h264": x} for h, x in self.PRESETS])
        self.b_vid.toggled.connect(self._mode)
        for cb in (self.q, self.c, self.k):
            cb.currentIndexChanged.connect(self._hint)

    def set_qualities(self, quals, keep=0):
        self.q.blockSignals(True)
        self.q.clear()
        self.q.addItem("Terbaik yang tersedia", (0, True))
        for q in quals:
            sz = f"   ·   ≈ {fmt_size(q['size'])}" if q.get("size") else ""
            self.q.addItem(f"{q['height']}p   ·   {'H.264' if q.get('h264') else 'VP9/AV1'}{sz}",
                           (q["height"], bool(q.get("h264"))))
        for i in range(self.q.count()):
            if (self.q.itemData(i) or (0,))[0] == keep:
                self.q.setCurrentIndex(i)
        self.q.blockSignals(False)
        self._hint()

    def _mode(self):
        v = self.b_vid.isChecked()
        self.vbox.setVisible(v)
        self.abox.setVisible(not v)
        self._hint()

    def _hint(self, *_):
        mp4 = self.c.currentData() == "mp4"
        self.k.setEnabled(mp4)
        h, h264 = self.q.currentData() or (0, True)
        if self.b_aud.isChecked():
            txt = "MP3/M4A diputar di semua perangkat. FLAC/Opus/WAV butuh pemutar yang mendukungnya."
        elif not mp4:
            txt = "MKV/WebM tidak bisa diputar di QuickTime & iPhone (gunakan VLC/IINA)."
        elif self.k.currentData():
            txt = ("Resolusi ini hanya ada dalam VP9/AV1, jadi dikonversi ke H.264 setelah diunduh (lebih lama)."
                   if h and not h264 else "H.264 + AAC: bisa diputar di QuickTime, iPhone, dan Windows.")
        else:
            txt = "VP9/AV1 asli: kualitas/ukuran terbaik, tetapi sering tidak bisa diputar di QuickTime/iPhone."
        self.hint.setText(txt)

    def load(self, mo):
        (self.b_aud if mo.get("mode") == "audio" else self.b_vid).setChecked(True)
        self.set_qualities([{"height": h, "size": 0, "h264": x} for h, x in self.PRESETS], keep=int(mo.get("height") or 0))
        self.c.setCurrentIndex(max(0, self.c.findData(mo.get("container", "mp4"))))
        self.k.setCurrentIndex(0 if mo.get("compat", True) else 1)
        self.a.setCurrentIndex(max(0, self.a.findData(mo.get("audio_codec", "mp3"))))
        self.br.setCurrentIndex(max(0, self.br.findData(str(mo.get("audio_quality", "192")))))
        self._mode()

    def opts(self, base):
        o = dict(base)
        if self.b_aud.isChecked():
            o.update(mode="audio", audio_codec=self.a.currentData(), audio_quality=self.br.currentData())
        else:
            h, h264 = self.q.currentData() or (0, True)
            c = self.c.currentData()
            o.update(mode="video", height=h, h264=h264, container=c, compat=bool(c == "mp4" and self.k.currentData()))
        return o


class AddDialog(QDialog):
    def __init__(self, win, manager, cfg, urls="", payload=None):
        super().__init__(None)                 # tanpa induk: tetap bisa tampil saat jendela utama di tray/diminimalkan
        self.win = win
        self.m, self.cfg, self.payload = manager, cfg, payload or {}
        self.analysis, self.seq, self.custom_dir = None, 0, False
        self.setWindowTitle("Tambah unduhan")
        self.setMinimumWidth(640)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.has_ff = bool(ffmpeg_path(cfg))
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(12)
        t = QLabel("Tambah unduhan")
        t.setObjectName("DlgTitle")
        root.addWidget(t)
        root.addWidget(muted("Tempel satu atau banyak URL. SwiftGet otomatis mengenali file, video, atau halaman berisi banyak tautan."))
        self.url_edit = QPlainTextEdit()
        self.url_edit.setPlaceholderText("https://…  (satu URL per baris)")
        self.url_edit.setFixedHeight(70)
        root.addWidget(self.url_edit)
        row = QHBoxLayout()
        b_paste = button("Tempel", "ghost", "copy")
        b_paste.clicked.connect(lambda: self.url_edit.setPlainText(QApplication.clipboard().text().strip()))
        self.b_an = button("Analisis", None, "search")
        self.b_an.clicked.connect(self.start_analysis)
        row.addWidget(b_paste)
        row.addStretch()
        row.addWidget(self.b_an)
        root.addLayout(row)

        self.stack = QStackedWidget()
        self.stack.setMinimumHeight(200)
        self.stack.addWidget(self._pg_hint())
        self.stack.addWidget(self._pg_busy())
        self.stack.addWidget(self._pg_file())
        self.stack.addWidget(self._pg_media())
        self.stack.addWidget(self._pg_links())
        self.stack.addWidget(self._pg_msg())
        root.addWidget(self.stack)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        d = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.textEdited.connect(lambda _: setattr(self, "custom_dir", True))
        b_dir = button("Telusuri…")
        b_dir.clicked.connect(self._browse)
        d.addWidget(self.dir_edit, 1)
        d.addWidget(b_dir)
        form.addRow("Simpan ke", d)
        o = QHBoxLayout()
        self.conn = QSpinBox()
        self.conn.setRange(1, 32)
        self.conn.setValue(int(cfg["connections"]))
        self.conn.setSuffix(" koneksi")
        self.conn.setToolTip("File biasa: 8 koneksi. Video (YouTube dll.): 1 koneksi, karena banyak situs menolak koneksi paralel.")
        self.conn_touched = False
        self.conn.valueChanged.connect(lambda _: setattr(self, "conn_touched", True))
        self.sum_edit = QLineEdit()
        self.sum_edit.setPlaceholderText("Checksum opsional (sha256:… / md5)")
        o.addWidget(self.conn)
        o.addWidget(self.sum_edit, 1)
        form.addRow("Opsi", o)
        s = QHBoxLayout()
        self.sched = QCheckBox("Mulai pada")
        self.when = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.when.setCalendarPopup(True)
        self.when.setDisplayFormat("dd MMM yyyy  HH:mm")
        self.when.setEnabled(False)
        self.sched.toggled.connect(self.when.setEnabled)
        s.addWidget(self.sched)
        s.addWidget(self.when)
        s.addStretch()
        form.addRow("Jadwal", s)
        root.addLayout(form)

        bar = QHBoxLayout()
        b_cancel = button("Batal", "ghost")
        b_cancel.clicked.connect(self.reject)
        b_later = button("Simpan untuk nanti")
        b_later.clicked.connect(lambda: self._commit(False))
        self.b_go = button("Mulai unduh", "primary", "download")
        self.b_go.clicked.connect(lambda: self._commit(True))
        bar.addWidget(b_cancel)
        bar.addStretch()
        bar.addWidget(b_later)
        bar.addWidget(self.b_go)
        root.addLayout(bar)

        self.timer = QTimer(self, singleShot=True, interval=700)
        self.timer.timeout.connect(self._auto)
        self.url_edit.textChanged.connect(self.timer.start)
        self.dir_edit.setText(self.m.default_dir(""))
        if urls:
            self.url_edit.setPlainText(urls)

    # ------------------------------------------------------------- halaman
    def _pg_hint(self):
        w = QLabel("Tempel URL di atas untuk mulai.\n\nContoh: link Google Drive, MediaFire, YouTube, atau file langsung (.zip, .exe, .mp4).")
        w.setAlignment(Qt.AlignCenter)
        w.setObjectName("Muted")
        return w

    def _pg_busy(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addStretch()
        lab = QLabel("Menganalisis tautan…")
        lab.setAlignment(Qt.AlignCenter)
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        l.addWidget(lab)
        l.addWidget(bar)
        l.addStretch()
        return w

    def _card(self):
        f = QFrame()
        f.setObjectName("Card")
        l = QVBoxLayout(f)
        l.setContentsMargins(16, 14, 16, 14)
        return f, l

    def _pg_file(self):
        f, l = self._card()
        self.f_name = QLineEdit()
        self.f_name.textChanged.connect(self._sync_dir)
        self.f_info = muted()
        l.addWidget(muted("Nama file"))
        l.addWidget(self.f_name)
        l.addWidget(self.f_info)
        l.addStretch()
        return f

    def _pg_media(self):
        f, l = self._card()
        top = QHBoxLayout()
        self.thumb = QLabel()
        self.thumb.setObjectName("Thumb")
        self.thumb.setFixedSize(176, 99)
        self.thumb.setAlignment(Qt.AlignCenter)
        info = QVBoxLayout()
        self.m_title = QLabel()
        self.m_title.setWordWrap(True)
        self.m_title.setStyleSheet("font-weight:700;font-size:14px")
        self.m_meta = muted()
        seg = QHBoxLayout()
        self.b_vid, self.b_aud = QPushButton("Video"), QPushButton("Audio")
        grp = QButtonGroup(self)
        for b in (self.b_vid, self.b_aud):
            b.setObjectName("Seg")
            b.setCheckable(True)
            grp.addButton(b)
            seg.addWidget(b)
        seg.addStretch()
        self.b_vid.setChecked(True)
        self.b_vid.toggled.connect(self._mode)
        info.addWidget(self.m_title)
        info.addWidget(self.m_meta)
        info.addStretch()
        info.addLayout(seg)
        top.addWidget(self.thumb)
        top.addLayout(info, 1)
        l.addLayout(top)
        self.vbox, self.abox = QWidget(), QWidget()
        vf, af = QFormLayout(self.vbox), QFormLayout(self.abox)
        for fl in (vf, af):
            fl.setContentsMargins(0, 6, 0, 0)
        self.q_combo, self.c_combo = QComboBox(), QComboBox()
        for c in ("mp4", "mkv", "webm"):
            self.c_combo.addItem(c.upper(), c)
        vf.addRow("Resolusi", self.q_combo)
        vf.addRow("Format", self.c_combo)
        self.compat_combo = QComboBox()
        cfg = self.cfg
        self.compat_combo.addItem("Kompatibel: H.264 + AAC (Mac, iPhone, Windows)", True)
        self.compat_combo.addItem("Kualitas asli: VP9/AV1, tanpa konversi (VLC/IINA)", False)
        self.compat_combo.setCurrentIndex(0 if cfg["video_compat"] else 1)
        vf.addRow("Kompatibilitas", self.compat_combo)
        self.a_combo, self.b_combo = QComboBox(), QComboBox()
        for n, c in (("MP3", "mp3"), ("M4A (AAC)", "m4a"), ("Opus", "opus"), ("FLAC (lossless)", "flac"),
                     ("WAV", "wav"), ("Asli — tanpa konversi", "best")):
            self.a_combo.addItem(n, c)
        for b in ("320", "256", "192", "128"):
            self.b_combo.addItem(f"{b} kbps", b)
        self.b_combo.setCurrentIndex(2)
        af.addRow("Format", self.a_combo)
        af.addRow("Kualitas", self.b_combo)
        l.addWidget(self.vbox)
        self.codec_hint = muted()
        l.addWidget(self.codec_hint)
        for cb in (self.q_combo, self.c_combo, self.compat_combo):
            cb.currentIndexChanged.connect(self._codec_hint)
        l.addWidget(self.abox)
        self.abox.hide()
        self.k_playlist = QCheckBox("Unduh seluruh playlist")
        self.k_subs = QCheckBox("Unduh subtitle (ID/EN)")
        ck = QHBoxLayout()
        ck.addWidget(self.k_playlist)
        ck.addWidget(self.k_subs)
        ck.addStretch()
        l.addLayout(ck)
        self.ff_warn = QLabel("FFmpeg tidak ditemukan: video resolusi tinggi tidak bisa digabung dan konversi MP3 tidak tersedia. "
                              "Jalankan: pip install imageio-ffmpeg, atau atur path-nya di Pengaturan › Video.")
        self.ff_warn.setObjectName("Warn")
        self.ff_warn.setWordWrap(True)
        self.ff_warn.setVisible(False)
        l.addWidget(self.ff_warn)
        return f

    def _pg_links(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.l_info = muted()
        self.l_list = QListWidget()
        self.l_list.setObjectName("Links")
        r = QHBoxLayout()
        ba, bn = button("Pilih semua", "ghost"), button("Kosongkan", "ghost")
        ba.clicked.connect(lambda: self._check_all(True))
        bn.clicked.connect(lambda: self._check_all(False))
        r.addWidget(ba)
        r.addWidget(bn)
        r.addStretch()
        l.addWidget(self.l_info)
        l.addWidget(self.l_list, 1)
        l.addLayout(r)
        return w

    def _pg_msg(self):
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self.msg.setAlignment(Qt.AlignCenter)
        return self.msg

    # -------------------------------------------------------------- analisis
    def _lines(self):
        return [x.strip() for x in self.url_edit.toPlainText().splitlines() if x.strip()]

    def _auto(self):
        ls = self._lines()
        if len(ls) == 1 and ls[0].lower().startswith("http"):
            self.start_analysis()
        elif not ls:
            self.stack.setCurrentIndex(HINT)

    def start_analysis(self):
        ls = self._lines()
        if len(ls) != 1:
            if len(ls) > 1:
                self.msg.setText(f"{len(ls)} URL akan ditambahkan sebagai unduhan terpisah.")
                self.stack.setCurrentIndex(MSG)
                self.analysis = None
            return
        self.seq += 1
        seq, p = self.seq, self.payload
        self.stack.setCurrentIndex(BUSY)
        self.analysis = None
        th = Func(lambda: analyze(self.cfg, ls[0], p.get("referer", ""), p.get("cookies", ""), p.get("userAgent", ""),
                                  p.get("alt") or ()))
        th.done.connect(lambda res, s=seq: self._result(res, s))
        th.start()

    def _result(self, res, seq):
        if not isValid(self) or seq != self.seq:
            return
        if isinstance(res, Exception):
            res = Analysis(kind="error", message=str(res))
        self.analysis = res
        if res.kind == "file":
            self._set_conn(self.cfg["connections"])
            name = res.filename or self.payload.get("filename", "")
            self.f_name.setText(name)
            self.f_info.setText(f"Ukuran: {fmt_size(res.total) if res.total else 'tidak diketahui'}   ·   "
                                f"Resume: {'didukung' if res.resumable else 'tidak didukung'}   ·   "
                                f"Tipe: {res.mime or '—'}" + (f"   ·   Sumber: {res.resolver}" if res.resolver != "direct" else ""))
            self.stack.setCurrentIndex(FILE)
        elif res.kind == "media":
            self._set_conn(self.cfg["media_connections"])
            self._fill_media(res.media)
            self.stack.setCurrentIndex(MEDIA)
        elif res.kind == "links":
            self.l_info.setText(res.message + f" ({len(res.links)} tautan)")
            self.l_list.clear()
            for k in res.links:
                it = QListWidgetItem(f"{k['name']}   ·   {k['category']}")
                it.setData(Qt.UserRole, k)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Unchecked)
                self.l_list.addItem(it)
            self.stack.setCurrentIndex(LINKS)
        else:
            self.msg.setText(res.message or "Tidak ada yang bisa diunduh.")
            self.stack.setCurrentIndex(MSG)
        self._sync_dir()

    def _fill_media(self, mi):
        self.m_title.setText(mi["title"])
        bits = [mi.get("uploader"), fmt_duration(mi.get("duration")), mi.get("extractor")]
        if mi.get("is_playlist"):
            bits.insert(0, f"Playlist · {mi['count']} video")
        self.m_meta.setText("  ·  ".join(b for b in bits if b))
        self.q_combo.clear()
        self.q_combo.addItem("Terbaik yang tersedia", (0, True))
        for q in mi["qualities"]:
            sz = f"   ·   ≈ {fmt_size(q['size'])}" if q["size"] else ""
            codec = "H.264" if q.get("h264") else "VP9/AV1"
            self.q_combo.addItem(f"{q['height']}p   ·   {codec}{sz}", (q["height"], bool(q.get("h264"))))
        self._codec_hint()
        self.k_playlist.setVisible(True)
        self.k_playlist.setChecked(bool(mi.get("is_playlist")))
        self.ff_warn.setVisible(not self.has_ff)
        (self.b_aud if mi.get("audio_only") else self.b_vid).setChecked(True)
        self.thumb.setText("")
        self.thumb.setPixmap(QPixmap())
        if mi.get("thumbnail"):
            url, seq = mi["thumbnail"], self.seq
            th = Func(lambda: requests.get(url, timeout=10).content)
            th.done.connect(lambda data, s=seq: self._thumb(data, s))
            th.start()

    def _thumb(self, data, seq):
        if not isValid(self) or seq != self.seq or isinstance(data, Exception):
            return
        pm = QPixmap()
        if pm.loadFromData(data):
            self.thumb.setPixmap(pm.scaled(176, 99, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def _codec_hint(self, *_):
        mp4 = self.c_combo.currentData() == "mp4"
        self.compat_combo.setEnabled(mp4)
        h, h264 = self.q_combo.currentData() or (0, True)
        if not mp4:
            txt = "MKV/WebM tidak bisa diputar di QuickTime & iPhone (gunakan VLC). Pilih MP4 untuk kompatibilitas penuh."
        elif self.compat_combo.currentData():
            txt = ("Resolusi ini hanya tersedia dalam VP9/AV1. Setelah diunduh, SwiftGet mengonversinya ke H.264 "
                   "(lebih lama, butuh FFmpeg)." if h and not h264 else
                   "Hasil H.264 + AAC: bisa diputar di QuickTime, iPhone, dan Windows.")
        else:
            txt = "VP9/AV1 + Opus: kualitas terbaik, tetapi sering tidak bisa diputar di QuickTime/iPhone."
        self.codec_hint.setText(txt)

    def _mode(self):
        vid = self.b_vid.isChecked()
        self.vbox.setVisible(vid)
        self.abox.setVisible(not vid)
        self._sync_dir()

    def _check_all(self, on):
        for i in range(self.l_list.count()):
            self.l_list.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih folder", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)
            self.custom_dir = True

    def _category(self):
        a = self.analysis
        if a and a.kind == "media":
            return "Video" if self.b_vid.isChecked() else "Musik"
        if a and a.kind == "file":
            return categorize(self.f_name.text())
        return ""

    def _set_conn(self, v):
        if not self.conn_touched:
            self.conn.blockSignals(True)
            self.conn.setValue(int(v))
            self.conn.blockSignals(False)

    def _conn(self, media):
        return self.conn.value() if self.conn_touched else int(self.cfg["media_connections" if media else "connections"])

    def _sync_dir(self):
        if not self.custom_dir:
            self.dir_edit.setText(self.m.default_dir(self._category()))

    # ---------------------------------------------------------------- simpan
    def _media_opts(self):
        mi = self.analysis.media
        if self.b_aud.isChecked():
            codec = self.a_combo.currentData()
            return {"mode": "audio", "audio_codec": codec if self.has_ff else "best",
                    "audio_quality": self.b_combo.currentData(), "playlist": self.k_playlist.isChecked(),
                    "subs": False}
        h, h264 = self.q_combo.currentData() or (0, True)
        c = self.c_combo.currentData()
        return {"mode": "video", "height": h, "h264": h264, "container": c,
                "compat": bool(c == "mp4" and self.compat_combo.currentData()),
                "playlist": self.k_playlist.isChecked(), "subs": self.k_subs.isChecked()}

    def _commit(self, start):
        lines = self._lines()
        p, a = self.payload, self.analysis
        if not lines and not (a and a.kind == "links"):
            return
        start_at = float(self.when.dateTime().toSecsSinceEpoch()) if self.sched.isChecked() else 0.0
        common = dict(save_dir=self.dir_edit.text() if self.custom_dir else None,
                      referer=p.get("referer", ""), cookies=p.get("cookies", ""), user_agent=p.get("userAgent", ""),
                      start=start, start_at=start_at)
        jobs = []          # (url, kwargs) untuk setiap unduhan yang akan dibuat
        if len(lines) == 1 and a and a.kind == "file":
            jobs.append((lines[0], dict(filename=self.f_name.text().strip(), checksum=self.sum_edit.text(),
                                        connections=self._conn(False))))
        elif len(lines) == 1 and a and a.kind == "media":
            jobs.append((lines[0], dict(kind="media", media_opts=self._media_opts(), title=a.media["title"],
                                        connections=self._conn(True))))
        elif a and a.kind == "links":
            for i in range(self.l_list.count()):
                it = self.l_list.item(i)
                if it.checkState() == Qt.Checked:
                    k = it.data(Qt.UserRole)
                    if k["ext"] in ("m3u8", "mpd"):
                        jobs.append((k["url"], dict(kind="media", media_opts=dict(DEFAULT_MEDIA), referer=a.url,
                                                    connections=self._conn(True))))
                    else:
                        jobs.append((k["url"], dict(filename=k["name"], referer=a.url, connections=self._conn(False))))
            if not jobs:
                QMessageBox.information(self, "Pilih tautan", "Centang minimal satu tautan.")
                return
        else:
            for u in lines:
                if MEDIA_HOSTS.search(u):
                    jobs.append((u, dict(kind="media", media_opts=dict(DEFAULT_MEDIA), connections=self._conn(True))))
                else:
                    jobs.append((u, dict(checksum=self.sum_edit.text() if len(lines) == 1 else "",
                                         connections=self._conn(False))))
        policy = self._dup_policy(jobs, common["save_dir"])
        if policy is None:
            return
        for url, kw in jobs:
            self.m.add(url, dup=policy, **{**common, **kw})
        self.accept()

    def _dup_policy(self, jobs, save_dir):
        """Cek duplikat. Kembalikan 'number' | 'replace', atau None bila dibatalkan."""
        found = []
        for url, kw in jobs:
            d = self.m.find_duplicates(url, kind=kw.get("kind", "file"), filename=kw.get("filename", ""), save_dir=save_dir,
                                       media_opts=kw.get("media_opts"), title=kw.get("title", ""))
            if d:
                found.append((url, kw, d))
        if not found:
            return "number"
        dlg = DuplicateDialog(self, found)
        dlg.exec()
        if dlg.choice == "open":
            path = next((x["path"] for _, _, d in found for x in d if x["path"]), "")
            if path and self.win:
                self.win.reveal(path)
            return None
        if dlg.choice == "replace":
            for _, _, d in found:
                for x in d:
                    if x["type"] == "task" and x["task"].status == "completed":
                        self.m.remove(x["task"].id, delete_file=False)     # file lama akan ditimpa; hapus entri lamanya
            return "replace"
        return "number" if dlg.choice == "number" else None


class DuplicateDialog(QDialog):
    """Peringatan duplikat: beri nomor / ganti file lama / buka folder / batal."""

    def __init__(self, parent, found):
        super().__init__(parent)
        self.choice = "cancel"
        url, kw, dups = found[0]
        path = next((x["path"] for _, _, d in found for x in d if x["path"]), "")
        self.setWindowTitle("Unduhan yang sama terdeteksi")
        self.setMinimumWidth(520)
        l = QVBoxLayout(self)
        l.setContentsMargins(24, 22, 24, 18)
        l.setSpacing(10)
        t = QLabel("File ini sudah pernah diunduh" if path else "Unduhan yang sama sudah ada di daftar")
        t.setObjectName("DlgTitle")
        l.addWidget(t)
        name = kw.get("filename") or kw.get("title") or url
        if len(found) > 1:
            body = f"{len(found)} dari unduhan yang akan ditambahkan sudah ada. Contoh:\n{name}"
        else:
            st = dups[0].get("status", "")
            body = name + ("\n\nLokasi file sebelumnya:\n" + path if path else
                           f"\n\nStatus unduhan yang ada: {st}")
        lab = muted(body)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l.addWidget(lab)
        l.addSpacing(6)

        def add(text, choice, variant=None):
            b = button(text, variant)
            b.setMinimumHeight(38)
            b.clicked.connect(lambda: (setattr(self, "choice", choice), self.accept()))
            l.addWidget(b)
            return b
        add("Simpan dengan nomor di belakang nama  ( … (1) )", "number", "primary")
        if path:
            add("Ganti file lama (timpa)", "replace", "danger")
            add("Buka folder file sebelumnya", "open")
        c = button("Batal", "ghost")
        c.clicked.connect(self.reject)
        l.addWidget(c)


class CountdownDialog(QDialog):
    def __init__(self, parent, action_label, seconds=30):
        super().__init__(parent)
        self.setWindowTitle("Antrean selesai")
        self.left = seconds
        self.label = QLabel()
        l = QVBoxLayout(self)
        l.setContentsMargins(24, 20, 24, 20)
        l.addWidget(self.label)
        b = button("Batalkan", "primary")
        b.clicked.connect(self.reject)
        l.addWidget(b)
        self.action_label = action_label
        self.t = QTimer(self, interval=1000)
        self.t.timeout.connect(self._tick)
        self.t.start()
        self._tick(first=True)

    def _tick(self, first=False):
        if not first:
            self.left -= 1
        self.label.setText(f"Semua unduhan selesai.\n{self.action_label} dalam {self.left} detik…")
        if self.left <= 0:
            self.t.stop()
            self.accept()


class SettingsDialog(QDialog):
    def __init__(self, win, cfg, manager, tab=0):
        super().__init__(win)
        self.cfg, self.m, self.win = cfg, manager, win
        self.setWindowTitle("Pengaturan")
        self.setMinimumSize(700, 540)
        self.fields = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        tabs = QTabWidget()
        tabs.tabBar().setElideMode(Qt.ElideNone)
        tabs.tabBar().setUsesScrollButtons(False)
        root.addWidget(tabs, 1)
        tabs.addTab(self._tab_general(), "Umum")
        tabs.addTab(self._tab_network(), "Jaringan")
        tabs.addTab(self._tab_video(), "Video & Audio")
        tabs.addTab(self._tab_browser(), "Browser")
        tabs.setCurrentIndex(tab)
        bar = QHBoxLayout()
        bar.addStretch()
        c, s = button("Batal", "ghost"), button("Simpan", "primary")
        c.clicked.connect(self.reject)
        s.clicked.connect(self._save)
        bar.addWidget(c)
        bar.addWidget(s)
        root.addLayout(bar)

    # helper pembuat field
    def _reg(self, key, w, form, label):
        self.fields[key] = w
        if form is not None:
            form.addRow(label, w)
        v = self.cfg[key]
        if isinstance(w, QCheckBox):
            w.setChecked(bool(v))
        elif isinstance(w, QSpinBox):
            w.setValue(int(v))
        elif isinstance(w, QComboBox):
            w.setCurrentIndex(max(0, w.findData(v)))
        else:
            w.setText(str(v))
        return w

    def _check(self, key, text, form):
        w = QCheckBox(text)
        self._reg(key, w, form, "")
        return w

    def _spin(self, key, lo, hi, form, label, suffix=""):
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setSuffix(suffix)
        return self._reg(key, w, form, label)

    def _combo(self, key, items, form, label):
        w = QComboBox()
        for n, d in items:
            w.addItem(n, d)
        return self._reg(key, w, form, label)

    def _page(self):
        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(8, 18, 8, 8)
        f.setVerticalSpacing(12)
        f.setHorizontalSpacing(16)
        return w, f

    def _path_row(self, key, form, label, folder=True):
        w = QLineEdit()
        self._reg(key, w, None, label)
        row = QHBoxLayout()
        b = button("Telusuri…")

        def pick():
            p = (QFileDialog.getExistingDirectory(self, "Pilih folder", w.text()) if folder
                 else QFileDialog.getOpenFileName(self, "Pilih file", w.text())[0])
            if p:
                w.setText(p)
        b.clicked.connect(pick)
        row.addWidget(w, 1)
        row.addWidget(b)
        form.addRow(label, row)
        return w

    def _tab_general(self):
        w, f = self._page()
        self._path_row("download_dir", f, "Folder unduhan")
        self._check("auto_categorize", "Pisahkan otomatis ke subfolder kategori (Video, Musik, Arsip, …)", f)
        self._spin("max_concurrent", 1, 10, f, "Unduhan bersamaan")
        self._spin("connections", 1, 32, f, "Koneksi per file", " koneksi")
        self._spin("media_connections", 1, 16, f, "Koneksi video (YouTube dll.)", " koneksi")
        self._spin("speed_limit_kbps", 0, 10_000_000, f, "Batas kecepatan", " KB/s  (0 = tanpa batas)")
        self._combo("after_queue", [("Tidak ada", "nothing"), ("Tutup SwiftGet", "quit"), ("Tidur (sleep)", "sleep"),
                                    ("Matikan komputer", "shutdown")], f, "Setelah antrean selesai")
        self._combo("theme", [(label, key) for key, label in theme.THEMES], f, "Tema")
        if sys.platform == "darwin":
            self._check("native_glass", "Efek kaca native macOS (eksperimental, perlu pyobjc & restart)", f)
        self._check("autostart", "Jalankan SwiftGet saat login (di latar belakang, agar extension selalu terhubung)", f)
        self._check("clipboard_monitor", "Deteksi URL yang disalin ke clipboard", f)
        self._check("minimize_to_tray", "Tutup jendela = sembunyikan ke system tray", f)
        self._check("notify", "Tampilkan notifikasi saat unduhan selesai/gagal", f)
        return w

    def _tab_network(self):
        w, f = self._page()
        self._reg("proxy", QLineEdit(), f, "Proxy").setPlaceholderText("http://host:port atau socks5://host:port")
        self._reg("user_agent", QLineEdit(), f, "User-Agent")
        self._spin("timeout", 5, 300, f, "Timeout", " detik")
        self._spin("retries", 0, 30, f, "Percobaan ulang")
        return w

    def _tab_video(self):
        w, f = self._page()
        self._path_row("ffmpeg_path", f, "Lokasi FFmpeg", folder=False)
        found = ffmpeg_path(self.cfg)
        f.addRow("", muted(f"Terdeteksi: {found}" if found else "FFmpeg belum ditemukan. Cara termudah (tanpa brew): pip install imageio-ffmpeg, lalu mulai ulang SwiftGet. "
                           "Atau unduh binary FFmpeg sendiri dan pilih lokasinya di atas."))
        self._combo("cookies_browser", [("Tidak dipakai", ""), ("Chrome", "chrome"), ("Firefox", "firefox"), ("Edge", "edge"),
                                        ("Brave", "brave"), ("Safari", "safari"), ("Opera", "opera"), ("Vivaldi", "vivaldi")],
                    f, "Ambil cookies dari")
        f.addRow("", muted("Untuk video yang butuh login/usia. Safari di macOS memerlukan izin Full Disk Access."))
        self._combo("video_compat", [("Kompatibel: H.264 + AAC (diputar di Mac, iPhone, Windows)", True),
                                     ("Kualitas asli: VP9/AV1 tanpa konversi (untuk VLC/IINA)", False)], f, "Mode video bawaan")
        self._check("embed_metadata", "Sematkan metadata (judul, artis) ke file", f)
        self._check("embed_thumbnail", "Sematkan thumbnail sebagai cover", f)
        self.upd = button("Perbarui yt-dlp", None, "refresh")
        self.upd_lab = muted()
        self.upd.clicked.connect(self._update_ytdlp)
        f.addRow("", self.upd)
        f.addRow("", self.upd_lab)
        return w

    def _update_ytdlp(self):
        if getattr(sys, "frozen", False):
            self.upd_lab.setText("Versi terpaket: unduh rilis SwiftGet terbaru untuk memperbarui yt-dlp.")
            return
        self.upd.setEnabled(False)
        self.upd_lab.setText("Memperbarui…")

        def job():
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"], capture_output=True, text=True)
            return (r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] or [""])
        th = Func(job)
        th.done.connect(self._upd_done)
        th.start()

    def _upd_done(self, res):
        self.upd.setEnabled(True)
        self.upd_lab.setText("Gagal: " + str(res) if isinstance(res, Exception)
                             else ("Berhasil diperbarui. Mulai ulang SwiftGet." if res[0] == 0 else "Gagal: " + res[1][0]))

    def _tab_browser(self):
        w, f = self._page()
        f.addRow("", muted("Extension terhubung otomatis: setelah dipasang, SwiftGet menanyakan izin sekali (klik \"Ya\"). "
                           "Tidak perlu menyalin token."))
        row = QHBoxLayout()
        for label, key in (("Chrome", "chrome"), ("Edge", "edge"), ("Brave", "brave"), ("Firefox", "firefox")):
            b = button(label)
            b.clicked.connect(lambda _=False, k=key: self.win.install_extension(k))
            row.addWidget(b)
        row.addStretch()
        f.addRow("Pasang extension", row)
        bf = button("Buka folder extension", None, "folder")
        bf.clicked.connect(lambda: self.win.reveal(str(export_extension())))
        f.addRow("", bf)
        self._check("server_enabled", "Aktifkan server lokal untuk extension browser", f)
        self._spin("server_port", 1024, 65535, f, "Port")
        self._check("extension_ask", "Tampilkan dialog konfirmasi saat extension mengirim unduhan", f)
        self.paired = muted()
        f.addRow("Terhubung", self.paired)
        self._paired_label()
        bu = button("Putuskan semua extension", "danger")
        bu.clicked.connect(self._unpair)
        f.addRow("", bu)
        row = QHBoxLayout()
        self.tok = QLineEdit(self.cfg["token"])
        self.tok.setReadOnly(True)
        bc = button("Salin")
        bc.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.tok.text()))
        row.addWidget(self.tok, 1)
        row.addWidget(bc)
        f.addRow("Token (lanjutan)", row)
        return w

    def _paired_label(self):
        n = len(self.cfg["paired_origins"])
        self.paired.setText(f"{n} extension terhubung" if n else "Belum ada extension yang terhubung")

    def _unpair(self):
        import secrets
        self.cfg["paired_origins"] = []
        self.cfg["token"] = secrets.token_urlsafe(24)
        self.tok.setText(self.cfg["token"])
        self.cfg.save()
        self._paired_label()

    def _save(self):
        old = (self.cfg["server_enabled"], self.cfg["server_port"], self.cfg["theme"], self.cfg["native_glass"])
        for k, w in self.fields.items():
            self.cfg[k] = (w.isChecked() if isinstance(w, QCheckBox) else w.value() if isinstance(w, QSpinBox)
                           else w.currentData() if isinstance(w, QComboBox) else w.text().strip())
        self.cfg.save()
        autostart.enable(bool(self.cfg["autostart"]))
        self.m.apply_settings()
        self.win.settings_changed(old)
        self.accept()


class PropertiesDialog(QDialog):
    """Ubah koneksi, lokasi, nama, serta resolusi/format video dari unduhan yang sudah ada (klik kanan › Properti)."""

    def __init__(self, win, manager, tasks):
        super().__init__(win)
        self.m, self.tasks = manager, tasks
        t = tasks[0]
        one = len(tasks) == 1
        media = [x for x in tasks if x.kind == "media"]
        self.setWindowTitle("Properti unduhan")
        self.setMinimumWidth(600)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(12)
        title = QLabel(t.name if one else f"{len(tasks)} unduhan terpilih")
        title.setObjectName("DlgTitle")
        root.addWidget(title)
        if one:
            root.addWidget(muted(t.url, wrap=False))
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        self.name = QLineEdit(t.filename if one else "")
        self.name.setEnabled(one and (t.kind == "file" or t.status == "completed"))
        if not one:
            self.name.setPlaceholderText("(tidak diubah)")
        form.addRow("Nama file", self.name)
        row = QHBoxLayout()
        self.dir = QLineEdit(t.save_dir if all(x.save_dir == t.save_dir for x in tasks) else "")
        self.dir.setPlaceholderText("(tidak diubah)")
        b = button("Telusuri…")
        b.clicked.connect(self._browse)
        row.addWidget(self.dir, 1)
        row.addWidget(b)
        form.addRow("Simpan di", row)
        self.conn = QSpinBox()
        self.conn.setRange(1, 32)
        self.conn.setValue(t.connections)
        self.conn.setSuffix(" koneksi")
        form.addRow("Koneksi", self.conn)
        root.addLayout(form)

        self.mopts = None
        if media and len(media) == len(tasks):
            sep = QLabel("Resolusi & format")
            sep.setStyleSheet("font-weight:700")
            root.addWidget(sep)
            self.mopts = MediaOptions(manager.cfg)
            self.mopts.load(t.media_opts)
            self.mopts.b_load.clicked.connect(self._load_real)
            root.addWidget(self.mopts)
            self.mnote = muted("Mengubah resolusi/format akan mengunduh ulang media ini." if t.status != "completed" else
                               "Unduhan sudah selesai: perubahan resolusi/format akan ditambahkan sebagai unduhan BARU "
                               "(file lama tetap disimpan).")
            root.addWidget(self.mnote)
        self.resume = QCheckBox("Lanjutkan unduhan setelah disimpan")
        self.resume.setChecked(True)
        self.resume.setVisible(any(x.status != "completed" for x in tasks))
        root.addWidget(self.resume)
        notes = []
        if any(x.is_active for x in tasks):
            notes.append("Unduhan yang sedang berjalan akan dijeda sebentar, lalu dilanjutkan.")
        if any(x.status == "completed" for x in tasks):
            notes.append("File yang sudah selesai akan dipindahkan/diganti namanya di disk.")
        notes.append("Tips: kalau unduhan gagal/ditolak server, turunkan jumlah koneksi (YouTube paling aman 1).")
        root.addWidget(muted("  ".join(notes)))
        bar = QHBoxLayout()
        c, ok = button("Batal", "ghost"), button("Simpan", "primary")
        c.clicked.connect(self.reject)
        ok.clicked.connect(self._save)
        bar.addStretch()
        bar.addWidget(c)
        bar.addWidget(ok)
        root.addLayout(bar)
        self._t0 = t

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Pilih folder", self.dir.text())
        if d:
            self.dir.setText(d)

    def _load_real(self):
        t = self._t0
        self.mopts.b_load.setEnabled(False)
        self.mopts.b_load.setText("Memuat…")
        keep = int(self.mopts.q.currentData()[0]) if self.mopts.q.currentData() else 0
        th = Func(lambda: fetch_media_info(self.m.cfg, t.url, t.referer, t.cookies))
        th.done.connect(lambda res, k=keep: self._loaded(res, k))
        th.start()

    def _loaded(self, res, keep):
        if not isValid(self):
            return
        self.mopts.b_load.setEnabled(True)
        self.mopts.b_load.setText("Muat resolusi asli dari video")
        if isinstance(res, Exception) or not res[0]:
            self.mnote.setText("Gagal memuat daftar resolusi: " + (str(res) if isinstance(res, Exception) else res[1]))
            return
        self.mopts.set_qualities(res[0]["qualities"], keep=keep)

    def _save(self):
        new_dir = self.dir.text().strip() or None
        for t in self.tasks:
            mo = None
            if self.mopts:
                new = self.mopts.opts(t.media_opts)
                if new != t.media_opts:
                    if t.status == "completed":
                        self.m.add(t.url, kind="media", media_opts=new, title=t.title, referer=t.referer, cookies=t.cookies,
                                   user_agent=t.user_agent, connections=self.conn.value(),
                                   save_dir=None if t.auto_dir else t.save_dir)
                    else:
                        mo = new
            self.m.update_task(t.id, connections=self.conn.value() if self.conn.value() != t.connections else None,
                               save_dir=new_dir if new_dir and new_dir != t.save_dir else None,
                               filename=self.name.text().strip() if len(self.tasks) == 1 and self.name.isEnabled()
                               and self.name.text().strip() != t.filename else None,
                               media_opts=mo, resume=self.resume.isChecked())
        self.accept()
