import sys
import cv2
import time
import os
from fer import FER
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QTimer, Qt, QUrl
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from flask import Flask, jsonify, request

# CONSTANTS
HAPPY_THRESHOLD = 50  # threashold for when the algorithm will detect the presenter is happy in %

appState = {'counter': 1}
flaskApp = Flask(__name__)


class ServerSignals(QThread):
    updateCounter = pyqtSignal(int)
    flashSignal = pyqtSignal()


serverSignals = ServerSignals()


@flaskApp.route('/query', methods=['GET'])
def Query():
    return jsonify({'counter': appState['counter']})


@flaskApp.route('/increment', methods=['POST'])
def IncrementCounter():
    appState['counter'] += 1
    serverSignals.updateCounter.emit(appState['counter'])
    serverSignals.flashSignal.emit()
    return jsonify({'success': True, 'counter': appState['counter']})


@flaskApp.route('/decrement', methods=['POST'])
def DecrementCounter():
    appState['counter'] -= 1
    serverSignals.updateCounter.emit(appState['counter'])
    return jsonify({'success': True, 'counter': appState['counter']})


class ServerThread(QThread):
    def run(self):
        flaskApp.run(host='10.0.2.15', port=5000, debug=False)


class CombinedApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('Server.ui', self)

        self.serverThread = ServerThread()
        self.serverThread.start()

        serverSignals.updateCounter.connect(self.UpdateCounterLabel)
        serverSignals.flashSignal.connect(self.StartFlash)
        serverSignals.flashSignal.connect(self.PlaySound)

        # Setup Media Player
        self.mediaPlayer = QMediaPlayer()
        soundPath = os.path.abspath("ding.mp3")
        url = QUrl.fromLocalFile(soundPath)
        content = QMediaContent(url)
        self.mediaPlayer.setMedia(content)
        self.mediaPlayer.setVolume(100)

        # Timer for the total duration of the flashing (3 seconds)
        self.flashDurationTimer = QTimer()
        self.flashDurationTimer.setSingleShot(True)
        self.flashDurationTimer.timeout.connect(self.StopFlash)

        # Timer for the toggle interval (blinking speed)
        self.flashToggleTimer = QTimer()
        self.flashToggleTimer.timeout.connect(self.ToggleColor)
        self.isFlashRed = False

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            return

        self.fpsFrameCount = 0
        self.fpsStartTime = time.time()

        self.detector = FER(mtcnn=True)
        self.emotionTimer = time.time()
        self.lastDetectionResult = []

        self.timer = QTimer()
        self.timer.timeout.connect(self.UpdateFrame)
        self.timer.start(0)

        self.UpdateCounterLabel(appState['counter'])
        self.StopFlash()  # Ensure it starts in default state

    @pyqtSlot(int)
    def UpdateCounterLabel(self, newValue):
        self.CounterLabel.setText(f"{newValue}")

    @pyqtSlot()
    def PlaySound(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.mediaPlayer.setPosition(0)
        self.mediaPlayer.play()

    @pyqtSlot()
    def StartFlash(self):
        # Restart the 3-second timer. If called while running, it resets to 3s.
        self.flashDurationTimer.start(3000)

        # If not already blinking, start the toggle timer
        if not self.flashToggleTimer.isActive():
            self.isFlashRed = True
            self.SetRedStyle()
            self.flashToggleTimer.start(200)  # Blink every 200ms

    def ToggleColor(self):
        if self.isFlashRed:
            self.SetDefaultStyle()
        else:
            self.SetRedStyle()
        self.isFlashRed = not self.isFlashRed

    def StopFlash(self):
        self.flashToggleTimer.stop()
        self.SetDefaultStyle()
        self.isFlashRed = False

    def SetRedStyle(self):
        self.CounterLabel.setStyleSheet("background-color: red; color: black;")

    def SetDefaultStyle(self):
        self.CounterLabel.setStyleSheet("background-color: #000000; color: white;")

    def UpdateFrame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        if self.mirrorCheckBox.isChecked():
            frame = cv2.flip(frame, 1)

        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = image.shape
        bytesPerLine = ch * w
        qtImage = QImage(image.data, w, h, bytesPerLine, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qtImage)

        self.fpsFrameCount += 1
        currentTime = time.time()

        if currentTime - self.emotionTimer >= 2:
            self.lastDetectionResult = self.detector.detect_emotions(frame)
            self.emotionTimer = currentTime

        if self.lastDetectionResult:
            firstFace = self.lastDetectionResult[0]
            emotions = firstFace['emotions']
            happyScore = emotions['happy'] * 100

            # Logic for updating the emotionLabel based on the threshold
            if happyScore >= HAPPY_THRESHOLD:
                self.emotionLabel.setText("Good job, keep smiling!")
                self.emotionLabel.setStyleSheet("background-color: green; color: white;")
            else:
                self.emotionLabel.setText("Smile more!")
                self.emotionLabel.setStyleSheet("background-color: red; color: white;")
        else:
            # Fallback if no face is detected
            self.emotionLabel.setText("Scanning for face...")
            self.emotionLabel.setStyleSheet("background-color: gray; color: white;")

        elapsedTime = currentTime - self.fpsStartTime

        if elapsedTime >= 1:
            fps = self.fpsFrameCount / elapsedTime
            self.fpsLabel.setText(f"FPS: {fps: .2f}")
            self.fpsFrameCount = 0
            self.fpsStartTime = currentTime

        self.imageLabel.setPixmap(
            pixmap.scaled(self.imageLabel.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def closeEvent(self, event):
        self.cap.release()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CombinedApp()
    window.show()
    sys.exit(app.exec_())