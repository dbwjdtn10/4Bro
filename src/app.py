"""Application bootstrap for 4Bro v2.0."""

import sys

from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor, QPainter, QFont

from core.engine import AIEngine
from core.database import Database
from gui.main_window import MainWindow
from gui.styles import apply_stylesheet


def create_splash_pixmap() -> QPixmap:
    pixmap = QPixmap(400, 200)
    pixmap.fill(QColor("#1e1e2e"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("#89b4fa"))
    font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "4Bro")
    painter.setPen(QColor("#a6adc8"))
    font2 = QFont("Segoe UI", 12)
    painter.setFont(font2)
    painter.drawText(
        pixmap.rect().adjusted(0, 60, 0, 0),
        Qt.AlignmentFlag.AlignHCenter,
        "AI 광고 어시스턴트 로딩 중...",
    )
    painter.end()
    return pixmap


def run():
    app = QApplication(sys.argv)
    apply_stylesheet(app)

    # Splash
    splash = QSplashScreen(create_splash_pixmap())
    splash.show()
    app.processEvents()

    # Initialize
    engine = AIEngine()
    engine.check_ollama()
    db = Database()

    # Create main window
    window = MainWindow(engine, db)

    splash.close()
    window.show()

    # If no API key configured, show settings dialog
    if not engine.status.gemini_available:
        from gui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(engine, window)
        dialog.exec()

    sys.exit(app.exec())
