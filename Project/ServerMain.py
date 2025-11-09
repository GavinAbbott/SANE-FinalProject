import sys
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from flask import Flask, jsonify, request


appState = {'counter': 10, 'color': 'ff0055'}

flaskApp = Flask(__name__)

class ServerSignals(QThread):
    updateCounter = pyqtSignal(int)
    updateColor = pyqtSignal(object)

serverSignals = ServerSignals()

@flaskApp.route('/query', methods=['GET'])
def getCounter():
    return jsonify({'counter': appState['counter']})

@flaskApp.route('/increment',methods=['POST'])
def IncrementCounter():
    appState['counter'] += 1
    serverSignals.updateCounter.emit(appState['counter'])
    return jsonify({'success': True, 'counter': appState['counter']})
@flaskApp.route('/decrement', methods=['POST'])
def decrementCounter():
    appState['counter'] -= 1
    serverSignals.updateCounter.emit(appState['counter'])
    return jsonify({'success':True,'counter':appState['counter']})
@flaskApp.route('/query-color',methods=['GET'])
def getColor():
    return jsonify({'color': appState['color']})

@flaskApp.route('/color',methods=['POST'])
def setColor():
    data = request.get_json()
    if data and 'color' in data:
        newColor = str(data['color']).strip().lstrip('#')
        print(f"DEBUG: Received data on server: {newColor}")

        appState['color'] = newColor
        serverSignals.updateColor.emit(newColor)
        return jsonify({'success':True,'color':newColor})
    return jsonify({'success': False, 'error': 'Invalid request'}), 400

class ServerThread(QThread):
    def run(self):
        flaskApp.run(host = '10.0.2.15', port=5000, debug=False) #check this line later


class ServerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        uic.loadUi('Server.ui',self)

        self.serverThread = ServerThread()
        self.serverThread.start()

        self.IncrementButton.clicked.connect(self.GuiIncrement)
        self.DecrementButton.clicked.connect(self.GuiDecrement)
        self.ColorText.returnPressed.connect(self.GuiColorChange)


        serverSignals.updateCounter.connect(self.updateCounterLabel)
        serverSignals.updateColor.connect(self.updateBackgroundColor)

        self.updateCounterLabel(appState['counter'])
        self.updateBackgroundColor(appState['color'])

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
    def updateCounterLabel(self, newValue):
        self.CounterLabel.setText(f"{newValue}")

    @pyqtSlot(object)
    def updateBackgroundColor(self, newColorHex):

        self.CounterLabel.setStyleSheet(f"background-color: #{newColorHex}; color: black;")

    def closeEvent(self, event):
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ServerApp()
    window.show()
    sys.exit(app.exec_())








