import sys
import cv2
import time
from fer import FER
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from flask import Flask, jsonify, request

appState = {'counter': 1, 'color': '000000'}
flaskApp = Flask(__name__)

class ServerSignals(QThread):
    updateCounter = pyqtSignal(int)
    updateColor = pyqtSignal(object)

serverSignals = ServerSignals()

@flaskApp.route('/query', methods=['GET'])
def Query():
    return jsonify({'counter': appState['counter'], 'color': appState['color']})

@flaskApp.route('/increment', methods=['POST'])
def IncrementCounter():
    appState['counter'] += 1
    serverSignals.updateCounter.emit(appState['counter'])
    return jsonify({'success': True, 'counter': appState['counter']})

@flaskApp.route('/decrement', methods=['POST'])
def DecrementCounter():
    appState['counter'] -= 1
    serverSignals.updateCounter.emit(appState['counter'])
    return jsonify({'success': True, 'counter': appState['counter']})

@flaskApp.route('/color', methods=['POST'])
def SetColor():
    data = request.get_json()
    if data and 'color' in data:
        newColor = str(data['color']).strip().lstrip('#')
        appState['color'] = newColor
        serverSignals.updateColor.emit(newColor)
        return jsonify({'success': True, 'color': newColor})
    return jsonify({'success': False, 'error': 'Invalid request'}), 400

class ServerThread(QThread):
    def run(self):
        flaskApp.run(host='10.0.2.15', port=5000, debug=False)

class CombinedApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('Server.ui', self)

        self.serverThread = ServerThread()
        self.serverThread.start()

        self.IncrementButton.clicked.connect(self.GuiIncrement)
        self.DecrementButton.clicked.connect(self.GuiDecrement)
        self.ColorText.returnPressed.connect(self.GuiColorChange)

        serverSignals.updateCounter.connect(self.UpdateCounterLabel)
        serverSignals.updateColor.connect(self.UpdateBackgroundColor)

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

    def GuiIncrement(self):
        appState['counter'] += 1
        serverSignals.updateCounter.emit(appState['counter'])

    def GuiDecrement(self):
        appState['counter'] -= 1
        serverSignals.updateCounter.emit(appState['counter'])

    def GuiColorChange(self):
        newColor = self.ColorText.text().strip().lstrip('#')
        appState['color'] = newColor
        serverSignals.updateColor.emit(newColor)
        self.ColorText.clear()

    @pyqtSlot(int)
    def UpdateCounterLabel(self, newValue):
        self.CounterLabel.setText(f"{newValue}")

    @pyqtSlot(object)
    def UpdateBackgroundColor(self, newColorHex):
        self.CounterLabel.setStyleSheet(f"background-color: #{newColorHex}; color: black;")

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
            sadScore = emotions['sad'] * 100
            angryScore = emotions['angry'] * 100
            neutralScore = emotions['neutral'] * 100

            self.happyLabel.setText(f"Happy: {happyScore: .1f}%")
            self.sadLabel.setText(f"Sad: {sadScore: .1f}%")
            self.angryLabel.setText(f"Angry: {angryScore: .1f}%")
            self.neutralLabel.setText(f"Neutral: {neutralScore: .1f}%")
        else:
            self.happyLabel.setText("Happy: ?%")
            self.sadLabel.setText("Sad: ?%")
            self.angryLabel.setText("Angry: ?%")
            self.neutralLabel.setText("Neutral: ?%")

        elapsedTime = currentTime - self.fpsStartTime

        if elapsedTime >= 1:
            fps = self.fpsFrameCount / elapsedTime
            self.fpsLabel.setText(f"FPS: {fps: .2f}")
            self.fpsFrameCount = 0
            self.fpsStartTime = currentTime

        self.imageLabel.setPixmap(pixmap.scaled(self.imageLabel.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    def closeEvent(self, event):
        self.cap.release()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CombinedApp()
    window.show()
    sys.exit(app.exec_())