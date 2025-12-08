import sys
import requests
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer


# This class handles the main window for the ClientApp.
class ClientApp(QMainWindow):
    def __init__(self):
        super().__init__()  # Initializes the QMainWindow parent class.
        uic.loadUi('Client.ui', self)  # Loads the UI file created in Qt Designer.

        self.serverUrl = 'http://10.0.2.15:5000'  # The URL where the presenter's server is running.

        # Connects the buttons on the UI to their respective functions.
        self.IncrementButton.clicked.connect(self.IncrementCounter)
        self.DecrementButton.clicked.connect(self.DecrementCounter)


        # This section sets up a timer that runs in the background.
        # It calls the QueryCounter function every 500ms (0.5 seconds).
        # This keeps the client updated if the server resets the counter (like when a new presentation starts).
        self.pollTimer = QTimer()
        self.pollTimer.timeout.connect(self.QueryCounter)
        self.pollTimer.start(500)

        # Calls this once at startup to get the initial count immediately.
        self.QueryCounter()

    # This function is called when the "Increment" button is clicked.
    # It sends a request to the server to add 1 to the counter.
    def IncrementCounter(self):
        try:
            # Sends a POST request to the /increment route on the server.
            response = requests.post(f"{self.serverUrl}/increment")

            # checks if the server responds with "OK" (200), we update our label with the new count.
            if response.status_code == 200:
                data = response.json()  # Converts the JSON response to a dictionary.
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
        except Exception as e:
            # checks if something goes wrong
            print(f"Post Error: {e}")

    # This function is called when the "Decrement" button is clicked.
    # It works just like Increment, but calls the /decrement route instead.
    def DecrementCounter(self):
        try:
            response = requests.post(f"{self.serverUrl}/decrement")
            if response.status_code == 200:
                data = response.json()
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
        except Exception as e:
            print(f"Post Error: {e}")

    # This function is called automatically by the timer every 0.5 seconds.
    # gets the current ah counter from the server.
    def QueryCounter(self):
        try:
            # Sends a GET request to the /query route.
            response = requests.get(f"{self.serverUrl}/query")

            if response.status_code == 200:
                data = response.json()
                # Updates the label with the current count from the server.
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
        except Exception as e:

            pass


# This runs when you execute the script.
if __name__ == '__main__':
    app = QApplication(sys.argv)  # Creates the application instance.
    window = ClientApp()  # Creates the main window.
    window.show()  # Makes the window visible.
    sys.exit(app.exec_())  # Enters the main event loop and waits for the window to close.