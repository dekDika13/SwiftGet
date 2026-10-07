"""Titik masuk aplikasi (dipakai run.py, `python -m swiftget`, dan perintah `swiftget`)."""
import os, sys


def main() -> int:
    # Aplikasi "windowed" tidak punya stdout/stderr; yt-dlp bisa crash bila menulis ke None
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w"))
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox

    from .config import APP_NAME, Settings, data_dir
    from .manager import Manager
    from .models import DB
    from .ui import theme
    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(data_dir() / "app.lock"))
    if not lock.tryLock(200):
        QMessageBox.information(None, APP_NAME, "SwiftGet sudah berjalan (cek system tray / menu bar).")
        return 0
    cfg = Settings()
    theme.set_theme(cfg["theme"])
    manager = Manager(cfg, DB(data_dir() / "downloads.db"))
    win = MainWindow(cfg, manager)
    if "--background" in sys.argv and win.tray.isVisible():
        pass                                  # mulai tersembunyi di system tray
    else:
        win.show()
    code = app.exec()
    lock.unlock()
    return code
