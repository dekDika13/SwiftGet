"""Widget kustom: sidebar, grafik kecepatan, peta segmen."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QWidget

from . import icons, theme


class NavRow(QWidget):
    def __init__(self, label, icon_name, color=None):
        super().__init__()
        self.setObjectName("NavRow")
        self.icon_name, self.color = icon_name, color
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)
        self.ic = QLabel()
        self.ic.setFixedSize(18, 18)
        self.name = QLabel(label)
        self.count = QLabel("0")
        self.count.setObjectName("NavCount")
        lay.addWidget(self.ic)
        lay.addWidget(self.name, 1)
        lay.addWidget(self.count)
        self.refresh_icon()

    def refresh_icon(self):
        self.ic.setPixmap(icons.pixmap(self.icon_name, self.color or theme.c("muted"), 18))

    def set_count(self, n):
        self.count.setText(str(n) if n else "")


class Sidebar(QListWidget):
    changed = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Nav")
        self.setFrameShape(QListWidget.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSpacing(1)
        self.rows = {}
        self.currentItemChanged.connect(self._chg)

    def _chg(self, cur, _prev):
        d = cur.data(Qt.UserRole) if cur else None
        if d:
            self.changed.emit(*d)

    def header(self, text):
        it = QListWidgetItem()
        it.setFlags(Qt.NoItemFlags)
        it.setSizeHint(QSize(0, 34))
        self.addItem(it)
        lab = QLabel(text.upper())
        lab.setObjectName("NavHeader")
        self.setItemWidget(it, lab)

    def entry(self, kind, key, label, icon_name, color=None):
        it = QListWidgetItem()
        it.setData(Qt.UserRole, (kind, key))
        it.setSizeHint(QSize(0, 36))
        self.addItem(it)
        row = NavRow(label, icon_name, color)
        self.setItemWidget(it, row)
        self.rows[(kind, key)] = row
        return it

    def set_counts(self, d):
        for k, v in d.items():
            if k in self.rows:
                self.rows[k].set_count(v)

    def refresh_icons(self):
        for r in self.rows.values():
            r.refresh_icon()


class SpeedGraph(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(44)
        self.values = []

    def set_values(self, v):
        self.values = list(v)
        self.update()

    def paintEvent(self, e):
        v = self.values
        if len(v) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - 4
        mx = max(max(v), 1.0)
        pts = [QPointF(i * w / (len(v) - 1), 2 + h - (x / mx) * h) for i, x in enumerate(v)]
        path = QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        fill = QPainterPath(path)
        fill.lineTo(w, h + 2)
        fill.lineTo(0, h + 2)
        g = QLinearGradient(0, 0, 0, h)
        top = QColor(theme.c("accent"))
        top.setAlpha(110)
        bot = QColor(theme.c("accent"))
        bot.setAlpha(0)
        g.setColorAt(0, top)
        g.setColorAt(1, bot)
        p.fillPath(fill, g)
        p.setPen(QPen(QColor(theme.c("accent")), 1.6))
        p.drawPath(path)


class SegmentMap(QWidget):
    """Visualisasi chunk yang sedang/sudah diunduh (seperti IDM)."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(16)
        self.task = None

    def set_task(self, t):
        self.task = t
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        track = QRectF(0, 3, w, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(theme.qc("border"))
        p.drawRoundedRect(track, 4, 4)
        t = self.task
        if not t:
            return
        p.setClipPath(self._clip(track))
        if t.status == "completed":
            p.setBrush(QColor(theme.c("green")))
            p.drawRect(track)
            return
        if t.total <= 0 or not t.chunks:
            return
        p.setBrush(QColor(theme.c("accent")))
        for s, en, d in list(t.chunks):
            if en < s or d <= 0:
                continue
            x = s / t.total * w
            p.drawRect(QRectF(x, 3, (d / t.total) * w, 10))
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        for s, en, d in list(t.chunks)[1:]:
            x = s / t.total * w
            p.drawLine(QPointF(x, 3), QPointF(x, 13))

    @staticmethod
    def _clip(r):
        path = QPainterPath()
        path.addRoundedRect(r, 4, 4)
        return path


class Backdrop(QWidget):
    """Latar jendela utama: aurora lembut di tema Glass (ditembus panel kaca), warna polos di tema lain."""

    def paintEvent(self, e):
        p = QPainter(self)
        r = self.rect()
        if not theme.glass():
            p.fillRect(r, theme.qc("bg"))
            return
        spec = theme.BACKDROP[theme.name]
        base = QColor(spec["base"])
        if theme.native:
            base.setAlpha(110)
        p.fillRect(r, base)
        for fx, fy, fr, col in spec["blobs"]:
            c1, c2 = QColor(col), QColor(col)
            c1.setAlpha(spec["alpha"] // (2 if theme.native else 1))
            c2.setAlpha(0)
            g = QRadialGradient(r.width() * fx, r.height() * fy, max(r.width(), r.height()) * fr)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.fillRect(r, QBrush(g))
