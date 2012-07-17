#! /usr/bin/python
# -*- coding: utf-8 -*-

import sys

from PyQt4.QtGui import QApplication

from MainWindow import MainWindow
from SerialThread import SerialThread

if __name__ == '__main__':

    # try to import psyco for speed up
    try:
        import psyco
        # do full compilation since this is a fairly small program
        psyco.full()
    except:
        pass

    app = QApplication(sys.argv)

    # setup serial communication thread
    serialThread = SerialThread(app)

    # setup main window
    mainWindow = MainWindow(serialThread, parent=app)
    mainWindow.show()

    # connect signals
    serialThread.logMessage.connect(mainWindow.log)
    serialThread.serialConnectionError.connect(mainWindow.serialConnectionError)
    serialThread.servoPing.connect(mainWindow.servoAdd)
    serialThread.servoData.connect(mainWindow.servoDataUpdate)
    serialThread.packetSent.connect(mainWindow.packetSent)
    serialThread.packetReceived.connect(mainWindow.packetReceived)
    mainWindow.serialConnectionOpen.connect(serialThread.openSerialPort)
    mainWindow.serialConnectionClose.connect(serialThread.closeSerialPort)
    mainWindow.serialConnectionStartListening.connect(serialThread.start)
    mainWindow.serialConnectionPing.connect(serialThread.pingServos)
    mainWindow.serialConnectionScan.connect(serialThread.scanForServos)
    mainWindow.serialConnectionScanSlow.connect(serialThread.scanForServosSlow)
    mainWindow.serialConnectionReadAllData.connect(serialThread.readAllServoData)
    mainWindow.serialConnectionReadData.connect(serialThread.readServoData)
    mainWindow.serialConnectionWriteData.connect(serialThread.writeServoData)
    mainWindow.serialConnectionSendData.connect(serialThread.sendData)
    mainWindow.serialConnectionSendCustomPacket.connect(serialThread.sendPacket)

    # start main qt thread
    exitCode = app.exec_()

    sys.exit(exitCode)

