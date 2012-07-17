# -*- coding: utf-8 -*-
from PyQt4.QtGui import QColor
from PyQt4.QtCore import QObject, pyqtSignal as Signal, pyqtSlot as Slot

class LogView(QObject):
    logMessage = Signal(int, str)
    logLevelChanged = Signal(int)

    darkColors = [
        QColor(128, 64, 0),
        QColor(0, 128, 0),
        QColor(0, 64, 128),
        QColor(0, 128, 128),
        QColor(128, 0, 128),
        QColor(128, 128, 0),
        QColor(128, 64, 0),
        QColor(0, 128, 64),
        QColor(64, 64, 128),
    ]

    brightColors = [
        QColor(255, 64, 0),
        QColor(0, 255, 0),
        QColor(0, 128, 255),
        QColor(0, 255, 255),
        QColor(255, 0, 255),
        QColor(255, 255, 0),
        QColor(255, 64, 0),
        QColor(0, 255, 64),
        QColor(64, 64, 255),
    ]

    textColor = darkColors

    def __init__(self, parent, textLogView):
        QObject.__init__(self)
        self.logLevel = 4
        self.textLogView = textLogView
        self.logLevelChanged.connect(self.on_logLevelChanged)
        self.logMessage.connect(self.on_appendMessageToLog)

    @Slot(int)
    def on_logLevelChanged(self, logLevel):
        self.logLevel = logLevel

    @Slot(int, str)
    def on_appendMessageToLog(self, logLevel, message):
        if logLevel <= self.logLevel:
            self.textLogView.setTextColor(self.textColor[logLevel])
            self.textLogView.append(str(message))
