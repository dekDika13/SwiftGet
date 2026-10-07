"""Jendela utama SwiftGet."""
import os, re, shutil, subprocess, sys, threading
from urllib.parse import urlparse

from shiboken6 import isValid
from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSizePolicy, QSplitter, QStackedWidget,
                               QSystemTrayIcon, QTableView, QToolButton, QVBoxLayout, QWidget)

from .. import autostart, resolvers
from ..analyzer import MEDIA_HOSTS
from ..config import (ALL_EXTS, APP_NAME, APP_VERSION, CATEGORY_NAMES, EXT_STORE, data_dir, export_extension)
from ..server import LocalServer
from ..util import fmt_eta, fmt_size, fmt_speed
from . import icons, theme
from . import mac_glass
from .dialogs import AddDialog, CountdownDialog, PropertiesDialog, SettingsDialog, WelcomeDialog
from .playlist import PlaylistDialog
from .table import (CAT_COLOR, CAT_ICON, ROLE_TASK, STATUS_LABEL, DownloadModel, NameDelegate, ProgressDelegate, Proxy,
                    StatusDelegate)
from .widgets import Backdrop, SegmentMap, Sidebar, SpeedGraph
from .winutil import bring_to_front


class ElideLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.full = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def set_full(self, t):
        self.full = t
        self.setToolTip(t)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(self.palette().windowText().color())
        p.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, self.fontMetrics().elidedText(self.full, Qt.ElideMiddle, self.width()))


class MainWindow(QMainWindow):
    sig_event = Signal(str, int)
    sig_ext = Signal(str, object)
    sig_pair = Signal(str, object)

    def __init__(self, cfg, manager):
        super().__init__()
        self.cfg, self.m = cfg, manager
        self.dialogs, self.server, self._pl_dialogs = [], None, {}
        self.cfg["autostart"] = autostart.is_enabled()      # selaraskan dengan kondisi sebenarnya di OS (installer bisa mengaktifkannya)
        self._quitting = self._cleaned = self._hint_shown = False
        self._pending_url = self._last_clip = ""
        self._sig, self._tick, self._disk = None, 0, ""
        self.icon_buttons = []
        self._native_pending = bool(cfg["native_glass"]) and sys.platform == "darwin"
        if self._native_pending:
            theme.native = True
            self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.app_icon())
        self.resize(1260, 780)
        self.setMinimumSize(980, 560)
        self.setAcceptDrops(True)
        self._build()
        self._make_tray()
        self.apply_theme()
        self.sig_event.connect(self._on_event)
        self.sig_ext.connect(self._on_ext)
        self.sig_pair.connect(self._on_pair)
        self._pairing = False
        if (os.path.exists(os.path.expanduser("~/SwiftGet Extension"))):
            threading.Thread(target=lambda: export_extension(), daemon=True).start()   # segarkan extension yang sudah diekspor
        self.m.on_event = lambda k, i: self.sig_event.emit(k, i)
        QGuiApplication.clipboard().dataChanged.connect(self._clip)
        QApplication.instance().aboutToQuit.connect(self._cleanup)
        for seq, slot in ((QKeySequence.New, self.open_add), (QKeySequence.Find, lambda: self.search.setFocus())):
            QShortcut(seq, self).activated.connect(slot)
        for key in (Qt.Key_Delete, Qt.Key_Backspace):
            QShortcut(QKeySequence(key), self.table, context=Qt.WidgetShortcut).activated.connect(self.act_remove)
        for key in (Qt.Key_Return, Qt.Key_Enter):
            QShortcut(QKeySequence(key), self.table, context=Qt.WidgetShortcut).activated.connect(self.act_open)
        self.start_server()
        if not self.cfg["onboarded"] and "--background" not in sys.argv:
            QTimer.singleShot(900, self._onboard)
        self.timer = QTimer(self, interval=500)
        self.timer.timeout.connect(self._refresh)
        self.timer.start()
        self._refresh()

    # ------------------------------------------------------------------ UI
    def tool(self, text, icon, slot, tip=""):
        b = QToolButton()
        b.setObjectName("ToolBtn")
        b.setText(text)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        b.setIconSize(QSize(22, 22))
        b.setToolTip(tip or text)
        b.setCursor(Qt.PointingHandCursor)
        if slot:
            b.clicked.connect(slot)
        self.icon_buttons.append((b, icon))
        return b

    def _build(self):
        central = Backdrop()
        self.setCentralWidget(central)
        self.root_l = QHBoxLayout(central)
        self.root_l.addWidget(self._sidebar())
        self.root_l.addWidget(self._main(), 1)
        sb = self.statusBar()
        sb.setSizeGripEnabled(False)
        self.lbl_counts, self.lbl_srv = QLabel(), QLabel()
        sb.addWidget(self.lbl_counts, 1)
        sb.addPermanentWidget(self.lbl_srv)
        sb.addPermanentWidget(QLabel(f"v{APP_VERSION}"))

    def _sidebar(self):
        f = QFrame()
        f.setObjectName("Sidebar")
        f.setFixedWidth(244)
        l = QVBoxLayout(f)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        brand = QHBoxLayout()
        brand.setContentsMargins(20, 20, 18, 12)
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(30))
        logo.setFixedSize(30, 30)
        name = QLabel(APP_NAME)
        name.setObjectName("Brand")
        brand.addWidget(logo)
        brand.addWidget(name)
        brand.addStretch()
        l.addLayout(brand)
        self.nav = Sidebar()
        self.nav.header("Unduhan")
        first = self.nav.entry("status", "all", "Semua unduhan", "layers")
        self.nav.entry("status", "active", "Sedang berjalan", "download")
        self.nav.entry("status", "queued", "Antrean", "clock")
        self.nav.entry("status", "paused", "Dijeda", "pause")
        self.nav.entry("status", "done", "Selesai", "check")
        self.nav.entry("status", "error", "Gagal", "alert")
        self.nav.header("Kategori")
        for c in CATEGORY_NAMES:
            self.nav.entry("cat", c, c, CAT_ICON[c], CAT_COLOR[c])
        self.nav.changed.connect(lambda k, v: self.proxy.set_filter(k, v))
        l.addWidget(self.nav, 1)
        foot = QFrame()
        foot.setObjectName("Footer")
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(14, 12, 14, 12)
        fl.setSpacing(4)
        cap = QLabel("Kecepatan unduh")
        cap.setObjectName("Muted")
        self.lbl_speed = QLabel("0 B/s")
        self.lbl_speed.setObjectName("Big")
        self.graph = SpeedGraph()
        self.lbl_disk = QLabel()
        self.lbl_disk.setObjectName("Muted")
        for w in (cap, self.lbl_speed, self.graph, self.lbl_disk):
            fl.addWidget(w)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(12, 6, 12, 14)
        wrap.addWidget(foot)
        l.addLayout(wrap)
        self._first_nav = first
        return f

    def _main(self):
        w = QWidget()
        v = self.main_l = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        tb = QFrame()
        tb.setObjectName("Toolbar")
        h = QHBoxLayout(tb)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(2)
        self.add_btn = QPushButton("  Tambah URL")
        self.add_btn.setProperty("variant", "primary")
        self.add_btn.setObjectName("AddBtn")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setMinimumHeight(38)
        self.add_btn.clicked.connect(lambda: self.open_add())
        h.addWidget(self.add_btn)
        h.addSpacing(12)
        self.b_resume = self.tool("Lanjutkan", "play", self.act_resume, "Lanjutkan unduhan terpilih (atau semuanya)")
        self.b_pause = self.tool("Jeda", "pause", self.act_pause, "Jeda unduhan terpilih (atau semuanya)")
        self.b_remove = self.tool("Hapus", "trash", self.act_remove)
        self.b_open = self.tool("Buka", "open", self.act_open, "Buka file")
        self.b_folder = self.tool("Folder", "folder", self.act_folder, "Tampilkan di folder")
        self.b_queue = self.tool("Antrean", "list", None)
        qm = QMenu(self)
        qm.addAction("Mulai semua", self.m.start_all)
        qm.addAction("Jeda semua", self.m.pause_all)
        qm.addSeparator()
        qm.addAction("Bersihkan yang selesai", self.m.clear_finished)
        self.b_queue.setMenu(qm)
        self.b_queue.setPopupMode(QToolButton.InstantPopup)
        for b in (self.b_resume, self.b_pause, self.b_remove, self.b_open, self.b_folder, self.b_queue):
            h.addWidget(b)
        h.addStretch()
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Cari unduhan…")
        self.search.setClearButtonEnabled(True)
        self.search_act = self.search.addAction(icons.icon("search", theme.c("muted")), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(lambda t: self.proxy.set_text(t))
        h.addWidget(self.search)
        h.addSpacing(8)
        self.b_theme = self.tool("Tema", "moon", self.toggle_theme)
        self.b_set = self.tool("Pengaturan", "settings", self.open_settings)
        h.addWidget(self.b_theme)
        h.addWidget(self.b_set)
        v.addWidget(tb)

        self.model = DownloadModel(self.m)
        self.proxy = Proxy()
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context)
        self.table.doubleClicked.connect(self._double)
        hd = self.table.horizontalHeader()
        hd.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, wd in enumerate((90, 200, 100, 80, 120, 150), start=1):
            hd.setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, wd)
        self.table.setItemDelegateForColumn(0, NameDelegate(self.table))
        self.table.setItemDelegateForColumn(2, ProgressDelegate(self.table))
        self.table.setItemDelegateForColumn(5, StatusDelegate(self.table))
        self.table.sortByColumn(6, Qt.DescendingOrder)
        self.table.selectionModel().selectionChanged.connect(lambda *_: self._sel_changed())

        self.stack = QStackedWidget()
        self.stack.addWidget(self._empty())
        self.stack.addWidget(self.table)
        self.stack.setCurrentIndex(0)
        split = QSplitter(Qt.Vertical)
        split.setChildrenCollapsible(False)
        content = QFrame()
        content.setObjectName("Content")
        self.content_l = QVBoxLayout(content)
        self.content_l.addWidget(self.stack)
        split.addWidget(content)
        split.addWidget(self._details())
        split.setStretchFactor(0, 1)
        v.addWidget(split, 1)
        self.nav.setCurrentItem(self._first_nav)
        return w

    def _empty(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setAlignment(Qt.AlignCenter)
        self.empty_icon = QLabel()
        self.empty_icon.setAlignment(Qt.AlignCenter)
        t = QLabel("Belum ada unduhan")
        t.setObjectName("Big")
        t.setAlignment(Qt.AlignCenter)
        s = QLabel("Tempel URL, seret tautan ke jendela ini, salin link (otomatis terdeteksi),\natau gunakan extension browser.")
        s.setObjectName("Muted")
        s.setAlignment(Qt.AlignCenter)
        b = QPushButton("Tambah URL")
        b.setProperty("variant", "primary")
        b.clicked.connect(lambda: self.open_add())
        for x in (self.empty_icon, t, s):
            l.addWidget(x)
        l.addSpacing(10)
        l.addWidget(b, 0, Qt.AlignCenter)
        return w

    def _details(self):
        f = QFrame()
        f.setObjectName("Details")
        l = QVBoxLayout(f)
        l.setContentsMargins(20, 14, 20, 14)
        l.setSpacing(8)
        self.d_title = QLabel()
        self.d_title.setStyleSheet("font-weight:700;font-size:14px")
        l.addWidget(self.d_title)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(6)
        self.d = {}
        for i, (k, label) in enumerate((("url", "URL"), ("dir", "Folder"), ("size", "Ukuran"), ("conn", "Koneksi"),
                                        ("resume", "Resume"), ("err", "Info"))):
            r, c = divmod(i, 2)
            cap = QLabel(label)
            cap.setObjectName("Muted")
            val = ElideLabel()
            self.d[k] = val
            g.addWidget(cap, r, c * 2)
            g.addWidget(val, r, c * 2 + 1)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        l.addLayout(g)
        self.segmap = SegmentMap()
        l.addWidget(self.segmap)
        f.hide()
        self.details = f
        return f

    # --------------------------------------------------------------- tema
    def _apply_mode(self):
        g = theme.glass()
        m = 14 if g else 0
        self.root_l.setContentsMargins(m, m, m, m)
        self.root_l.setSpacing(14 if g else 0)
        self.main_l.setSpacing(12 if g else 0)
        self.content_l.setContentsMargins(*(2, 2, 2, 2) if g else (0, 0, 0, 0))
        self.centralWidget().update()

    def apply_theme(self):
        QApplication.instance().setStyleSheet(theme.stylesheet(data_dir() / "assets"))
        self._apply_mode()
        for b, n in self.icon_buttons:
            b.setIcon(icons.icon(n, theme.c("text"), theme.c("muted"), 22))
        self.add_btn.setIcon(icons.icon("plus", "#ffffff", "#ffffff", 18))
        self.search_act.setIcon(icons.icon("search", theme.c("muted"), theme.c("muted"), 16))
        self.empty_icon.setPixmap(icons.pixmap("download", theme.c("muted"), 56))
        self.nav.refresh_icons()
        self.table.viewport().update()

    def toggle_theme(self):
        keys = [k for k, _ in theme.THEMES]
        self.cfg["theme"] = keys[(keys.index(theme.name) + 1) % len(keys)]
        self.cfg.save()
        theme.set_theme(self.cfg["theme"])
        self.apply_theme()

    def settings_changed(self, old):
        if self.cfg["theme"] != theme.name:
            theme.set_theme(self.cfg["theme"])
            self.apply_theme()
        if self.cfg["native_glass"] != old[3]:
            QMessageBox.information(self, APP_NAME, "Efek kaca native baru aktif setelah SwiftGet dimulai ulang.")
        if (self.cfg["server_enabled"], self.cfg["server_port"]) != old[:2]:
            self.start_server()

    # --------------------------------------------------------------- dialog
    def open_add(self, urls="", payload=None):
        d = AddDialog(self, self.m, self.cfg, urls, payload)       # jendela mandiri: tetap muncul walau aplikasi di tray
        if not self.isActiveWindow():
            d.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.dialogs.append(d)
        d.destroyed.connect(lambda *_: self.dialogs.remove(d) if d in self.dialogs else None)
        bring_to_front(d)

    def open_playlist(self, pid):
        """Buka popup isi playlist (jendela yang sama dipakai ulang)."""
        if pid not in self.m.tasks:
            return
        d = self._pl_dialogs.get(pid)
        if d is not None and isValid(d):
            bring_to_front(d)
            return
        d = PlaylistDialog(self, self.m, pid)
        self._pl_dialogs[pid] = d
        d.destroyed.connect(lambda *_: self._pl_dialogs.pop(pid, None))
        bring_to_front(d)

    def open_settings(self, tab=0):
        SettingsDialog(self, self.cfg, self.m, tab).exec()

    # ------------------------------------------------------------- aksi
    def sel(self):
        out = []
        for ix in self.table.selectionModel().selectedRows():
            t = self.model.task(self.proxy.mapToSource(ix).row())
            if t:
                out.append(t)
        return out

    def act_resume(self):
        s = self.sel()
        for t in s:
            self.m.resume(t.id)
        if not s:
            self.m.start_all()

    def act_pause(self):
        s = self.sel()
        for t in s:
            self.m.pause(t.id)
        if not s:
            self.m.pause_all()

    def act_remove(self):
        s = self.sel()
        if not s:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Hapus unduhan")
        box.setText(f"Hapus {len(s)} unduhan terpilih?")
        box.setInformativeText("Anda bisa menghapus dari daftar saja, atau sekaligus menghapus file hasil unduhan dari disk.")
        b1 = box.addButton("Hapus dari daftar", QMessageBox.AcceptRole)
        b2 = box.addButton("Hapus beserta file", QMessageBox.DestructiveRole)
        box.addButton("Batal", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() in (b1, b2):
            for t in s:
                self.m.remove(t.id, delete_file=box.clickedButton() is b2)

    def act_props(self):
        s = self.sel()
        if s:
            PropertiesDialog(self, self.m, s).exec()

    def act_open(self):
        for t in self.sel():
            if t.status == "completed" and os.path.exists(t.path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(t.path))

    def act_folder(self):
        for t in self.sel()[:1]:
            self.reveal(t.path if os.path.exists(t.path) else t.save_dir)

    def reveal(self, path):
        path = os.path.abspath(path)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path] if os.path.isfile(path) else ["open", path])
            elif sys.platform.startswith("win"):
                subprocess.Popen(["explorer", f"/select,{path}"] if os.path.isfile(path) else ["explorer", path])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(path if os.path.isdir(path) else os.path.dirname(path)))
        except OSError:
            pass

    def _double(self, ix):
        t = self.model.task(self.proxy.mapToSource(ix).row())
        if not t:
            return
        if t.kind == "playlist":
            self.open_playlist(t.id)
        elif t.status == "completed":
            self.act_open()
        elif t.status in ("paused", "error"):
            self.m.resume(t.id)
        elif t.is_active:
            self.m.pause(t.id)

    def _context(self, pos):
        s = self.sel()
        if not s:
            return
        t = s[0]
        menu = QMenu(self)
        if t.kind == "playlist":
            menu.addAction("Lihat isi playlist…", lambda: self.open_playlist(t.id))
            menu.addSeparator()
        elif t.status == "completed":
            menu.addAction("Buka file", self.act_open)
        menu.addAction("Tampilkan di folder", self.act_folder)
        menu.addSeparator()
        if any(x.status in ("paused", "error", "scheduled") for x in s):
            menu.addAction("Lanjutkan / coba lagi", self.act_resume)
        if any(x.is_active or x.status == "queued" for x in s):
            menu.addAction("Jeda", self.act_pause)
        if t.status in ("completed", "error"):
            menu.addAction("Unduh ulang", lambda: [self.m.redownload(x.id) for x in s])
        if t.kind != "playlist":
            if t.status not in ("completed",):
                menu.addAction("Naikkan prioritas", lambda: self.m.move(t.id, -1))
                menu.addAction("Turunkan prioritas", lambda: self.m.move(t.id, 1))
            menu.addAction("Ubah resolusi / format…" if t.kind == "media" else "Properti: koneksi, lokasi, nama…", self.act_props)
            if t.kind == "media":
                menu.addAction("Properti: koneksi, lokasi, nama…", self.act_props)
        menu.addSeparator()
        menu.addAction("Salin tautan", lambda: self._copy("\n".join(x.url for x in s)))
        menu.addSeparator()
        menu.addAction("Hapus…", self.act_remove)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy(self, text):
        self._last_clip = text
        QGuiApplication.clipboard().setText(text)

    # -------------------------------------------------------------- refresh
    def _sel_changed(self):
        s = self.sel()
        has = bool(s)
        for b in (self.b_remove, self.b_open, self.b_folder):
            b.setEnabled(has)
        self.b_open.setEnabled(has and s[0].status == "completed")
        self._details_update()

    def _details_update(self):
        s = self.sel()
        if len(s) != 1:
            self.details.hide()
            return
        t = s[0]
        self.details.show()
        self.d_title.setText(f"{t.name}   ·   {STATUS_LABEL.get(t.status, t.status)}")
        if t.kind == "playlist":
            self.d["url"].set_full(t.url)
            self.d["dir"].set_full(t.save_dir)
            self.d["size"].set_full(f"{t.n_items} video")
            self.d["conn"].set_full(f"{t.connections} koneksi per video")
            self.d["resume"].set_full("Klik dua kali untuk melihat isi playlist")
            self.d["err"].set_full(t.error or t.note or "—")
            self.segmap.set_task(None)
            return
        self.d["url"].set_full(t.url)
        self.d["dir"].set_full(t.path if t.status == "completed" else t.save_dir)
        self.d["size"].set_full(f"{fmt_size(t.downloaded)} / {fmt_size(t.total)}" if t.total else fmt_size(t.downloaded))
        pending = sum(1 for c in t.chunks if c[1] < 0 or c[2] < c[1] - c[0] + 1)
        self.d["conn"].set_full(f"{min(t.connections, pending)} aktif" if t.kind == "file" and t.is_active
                                else (f"{t.connections} koneksi" if t.kind == "file" else "yt-dlp"))
        self.d["resume"].set_full("Didukung" if t.resumable else ("Tidak didukung" if t.kind == "file" and t.total else "—"))
        self.d["err"].set_full(t.error or t.note or (t.resolver if t.resolver not in ("", "direct") else "—"))
        self.segmap.set_task(t)

    def _refresh(self):
        self.model.refresh()
        tasks = list(self.m.tasks.values())
        sig = tuple((t.id, t.status, t.category) for t in tasks)
        if sig != self._sig:
            self._sig = sig
            self.proxy.invalidateFilter()
            self._counts(tasks)
        self.stack.setCurrentIndex(1 if self.proxy.rowCount() else 0)
        sp = self.m.speed
        self.lbl_speed.setText(fmt_speed(sp) if sp > 1 else "0 B/s")
        self.graph.set_values(self.m.speed_hist)
        act = sum(t.is_active and t.kind != "playlist" for t in tasks)
        que = sum(t.status in ("queued", "scheduled") and t.kind != "playlist" for t in tasks)
        lim = int(self.cfg["speed_limit_kbps"])
        self.lbl_counts.setText(f"  {act} aktif  ·  {que} antre  ·  {sum(t.status == 'completed' and not t.parent_id for t in tasks)} selesai"
                                + (f"  ·  batas {fmt_size(lim * 1024)}/s" if lim else ""))
        self.setWindowTitle(f"{APP_NAME}  —  ↓ {fmt_speed(sp)}" if sp > 1 else APP_NAME)
        self._tick += 1
        if self._tick % 20 == 1:
            try:
                base = self.cfg["download_dir"]
                while base and not os.path.exists(base):
                    base = os.path.dirname(base)
                self._disk = f"Disk kosong: {fmt_size(shutil.disk_usage(base or os.path.expanduser('~')).free)}"
            except OSError:
                self._disk = ""
        self.lbl_disk.setText(self._disk)
        self.tray.setToolTip(f"{APP_NAME} — {act} aktif, ↓ {fmt_speed(sp)}")
        if self.table.selectionModel().hasSelection():
            self._details_update()
        else:
            self.b_open.setEnabled(False)
            self.b_remove.setEnabled(False)
            self.b_folder.setEnabled(False)

    def _counts(self, tasks):
        tasks = [t for t in tasks if not t.parent_id]          # isi playlist tidak dihitung terpisah
        c = {("status", "all"): len(tasks)}
        for key, grp in (("active", ("preparing", "downloading", "processing", "verifying")), ("queued", ("queued", "scheduled")),
                         ("paused", ("paused",)), ("done", ("completed",)), ("error", ("error",))):
            c[("status", key)] = sum(t.status in grp for t in tasks)
        for cat in CATEGORY_NAMES:
            c[("cat", cat)] = sum(t.category == cat for t in tasks)
        self.nav.set_counts(c)

    # ------------------------------------------------------- tray & event
    def _make_tray(self):
        self.tray = QSystemTrayIcon(icons.app_icon(), self)
        m = QMenu()
        m.addAction("Tampilkan SwiftGet", self.show_normal)
        m.addAction("Tambah URL…", lambda: (self.show_normal(), self.open_add()))
        m.addSeparator()
        m.addAction("Mulai semua", self.m.start_all)
        m.addAction("Jeda semua", self.m.pause_all)
        m.addSeparator()
        m.addAction("Keluar", self.quit_app)
        self._tray_menu = m
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) and self.show_normal())
        self.tray.messageClicked.connect(self._msg_clicked)
        self.tray.show()

    def show_normal(self):
        self.showNormal()
        bring_to_front(self)

    def notify(self, title, msg):
        if self.tray.isVisible() and self.cfg["notify"]:
            self.tray.showMessage(title, msg, QSystemTrayIcon.Information, 5000)

    def _msg_clicked(self):
        if self._pending_url:
            u, self._pending_url = self._pending_url, ""
            self.show_normal()
            self.open_add(u)

    def _on_event(self, kind, tid):
        t = self.m.tasks.get(tid)
        if kind == "completed" and t:
            self.notify("Unduhan selesai", t.name)
        elif kind == "error" and t:
            self.notify("Unduhan gagal", f"{t.name}\n{t.error[:120]}")
        elif kind == "queue_done":
            self._after_queue()

    def _after_queue(self):
        a = self.cfg["after_queue"]
        if a == "nothing":
            return
        label = {"quit": "SwiftGet akan ditutup", "sleep": "Komputer akan tidur", "shutdown": "Komputer akan dimatikan"}[a]
        if CountdownDialog(self, label).exec() != QDialog.Accepted:
            return
        if a == "quit":
            return self.quit_app()
        cmds = {"darwin": {"sleep": ["osascript", "-e", 'tell application "System Events" to sleep'],
                           "shutdown": ["osascript", "-e", 'tell application "System Events" to shut down']},
                "win": {"sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "shutdown": ["shutdown", "/s", "/t", "5"]},
                "linux": {"sleep": ["systemctl", "suspend"], "shutdown": ["systemctl", "poweroff"]}}
        key = "darwin" if sys.platform == "darwin" else "win" if sys.platform.startswith("win") else "linux"
        try:
            subprocess.Popen(cmds[key][a])
        except OSError:
            pass

    def _clip(self):
        if not self.cfg["clipboard_monitor"]:
            return
        txt = QGuiApplication.clipboard().text().strip()
        if txt == self._last_clip or len(txt) > 2000 or not re.fullmatch(r"https?://\S+", txt):
            return
        self._last_clip = txt
        ext = os.path.splitext(urlparse(txt).path)[1].lstrip(".").lower()
        if ext in ALL_EXTS or resolvers.match(txt) or MEDIA_HOSTS.search(txt):
            self._pending_url = txt
            self.notify("URL terdeteksi", "Klik untuk menambahkan ke SwiftGet\n" + txt[:90])

    # ------------------------------------------------------ extension server
    def start_server(self):
        self.stop_server()
        if not self.cfg["server_enabled"]:
            self.lbl_srv.setText("Extension: nonaktif   ")
            return
        s = LocalServer(self.cfg, lambda route, data: self.sig_ext.emit(route, data), self._pair_request)
        try:
            s.start()
            self.server = s
            self.lbl_srv.setText(f"Extension: port {self.cfg['server_port']}   ")
        except OSError:
            self.lbl_srv.setText(f"Extension: port {self.cfg['server_port']} dipakai aplikasi lain   ")

    # --- pairing otomatis: extension meminta terhubung, pengguna cukup menekan "Izinkan"
    def _pair_request(self, origin):          # dipanggil dari thread server
        if origin in self.cfg["paired_origins"]:
            return self.cfg["token"]
        if self._pairing:
            return None
        self._pairing = True
        box = {"ev": threading.Event(), "ok": False}
        self.sig_pair.emit(origin, box)
        box["ev"].wait(90)
        self._pairing = False
        return self.cfg["token"] if box["ok"] else None

    def _on_pair(self, origin, box):
        kind = "Firefox" if origin.startswith("moz-extension") else "Chrome / Edge / Brave"
        box_ui = QMessageBox(QMessageBox.Question, "Hubungkan extension browser",
                             f"Extension SwiftGet di browser ({kind}) ingin terhubung untuk mengambil alih unduhan.\n\n"
                             f"Izinkan?\n\nID: {origin}", QMessageBox.Yes | QMessageBox.No)
        box_ui.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        bring_to_front(box_ui)
        if box_ui.exec() == QMessageBox.Yes:
            self.cfg["paired_origins"] = list(self.cfg["paired_origins"]) + [origin]
            self.cfg.save()
            box["ok"] = True
            self.notify("Extension terhubung", "Unduhan dari browser kini otomatis dikirim ke SwiftGet.")
        box["ev"].set()

    def install_extension(self, key):
        """Siapkan folder extension lalu buka halaman extensions browser (atau halaman toko bila sudah dipublikasikan)."""
        if EXT_STORE.get(key):
            QDesktopServices.openUrl(QUrl(EXT_STORE[key]))
            return
        path = str(export_extension())
        self._copy(path)
        app, win_exe, linux_exe, url = {
            "chrome": ("Google Chrome", "chrome", "google-chrome", "chrome://extensions"),
            "edge": ("Microsoft Edge", "msedge", "microsoft-edge", "edge://extensions"),
            "brave": ("Brave Browser", "brave", "brave-browser", "brave://extensions"),
            "firefox": ("Firefox", "firefox", "firefox", "about:debugging#/runtime/this-firefox")}[key]
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app, url])
            elif sys.platform.startswith("win"):
                subprocess.Popen(["cmd", "/c", "start", "", win_exe, url])
            else:
                subprocess.Popen([linux_exe, url])
        except OSError:
            pass
        steps = ("Klik \"Load Temporary Add-on…\" lalu pilih file manifest.json di folder tersebut."
                 if key == "firefox" else
                 "Aktifkan \"Developer mode\", klik \"Load unpacked\", lalu pilih folder tersebut.")
        QMessageBox.information(self, "Pasang extension",
                                f"Folder extension sudah disiapkan (path-nya juga disalin ke clipboard):\n\n{path}\n\n{steps}\n\n"
                                "Setelah terpasang, SwiftGet akan meminta izin sekali. Klik \"Ya\" dan selesai.")

    def stop_server(self):
        if self.server:
            self.server.stop()
            self.server = None

    def _on_ext(self, route, data):
        url = (data.get("url") or "").strip()
        if data.get("urls"):
            url = "\n".join(data["urls"])
        if not url:
            return
        if route == "add" and not self.cfg["extension_ask"] and "\n" not in url:
            t = self.m.add(url, filename=data.get("filename", ""), referer=data.get("referer", ""),
                           cookies=data.get("cookies", ""), user_agent=data.get("userAgent", ""))
            self.notify("Ditambahkan ke SwiftGet", t.name)
            return
        self.open_add(url, data)

    # ---------------------------------------------------------- drag & close
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        urls = [u.toString() for u in md.urls() if u.scheme() in ("http", "https")]
        if not urls and md.hasText():
            urls = re.findall(r"https?://\S+", md.text())
        if urls:
            self.open_add("\n".join(urls))

    def showEvent(self, e):
        super().showEvent(e)
        if self._native_pending:
            self._native_pending = False
            QTimer.singleShot(80, self._go_native)

    def _onboard(self):
        dlg = WelcomeDialog(self)
        accepted = dlg.exec() == QDialog.Accepted
        self.cfg["onboarded"] = True
        if accepted and dlg.k_auto.isVisible() and dlg.k_auto.isChecked():
            self.cfg["autostart"] = bool(autostart.enable(True))
        self.cfg.save()
        if accepted and dlg.k_ext.isChecked():
            self.open_settings(3)

    def _go_native(self):
        if not mac_glass.apply(self):
            theme.native = False
            self.apply_theme()

    def closeEvent(self, e):
        if e.spontaneous() and not self._quitting and self.cfg["minimize_to_tray"] and self.tray.isVisible():
            e.ignore()
            self.hide()
            if not self._hint_shown:
                self._hint_shown = True
                self.notify("SwiftGet masih berjalan", "Unduhan berlanjut di latar belakang. Klik ikon tray untuk membuka.")
            return
        self._quitting = True
        e.accept()
        QApplication.quit()

    def quit_app(self):
        self._quitting = True
        QApplication.quit()

    def _cleanup(self):
        if self._cleaned:
            return
        self._cleaned = True
        self.timer.stop()
        self.stop_server()
        self.m.shutdown()
        self.tray.hide()
