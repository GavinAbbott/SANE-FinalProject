import sys
import cv2
import time
from fer import FER
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
# Structure that is directly linked to the QT window.
class WebcamApp(QMainWindow):
    def __init__(self):
        super().__init__() #starts as soon as this class is called.

        uic.loadUi('Main.ui',self) #loads the UI as soon as this class is called.


        self.cap = cv2.VideoCapture(0) #capture the first frame from the webcam.
        if not self.cap.isOpened(): #if the webcam is not opened for some reason.
            print("Cannot open video camera") #print out an error.
            return

        self.fpsFrameCount = 0 #using this to count how many frames were displayed per second.
        self.fpsStartTime = time.time() #gets the current time right when the class is called.

        self.detector = FER(mtcnn=True) #utilizes the FER facial recognition.
        self.emotionTimer = time.time() #gets the current time when the facial recognition first gets utilized.
        self.lastDetectionResult = [] #this will store the facial analysis data.


        self.timer = QTimer() #creates a timer.
        self.timer.timeout.connect(self.UpdateFrame) #connects the timer to the function UpdateFrame
        self.timer.start(0) #starts the timer, the timmer runs as fast as it can
        #but limited to 30 fps because that is what my laptop camera is capped at.

    def UpdateFrame(self):
        ret, frame = self.cap.read() #gets the frame from the screen capture.
        if not ret:
            return

        if self.mirrorbox.isChecked(): # if the mirrored checkbox is checked, the
            #frame that was just captured will be flipped.
            frame = cv2.flip(frame,1)




        image = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB) #converts the image into something that can be displayed by the UI.

        h, w, ch = image.shape #gets the different data about the image shape.

        bytesPerLine = ch * w #calculated the bytes per line needed for the QImage.

        qtImage = QImage(image.data, w, h, bytesPerLine, QImage.Format_RGB888) #gets the QImage

        pixmap = QPixmap.fromImage(qtImage) #converts the qtImage into a piximap.

        self.fpsFrameCount += 1 #this increases the frame counter by one.

        currentTime = time.time() #this gets the current time during this frame.


        if currentTime - self.emotionTimer >= 2:
            # since analyzing the facial expression constantly would use up alot of processing power,
            # this code here waits til the time since the last facial analysis is equal to 2 seconds,
            #then the code does another analysis.
            self.lastDetectionResult = self.detector.detect_emotions(frame) #gets emotional data.
            self.emotionTimer = currentTime #resets the emotional timer.

        if self.lastDetectionResult: # if there was a detection.
            firstFace = self.lastDetectionResult[0] #this gets the last detection result data.
            emotions = firstFace['emotions'] #this will only get the emotions data.
            #this will convert all of the emotions into percentages.
            happyScore = emotions['happy'] * 100
            sadScore = emotions['sad'] * 100
            angryScore = emotions['angry'] * 100
            neutralScore = emotions['neutral'] * 100

            #sets all of the data into the labels.
            self.happyLabel.setText(f"Happy: {happyScore: .1f}%")
            self.sadLabel.setText(f"Sad: {sadScore: .1f}%")
            self.angryLabel.setText(f"Angry: {angryScore: .1f}%")
            self.neutralLabel.setText(f"Neutral: {neutralScore: .1f}%" )
        else: # if there is not emotional data for some reason, the
            #labels will be set to ?.
            self.happyLabel.setText("Happy: ?%")
            self.sadLabel.setText("Sad: ?%")
            self.angryLabel.setText("Angry: ?%" )
            self.neutralLabel.setText("Neutral: ?%" )


        elapsedTime = currentTime - self.fpsStartTime
        # this line returns the time since the first frame was captured.

        if elapsedTime >= 1:
            #if the time since the first frame is more then 1 second/

            fps = self.fpsFrameCount/ elapsedTime #this calculateds how many frames there was in one second.
            self.fpsLabel.setText(f"FPS: {fps: .2f}") #sets the label the current fps.
            #resets the fraem count and the time.
            self.fpsFrameCount = 0
            self.fpsStartTime = currentTime


        #this line finally sets the label to the piximap, displaying the current frame and thus creating a live video.
        self.image_label.setPixmap(pixmap.scaled(self.image_label.size(),Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation))
    #this function gets called when the window gets closed, it releases the laptop's camera and makes sure the Qt window closes right.
    def closeEvent(self, event):
        self.cap.release()
        super().closeEvent(event)




#main function, gets called when the python application gets ran.
if __name__=='__main__':
   #creates a new Qapplication.
    app = QApplication(sys.argv)
    window = WebcamApp() #gets the wnidow of the webcam app.
    window.show() #shows the window.
    sys.exit(app.exec_()) #exits at the end.



