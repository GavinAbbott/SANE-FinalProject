import sys
import requests
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer


class ClientApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('Client.ui', self)

        self.serverUrl = 'http://10.0.2.15:5000'

        self.IncrementButton.clicked.connect(self.IncrementCounter)
        self.DecrementButton.clicked.connect(self.DecrementCounter)

        # --- POLLING TIMER ---
        # This timer checks the server status every 500ms (0.5 seconds)
        # This ensures that if the server resets the counter to 0,
        # the client will see it automatically.
        self.pollTimer = QTimer()
        self.pollTimer.timeout.connect(self.QueryCounter)
        self.pollTimer.start(500)

    def IncrementCounter(self):
        try:
            # We still update immediately on click for better responsiveness
            response = requests.post(f"{self.serverUrl}/increment")
            if response.status_code == 200:
                data = response.json()
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
        except Exception as e:
            print(e)

    def DecrementCounter(self):
        try:
            response = requests.post(f"{self.serverUrl}/decrement")
            if response.status_code == 200:
                data = response.json()
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
        except Exception as e:
            print(e)

    def QueryCounter(self):
        try:
            # This function runs in the background
            response = requests.get(f"{self.serverUrl}/query")
            if response.status_code == 200:
                data = response.json()
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
        except Exception as e:
            # We print errors to console but don't change the label to "Error"
            # to avoid flashing text if a single request fails.
            print(f"Polling Error: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientApp()
    window.show()
    sys.exit(app.exec_())