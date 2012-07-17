#!/usr/bin/python
# -*- coding: utf-8 -*-

import serial

from PyQt4.QtCore import QThread, QMutex, pyqtSignal as Signal

from SerialProtocol import SerialProtocol

class SerialThread(QThread, SerialProtocol):
    logMessage = Signal(int, str)
    serialConnectionError = Signal()
    servoPing = Signal(int)
    servoData = Signal(int, int, object)
    packetSent = Signal(object)
    packetReceived = Signal(object)
    minServoId = 0
    maxServoId = 25

    def __init__(self, parent):
        QThread.__init__(self)
        SerialProtocol.__init__(self)
        self.parent = parent
        self.running = False
        self.serialPort = serial.Serial()
        self.serialTimeout = 0.1
        self.mutex = QMutex(QMutex.Recursive)
        self.nextPacketIsAServoAnswerFromId = -1
        self.lastReqeustPacket = {}


    def __del__(self):
        self.closeSerialPort()


    def log(self, level, message):
        self.logMessage.emit(level, message)


    def openSerialPort(self, serialPortNameOrNumber, serialBaudrate):
        try:
            self.serialPort.port = str(serialPortNameOrNumber)
            self.serialPort.baudrate = serialBaudrate
            self.serialPort.timeout = self.serialTimeout
            self.serialPort.open()
        except serial.serialutil.SerialException, e:
            self.log(0, 'Error opening %s (Maybe it is already in use):\n%s' % (self.serialPort.name, e))
            self.serialConnectionError.emit()
        else:
            self.log(1, 'Connected to serial port %s with %d baud' % (self.serialPort.portstr, self.serialPort.baudrate))


    def closeSerialPort(self):
        # stop the reading thread before closing the serial port
        if self.running:
            self.running = False
            self.log(3, 'Waiting for the serial thread...')
            self.wait()
        if self.serialPort.isOpen():
            self.log(1, 'Closing the serial port %s' % self.serialPort.portstr)
            self.serialPort.close()


    def scanForServosSlow(self):
        for servoId in range(self.minServoId, self.maxServoId):
            self.sendPacket(servoId, 'PING', [])


    def pingServos(self, servoIdList):
        servoIdList = list(servoIdList)
        for servoId in servoIdList:
            self.sendPacket(servoId, 'PING', [])


    def readAllServoData(self, servoIdList):
        self.readServoData(servoIdList, 0, self.memoryInfo['memorySize'])


    def readServoData(self, servoIdList, memoryAddress, length):
        servoIdList = list(servoIdList)
        for servoId in servoIdList:
            self.log(7, 'Reading data from servo id %d ...' % servoId)
            self.sendPacket(servoId, 'READ', [memoryAddress, length])


    def writeServoData(self, servoIdList, memoryAddress, memoryData):
        servoIdList = list(servoIdList)
        memoryDataList = list(memoryData)
        for servoId in servoIdList:
            self.log(7, 'Writing data to servo id %d ...' % servoId)
            self.sendPacket(servoId, 'WRITE', [memoryAddress, ] + memoryDataList)


    def resetServo(self, servoIdList):
        servoIdList = list(servoIdList)
        for servoId in servoIdList:
            self.log(1, 'Resetting servo id %d ...' % servoId)
            self.sendPacket(servoId, 'RESET', [])

    def run(self):
        self.running = True
        try:
            while self.running:
                self.receivePacket()
        except:
            self.running = False


    def receivePacket(self):
        receivedBytes = []
        self.mutex.lock()
        while True:
            if not self.serialPort.isOpen():
                self.mutex.unlock()
                break
            char = self.serialPort.read(1)
            if char == '':
                self.log(7, 'reveicePacket timed out after waiting for %0.3f seconds' % self.serialTimeout)
                self.mutex.unlock()
                receivedBytes = []
                break

            receivedBytes.append(ord(char))

            while len(receivedBytes) >= 2 and receivedBytes[:2] != [0xff, 0xff]: # packet has to start with two 0xff
                self.log(6, 'discarding byte: %02x (packet has to start with ff ff)' % (receivedBytes[0]))
                receivedBytes.pop(0)

            if len(receivedBytes) == 3 and receivedBytes[2] == 0xff: # id can't be 0xff
                self.log(6, 'discarding byte: %02x (invalid id: %d)' % (receivedBytes[0], receivedBytes[2]))
                receivedBytes.pop(0)

            elif len(receivedBytes) >= 4 and receivedBytes[3] < 2: # length can't be smaler than 2
                self.log(6, 'discarding byte: %02x (packet length to small: %d)' % (receivedBytes[0], receivedBytes[3]))
                receivedBytes.pop(0)

            elif len(receivedBytes) >= 6 and len(receivedBytes) == 4 + receivedBytes[3]: # only if we have the full packet
                formatString = '%38s ' + '%02x ' * len(receivedBytes)
                self.log(5, formatString % (('received hex',) + tuple(receivedBytes)))
                self.evaluatePacket(receivedBytes)
                self.mutex.unlock()
                self.packetReceived.emit(receivedBytes)
                break

        return receivedBytes # return after evaluating the received packet


    def sendPacket(self, servoId, instruction, data):
        self.sendData(self.makePacket(servoId, instruction, data))

    def sendData(self, packetString):
        if not self.serialPort.isOpen():
            return
        if type(packetString) is not str:
            packetString = ''.join(packetString)
        packetBytes = []
        for char in packetString:
            packetBytes.append(ord(char))
        formatString = '%38s ' + '%02x ' * len(packetBytes)
        self.mutex.lock()
        self.log(6, formatString % (('sending hex',) + tuple(packetBytes)))
        self.evaluatePacket(packetBytes, sending=True)
        self.serialPort.flushInput() # purge input buffer
        self.serialPort.write(packetString)
#        self.serialPort.flush()
        self.mutex.unlock()
        self.packetSent.emit(packetBytes)
        self.receivePacket()


    def evaluatePacket(self, packetBytes, sending=False):
        servoId, instruction, packetData, packetChecksum, realChecksum = self.parsePacket(packetBytes)
        if servoId == None:
            self.log(0, 'Packet not parsable')
            return

        formatString = 'DATA: ' + '%02x ' * len(packetData)
        dataString = formatString % tuple(packetData)

        if (packetChecksum == realChecksum):
            checkSumErrorString = ''
        else:
            checkSumErrorString = 'CKS ERR: %02x!=%02x' % (packetChecksum, realChecksum)

        instructionName = self.instructionName.get(instruction, '? 0x%02x ?' % instruction)
        addressName = ''
        addressOffset = 0
        if instructionName in ['READ', 'WRITE', 'REG_WRITE']:
            try:
                addressOffset = packetData[0]
                addressName = self.memoryInfo[addressOffset]['name']
            except:
                addressName = 'UnknownAddress'
        reqeustPacket = {'servoId' : servoId, 'instructionName' : instructionName, 'addressOffset' : addressOffset, 'dataString' : dataString}

        if sending or (servoId != self.nextPacketIsAServoAnswerFromId and self.nextPacketIsAServoAnswerFromId != self.broadcastId):
            # this is a request packet from the controller

            self.log(4, 'Request Id %3d %9s %-18s %s %s' % (servoId, instructionName, addressName, dataString, checkSumErrorString))

            self.lastReqeustPacket = reqeustPacket
            self.nextPacketIsAServoAnswerFromId = servoId

        else:

            # this is an answer packet from a servo
            errorCode = instruction
            self.log(3, 'Answer  Id %3d Error: %02x %-18s %s %s' % (servoId, errorCode, '', dataString, checkSumErrorString))

            if (packetChecksum == realChecksum):
                instructionName = self.lastReqeustPacket.get('instructionName')
                if instructionName == 'PING':
                    self.log(2, 'Found servo with id %d' % servoId)
                    self.servoPing.emit(servoId)

                elif instructionName in ['READ', 'WRITE', 'REG_WRITE']:
                    self.servoData.emit(self.lastReqeustPacket.get('servoId'), self.lastReqeustPacket.get('addressOffset'), packetData)
