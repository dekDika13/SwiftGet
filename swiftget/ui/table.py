"""Model tabel, filter, dan delegate kustom untuk daftar unduhan."""
import time
from datetime import datetime

from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QRect, QRectF, QSize, QSortFilterProxyModel, Qt)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from ..models import ACTIVE
from ..util import fmt_eta, fmt_size, fmt_speed
from . import icons, theme

ROLE_TASK = Qt.UserRole + 1
ROLE_SORT = Qt.UserRole + 2
COLS = ["Nama", "Ukuran", "Progres", "Kecepatan", "Sisa", "Status", "Ditambahkan"]

STATUS_LABEL = {"queued": "Mengantre", "scheduled": "Terjadwal", "preparing": "Menyiapkan", "downloading": "Mengunduh",
                "processing": "Memproses", "verifying": "Memeriksa", "paused": "Dijeda", "completed": "Selesai", "error": "Gagal"}
STATUS_COLOR = {"downloading": "accent", "preparing": "accent", "processing": "accent", "verifying": "accent",
                "completed": "green", "paused": "amber", "error": "red", "queued": "muted", "scheduled": "muted"}
CAT_COLOR = {"Video": "#8B9DFF", "Musik": "#2DD4BF", "Dokumen": "#38BDF8", "Arsip": "#FBBF24",
             "Program": "#34D399", "Gambar": "#FB923C", "Lainnya": "#94A3B8"}
CAT_ICON = {"Video": "film", "Musik": "music", "Dokumen": "file", "Arsip": "archive",
            "Program": "box", "Gambar": "image", "Lainnya": "file"}
GROUPS = {"all": None, "active": ACTIVE, "queued": ("queued", "scheduled"), "paused": ("paused",),
          "done": ("completed",), "error": ("error",)}


class DownloadModel(QAbstractTableModel):
    def __init__(self, manager):
        super().__init__()
        self.m = manager
        self.ids = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.ids)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLS)

    def headerData(self, s, o, role=Qt.DisplayRole):
        if o == Qt.Horizontal and role == Qt.DisplayRole:
            return COLS[s]

    def task(self, row):
        return self.m.tasks.get(self.ids[row]) if 0 <= row < len(self.ids) else None

    def data(self, idx, role=Qt.DisplayRole):
        t = self.task(idx.row())
        if not t:
            return None
        c = idx.column()
        if role == ROLE_TASK:
            return t
        if role == ROLE_SORT:
            return [t.name.lower(), t.n_items if t.kind == "playlist" else t.total, t.progress(), t.speed, t.eta if t.eta >= 0 else 1e12,
                    STATUS_LABEL.get(t.status, t.status), t.added][c]
        if role == Qt.DisplayRole:
            p = t.progress()
            size = f"{t.n_items} video" if t.kind == "playlist" else (fmt_size(t.total) if t.total > 0 else "—")
            return [t.name, size, f"{p * 100:.0f}%" if p >= 0 else "…",
                    fmt_speed(t.speed) if t.is_active else "—", fmt_eta(t.eta) if t.is_active else "—",
                    STATUS_LABEL.get(t.status, t.status), datetime.fromtimestamp(t.added).strftime("%d %b %Y, %H:%M")][c]
        if role == Qt.TextAlignmentRole and c in (1, 3, 4):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role == Qt.ForegroundRole and c in (1, 3, 4, 6):
            return QColor(theme.c("muted"))

    def refresh(self):
        ids = sorted(list(self.m.tasks.keys()))
        if ids != self.ids:
            self.beginResetModel()
            self.ids = ids
            self.endResetModel()
        elif ids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(ids) - 1, len(COLS) - 1))


class Proxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.group, self.cat, self.text = "all", None, ""
        self.parent_id = 0          # 0 = daftar utama (isi playlist disembunyikan); >0 = hanya isi playlist itu
        self.setSortRole(ROLE_SORT)
        self.setDynamicSortFilter(True)

    def set_filter(self, kind, key):
        self.group, self.cat = ("all", None)
        if kind == "status":
            self.group = key
        else:
            self.cat = key
        self.invalidateFilter()

    def set_text(self, text):
        self.text = text.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        t = self.sourceModel().task(row)
        if not t:
            return False
        if t.parent_id != self.parent_id:
            return False
        g = GROUPS.get(self.group)
        if g and t.status not in g:
            return False
        if self.cat and t.category != self.cat:
            return False
        return not self.text or self.text in t.name.lower() or self.text in t.url.lower()


def _base(delegate, p, opt, idx):
    o = QStyleOptionViewItem(opt)
    delegate.initStyleOption(o, idx)
    o.text, o.icon = "", QIcon()
    o.state &= ~QStyle.State_HasFocus
    (opt.widget.style() if opt.widget else QApplication.style()).drawControl(QStyle.CE_ItemViewItem, o, p, opt.widget)


class NameDelegate(QStyledItemDelegate):
    def sizeHint(self, opt, idx):
        return QSize(280, 54)

    def paint(self, p, opt, idx):
        t = idx.data(ROLE_TASK)
        if not t:
            return
        _base(self, p, opt, idx)
        r = opt.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(CAT_COLOR.get(t.category, "#94A3B8"))
        tile = QRectF(r.left() + 12, r.center().y() - 17, 34, 34)
        bg = QColor(col)
        bg.setAlpha(38)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(tile, 9, 9)
        p.drawPixmap(int(tile.center().x() - 9), int(tile.center().y() - 9),
                     icons.pixmap("list" if t.kind == "playlist" else CAT_ICON.get(t.category, "file"), col.name(), 18))
        x = int(tile.right()) + 12
        w = r.right() - x - 10
        f = QFont(opt.font)
        f.setPixelSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(theme.c("text")))
        p.drawText(QRect(x, r.top() + 9, w, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f).elidedText(t.name, Qt.ElideMiddle, w))
        f.setPixelSize(11)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        if t.kind == "playlist":
            sub, colr = f"Playlist  ·  {t.note}", theme.c("red") if t.status == "error" else theme.c("muted")
        elif t.status == "error" and t.error:
            sub, colr = t.error, theme.c("red")
        elif t.note and t.is_active:
            sub, colr = t.note, theme.c("muted")
        else:
            sub, colr = f"{t.category}  ·  {t.resolver if t.resolver and t.resolver != 'direct' else (t.host or 'media')}", theme.c("muted")
        p.setPen(QColor(colr))
        p.drawText(QRect(x, r.top() + 28, w, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f).elidedText(sub, Qt.ElideRight, w))
        p.restore()


class ProgressDelegate(QStyledItemDelegate):
    def paint(self, p, opt, idx):
        t = idx.data(ROLE_TASK)
        if not t:
            return
        _base(self, p, opt, idx)
        r = opt.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        bar = QRectF(r.left() + 10, r.center().y() - 3, max(20, r.width() - 72), 6)
        p.setPen(Qt.NoPen)
        p.setBrush(theme.qc("border"))
        p.drawRoundedRect(bar, 3, 3)
        color = QColor(theme.c(STATUS_COLOR.get(t.status, "muted")))
        pr = t.progress()
        p.setBrush(color)
        if pr >= 0:
            if pr > 0:
                p.drawRoundedRect(QRectF(bar.left(), bar.top(), max(6.0, bar.width() * pr), 6), 3, 3)
        elif t.is_active:
            seg = bar.width() * 0.3
            off = (time.time() * 0.9 % 1.0) * (bar.width() - seg)
            p.drawRoundedRect(QRectF(bar.left() + off, bar.top(), seg, 6), 3, 3)
        f = QFont(opt.font)
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(theme.c("text")))
        p.drawText(QRect(int(bar.right()) + 8, r.top(), 52, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   idx.data(Qt.DisplayRole))
        p.restore()


class StatusDelegate(QStyledItemDelegate):
    def paint(self, p, opt, idx):
        t = idx.data(ROLE_TASK)
        if not t:
            return
        _base(self, p, opt, idx)
        r = opt.rect
        col = QColor(theme.c(STATUS_COLOR.get(t.status, "muted")))
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QRectF(r.left() + 12, r.center().y() - 3.5, 7, 7))
        p.setPen(col if t.status in ("error", "completed") else QColor(theme.c("text")))
        f = QFont(opt.font)
        f.setPixelSize(12)
        f.setWeight(QFont.Medium)
        p.setFont(f)
        p.drawText(QRect(r.left() + 26, r.top(), r.width() - 30, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   STATUS_LABEL.get(t.status, t.status))
        p.restore()
