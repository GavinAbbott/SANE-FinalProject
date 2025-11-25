import sys
import requests
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow


class ClientApp(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('Client.ui', self)

        self.serverUrl = 'http://10.0.2.15:5000'

        self.IncrementButton.clicked.connect(self.IncrementCounter)
        self.DecrementButton.clicked.connect(self.DecrementCounter)

    def IncrementCounter(self):
        try:
            response = requests.post(f"{self.serverUrl}/increment")
            if response.status_code == 200:
                data = response.json()
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
            else:
                self.CounterLabel.setText("Error")
        except Exception as e:
            self.CounterLabel.setText("Error")
            print(e)

    def DecrementCounter(self):
        try:
            response = requests.post(f"{self.serverUrl}/decrement")
            if response.status_code == 200:
                data = response.json()
                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
            else:
                self.CounterLabel.setText("Error")
        except Exception as e:
            self.CounterLabel.setText("Error")
            print(e)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientApp()
    window.show()
    sys.exit(app.exec_())