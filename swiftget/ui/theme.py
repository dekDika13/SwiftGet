"""Tema: Glass (gelap/terang, gaya Liquid Glass Tahoe) dan Gelap/Terang klasik."""
import re
from pathlib import Path

from PySide6.QtGui import QColor

_BASE = dict(accent="#3B82F6", accent_h="#2F6FDB")


def _flat(**c):
    b = c["border"]
    c = {**_BASE, **c}
    c.update(glass=False, win=c["bg"], dlg=c["bg"], menu=c["surface"],
             sidebar_css=f"border-right:1px solid {b};", toolbar_css=f"border-bottom:1px solid {b};",
             details_css=f"border-top:1px solid {b};", content_css="border:none;", content_bg="transparent",
             r_btn="8px", r_in="8px", r_card="12px", r_cap="8px", r_search="16px", r_nav="8px",
             split_h="1px", split_bg=b)
    return c


def _glass(**c):
    b = c["border"]
    c = {**_BASE, **c}
    frame = f"border:1px solid {b}; border-radius:24px;"
    c.update(glass=True, sidebar_css=frame, toolbar_css="border:1px solid %s; border-radius:22px;" % b,
             details_css=frame, content_css=frame, content_bg=c["panel"],
             r_btn="13px", r_in="12px", r_card="18px", r_cap="20px", r_search="18px", r_nav="13px",
             split_h="12px", split_bg="transparent")
    return c


PALETTES = {
    "glass": _glass(bg="#0B1020", win="#0A0F1E", dlg="#151B33", menu="#1B2242", panel="rgba(255,255,255,0.075)",
                    surface="rgba(255,255,255,0.10)", input="rgba(0,0,0,0.30)", border="rgba(255,255,255,0.17)",
                    text="#F2F5FF", muted="#A9B1CA", hover="rgba(255,255,255,0.13)", sel="rgba(110,160,255,0.30)",
                    accent="#4C8DFF", accent_h="#3F7BEA", green="#34D399", amber="#FBBF24", red="#F87171"),
    "glass_light": _glass(bg="#E7EDFA", win="#E3EAF8", dlg="#EEF2FB", menu="#F8FAFF", panel="rgba(255,255,255,0.58)",
                          surface="rgba(255,255,255,0.78)", input="rgba(255,255,255,0.85)", border="rgba(110,125,165,0.28)",
                          text="#182033", muted="#5B6783", hover="rgba(60,90,170,0.10)", sel="rgba(59,130,246,0.20)",
                          green="#16A34A", amber="#D97706", red="#DC2626"),
    "dark": _flat(bg="#101217", panel="#171A21", surface="#1E222B", input="#13161C", border="#2A2F3B", text="#E7EAF0",
                  muted="#8B94A7", hover="#252A35", sel="rgba(59,130,246,0.20)", green="#22C55E", amber="#F59E0B",
                  red="#EF4444"),
    "light": _flat(bg="#F2F4F8", panel="#FFFFFF", surface="#FFFFFF", input="#FFFFFF", border="#E1E5EC", text="#1A1D24",
                   muted="#6B7385", hover="#EDF0F5", sel="rgba(59,130,246,0.13)", green="#16A34A", amber="#D97706",
                   red="#DC2626"),
}
THEMES = [("glass", "Glass (gelap)"), ("glass_light", "Glass (terang)"), ("dark", "Gelap"), ("light", "Terang")]

# Latar "aurora" yang ditembus panel kaca: (x, y, radius, warna) dalam fraksi ukuran jendela
BACKDROP = {
    "glass": dict(base="#0B1220", alpha=135, blobs=[(0.10, 0.08, 0.65, "#2F6FDB"), (0.92, 0.90, 0.70, "#1E4F8F"),
                                                    (0.88, 0.10, 0.45, "#0E7C86"), (0.18, 0.95, 0.45, "#27407A")]),
    "glass_light": dict(base="#E4EAF3", alpha=185, blobs=[(0.10, 0.08, 0.60, "#9CC2F2"), (0.92, 0.90, 0.70, "#9FB4D6"),
                                                          (0.88, 0.10, 0.45, "#A5D3D8"), (0.15, 0.95, 0.45, "#BCCBE3")]),
}

current = dict(PALETTES["glass"])
name = "glass"
native = False   # True saat efek kaca native macOS aktif (jendela transparan)


def set_theme(n):
    global name
    name = n if n in PALETTES else "glass"
    current.clear()
    current.update(PALETTES[name])


def glass() -> bool:
    return bool(current["glass"])


def c(key):
    return current[key]


def qc(key) -> QColor:
    """QColor dari warna palet; mendukung nilai rgba(r,g,b,a)."""
    v = current[key]
    if v.startswith("rgba("):
        r, g, b, a = [x.strip() for x in v[5:-1].split(",")]
        return QColor(int(r), int(g), int(b), int(float(a) * 255))
    return QColor(v)


def write_assets(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    out = {}
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="{w}" '
           'stroke-linecap="round" stroke-linejoin="round"><polyline points="{pts}"/></svg>')
    for key, fname, c, w, pts in (("check", "check", "white", 3.5, "20 6 9 17 4 12"),
                                  ("arrow_up", f"arrow_up_{name}", current["text"], 3, "6 15 12 9 18 15"),
                                  ("arrow_down", f"arrow_down_{name}", current["text"], 3, "6 9 12 15 18 9")):
        p = directory / f"{fname}.svg"
        p.write_text(svg.format(c=c, w=w, pts=pts))
        out[key] = p.as_posix()
    return out


QSS = """
QWidget { color:@text; font-size:13px; }
QMainWindow { background:@win; }
QDialog { background:@dlg; }
QToolTip { background:@menu; color:@text; border:1px solid @border; padding:5px 8px; }
QFrame#Sidebar { background:@panel; @sidebar_css }
QFrame#Toolbar { background:@panel; @toolbar_css }
QFrame#Details { background:@panel; @details_css }
QFrame#Content { background:@content_bg; @content_css }
QFrame#Card { background:@surface; border:1px solid @border; border-radius:@r_card; }
QFrame#Footer { background:@surface; border:1px solid @border; border-radius:@r_card; }
QLabel { background:transparent; }
QLabel#Brand { font-size:17px; font-weight:700; }
QLabel#NavHeader { color:@muted; font-size:10px; font-weight:700; padding-left:14px; }
QLabel#Muted, QLabel#NavCount { color:@muted; }
QLabel#Big { font-size:20px; font-weight:700; }
QLabel#DlgTitle { font-size:19px; font-weight:700; }
QLabel#Thumb { background:@input; border-radius:10px; }
QLabel#Warn { color:@amber; }
QWidget#NavRow { background:transparent; }
QListWidget#Nav { background:transparent; border:none; outline:0; padding:2px 10px; }
QListWidget#Nav::item { border-radius:@r_nav; }
QListWidget#Nav::item:hover { background:@hover; }
QListWidget#Nav::item:selected { background:@sel; }
QListWidget#Links { background:@input; border:1px solid @border; border-radius:@r_in; outline:0; }
QListWidget#Links::item { padding:5px 6px; }
QPushButton { background:@surface; border:1px solid @border; border-radius:@r_btn; padding:7px 16px; font-weight:600; }
QPushButton:hover { background:@hover; }
QPushButton:disabled { color:@muted; }
QPushButton[variant="primary"] { background:@accent; border:1px solid @accent; color:white; }
QPushButton[variant="primary"]:hover { background:@accent_h; }
QPushButton[variant="primary"]:disabled { background:@border; border-color:@border; color:@muted; }
QPushButton[variant="ghost"] { background:transparent; border:1px solid transparent; color:@muted; }
QPushButton[variant="ghost"]:hover { background:@hover; color:@text; }
QPushButton[variant="danger"] { color:@red; }
QPushButton#AddBtn { border-radius:@r_cap; padding:0 22px; }
QPushButton#Seg { padding:6px 18px; }
QPushButton#Seg:checked { background:@accent; border-color:@accent; color:white; }
QToolButton#ToolBtn { background:transparent; border:none; border-radius:@r_btn; padding:6px 10px; font-size:11px; }
QToolButton#ToolBtn:hover { background:@hover; }
QToolButton#ToolBtn:pressed { background:@sel; }
QToolButton#ToolBtn:disabled { color:@muted; }
QToolButton::menu-indicator { image:none; }
QLineEdit, QPlainTextEdit, QSpinBox, QDateTimeEdit, QComboBox { background:@input; border:1px solid @border;
    border-radius:@r_in; padding:6px 10px; selection-background-color:@accent; selection-color:white; }
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus { border:1px solid @accent; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDateTimeEdit:disabled { color:@muted; }
QLineEdit#Search { border-radius:@r_search; padding:6px 12px; min-width:200px; }
QComboBox::drop-down { border:none; width:28px; }
QComboBox::down-arrow, QDateTimeEdit::down-arrow, QSpinBox::down-arrow { image:url(@arrow_down); width:10px; height:10px; }
QSpinBox::up-arrow { image:url(@arrow_up); width:10px; height:10px; }
QSpinBox, QDateTimeEdit { padding-right:30px; }
QSpinBox::up-button { subcontrol-origin:border; subcontrol-position:top right; width:26px; border:none;
    background:transparent; margin:1px 1px 0 0; border-top-right-radius:@r_in; }
QSpinBox::down-button { subcontrol-origin:border; subcontrol-position:bottom right; width:26px; border:none;
    background:transparent; margin:0 1px 1px 0; border-bottom-right-radius:@r_in; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background:@hover; }
QDateTimeEdit::drop-down { subcontrol-origin:border; subcontrol-position:center right; width:28px; border:none; }
QComboBox QAbstractItemView { background:@menu; border:1px solid @border; selection-background-color:@sel;
    selection-color:@text; outline:0; padding:4px; }
QCheckBox { spacing:8px; background:transparent; }
QCheckBox::indicator { width:16px; height:16px; border-radius:5px; border:1px solid @border; background:@input; }
QCheckBox::indicator:checked { background:@accent; border:1px solid @accent; image:url(@check); }
QTableView { background:transparent; border:none; outline:0; gridline-color:transparent; }
QTableView::item { border-bottom:1px solid @border; padding-left:6px; }
QTableView::item:selected { background:@sel; color:@text; }
QHeaderView { background:transparent; }
QHeaderView::section { background:transparent; color:@muted; border:none; border-bottom:1px solid @border;
    padding:9px 10px; font-size:11px; font-weight:600; }
QScrollBar:vertical { background:transparent; width:12px; margin:2px; }
QScrollBar::handle:vertical { background:@border; border-radius:4px; min-height:30px; }
QScrollBar::handle:vertical:hover { background:@muted; }
QScrollBar:horizontal { background:transparent; height:12px; margin:2px; }
QScrollBar::handle:horizontal { background:@border; border-radius:4px; min-width:30px; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
QScrollBar::add-page, QScrollBar::sub-page { background:transparent; }
QMenu { background:@menu; border:1px solid @border; border-radius:12px; padding:6px; }
QMenu::item { padding:7px 28px 7px 14px; border-radius:8px; }
QMenu::item:selected { background:@sel; }
QMenu::item:disabled { color:@muted; }
QMenu::separator { height:1px; background:@border; margin:6px 8px; }
QTabWidget::pane { border:none; border-top:1px solid @border; top:-1px; }
QTabBar::tab { background:transparent; color:@muted; padding:9px 16px; border-bottom:2px solid transparent; font-weight:600; }
QTabBar::tab:selected { color:@text; border-bottom:2px solid @accent; }
QTabBar::tab:hover { color:@text; }
QProgressBar { background:@border; border:none; border-radius:2px; max-height:4px; }
QProgressBar::chunk { background:@accent; border-radius:2px; }
QStatusBar { background:transparent; color:@muted; }
QStatusBar::item { border:none; }
QSplitter::handle { background:@split_bg; height:@split_h; }
"""


def stylesheet(asset_dir: Path) -> str:
    assets = write_assets(asset_dir)
    vals = dict(current, check=assets["check"], arrow_up=assets["arrow_up"], arrow_down=assets["arrow_down"])
    if native:
        vals["win"] = "transparent"
    return re.sub(r"@(\w+)", lambda m: str(vals[m.group(1)]), QSS)
