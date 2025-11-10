import sys
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from flask import Flask, jsonify, request

#dictionary that stores the counter data nad the color. doing this to bypass having to use global through every function.
appState = {'counter': 1, 'color': '000000'}
#creates a new flask application.
flaskApp = Flask(__name__)
#this class handles two threads that are created for updating the counter and the color. it inherits parts from the
#QThread class.
class ServerSignals(QThread):
    updateCounter = pyqtSignal(int)
    updateColor = pyqtSignal(object)

serverSignals = ServerSignals()

@flaskApp.route('/query', methods=['GET']) #creats a GET route that calls the function directly below it when requested.
def Query(): #this function returns the counter element in the appState dictionary.
    return jsonify({'counter': appState['counter'], 'color': appState['color']})

@flaskApp.route('/increment',methods=['POST']) #cretes a POST route that calls the function directly below it when requested.
#this function updates the counter element in the dictionary, then updates the label.
def IncrementCounter():
    appState['counter'] += 1 #updates counter element in dictionary.
    serverSignals.updateCounter.emit(appState['counter']) #sends signal to update counter label.
    return jsonify({'success': True, 'counter': appState['counter']}) #returns success to the post request.
@flaskApp.route('/decrement', methods=['POST']) #creates a POST route that calls the function directly below it when requested.
#this function decrements the counter element in the dictionary and also updates the counter label.
def decrementCounter():
    appState['counter'] -= 1 #decrements the counter element in the dictionary.
    serverSignals.updateCounter.emit(appState['counter']) # sends signal to update the counter label.
    return jsonify({'success':True,'counter':appState['counter']}) #returns success to the client.


@flaskApp.route('/color',methods=['POST']) #creates a post route that will call the function directly below when requested.
def setColor():
    data = request.get_json() #gets the data that was posted by the client.
    if data and 'color' in data: #makes sure that the dictionary in the data has color element.
        newColor = str(data['color']).strip().lstrip('#') #converts the data into string and removes # if added.

        appState['color'] = newColor #updates the dictionary to the color that the client sent.
        serverSignals.updateColor.emit(newColor) #updates the background color by calling the signal.
        return jsonify({'success':True,'color':newColor}) #returns success to the client
    return jsonify({'success': False, 'error': 'Invalid request'}), 400
#this class creats another thread that handles the flask web server so that this can run in the background.
class ServerThread(QThread):
    def run(self):
        flaskApp.run(host = '10.0.2.15', port=5000, debug=False) #check this line later

#this class handles the main window of the GUI.
class ServerApp(QMainWindow):
    def __init__(self):
        super().__init__() #super constructor. gets called when the class is first initialized.

        uic.loadUi('Server.ui',self) #loads the UI

        self.serverThread = ServerThread() #creates  the server thread class.
        self.serverThread.start()#starts the server thread.
        #here are all of the events that are connected to when the buttons are pressed.
        self.IncrementButton.clicked.connect(self.GuiIncrement)
        self.DecrementButton.clicked.connect(self.GuiDecrement)
        self.ColorText.returnPressed.connect(self.GuiColorChange)
        #^^ I only did it this way because I forgot to add a button for it and I was too lazy to go back and add a button :)

        #connects the two server signals to the respected functions.
        serverSignals.updateCounter.connect(self.updateCounterLabel)
        serverSignals.updateColor.connect(self.updateBackgroundColor)
#------- these 3 functions handle the buttons that are on the server gui ------------
    #this function simply increments the counter element in the dictionary and updates the counter label
    def GuiIncrement(self):
        appState['counter'] += 1 #updates the counter element in the dictionary.
        serverSignals.updateCounter.emit(appState['counter']) #updates the label
    #this function simply decrements the counter element in the dictionary and updates the counter label
    def GuiDecrement(self):
        appState['counter'] -= 1 #decrements the counter element in the dictionary.
        serverSignals.updateCounter.emit(appState['counter']) #sends signal to update the label.
    #this function changes the color of the gui. based off of what is in the text box on the server's gui.
    def GuiColorChange(self):
        newColor = self.ColorText.text().strip().lstrip('#') #gets the text from the text box, gets rid of the # if included.
        appState['color'] = newColor #sets the color element in the dictionary to the new color.
        serverSignals.updateColor.emit(newColor) #sends signal to update the background color.

        self.ColorText.clear()

    @pyqtSlot(int) #this defines the slot for the signal thread. calls the function directly below it.
    def updateCounterLabel(self, newValue): # this function simply changes the counter label to what is in the dictionary.
        self.CounterLabel.setText(f"{newValue}")

    @pyqtSlot(object) #creats another slot that is recieving an object.
    def updateBackgroundColor(self, newColorHex): #this function updates the background color to what is in the dictionary.

        self.CounterLabel.setStyleSheet(f"background-color: #{newColorHex}; color: black;")
        #The GUI basically has a really large label that acts like the background for the main portion of the ui.
        #so this command is basically changing the background color of that label, which gives the appearance of that the
        #backgound of the UI is changing.
    #makes sure to close when the close everything when the window is closed.
    def closeEvent(self, event):
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv) #defines the application.
    window = ServerApp()# defines the window.
    window.show() #shows the window
    sys.exit(app.exec_()) #exits when window is exited.








