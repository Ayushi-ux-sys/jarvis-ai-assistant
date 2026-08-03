import sys
from PyQt6.QtCore import QPointF, QRectF, QThread, QTime, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ArcReactorWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 250)
        self.angle = 0
        self.pulse = 0
        self.pulse_dir = 1

        # States: standby (#00d2ff), listening (#ffc107), thinking (#9c27b0), speaking (#00e676)
        self.core_color = QColor("#00d2ff")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(20)

    def set_state_color(self, hex_code: str):
        self.core_color = QColor(hex_code)
        self.update()

    def update_animation(self):
        self.angle = (self.angle + 2) % 360
        self.pulse += 0.5 * self.pulse_dir
        if self.pulse >= 15 or self.pulse <= 0:
            self.pulse_dir *= -1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        center = QPointF(width / 2, height / 2)

        # Outer Sci-Fi Ring
        pen = QPen(QColor(self.core_color.red(), self.core_color.green(), self.core_color.blue(), 100), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawEllipse(center, 100, 100)

        # Rotating Segmented Ring
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle)
        pen = QPen(self.core_color, 3)
        painter.setPen(pen)
        for i in range(8):
            painter.drawArc(QRectF(-85, -85, 170, 170), i * 45 * 16, 25 * 16)
        painter.restore()

        # Counter-rotating Inner Ring
        painter.save()
        painter.translate(center)
        painter.rotate(-self.angle * 1.5)
        pen = QPen(QColor(255, 255, 255, 180), 2)
        painter.setPen(pen)
        for i in range(4):
            painter.drawArc(QRectF(-65, -65, 130, 130), i * 90 * 16, 40 * 16)
        painter.restore()

        # Pulsing Center Core Glow
        r = 35 + self.pulse
        gradient = QLinearGradient(center.x() - r, center.y() - r, center.x() + r, center.y() + r)
        gradient.setColorAt(0, self.core_color)
        gradient.setColorAt(1, QColor(0, 0, 0, 200))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.drawEllipse(center, r, r)


class JarvisHUD(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. SYSTEM INTERFACE")
        self.resize(550, 700)
        self.setStyleSheet("background-color: #0b0e14; color: #00d2ff;")

        main_layout = QVBoxLayout()

        # Top Header
        self.title = QLabel("J.A.R.V.I.S.")
        self.title.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("color: #00d2ff; letter-spacing: 6px;")
        main_layout.addWidget(self.title)

        # Status Label
        self.status_lbl = QLabel("SYSTEM STANDBY")
        self.status_lbl.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setStyleSheet("color: #00a8ff;")
        main_layout.addWidget(self.status_lbl)

        # Arc Reactor HUD Visualizer
        self.reactor = ArcReactorWidget(self)
        main_layout.addWidget(self.reactor, alignment=Qt.AlignmentFlag.AlignCenter)

        # Terminal Output Feed
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 10))
        self.log_box.setStyleSheet(
            "background-color: #05070a; color: #58a6ff; border: 1px solid #1f293d; border-radius: 8px; padding: 10px;"
        )
        main_layout.addWidget(self.log_box)

        # Main Widget Container
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def update_state(self, status_text: str, color_hex: str):
        """Called by JARVIS core thread to change UI status & reactor glow."""
        self.status_lbl.setText(status_text.upper())
        self.status_lbl.setStyleSheet(f"color: {color_hex};")
        self.reactor.set_state_color(color_hex)

    def append_log(self, text: str):
        """Appends timestamped text to the terminal HUD."""
        time_str = QTime.currentTime().toString("hh:mm:ss")
        self.log_box.append(f"[{time_str}] {text}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = JarvisHUD()
    window.show()
    sys.exit(app.exec())