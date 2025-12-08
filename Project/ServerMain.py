import sys
import cv2
import time
import os
import datetime
from fer import FER
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QSizePolicy
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QTimer, Qt, QUrl
from PyQt5.QtGui import QImage, QPixmap
# Switched from QMediaPlayer to QSoundEffect for lower latency
from PyQt5.QtMultimedia import QSoundEffect
from flask import Flask, jsonify, request

# CONSTANTS
HAPPY_THRESHOLD = 50  # this constant defines how easy it is for the presenter to make FER detect you are happpy.

appState = {'counter': 0}  # this is where the "Uh counter" is stored
flaskApp = Flask(__name__)  # intializes Flask


# This section handles the two pyqtSignal's that are used to communicate between threads.
class ServerSignals(QThread):
    updateCounter = pyqtSignal(int)
    flashSignal = pyqtSignal()


serverSignals = ServerSignals()


# Links function to a flask route. whenever /query is accessed, the function returns the current "ah counter"
@flaskApp.route('/query', methods=['GET'])
def Query():
    return jsonify({'counter': appState['counter']})


# links function to this flask route. whenever /incrmenet ic accessed, the function incrmeents the value insideo of the counter dictionary.
@flaskApp.route('/increment', methods=['POST'])
def IncrementCounter():
    appState['counter'] += 1
    serverSignals.updateCounter.emit(appState['counter'])
    serverSignals.flashSignal.emit()
    return jsonify({'success': True, 'counter': appState['counter']})


# links function to flask route. this section calls function whenever the /decrement is accessed and decrements whatever value is inside of the counter dictionary.
@flaskApp.route('/decrement', methods=['POST'])
def DecrementCounter():
    appState['counter'] -= 1
    serverSignals.updateCounter.emit(appState['counter'])
    return jsonify({'success': True, 'counter': appState['counter']})


# This section runs the server thread through flask so that the webserver can be accessed without interupting the other processes.
class ServerThread(QThread):
    def run(self):
        flaskApp.run(host='10.0.2.15', port=5000, debug=False)


# This class handles the SummaryPopup GUI. this GUI is what shows at the end of the presentation and displayed the presentation data.
class SummaryPopup(QMainWindow):
    def __init__(self, start_time, time_left, uh_count):
        super().__init__()
        uic.loadUi('popup.ui', self)

        # calculates the persentation start time, time left and uh counter value.
        self.actual_duration = start_time - time_left
        self.start_time_val = start_time
        self.time_left_val = time_left
        self.uh_count_val = uh_count

        # This function formates the time inputted into minutes and seconds.
        def format_time(seconds):
            mins, secs = divmod(abs(seconds), 60)
            sign = "-" if seconds < 0 else ""
            return f"{sign}{mins:02}:{secs:02}"

        # This section formates all of the presentation data then sets the corrisponding labels to said values.
        self.str_start_time = format_time(start_time)
        self.str_time_left = format_time(time_left)
        self.str_total_duration = format_time(self.actual_duration)

        self.PresentationStartTimeLabel.setText(self.str_start_time)
        self.PresentationTimeLeftLabel.setText(self.str_time_left)
        self.TotalPresentationTimeLabel.setText(self.str_total_duration)
        self.TotalUhCounterLabel.setText(str(uh_count))

        # these are two buttons that are connected to two different functions listed below.
        self.ContinueButton.clicked.connect(self.close)
        self.SaveDataButton.clicked.connect(self.SaveToFile)

    # This function saves the data that was shown in the summary pop up into a text file so that the presenter can view said data later.
    def SaveToFile(self):
        try:
            # This section gets the current date so it can name the presentation file and sets it to that name.
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"presentation_summary_{timestamp}.txt"

            # gets the file path of where this script is running.
            script_dir = os.path.dirname(os.path.abspath(__file__))

            # combinds the file path with the name so it saves in the right folder.
            full_path = os.path.join(script_dir, filename)

            # opens the txt file and puts in the data about the presentation.
            with open(full_path, "w") as file:
                file.write("--- Presentation Summary ---\n")
                file.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                file.write(f"Presentation Length Set: {self.str_start_time}\n")
                file.write(f"Time Left at Stop:       {self.str_time_left}\n")
                file.write(f"Actual Duration:         {self.str_total_duration}\n")
                file.write(f"Total Uh Count:          {self.uh_count_val}\n")

            print(f"Successfully saved to: {full_path}")

            # closes the popup window after saving the data to the text file.
            self.close()
        # catches error if file saving went wrong so the app doesn't crash.
        except Exception as e:
            print(f"Error saving file: {e}")


# This is the main server application window that has the facial recognition, presentation timing and the "uh counter"
class CombinedApp(QMainWindow):
    def __init__(self):
        super().__init__()  # starts as soon as this class is called.
        uic.loadUi('Server.ui', self)  # loads UI

        self.serverThread = ServerThread()  # initializes the server thread
        self.serverThread.start()  # starts the server thread running in background

        serverSignals.updateCounter.connect(
            self.UpdateCounterLabel)  # connects a server signal to updatecounter function
        serverSignals.flashSignal.connect(self.StartFlash)  # connects server signal to flash signal function
        serverSignals.flashSignal.connect(self.PlaySound)  # conects server siganl to play sound function.

        # this section initializes the sound library, sets path to sound and sets the volume to high.
        self.soundEffect = QSoundEffect()
        soundPath = os.path.abspath("ding.mp3")
        url = QUrl.fromLocalFile(soundPath)
        self.soundEffect.setSource(url)
        self.soundEffect.setVolume(1.0)

        # This section sets up the flash timer that shows when the ah counter increments. Sets it to only flash one time and connects the ending timer to a function.
        self.flashDurationTimer = QTimer()
        self.flashDurationTimer.setSingleShot(True)
        self.flashDurationTimer.timeout.connect(self.StopFlash)

        # This timer handles the blinking effect speed when the warning happens.
        self.flashToggleTimer = QTimer()
        self.flashToggleTimer.timeout.connect(self.ToggleColor)
        self.isFlashRed = False


        # connects the start presentation button to the toggle function.
        self.StartPresentationButton.clicked.connect(self.TogglePresentation)

        # this timer counts down every second for the presentation timer.
        self.presentationTimer = QTimer()
        self.presentationTimer.timeout.connect(self.UpdatePresentationTimer)
        self.presentationTimer.setInterval(1000)

        # this timer handles the blinking for the orange/red alerts.
        self.blinkTimer = QTimer()
        self.blinkTimer.timeout.connect(self.BlinkTimeLabel)
        self.blinkTimer.setInterval(500)

        # variables to store the state of the presentation.
        self.isPresentationRunning = False
        self.timeRemaining = 0
        self.initialDuration = 0  # Track initial time for the summary popup
        self.alert1Time = -1
        self.alert2Time = -1
        self.blinkState = False
        self.blinkMode = None
        self.previousTimeLabelText = ""


        self.cap = cv2.VideoCapture(0)  # capture the first frame from the webcam.
        if not self.cap.isOpened():  # cancel if the webcam is not open.
            return

        self.fpsFrameCount = 0  # count how many frames were displayed per second.
        self.fpsStartTime = time.time()  # gets the current time right when the class is called.

        self.detector = FER(mtcnn=True)  # utilizes the FER facial recognition.
        self.emotionTimer = time.time()  # gets the current time when the facial recognition first gets utilized.
        self.lastDetectionResult = []  # this will store the facial analysis data.

        # this timer calls the UpdateFrame function as fast as possible to make the video look smooth.
        self.timer = QTimer()
        self.timer.timeout.connect(self.UpdateFrame)
        self.timer.start(0)

        self.UpdateCounterLabel(appState['counter'])
        self.StopFlash()


    # this function gets called when the button is clicked and decides whether to start or stop based on current state.
    def TogglePresentation(self):
        if not self.isPresentationRunning:
            self.StartPresentation()
        else:
            self.StopPresentation()

    # this function handles all the logic for starting the presentation. it formates the time, validates alerts, and locks the UI inputs.
    def StartPresentation(self):
        try:
            # tries to parse the time from the input box.
            total_seconds = self.ParseTimeInput(self.PresentationLengthEdit.text())

            if total_seconds <= 0:  # Ensure presentation time is positive or it throws an error.
                self.TriggerInvalidTimeAlert()
                return

            # Helper function to check if the alert time makes sense (must be less than total time).
            def validate_alert(time_val):
                return time_val > 0 and time_val < total_seconds

            # checks if it's empty or invalid, if so defaults to half time.
            alert1_input = self.Alert1Edit.text().strip()
            self.alert1Time = self.ParseTimeInput(alert1_input)

            if not validate_alert(self.alert1Time):
                self.alert1Time = int(total_seconds / 2)
                mins, secs = divmod(self.alert1Time, 60)
                self.Alert1Edit.setText(f"{mins:02}:{secs:02}")

            # checks if it's empty or invalid, if so defaults to quarter time.
            alert2_input = self.Alert2Edit.text().strip()
            self.alert2Time = self.ParseTimeInput(alert2_input)

            if not validate_alert(self.alert2Time):
                self.alert2Time = int(total_seconds / 4)
                mins, secs = divmod(self.alert2Time, 60)
                self.Alert2Edit.setText(f"{mins:02}:{secs:02}")

        #if not a number of in right format, throws an error.
        except ValueError:
            self.TimeLeftLabel.setText("Invalid Time Format")
            return

        # Reset Counter Logic back to 0 for the new presentation.
        appState['counter'] = 0
        serverSignals.updateCounter.emit(appState['counter'])

        # updates state variables
        self.isPresentationRunning = True
        self.initialDuration = total_seconds  # Store this so we can calculate total time later
        self.timeRemaining = total_seconds

        # greys out the input boxes so they cant be changed while running.
        self.PresentationLengthEdit.setEnabled(False)
        self.Alert1Edit.setEnabled(False)
        self.Alert2Edit.setEnabled(False)

        # changes button text to Stop
        self.StartPresentationButton.setText("Stop Presentation")

        self.UpdateTimerLabelDisplay()
        self.presentationTimer.start()  # starts the countdown.

    # this function gets called to stop the presentation. it opens the summary popup and resets the UI for the next run
    def StopPresentation(self):

        # We launch the popup here passing: Initial Time, Time Left, and Counter
        self.summaryPopup = SummaryPopup(self.initialDuration, self.timeRemaining, appState['counter'])
        self.summaryPopup.show()

        # Resets Timer Logic and stops blinking
        self.presentationTimer.stop()
        self.blinkTimer.stop()

        self.isPresentationRunning = False
        self.blinkMode = None
        self.TimeLeftLabel.setStyleSheet("")

        # re-enables the input boxes.
        self.PresentationLengthEdit.setEnabled(True)
        self.Alert1Edit.setEnabled(True)
        self.Alert2Edit.setEnabled(True)

        self.StartPresentationButton.setText("Start Presentation")

    # this function handles the invalid time alert, flashing the time label red for 5 seconds to warn the user.
    def TriggerInvalidTimeAlert(self):
        current_text = self.TimeLeftLabel.text()
        # save the current text so we can put it back later.
        if current_text != "Please insert length of presentation":
            self.previousTimeLabelText = current_text

        self.TimeLeftLabel.setText("Please insert length of presentation")
        self.TimeLeftLabel.setStyleSheet("background-color: red; color: white;")
        QTimer.singleShot(5000, self.ResetTimeLabelError)

    # this function resets the time label error message back to normal after the 5 second timeout.
    def ResetTimeLabelError(self):
        if not self.isPresentationRunning:
            self.TimeLeftLabel.setText(self.previousTimeLabelText)
            self.TimeLeftLabel.setStyleSheet("")

    # this function is called every second by the timer to decrement the time remaining and check for alerts.
    def UpdatePresentationTimer(self):
        self.timeRemaining -= 1
        self.UpdateTimerLabelDisplay()

        # checks if we hit one of the warning times.
        if self.timeRemaining == self.alert1Time or self.timeRemaining == self.alert2Time:
            self.TriggerOrangeAlert()

        # checks if we ran out of time.
        if self.timeRemaining <= 0:
            if self.blinkMode != 'RED':
                self.blinkMode = 'RED'
                if not self.blinkTimer.isActive():
                    self.blinkTimer.start()

    # this function starts the orange blinking alert for warning times.
    def TriggerOrangeAlert(self):
        self.blinkMode = 'ORANGE'
        if not self.blinkTimer.isActive():
            self.blinkTimer.start()
        QTimer.singleShot(5000, self.StopOrangeAlert)  # stops it after 5 seconds.

    # this function stops the orange alert and resets the color.
    def StopOrangeAlert(self):
        if self.blinkMode == 'ORANGE':
            self.blinkMode = None
            self.blinkTimer.stop()
            self.TimeLeftLabel.setStyleSheet("")

    # this function toggles the background color of the time label for blinking effects (Red or Orange).
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

    # this function formats the remaining time into MM:SS and updates the label on screen.
    def UpdateTimerLabelDisplay(self):
        abs_seconds = abs(self.timeRemaining)
        mins, secs = divmod(abs_seconds, 60)

        time_str = f"{mins:02}:{secs:02}"

        if self.timeRemaining < 0:
            self.TimeLeftLabel.setText(f"-{time_str}")
        else:
            self.TimeLeftLabel.setText(time_str)

    # this function parses the time input string into total seconds, handling both MM:SS and raw minutes.
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


    @pyqtSlot(int)
    # this function updates the counter label on the GUI when the signal is received from the server thread.
    def UpdateCounterLabel(self, newValue):
        self.CounterLabel.setText(f"{newValue}")

    @pyqtSlot()
    # this function plays the ding sound effect.
    def PlaySound(self):
        self.soundEffect.play()

    @pyqtSlot()
    # this function starts the red flash on the counter label.
    def StartFlash(self):
        self.flashDurationTimer.start(3000)
        if not self.flashToggleTimer.isActive():
            self.isFlashRed = True
            self.SetRedStyle()
            self.flashToggleTimer.start(200)

    # this function toggles the red/black colors for the flashing effect.
    def ToggleColor(self):
        if self.isFlashRed:
            self.SetDefaultStyle()
        else:
            self.SetRedStyle()
        self.isFlashRed = not self.isFlashRed

    # this function stops the flashing effect and resets the style.
    def StopFlash(self):
        self.flashToggleTimer.stop()
        self.SetDefaultStyle()
        self.isFlashRed = False

    # helper to set the label to red.
    def SetRedStyle(self):
        self.CounterLabel.setStyleSheet("background-color: red; color: black;")

    # helper to reset the label to default black.
    def SetDefaultStyle(self):
        self.CounterLabel.setStyleSheet("background-color: #000000; color: white;")


    # this function is called every frame to capture video, detect emotions, and update the display.
    def UpdateFrame(self):
        ret, frame = self.cap.read()  # gets the frame from the screen capture.
        if not ret:
            return

        if self.mirrorCheckBox.isChecked():  # if the mirrored checkbox is checked, the
            frame = cv2.flip(frame, 1)  # frame that was just captured will be flipped.

        image = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)  # converts the image into something that can be displayed by the UI.
        h, w, ch = image.shape  # gets the different data about the image shape.
        bytesPerLine = ch * w  # calculates the bytes per line needed for the QImage.
        qtImage = QImage(image.data, w, h, bytesPerLine, QImage.Format_RGB888)  # gets the QImage
        pixmap = QPixmap.fromImage(qtImage)  # converts the qtImage into a piximap.

        self.fpsFrameCount += 1  # this increases the frame counter by one.
        currentTime = time.time()  # this gets the current time during this frame.

        if currentTime - self.emotionTimer >= 2:
            #waits every 2 seconds to do the facials recognition.
            self.lastDetectionResult = self.detector.detect_emotions(frame)
            self.emotionTimer = currentTime

        if self.lastDetectionResult:  # Checks for detection
            firstFace = self.lastDetectionResult[0]  # this gets the last detection result data.
            emotions = firstFace['emotions']  # this will only get the emotions data.
            happyScore = emotions['happy'] * 100  # converts to percentage

            # Updates the emotional data based off of threashold constant.
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
        # this line returns the time since the first frame was captured.

        if elapsedTime >= 1:
            # checks if the time since the first frame is more then 1 second
            fps = self.fpsFrameCount / elapsedTime  # this calculates how many frames there was in one second.
            self.fpsLabel.setText(f"FPS: {fps: .2f}")
            self.fpsFrameCount = 0
            self.fpsStartTime = currentTime


        # sets scaling parameters.
        self.imageLabel.setPixmap(pixmap.scaled(self.imageLabel.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))

    # this function ensures the camera is released when the window closes.
    def closeEvent(self, event):
        self.cap.release()
        event.accept()


# main function, gets called when the python application gets ran.
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CombinedApp()
    window.show()
    sys.exit(app.exec_())