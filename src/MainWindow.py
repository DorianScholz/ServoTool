#! /usr/bin/python
# -*- coding: utf-8 -*-
import os, glob, sys

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
BASE_PATH = os.path.abspath(os.path.join(SCRIPT_PATH, '..'))

from PyQt4 import uic
from PyQt4.QtGui import QMainWindow, QTableWidgetItem, QMenu, QIcon
from PyQt4.QtCore import QByteArray, QSettings, QSize, QTimer, Qt, QPoint, QVariant, pyqtSignal as Signal, pyqtSlot as Slot

from common.LogView import LogView
from common.Configuration import Configuration
from common.DataConverter import DataConverter

(MainWindowClass, MainWindowBaseClass) = uic.loadUiType(os.path.join(BASE_PATH, 'res', 'MainWindow.ui'))

class MainWindow(QMainWindow, MainWindowClass):
    serialConnectionOpen = Signal(str, int)
    serialConnectionClose = Signal()
    serialConnectionStartListening = Signal()
    serialConnectionPing = Signal(list)
    serialConnectionScan = Signal()
    serialConnectionScanSlow = Signal()
    serialConnectionReadAllData = Signal(list)
    serialConnectionReadData = Signal(list, int, int)
    serialConnectionWriteData = Signal(list, int, list)
    serialConnectionSendData = Signal(list)
    serialConnectionSendCustomPacket = Signal(int, str, list)

    def __init__(self, serialProtocol, parent=None):
        QMainWindow.__init__(self)

        # setup member variables
        self.serialProtocol = serialProtocol
        self.servos = {}
        self.columns = {}
        self.updating = False
        self.listenOnly = False
        self.timerDataRequest = QTimer(self)
        self.timerDataRequest.timeout.connect(self.timerDataRequest_timeout)

        # setup ui
        self.setupUi(self)
        self.buttonDataLog.setVisible(False)
        self.setWindowIcon(QIcon(os.path.join(BASE_PATH, 'res', 'SerialTool.png')))
        self.comboProtocolName.addItems(self.serialProtocol.availableProtocolNames)
        self.restoreGuiSettings()

        # open configuration file
        pathToScript = os.path.abspath(os.path.realpath(os.path.dirname(sys.argv[0])))
        nameOfScript = os.path.basename(sys.argv[0])
        self.configuration = Configuration(os.path.join(pathToScript, '%s.conf' % nameOfScript))

        self.converter = DataConverter(bigEndian=False)

        # restore data from configuration file
        self.restoreData()

        # init log view
        self.logView = LogView(self, self.textLogView)
        self.spinLogLevel.valueChanged.connect(self.logView.logLevelChanged)
        self.logView.logLevelChanged.emit(self.spinLogLevel.value()) # emit signal manually to set initial value

        # init data plot
        self.spinDataPlotInterval.valueChanged.connect(self.dataPlotIntervalChanged)
        self.buttonDataPlotClear.clicked.connect(self.dataPlotClear)
        self.buttonDataPlotPause.toggled.connect(self.dataPlotTogglePause)
        self.buttonDataPlotOsciMode.toggled.connect(self.dataPlot.toggleOscilloscopeMode)

        self.subscribedData = {}
        self.initTable()


    def initTable(self):
        # stop the update timer
        self.timerDataRequest.stop()

        # init servo memory data table
        self.tableServoData.clear()
        self.tableServoData.setColumnCount(1)
        self.tableServoData.setHorizontalHeaderItem(0, QTableWidgetItem('Parameter'))
        self.tableServoData.setRowCount(len(self.serialProtocol.memoryInfo['fieldNames']))
        rowNumber = 0
        for fieldName in self.serialProtocol.memoryInfo['fieldNames']:
            fieldInfo = self.serialProtocol.memoryInfo[fieldName]
            nameItem = QTableWidgetItem(fieldInfo['name'])
            if fieldInfo['writable']:
                nameItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            else:
                nameItem.setFlags(Qt.ItemFlag())
            self.tableServoData.setItem(rowNumber, 0, nameItem)
            self.tableServoData.resizeRowToContents(rowNumber)
            self.tableServoData.setRowHeight(rowNumber, self.tableServoData.rowHeight(rowNumber) - 7)
            rowNumber += 1
        self.tableServoData.resizeColumnToContents(0)

        # restart the update timer
        self.timerDataRequest.start(20)


    def closeEvent(self, event):
        self.saveGuiSettings()
        self.storeData()


    def storeData(self):
        # save baudrate combo
        baudrateList = []
        for i in range(self.comboSerialBaudrate.count()):
            baudrateList.append(int(self.comboSerialBaudrate.itemText(i)))
        baudrate = int(self.comboSerialBaudrate.currentText())

        baudrateList.sort()
        self.configuration.set('baudrateList', baudrateList)
        self.configuration.set('baudrate', baudrate)

        # save serial port combo
        portNameList = []
        for i in range(self.comboSerialPort.count()):
            portNameList.append(str(self.comboSerialPort.itemText(i)))

        portName = str(self.comboSerialPort.currentText())

        self.configuration.set('portNameList_%s' % os.name, portNameList)
        self.configuration.set('portName_%s' % os.name, portName)

        protocolName = str(self.comboProtocolName.currentText())
        self.configuration.set('protocolName', protocolName)


    def restoreData(self):
        # init baudrate combo
        baudrateList = self.configuration.get('baudrateList', [57600, 500000, 1000000])
        baudrate = self.configuration.get('baudrate', baudrateList[0])

        if not baudrate in baudrateList:
            baudrateList.append(baudrate)
            baudrateList.sort()

        currentIndex = baudrateList.index(baudrate)
        self.comboSerialBaudrate.addItems(map(str, baudrateList))
        self.comboSerialBaudrate.setCurrentIndex(currentIndex)

        # init serial port combo
        portNameList = self.configuration.get('portNameList_%s' % os.name, ['/dev/ttyUSB0'])
        if os.name == 'posix':
            portNameList = list(set(portNameList + glob.glob('/dev/ttyUSB*')))
        portName = self.configuration.get('portName_%s' % os.name, portNameList[0])
        portNameList.sort()

        self.comboSerialPort.addItems(portNameList)

        if portName in portNameList:
            self.comboSerialPort.setCurrentIndex(portNameList.index(portName))
        elif self.comboSerialPort.count > 0:
            self.comboSerialPort.setCurrentIndex(0)

        protocolName = self.configuration.get('protocolName', 'RobotisServo')
        self.comboProtocolName.setCurrentIndex(self.comboProtocolName.findText(protocolName))


    def saveGuiSettings(self):
        settings = QSettings('sim.informatik.tu-darmstadt.de', 'Servo Tool')
        settings.beginGroup('MainWindow')
        settings.setValue('state', QVariant(self.saveState()))
        settings.setValue('size', QVariant(self.size()))
        settings.setValue('pos', QVariant(self.pos()))
        settings.setValue('splitter', QVariant(self.splitter.saveState()))
        settings.setValue('splitter_2', QVariant(self.splitter_2.saveState()))
        settings.setValue('logLevel', QVariant(self.spinLogLevel.value()))
        settings.endGroup()


    def restoreGuiSettings(self):
        settings = QSettings('sim.informatik.tu-darmstadt.de', 'Servo Tool')
        settings.beginGroup('MainWindow')
        self.restoreState(settings.value('state', QVariant(QByteArray())).toByteArray())
        self.resize(settings.value('size', QVariant(QSize(800, 600))).toSize())
        self.move(settings.value('pos', QVariant(QPoint(200, 200))).toPoint())
        self.splitter.restoreState(settings.value('splitter', QVariant(QByteArray())).toByteArray())
        self.splitter_2.restoreState(settings.value('splitter_2', QVariant(QByteArray())).toByteArray())
        self.spinLogLevel.setValue(settings.value('logLevel', QVariant(3)).toInt()[0])
        settings.endGroup()


    def log(self, level, message):
        self.logView.logMessage.emit(level, message)


    def packetSent(self, packetBytes):
        # clear received data field, so unanswered packets don't show the last received packet
        self.textDataReceived.clear()
        formatString = '%02x ' * len(packetBytes)
        packetString = formatString % tuple(packetBytes)
        self.textDataSent.clear()
        self.textDataSent.appendPlainText(packetString)

    def packetReceived(self, packetBytes):
        formatString = '%02x ' * len(packetBytes)
        packetString = formatString % tuple(packetBytes)
        self.textDataReceived.clear()
        self.textDataReceived.appendPlainText(packetString)

    def servoChangedId(self, oldServoId, newServoId):
        self.comboServoId.setItemText(self.comboServoId.findText('%d' % oldServoId), '%d' % newServoId)
        columnNumber = self.servos[oldServoId]['columnNumber']
        self.tableServoData.setHorizontalHeaderItem(columnNumber, QTableWidgetItem('Id %d' % newServoId))
        self.tableServoData.resizeColumnToContents(columnNumber)
        self.servos[newServoId] = self.servos[oldServoId]
        self.servos[newServoId]['id'] = newServoId
        del self.servos[oldServoId]

    def servoDelete(self, servoId):
        self.comboServoId.removeItem(self.comboServoId.findText('%d' % servoId))
        columnNumber = self.servos[servoId]['columnNumber']
        # remove table column
        self.tableServoData.removeColumn(columnNumber)
        # remove servo mapping
        del self.servos[servoId]
        # correct other servo->column->servo mappings
        for servo in self.servos.values():
            if servo['columnNumber'] > columnNumber:
                del self.columns[servo['columnNumber']]
                servo['columnNumber'] -= 1
                self.columns[servo['columnNumber']] = servo

    def servoAdd(self, servoId):
        if self.servos.has_key(servoId):
            return
        self.comboServoId.addItem('%d' % servoId)
        columnNumber = self.tableServoData.columnCount()
        self.tableServoData.setColumnCount(columnNumber + 1)
        self.tableServoData.setHorizontalHeaderItem(columnNumber, QTableWidgetItem('Id %d' % servoId))
        self.tableServoData.resizeColumnToContents(columnNumber)
        self.servos[servoId] = {'id' : servoId, 'columnNumber': columnNumber}
        self.columns[columnNumber] = self.servos[servoId]
        self.labelNumServosFound.setText('%d found' % len(self.servos))


    def servoDataUpdate(self, servoId, addressOffset, servoData):
        if not self.servos.has_key(servoId):
            self.servoAdd(servoId)
        columnNumber = self.servos[servoId]['columnNumber']
        self.updating = True
        servoDataString = ('%c' * len(servoData)) % tuple(chr(c) for c in servoData)
        index = 0
        while index < len(servoDataString):
            fieldInfo = self.serialProtocol.memoryInfo[addressOffset + index]

            if fieldInfo['numElements'] != 1:
                self.log(0, 'ERROR: MainWindow.servoDataUpdate(): numElements != 1 -> Arrays are not supported, yet...')

            value = self.converter.fromString(servoDataString[index:], fieldInfo['type'])
            index += fieldInfo['size']

            # check if the item is being plotted
            subscribeId = '[%d].%s' % (servoId, fieldInfo['name'])
            if self.subscribedData.has_key(subscribeId):
                self.dataPlot.updateValue(subscribeId, float(value))

            # check for existing item, or create a new one
            dataItem = self.tableServoData.item(fieldInfo['index'], columnNumber)
            if not dataItem:
                dataItem = QTableWidgetItem()
                if fieldInfo['writable']:
                    dataItem.setFlags(Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsSelectable)
                else:
                    dataItem.setFlags(Qt.ItemFlag())
                self.tableServoData.setItem(fieldInfo['index'], columnNumber, dataItem)

            if type(value) == float:
                valueString = ('%.7f' % value).rstrip('0')
            else:
                valueString = str(value)
            dataItem.setText(valueString) # update item text
            dataItem.setToolTip(fieldInfo['makeToolTip'](value)) # update item tool tip

        self.tableServoData.resizeColumnToContents(columnNumber)
        self.updating = False


    def serialConnectionError(self):
        if self.buttonSerialConnect.isChecked():
            self.buttonSerialConnect.click()


    @Slot(str)
    def on_comboProtocolName_currentIndexChanged(self, text):
        self.serialProtocol.setProtocol(str(text))
        self.comboCustomCommand.clear()
        self.comboCustomCommand.addItems(self.serialProtocol.instructionName.values())
        servoIdList = self.servos.keys()
        self.servos = {}
        self.columns = {}
        self.initTable()
        for servoId in servoIdList:
            self.servoAdd(servoId)


    def enableButtons(self, enable):
        self.buttonServoScan.setEnabled(enable)
        self.buttonServoReadAll.setEnabled(enable)
        self.buttonServoRead.setEnabled(enable)
        self.buttonServoPing.setEnabled(enable)
        self.buttonCustomPacketSend.setEnabled(enable)


    @Slot(bool)
    def on_buttonSerialConnect_toggled(self, checked):
        self.comboSerialPort.setEnabled(not checked)
        self.comboSerialBaudrate.setEnabled(not checked)
        self.checkListenOnly.setEnabled(not checked)
        if checked:
            self.listenOnly = self.checkListenOnly.isChecked()
            self.enableButtons(not self.listenOnly)
            portName = str(self.comboSerialPort.currentText()).strip()
            if self.comboSerialPort.findText(portName) < 0:
                self.comboSerialPort.addItem(portName)
            self.serialConnectionOpen.emit(portName, int(self.comboSerialBaudrate.currentText()))
            if self.listenOnly:
                self.serialConnectionStartListening.emit()

        else:
            self.enableButtons(True)
            self.listenOnly = False
            self.dataPlotClear()
            self.servos = {}
            self.columns = {}
            self.tableServoData.setColumnCount(1)
            self.serialConnectionClose.emit()


    @Slot()
    def on_buttonServoScan_clicked(self):
        if not self.buttonSerialConnect.isChecked():
            self.buttonSerialConnect.click()
        self.servos = {}
        self.columns = {}
        self.tableServoData.setColumnCount(1)
        self.serialConnectionScan.emit()

    @Slot()
    def on_buttonServoScanSlow_clicked(self):
        if not self.buttonSerialConnect.isChecked():
            self.buttonSerialConnect.click()
        self.servos = {}
        self.columns = {}
        self.tableServoData.setColumnCount(1)
        self.serialConnectionScanSlow.emit()

    @Slot()
    def on_buttonServoReadAll_clicked(self):
        if not self.servos:
            self.on_buttonServoScan_clicked()
        self.serialConnectionReadAllData.emit(self.servos.keys())

    def getServoIdFrom_comboServoId(self):
        servoIdString = str(self.comboServoId.currentText()).strip()
        if len(servoIdString) == 0:
            self.log(0, 'Please enter a servo id.')
            return None
        try:
            servoId = int(servoIdString)
        except Exception, e:
            self.log(0, 'Error: %s' % e)
            return None
        return servoId

    @Slot()
    def on_buttonServoRead_clicked(self):
        if not self.buttonSerialConnect.isChecked():
            self.buttonSerialConnect.click()
        servoId = self.getServoIdFrom_comboServoId()
        if servoId is not None:
            self.serialConnectionReadAllData.emit([servoId])

    @Slot()
    def on_buttonServoPing_clicked(self):
        if not self.buttonSerialConnect.isChecked():
            self.buttonSerialConnect.click()
        servoId = self.getServoIdFrom_comboServoId()
        if servoId is not None:
            self.serialConnectionPing.emit([servoId])

    @Slot(str)
    def on_comboCustomCommand_currentIndexChanged(self, text):
        command = str(text).strip()
        toolTip = 'Packet data in hex (i.e. 0a ff 1e)\nParameters: '
        toolTip += self.serialProtocol.instructionDescription.get(command, '[no description available]')
        self.comboCustomData.setToolTip(toolTip)

    @Slot()
    def on_buttonCustomPacketSend_clicked(self):
        if not self.buttonSerialConnect.isChecked():
            self.buttonSerialConnect.click()
        servoId = self.spinCustomId.value()
        command = str(self.comboCustomCommand.currentText()).strip()
        text = str(self.comboCustomData.currentText()).strip()

        try:
            hexString = str(text).split('#', 1)[0].replace(' ', '')
            binString = self.converter.hexDecode(hexString)
        except Exception, e:
            self.log(0, 'Could not parse command string! Please use hexadecimal notation.\n%s' % (e))
            return

        if self.comboCustomCommand.findText(str(command)) < 0:
            self.comboCustomCommand.addItem(str(command))

        if self.comboCustomData.findText(text) < 0:
            self.comboCustomData.addItem(text)

        dataList = list(binString)
        if servoId < 0:
            self.log(3, 'sending custom raw data: %s' % (repr(dataList)))
            self.serialConnectionSendData.emit(dataList)
        else:
            self.log(3, 'sending custom packet with payload: %s' % (repr(dataList)))
            self.serialConnectionSendCustomPacket.emit(servoId, command, dataList)

    # updated cell data on left click or the whole row when clicking on the first column
    @Slot(int, int)
    def on_tableServoData_cellClicked(self, row, column):
        if column >= 0:
            fieldName = self.serialProtocol.memoryInfo['fieldNames'][row]
            fieldInfo = self.serialProtocol.memoryInfo[fieldName]
            if column == 0:
                servoIdList = self.servos.keys()
                if len(servoIdList) == 0:
                    return
            else:
                servoIdList = [self.columns[column]['id']]
            self.log(3, 'reading from servo id(s) %s: %s [%d]: %d bytes' % (servoIdList, fieldName, fieldInfo['address'], fieldInfo['size']))
            self.serialConnectionReadData.emit(servoIdList, fieldInfo['address'], fieldInfo['size'])

    # subscribe to regular updates of cell data or the whole row when selecting the first column
    def handleAddToDataPlot(self, item):
        if item and item.column() >= 0:
            fieldName = self.serialProtocol.memoryInfo['fieldNames'][item.row()]
            fieldInfo = self.serialProtocol.memoryInfo[fieldName]
            if item.column() == 0:
                servoIdList = self.servos.keys()
            else:
                servoIdList = [self.columns[item.column()]['id']]
            self.log(3, 'subscribing for servo id(s) %s: %s [%d]: %d bytes' % (servoIdList, fieldName, fieldInfo['address'], fieldInfo['size']))
            for servoId in servoIdList:
                subscribeId = '[%d].%s' % (servoId, fieldName)
                self.subscribedData[subscribeId] = {
                    'servoId': servoId,
                    'address': fieldInfo['address'],
                    'size': fieldInfo['size']
                }
                self.dataPlot.addCurve(subscribeId, subscribeId)

    @Slot()
    def timerDataRequest_timeout(self):
        if self.listenOnly:
            return
        for dataRequest in self.subscribedData.values():
            self.log(8, 'requesting: %s' % (dataRequest))
            self.serialConnectionReadData.emit([dataRequest['servoId']], dataRequest['address'], dataRequest['size'])

    @Slot(int)
    def dataPlotIntervalChanged(self, interval):
        self.timerDataRequest.start(interval)

    @Slot()
    def dataPlotClear(self):
        self.subscribedData = {}
        self.dataPlot.removeAllCurves()

    @Slot(bool)
    def dataPlotTogglePause(self, pause):
        if pause:
            self.timerDataRequest.stop()
        else:
            self.timerDataRequest.start()

    @Slot(int, int)
    def on_tableServoData_cellChanged(self, row, column):
        if self.updating:
            return
        if self.listenOnly:
            self.log(0, 'Can not send data in "listenOnly" mode!')
            return
        item = self.tableServoData.item(row, column)
        if item and item.column() > 0:
            servoId = self.columns[item.column()]['id']
            value = eval(str(item.text()))
            fieldName = self.serialProtocol.memoryInfo['fieldNames'][item.row()]
            fieldInfo = self.serialProtocol.memoryInfo[fieldName]
            memoryDataList = list(self.converter.toString(value, fieldInfo['type']))
            if fieldName == 'servoId' and value in self.servos:
                self.log(0, 'Error: trying to set a duplicate servo id: %d' % (value))
            else:
                self.log(3, 'writing to servo id %d: %s [%d]: 0x%04x' % (servoId, fieldName, fieldInfo['address'], value))
                self.serialConnectionWriteData.emit([servoId], fieldInfo['address'], memoryDataList)
                if fieldName == 'servoId':
                    self.servoChangedId(servoId, value)
                    servoId = value
            self.serialConnectionReadData.emit([servoId], fieldInfo['address'], fieldInfo['size'])


    @Slot(QPoint)
    def on_tableServoData_customContextMenuRequested(self, pos):
        item = self.tableServoData.itemAt(pos)
        if not item or item.column() < 1:
            return
        menu = QMenu(self)
        actionCopyToAllServos = menu.addAction("Copy To All Servos")
        actionAddToDataPlot = menu.addAction("Plot Value")
        action = menu.exec_(self.tableServoData.mapToGlobal(pos))
        if action == actionCopyToAllServos:
            self.handleCopyToAllServos(item)
        elif action == actionAddToDataPlot:
            self.handleAddToDataPlot(item)


    def handleCopyToAllServos(self, srcItem):
        # on right clicks on any column but the first, copy the value from the clicked to all other columns
        if srcItem.column() > 0:
            srcText = srcItem.text()
            srcRow = srcItem.row()
            srcCol = srcItem.column()
            self.log(1, 'copying to all servos: %d, %d: %s' % (srcRow, srcCol, srcText))
            for destCol in range(1, self.tableServoData.columnCount()):
                if destCol != srcCol:
                    destItem = self.tableServoData.item(srcRow, destCol)
                    if destItem:
                        destItem.setText(srcText)


