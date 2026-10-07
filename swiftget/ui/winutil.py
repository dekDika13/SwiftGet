"""Membawa jendela ke depan, termasuk saat aplikasi tersembunyi di tray / diminimalkan."""
import sys

from PySide6.QtCore import Qt


def bring_to_front(w):
    w.setWindowState((w.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
    w.show()
    w.raise_()
    w.activateWindow()
    if sys.platform.startswith("win"):
        try:    # Windows menolak "mencuri fokus"; menekan Alt sekejap membuat SetForegroundWindow diizinkan
            import ctypes
            u = ctypes.windll.user32
            u.keybd_event(0x12, 0, 0, 0)
            u.keybd_event(0x12, 0, 2, 0)
            u.SetForegroundWindow(ctypes.c_void_p(int(w.winId())))
        except Exception:
            pass
