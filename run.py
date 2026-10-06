"""Titik masuk SwiftGet: python run.py"""
import sys


def main():
    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication, QMessageBox

    from swiftget.config import APP_NAME, Settings, data_dir
    from swiftget.manager import Manager
    from swiftget.models import DB
    from swiftget.ui import theme
    from swiftget.ui.main_window import MainWindow

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
    win.show()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
