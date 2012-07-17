import sys, os
from PyQt4.QtCore import QObject, pyqtSlot as Slot

class DataLogger(QObject):
    dataKeys = {}
    dataNames = []
    dataValues = []
    dataFormat = '%f '
    fileName = 'data.log'
    fileHandle = None
    logging = False
    formatString = ''

    def __init__(self):
        self.filePath = os.path.abspath(os.path.realpath(os.path.dirname(sys.argv[0])))

    def addField(self, dataId, dataName):
        if self.logging or self.dataKeys.has_key(dataId):
            return
        self.dataKeys[dataId] = len(self.dataNames)
        self.dataNames.append(dataName)
        self.dataValues.append(None)

    def removeAllFields(self):
        self.toggleLogging(False)
        self.dataKeys = {}
        self.dataNames = []
        self.dataValues = []

    def logValue(self, dataId, dataValue):
        # log data to file
        if self.logging and self.dataKeys.has_key(dataId):
            self.dataValues[self.dataKeys[dataId]] = dataValue
            self.logDataCount += 1
            # after receiving a complete data set, write it into the file
            if self.logDataCount == len(self.dataNames):
                self.fileHandle.write(self.formatString % tuple(self.dataValues))
                self.logDataCount = 0

    @Slot(str)
    def changeLogFileName(self, fileName):
        self.fileName = str(fileName)

    @Slot(bool)
    def toggleLogging(self, enabled):
        if enabled:
            self.fileHandle = open(os.path.join(self.filePath, self.fileName), 'a')
            self.fileHandle.write(('# ' + '%s ' * len(self.dataNames) + '\n') % tuple(self.dataNames))
            self.formatString = self.dataFormat * len(self.dataNames) + '\n'
            self.logDataCount = 0
            self.logging = True
        else:
            self.logging = False
            if self.fileHandle:
                self.fileHandle.close()
