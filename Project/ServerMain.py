import sys
import cv2
import time
import os
from fer import FER
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QTimer, Qt, QUrl
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from flask import Flask, jsonify, request

# CONSTANTS
HAPPY_THRESHOLD = 50

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

        self.mediaPlayer = QMediaPlayer()
        soundPath = os.path.abspath("ding.mp3")
        url = QUrl.fromLocalFile(soundPath)
        content = QMediaContent(url)
        self.mediaPlayer.setMedia(content)
        self.mediaPlayer.setVolume(100)

        # --- COUNTER FLASH TIMERS ---
        self.flashDurationTimer = QTimer()
        self.flashDurationTimer.setSingleShot(True)
        self.flashDurationTimer.timeout.connect(self.StopFlash)

        self.flashToggleTimer = QTimer()
        self.flashToggleTimer.timeout.connect(self.ToggleColor)
        self.isFlashRed = False

        # --- PRESENTATION TIMER SETUP ---
        self.StartPresentationButton.clicked.connect(self.TogglePresentation)

        self.presentationTimer = QTimer()
        self.presentationTimer.timeout.connect(self.UpdatePresentationTimer)
        self.presentationTimer.setInterval(1000)

        self.blinkTimer = QTimer()
        self.blinkTimer.timeout.connect(self.BlinkTimeLabel)
        self.blinkTimer.setInterval(500)

        self.isPresentationRunning = False
        self.timeRemaining = 0
        self.alert1Time = -1
        self.alert2Time = -1
        self.blinkState = False
        self.blinkMode = None

        # --- CAMERA SETUP ---
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
        self.StopFlash()

    # --- PRESENTATION TIMER LOGIC ---
    def TogglePresentation(self):
        if not self.isPresentationRunning:
            self.StartPresentation()
        else:
            self.StopPresentation()

    def StartPresentation(self):
        try:
            total_seconds = self.ParseTimeInput(self.PresentationLengthEdit.text())
            self.alert1Time = self.ParseTimeInput(self.Alert1Edit.text())
            self.alert2Time = self.ParseTimeInput(self.Alert2Edit.text())
        except ValueError:
            self.TimeLeftLabel.setText("Invalid Time Format")
            return

        self.isPresentationRunning = True
        self.timeRemaining = total_seconds

        self.PresentationLengthEdit.setEnabled(False)
        self.Alert1Edit.setEnabled(False)
        self.Alert2Edit.setEnabled(False)

        self.StartPresentationButton.setText("Stop Presentation")

        self.UpdateTimerLabelDisplay()
        self.presentationTimer.start()

    def StopPresentation(self):
        self.presentationTimer.stop()
        self.blinkTimer.stop()

        self.isPresentationRunning = False
        self.blinkMode = None
        self.TimeLeftLabel.setStyleSheet("")

        self.PresentationLengthEdit.setEnabled(True)
        self.Alert1Edit.setEnabled(True)
        self.Alert2Edit.setEnabled(True)

        self.StartPresentationButton.setText("Start Presentation")

    def UpdatePresentationTimer(self):
        self.timeRemaining -= 1
        self.UpdateTimerLabelDisplay()

        if self.timeRemaining == self.alert1Time or self.timeRemaining == self.alert2Time:
            self.TriggerOrangeAlert()

        if self.timeRemaining <= 0:
            if self.blinkMode != 'RED':
                self.blinkMode = 'RED'
                if not self.blinkTimer.isActive():
                    self.blinkTimer.start()

    def TriggerOrangeAlert(self):
        self.blinkMode = 'ORANGE'
        if not self.blinkTimer.isActive():
            self.blinkTimer.start()
        QTimer.singleShot(5000, self.StopOrangeAlert)

    def StopOrangeAlert(self):
        if self.blinkMode == 'ORANGE':
            self.blinkMode = None
            self.blinkTimer.stop()
            self.TimeLeftLabel.setStyleSheet("")

    def BlinkTimeLabel(self):
        self.blinkState = not self.blinkState

        if self.blinkMode == 'RED':
            if self.blinkState:
                self.TimeLeftLabel.setStyleSheet("background-color: red; color: white;")
            else:
                self.TimeLeftLabel.setStyleSheet("background-color: transparent; color: black;")

        elif self.blinkMode == 'ORANGE':
            if self.blinkState:
                self.TimeLeftLabel.setStyleSheet("background-color: orange; color: white;")
            else:
                self.TimeLeftLabel.setStyleSheet("background-color: transparent; color: black;")
        else:
            self.TimeLeftLabel.setStyleSheet("")

    def UpdateTimerLabelDisplay(self):
        abs_seconds = abs(self.timeRemaining)
        mins, secs = divmod(abs_seconds, 60)

        time_str = f"{mins:02}:{secs:02}"

        if self.timeRemaining < 0:
            self.TimeLeftLabel.setText(f"-{time_str}")
        else:
            self.TimeLeftLabel.setText(time_str)

    def ParseTimeInput(self, text):
        text = text.strip()
        if not text:
            return -1

        if ':' in text:
            parts = text.split(':')
            minutes = int(parts[0])
            seconds = int(parts[1])
            return (minutes * 60) + seconds
        else:
            return int(text) * 60

    # --- SERVER/COUNTER LOGIC ---
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
        self.flashDurationTimer.start(3000)
        if not self.flashToggleTimer.isActive():
            self.isFlashRed = True
            self.SetRedStyle()
            self.flashToggleTimer.start(200)

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

    # --- FRAME UPDATE LOGIC ---
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

            if happyScore >= HAPPY_THRESHOLD:
                self.emotionLabel.setText("Good job, keep smiling!")
                self.emotionLabel.setStyleSheet("background-color: green; color: white;")
            else:
                self.emotionLabel.setText("Smile more!")
                self.emotionLabel.setStyleSheet("background-color: red; color: white;")
        else:
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