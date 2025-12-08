import sys
import cv2
import time
import os
import datetime
from fer import FER
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QTimer, Qt, QUrl
from PyQt5.QtGui import QImage, QPixmap
# Switched from QMediaPlayer to QSoundEffect for lower latency
from PyQt5.QtMultimedia import QSoundEffect
from flask import Flask, jsonify, request

# CONSTANTS
HAPPY_THRESHOLD = 50

appState = {'counter': 0}
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


# --- NEW POPUP CLASS ---
class SummaryPopup(QMainWindow):
    def __init__(self, start_time, time_left, uh_count):
        super().__init__()
        uic.loadUi('popup.ui', self)

        # Calculate actual presentation duration
        self.actual_duration = start_time - time_left
        self.start_time_val = start_time
        self.time_left_val = time_left
        self.uh_count_val = uh_count

        # Helper function to format seconds into MM:SS
        def format_time(seconds):
            mins, secs = divmod(abs(seconds), 60)
            sign = "-" if seconds < 0 else ""
            return f"{sign}{mins:02}:{secs:02}"

        # Set the labels
        self.str_start_time = format_time(start_time)
        self.str_time_left = format_time(time_left)
        self.str_total_duration = format_time(self.actual_duration)

        self.PresentationStartTimeLabel.setText(self.str_start_time)
        self.PresentationTimeLeftLabel.setText(self.str_time_left)
        self.TotalPresentationTimeLabel.setText(self.str_total_duration)
        self.TotalUhCounterLabel.setText(str(uh_count))

        # Connect Buttons using new names
        self.ContinueButton.clicked.connect(self.close)
        self.SaveDataButton.clicked.connect(self.SaveToFile)

    def SaveToFile(self):
        try:
            # Generate unique filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"presentation_summary_{timestamp}.txt"

            # 1. Get the directory where this python script is located
            script_dir = os.path.dirname(os.path.abspath(__file__))

            # 2. Combine that directory with the filename
            full_path = os.path.join(script_dir, filename)

            with open(full_path, "w") as file:
                file.write("--- Presentation Summary ---\n")
                file.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                file.write(f"Presentation Length Set: {self.str_start_time}\n")
                file.write(f"Time Left at Stop:       {self.str_time_left}\n")
                file.write(f"Actual Duration:         {self.str_total_duration}\n")
                file.write(f"Total Uh Count:          {self.uh_count_val}\n")

            print(f"Successfully saved to: {full_path}")

            # Close the popup window after saving
            self.close()

        except Exception as e:
            print(f"Error saving file: {e}")


class CombinedApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('Server.ui', self)

        self.serverThread = ServerThread()
        self.serverThread.start()

        serverSignals.updateCounter.connect(self.UpdateCounterLabel)
        serverSignals.flashSignal.connect(self.StartFlash)
        serverSignals.flashSignal.connect(self.PlaySound)

        # Switched to QSoundEffect for low-latency audio
        self.soundEffect = QSoundEffect()
        soundPath = os.path.abspath("ding.mp3")
        url = QUrl.fromLocalFile(soundPath)
        self.soundEffect.setSource(url)
        self.soundEffect.setVolume(1.0)  # Volume is 0.0 to 1.0 for SoundEffect

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
        self.initialDuration = 0  # Track initial time for the summary popup
        self.alert1Time = -1
        self.alert2Time = -1
        self.blinkState = False
        self.blinkMode = None
        self.previousTimeLabelText = ""

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

            if total_seconds <= 0:  # Ensure presentation time is positive
                self.TriggerInvalidTimeAlert()
                return

            # Helper function to validate alert time
            def validate_alert(time_val):
                # Must be an integer, > 0, and < total_seconds
                return time_val > 0 and time_val < total_seconds

            # Process Alert 1
            alert1_input = self.Alert1Edit.text().strip()
            self.alert1Time = self.ParseTimeInput(alert1_input)

            # If invalid or out of range, default to 1/2 time
            if not validate_alert(self.alert1Time):
                self.alert1Time = int(total_seconds / 2)
                mins, secs = divmod(self.alert1Time, 60)
                self.Alert1Edit.setText(f"{mins:02}:{secs:02}")

            # Process Alert 2
            alert2_input = self.Alert2Edit.text().strip()
            self.alert2Time = self.ParseTimeInput(alert2_input)

            # If invalid or out of range, default to 1/4 time
            if not validate_alert(self.alert2Time):
                self.alert2Time = int(total_seconds / 4)
                mins, secs = divmod(self.alert2Time, 60)
                self.Alert2Edit.setText(f"{mins:02}:{secs:02}")

        except ValueError:
            self.TimeLeftLabel.setText("Invalid Time Format")
            return

        # Reset Counter Logic
        appState['counter'] = 0
        serverSignals.updateCounter.emit(appState['counter'])

        self.isPresentationRunning = True
        self.initialDuration = total_seconds  # Store this so we can calculate total time later
        self.timeRemaining = total_seconds

        self.PresentationLengthEdit.setEnabled(False)
        self.Alert1Edit.setEnabled(False)
        self.Alert2Edit.setEnabled(False)

        self.StartPresentationButton.setText("Stop Presentation")

        self.UpdateTimerLabelDisplay()
        self.presentationTimer.start()

    def StopPresentation(self):
        # --- SHOW SUMMARY POPUP ---
        # We launch the popup here passing: Initial Time, Time Left, and Counter
        self.summaryPopup = SummaryPopup(self.initialDuration, self.timeRemaining, appState['counter'])
        self.summaryPopup.show()

        # Reset Timer Logic
        self.presentationTimer.stop()
        self.blinkTimer.stop()

        self.isPresentationRunning = False
        self.blinkMode = None
        self.TimeLeftLabel.setStyleSheet("")

        self.PresentationLengthEdit.setEnabled(True)
        self.Alert1Edit.setEnabled(True)
        self.Alert2Edit.setEnabled(True)

        self.StartPresentationButton.setText("Start Presentation")

    def TriggerInvalidTimeAlert(self):
        current_text = self.TimeLeftLabel.text()
        if current_text != "Please insert length of presentation":
            self.previousTimeLabelText = current_text

        self.TimeLeftLabel.setText("Please insert length of presentation")
        self.TimeLeftLabel.setStyleSheet("background-color: red; color: white;")
        QTimer.singleShot(5000, self.ResetTimeLabelError)

    def ResetTimeLabelError(self):
        if not self.isPresentationRunning:
            self.TimeLeftLabel.setText(self.previousTimeLabelText)
            self.TimeLeftLabel.setStyleSheet("")

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
            try:
                minutes = int(parts[0])
                seconds = int(parts[1])
                return (minutes * 60) + seconds
            except ValueError:
                return -1  # Return -1 for invalid parts
        else:
            try:
                return int(text) * 60
            except ValueError:
                return -1  # Return -1 if not a number

    # --- SERVER/COUNTER LOGIC ---
    @pyqtSlot(int)
    def UpdateCounterLabel(self, newValue):
        self.CounterLabel.setText(f"{newValue}")

    @pyqtSlot()
    def PlaySound(self):
        self.soundEffect.play()

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

        # Updated to use KeepAspectRatio to allow shrinking
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