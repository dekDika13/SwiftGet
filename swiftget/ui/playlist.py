"""Popup isi playlist: lihat progres tiap video, jeda / lanjutkan / hapus dari daftar."""
import os

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QMenu, QMessageBox,
                               QTableView, QVBoxLayout)

from ..util import fmt_speed
from .dialogs import PropertiesDialog, button, muted
from .table import DownloadModel, NameDelegate, ProgressDelegate, Proxy, StatusDelegate


class PlaylistDialog(QDialog):
    def __init__(self, win, manager, pid):
        super().__init__(None)                       # jendela mandiri; tidak ikut tersembunyi bersama jendela utama
        self.win, self.m, self.pid, self._sig = win, manager, pid, None
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Isi playlist")
        self.setMinimumSize(820, 460)
        self.resize(1000, 620)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(10)
        self.title = QLabel()
        self.title.setObjectName("DlgTitle")
        self.summary = muted(wrap=False)
        root.addWidget(self.title)
        root.addWidget(self.summary)

        self.model = DownloadModel(manager)
        self.proxy = Proxy()
        self.proxy.parent_id = pid                   # hanya video milik playlist ini
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context)
        self.table.doubleClicked.connect(self._double)
        hd = self.table.horizontalHeader()
        hd.setSectionResizeMode(0, QHeaderView.Stretch)
        for i, wd in enumerate((90, 190, 100, 80, 120), start=1):
            hd.setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, wd)
        self.table.setColumnHidden(6, True)
        self.table.setItemDelegateForColumn(0, NameDelegate(self.table))
        self.table.setItemDelegateForColumn(2, ProgressDelegate(self.table))
        self.table.setItemDelegateForColumn(5, StatusDelegate(self.table))
        root.addWidget(self.table, 1)

        bar = QHBoxLayout()
        for text, icon, slot, variant in (("Lanjutkan", "play", self.act_resume, None), ("Jeda", "pause", self.act_pause, None),
                                          ("Ubah resolusi / format", "settings", self.act_props, None),
                                          ("Hapus dari daftar", "trash", self.act_remove, "danger"),
                                          ("Buka folder", "folder", self.act_folder, None)):
            b = button(text, variant, icon)
            b.clicked.connect(lambda _=False, f=slot: f())
            bar.addWidget(b)
        bar.addStretch()
        c = button("Tutup", "ghost")
        c.clicked.connect(self.close)
        bar.addWidget(c)
        root.addLayout(bar)
        root.addWidget(muted("Tanpa pilihan baris, tombol Lanjutkan/Jeda berlaku untuk seluruh playlist. "
                             "Pilih beberapa baris (Ctrl/Shift) untuk memproses sebagian saja."))
        self.timer = QTimer(self, interval=500)
        self.timer.timeout.connect(self._refresh)
        self.timer.start()
        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self):
        p = self.m.tasks.get(self.pid)
        if not p:
            self.close()
            return
        self.model.refresh()
        sig = tuple((t.id, t.status) for t in self.m.children(self.pid))
        if sig != self._sig:
            self._sig = sig
            self.proxy.invalidateFilter()
        self.title.setText(p.name)
        self.summary.setText(f"{p.note}   ·   {fmt_speed(p.speed) if p.speed > 1 else 'tidak sedang mengunduh'}   ·   {p.save_dir}")

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
            self.m.resume(self.pid)

    def act_pause(self):
        s = self.sel()
        for t in s:
            self.m.pause(t.id)
        if not s:
            self.m.pause(self.pid)

    def act_props(self):
        s = self.sel()
        if s:
            PropertiesDialog(self.win, self.m, s).exec()
        else:
            QMessageBox.information(self, "Pilih video", "Pilih satu atau beberapa video di daftar dulu.")

    def act_remove(self):
        s = self.sel()
        if not s:
            QMessageBox.information(self, "Pilih video", "Pilih satu atau beberapa video yang ingin dihapus dari daftar.")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Hapus dari playlist")
        box.setText(f"Hapus {len(s)} video terpilih dari playlist ini?")
        box.setInformativeText("Video yang dihapus tidak akan diunduh. Pilih juga apakah file hasil unduhannya ikut dihapus dari disk.")
        b1 = box.addButton("Hapus dari daftar", QMessageBox.AcceptRole)
        b2 = box.addButton("Hapus beserta file", QMessageBox.DestructiveRole)
        box.addButton("Batal", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() in (b1, b2):
            for t in s:
                self.m.remove(t.id, delete_file=box.clickedButton() is b2)

    def act_folder(self):
        p = self.m.tasks.get(self.pid)
        if p and self.win:
            self.win.reveal(p.save_dir)

    def _double(self, ix):
        t = self.model.task(self.proxy.mapToSource(ix).row())
        if not t:
            return
        if t.status == "completed" and os.path.exists(t.path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(t.path))
        elif t.status in ("paused", "error"):
            self.m.resume(t.id)
        elif t.is_active or t.status == "queued":
            self.m.pause(t.id)

    def _context(self, pos):
        s = self.sel()
        if not s:
            return
        menu = QMenu(self)
        if s[0].status == "completed" and os.path.exists(s[0].path):
            menu.addAction("Buka file", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(s[0].path)))
            menu.addSeparator()
        menu.addAction("Lanjutkan / coba lagi", self.act_resume)
        menu.addAction("Jeda", self.act_pause)
        menu.addAction("Ubah resolusi / format…", self.act_props)
        menu.addSeparator()
        menu.addAction("Salin tautan", lambda: QGuiApplication.clipboard().setText("\n".join(t.url for t in s)))
        menu.addAction("Hapus dari daftar…", self.act_remove)
        menu.exec(self.table.viewport().mapToGlobal(pos))
