import sys
import requests
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
# this class handles the GUI window.
class ClientApp(QMainWindow):
    def __init__(self):
        super().__init__() #super constructor

        uic.loadUi('Client.ui',self) #loads GUI

        self.serverUrl = 'http://10.0.2.15:5000' #the server URL that the program is going to be looking at.
        #All of the buttons being connected to functions.
        self.IncrementButton.clicked.connect(self.IncrementCounter)
        self.DecrementButton.clicked.connect(self.DecrementCounter)
        self.QueryButton.clicked.connect(self.QueryCounter)
        self.UpdateButton.clicked.connect(self.SetColor)
    #here are all of the functions that are connected to said button's clicked event.

    #this function when called attempts to post to the  said URL/incrment, when someething is posted here
    #the server will detect it and increase the counter.
    def IncrementCounter(self):
        try:
            requests.post(f"{self.serverUrl}/increment") #trying to post to the serverURL/increment site.
        except Exception as e: #stores exception if error.
            self.CounterLabel.setText("Error") #if not, then change label to error.
            print(e)
    #does the same thing as the function above, but has uses /decrement instead of /increment and also decreases the
    #counter instead of increases it.
    def DecrementCounter(self):
        try:
            requests.post(f"{self.serverUrl}/decrement") #trying to post to the said URL with extension
        except Exception as e:
            self.CounterLabel.setText("Error")
            print(e)
    #This function uses the GET request to get information that is on the /query extension.
    def QueryCounter(self):
        try:
            response = requests.get(f"{self.serverUrl}/query") #stores the response from the GET request.
            if response.status_code == 200:
                data = response.json() #converts the data from json to a dictionary.

                self.CounterLabel.setText(f"Counter: {data.get('counter')}") #sets the label to what is in the counter dictionary.
            else:
                self.CounterLabel.setText("Error")
        except Exception as e:
            self.CounterLabel.setText("Error")
#this function gets the color that is inside of the text box and changes the background
#color of what is on the server.
    def SetColor(self):

        newColor = self.ColorTextBox.text() #gets the text that is inside of the text box.
        if not newColor:
            return

        try:
            payload = {'color': newColor} #puts it into a dictionary formate.
            requests.post(f"{self.serverUrl}/color", json=payload) #posts the dictionary in json format.
        except Exception as e:
            print(e)


if __name__ == '__main__':
    app = QApplication(sys.argv) #sets the application to app
    window = ClientApp() #defines the window
    window.show() #shows the window
    sys.exit(app.exec_()) #exits when the window is closed.


