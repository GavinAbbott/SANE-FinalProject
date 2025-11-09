import sys
import requests
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow

class ClientApp(QMainWindow):
    def __init__(self):
        super().__init__()

        uic.loadUi('Client.ui',self)

        self.serverUrl = 'http://10.0.2.15:5000' #look at this lien later

        self.IncrementButton.clicked.connect(self.IncrementCounter)
        self.DecrementButton.clicked.connect(self.DecrementCounter)
        self.QueryButton.clicked.connect(self.QueryCounter)
        self.UpdateButton.clicked.connect(self.SetColor)

    def IncrementCounter(self):
        try:
            requests.post(f"{self.serverUrl}/increment")
        except Exception as e:
            self.CounterLabel.setText("Error")
            print(e)

    def DecrementCounter(self):
        try:
            requests.post(f"{self.serverUrl}/decrement")
        except Exception as e:
            self.CounterLabel.setText("Error")
            print(e)

    def QueryCounter(self):
        try:
            response = requests.get(f"{self.serverUrl}/query")
            if response.status_code == 200:
                data = response.json()

                self.CounterLabel.setText(f"Counter: {data.get('counter')}")
            else:
                self.CounterLabel.setText("Error")
        except Exception as e:
            self.CounterLabel.setText("Error")

    def SetColor(self):

        newColor = self.ColorTextBox.text()
        if not newColor:
            return

        try:
            payload = {'color': newColor}
            requests.post(f"{self.serverUrl}/color", json=payload)
        except Exception as e:
            print(e)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ClientApp()
    window.show()
    sys.exit(app.exec_())


