#! /usr/bin/python
# -*- coding: utf-8 -*-
from common.DataConverter import DataConverter

class SerialProtocol:
    logLevel = 10
    serialTimeout = 0.030 # [sec]
    broadcastId = 0xfe

    def __init__(self, protocolName='RobotisServo'):
        global memoryFields
        self.setProtocol(protocolName)
        self.availableProtocolNames = memoryFields.keys()

    def log(self, level, message):
        if level < self.logLevel:
            print message

    def sendPacket(self):
        self.log(0, 'sendPacket is not implemented')

    def receivePacket(self):
        self.log(0, 'sendPacket is not implemented')

    def calulateChecksum(self, data):
        checksum = 0
        if type(data[0]) == int:
            for byte in data:
                checksum = (checksum + byte) & 0xff
        else:
            for char in data:
                checksum = (checksum + ord(char)) & 0xff
        checksum = (~checksum) & 0xff
        return checksum

    def scanForServos(self):
        self.log(2, 'Start scanning for servos...')
        self.sendPacket(self.broadcastId, 'PING', [])
        servoIdList = []
        failureCount = 0
        lastServoId = -1

        while (failureCount * (self.serialTimeout / 0.0012)) < (253 - lastServoId):

            packetServoId, _, _, _, _ = self.parsePacket(self.receivePacket())

            if packetServoId != None:
                servoIdList.append(packetServoId)
                failureCount = 0
                lastServoId = packetServoId
            else:
                failureCount += 1

        return servoIdList

    def parsePacket(self, packetBytes):
        if len(packetBytes) < 6:
            return (None, None, None, None, None)
        # skip the first two bytes, as they are just the packet start indicator 0xff 0xff
        servoId = packetBytes[2]
        #length = packetBytes[3]
        instruction = packetBytes[4]
        data = packetBytes[5:-1]
        checksum = packetBytes[-1]
        realChecksum = self.calulateChecksum(packetBytes[2:-1])
        return (servoId, instruction, data, checksum, realChecksum)

    def makePacket(self, servoId, instruction, data):
        try:
            instructionCode = int(instruction)
        except:
            instructionCode = self.instructionCode.get(str(instruction), None)
            if instructionCode == None:
                self.log(0, 'Unknown instruction "%s"' % instruction)
                return None
        packetString = '\xff\xff'
        packetString += chr(servoId)
        packetString += chr(1 + len(data) + 1)
        packetString += chr(instructionCode)
        for byte in data:
            if type(byte) == int:
                packetString += chr(byte)
            else:
                packetString += str(byte)
        packetString += chr(self.calulateChecksum(packetString[2:]))
        return packetString


    def allServosGetPosition(self, servos):
        data = [self.memoryInfo['PresentPositionL']['address'], 0x02]
        for servo in servos.values():
            self.sendPacket(servo.id, self.instructionCode['READ'], data)
            receivedString = self.serialPort.read(8)
            byteArray = []
            for char in receivedString:
                byteArray.append(ord(char))
            _, _, packetData, packetChecksumOK = self.parsePacket(byteArray)
            if packetChecksumOK:
                servo.presentPosition = (packetData[1] << 8) + packetData[0]

    def allServosSetPosition(self, servos):
        for servo in servos.values():
            position = servo.goalPosition
            data = [self.memoryInfo['GoalPositionL']['address'], position & 0xff, (position >> 8) & 0x03]
            self.sendPacket(servo.id, self.instructionCode['REG_WRITE'], data)
        self.sendPacket(self.broadcastId, self.instructionCode['ACTION'], [])

    def allServosSetTorque(self, servos, enabled):
        data = [self.memoryInfo['TorqueEnable']['address'], enabled]
        for servo in servos.values():
            self.sendPacket(servo.id, self.instructionCode['WRITE'], data)

    def setProtocol(self, protocolName):
        global memoryFields, instructionSets
        self.memoryFieldsKey = protocolName
        self.memoryInfo = {'fieldNames' : [], 'memorySize': 0}
        if protocolName not in memoryFields:
            self.log(0, 'Unknown memory structure "%s"' % protocolName)
            return
        index = 0
        address = 0
        converter = DataConverter()
        for memoryField in memoryFields[protocolName]:
            fieldBaseType = memoryField['type'].split(' ')[-1]
            arrayElements = fieldBaseType.split('[')
            if len(arrayElements) > 1:
                fieldBaseType = arrayElements[0]
                arraySize = int(arrayElements[1].split(']')[0])
            else:
                arraySize = 1

            typeSize = converter.getByteSize(fieldBaseType)
            fieldSize = typeSize * arraySize

            self.memoryInfo['fieldNames'].append(memoryField['name'])
            self.memoryInfo[address] = {
                'name'        : memoryField['name'],
                'size'        : fieldSize,
                'type'        : memoryField['type'].split('[')[0],
                'numElements' : arraySize,
                'writable'    : memoryField.get('writable', False),
                'address'     : address,
                'index'       : index,
                'makeToolTip' : memoryField.get('makeToolTip', repr),
            }
            self.memoryInfo[memoryField['name']] = self.memoryInfo[address]
            index += 1
            address += fieldSize

        self.memoryInfo['memorySize'] = address

        self.instructionName = {}
        self.instructionCode = {}
        self.instructionDescription = {}
        for instruction in instructionSets.get(protocolName, instructionSets['Default']):
            self.instructionName[instruction[0]] = instruction[1] # code to name
            self.instructionCode[instruction[1]] = instruction[0] # name to code
            self.instructionDescription[instruction[0]] = instruction[2] # code to description
            self.instructionDescription[instruction[1]] = instruction[2] # name to description


instructionSets = {
    'RobotisServo': [
        (0x01, 'PING', 'request a ping packet (broadcast: yes)'),
        (0x02, 'READ', 'memory address, length | returend values have little endian format (broadcast: no)'),
        (0x03, 'WRITE', 'memory address, N values | assigned values have little endian format (broadcast: yes)'),
        (0x04, 'REG_WRITE', 'memory address, N values | assigned values have little endian format (broadcast: yes)'),
        (0x05, 'ACTION', 'commit reg_write values to memory (broadcast: yes)'),
        (0x06, 'RESET', 'reset all servo settings including the servo id (broadcast: yes)'),
        (0x83, 'SYNC_WRITE', '(broadcast: yes)'),
        (249, 'GYRO', ''),
        (250, 'COUNT', ''),
        (252, 'START', ''),
        (253, 'STOP', ''),
    ],
    'DDServo': [
        (0x00, 'START BOOTLOADER', '0x01, 0x02, 0x03, 0x04 (broadcast: yes)'),
        (0x11, 'PING', 'optional red, green and blue signal color value (broadcast: yes)'),
        (0x12, 'READ', 'memory address, length | returend values have little endian format (broadcast: no)'),
        (0x13, 'WRITE', 'memory address, N values | assigned values have little endian format (broadcast: yes)'),
        (0x14, 'SET MOTOR POWER', 'motor power off (0), motor power on (1) (broadcast: yes)'),
        (0x15, 'SET LOGGING', 'logging off (0), logging on (1) (broadcast: yes)'),
        (0x16, 'SET CONTROL MODE', 'position control mode without trajectory (0), position control mode with trajectory (1), speed control mode without trajectory (2), speed control mode with trajectory (3), [torque control mode (4)], pulse width control mode (5) (broadcast: yes)'),
        (0x17, 'WRITE PENDING DATA', 'memory address and values | assigned values have little endian format (broadcast: yes)'),
        (0x18, 'TRIGGER PENDING DATA', '(broadcast: yes)'),
        (0x19, 'SYNCHRONIZED READ DATA', 'memory address, length, 1. servo id ... S. servo id or broadcast id | returned values have little endian format (broadcast: no)'),
        (0x1A, 'SYNCHRONIZED WRITE DATA', 'memory address, length, 1. servo id, N values ... S. servo id, N values | assigned values have little endian format (broadcast: yes)'),
        (0x1B, 'READ LOGGING DATA', '(broadcast: no)'),
        (0x1C, 'READ CHECKSUM', '(broadcast: no)'),
        (0x1D, 'SET POSITION OFFSET', '0x01, 0x02, 0x03, 0x04 optional position offset | assigned values have little endian format (broadcast: yes)'),
        (0x1E, 'REBOOT SERVO', '0x01, 0x02, 0x03, 0x04 (broadcast: yes)'),
        (0x1F, 'RESET ERRORS', '0x01, 0x02, 0x03, 0x04 (broadcast: yes)'),
        (0x20, 'RESET', '0x01, 0x02, 0x03, 0x04 (broadcast: yes)'),
    ],
}
instructionSets['Default'] = instructionSets['RobotisServo']


# define list of memory fields
memoryFields = {}
memoryFields['Common'] = [
    {'name': 'ModelNumber', 'type': 'signed short', 'writable': True},
    {'name': 'VersionofFirmware', 'type': 'unsigned char', 'writable': True},
    {'name': 'servoId', 'type': 'unsigned char', 'writable': True},
    {'name': 'BaudRateDivisor', 'type': 'unsigned char', 'writable': True},
    {'name': 'ReturnDelayTime', 'type': 'unsigned char', 'writable': True},
]

memoryFields['RobotisServo'] = memoryFields['Common'] + [
    {'name': 'CWAngleLimit', 'type': 'signed short', 'writable': True},
    {'name': 'CCWAngleLimit', 'type': 'signed short', 'writable': True},
    {'name': 'Reserved1', 'type': 'unsigned char'},
    {'name': 'HighestLimitTemperature', 'type': 'unsigned char', 'writable': True},
    {'name': 'LowestLimitVoltage', 'type': 'unsigned char', 'writable': True},
    {'name': 'HighestLimitVoltage', 'type': 'unsigned char', 'writable': True},
    {'name': 'MaxTorque', 'type': 'signed short', 'writable': True},
    {'name': 'StatusReturnLevel', 'type': 'unsigned char', 'writable': True},
    {'name': 'AlarmLED', 'type': 'unsigned char', 'writable': True},
    {'name': 'AlarmShutdown', 'type': 'unsigned char', 'writable': True},
    {'name': 'Reserved2', 'type': 'unsigned char'},
    {'name': 'DownCalibration', 'type': 'signed short'},
    {'name': 'UpCalibration', 'type': 'signed short'},
    {'name': 'TorqueEnable', 'type': 'unsigned char', 'writable': True},
    {'name': 'LED', 'type': 'unsigned char', 'writable': True},
    {'name': 'CWComplianceMargin', 'type': 'unsigned char', 'writable': True},
    {'name': 'CCWComplianceMargin', 'type': 'unsigned char', 'writable': True},
    {'name': 'CWComplianceSlope', 'type': 'unsigned char', 'writable': True},
    {'name': 'CCWComplianceSlope', 'type': 'unsigned char', 'writable': True},
    {'name': 'GoalPosition', 'type': 'signed short', 'writable': True},
    {'name': 'MovingSpeed', 'type': 'signed short', 'writable': True},
    {'name': 'TorqueLimit', 'type': 'signed short', 'writable': True},
    {'name': 'PresentPosition', 'type': 'signed short'},
    {'name': 'PresentSpeed', 'type': 'signed short'},
    {'name': 'PresentLoad', 'type': 'signed short'},
    {'name': 'PresentVoltage', 'type': 'unsigned char'},
    {'name': 'PresentTemperature', 'type': 'unsigned char'},
    {'name': 'RegisteredInstruction', 'type': 'unsigned char'},
    {'name': 'Reserved3', 'type': 'unsigned char'},
    {'name': 'Moving', 'type': 'unsigned char'},
    {'name': 'Lock', 'type': 'unsigned char', 'writable': True},
    {'name': 'Punch', 'type': 'signed short', 'writable': True},
]

memoryFields['AVRServo'] = memoryFields['RobotisServo'] + [
    {'name': 'ControllerProportionalFactor', 'type': 'signed short', 'writable': True},
    {'name': 'ControllerIntegralFactor', 'type': 'signed short', 'writable': True},
    {'name': 'ControllerDerivativeFactor', 'type': 'signed short', 'writable': True},
    {'name': 'ControlLoopTimeouts', 'type': 'signed short'},
    {'name': 'adcMeasuringsPerLoop', 'type': 'unsigned char'},
]

memoryFields['SPIConnector'] = memoryFields['Common'] + [
    {'name': 'reservedEEPROM', 'type': 'unsigned char[10]'},
    {'name': 'StatusReturnLevel', 'type': 'unsigned char', 'writable': True},
    {'name': 'reservedEEPROM2', 'type': 'unsigned char[7]'},
    {'name': 'positionRoll', 'type': 'signed int', 'writable': True},
    {'name': 'positionPitch', 'type': 'signed int', 'writable': True},
    {'name': 'positionYaw', 'type': 'signed int', 'writable': True},
    {'name': 'gyroRoll', 'type': 'signed short'},
    {'name': 'gyroPitch', 'type': 'signed short'},
    {'name': 'gyroYaw', 'type': 'signed short'},
    {'name': 'accelerometerX', 'type': 'signed short'},
    {'name': 'accelerometerY', 'type': 'signed short'},
    {'name': 'accelerometerZ', 'type': 'signed short'},
    {'name': 'gyroRollNew', 'type': 'unsigned char'},
    {'name': 'gyroPitchNew', 'type': 'unsigned char'},
    {'name': 'gyroYawNew', 'type': 'unsigned char'},
    {'name': 'accelerometerXNew', 'type': 'unsigned char'},
    {'name': 'accelerometerYNew', 'type': 'unsigned char'},
    {'name': 'accelerometerZNew', 'type': 'unsigned char'},
    {'name': 'numDataRead', 'type': 'unsigned char'},
    {'name': 'ControlLoopTimeouts', 'type': 'signed short'},
    {'name': 'command', 'type': 'unsigned char', 'writable': True},
    {'name': 'address', 'type': 'unsigned char', 'writable': True},
    {'name': 'value', 'type': 'signed short', 'writable': True},
]

ddFlagStrings = [
    'FLAG_MOTOR_POWER_ACTIVATED',
    'FLAG_LOGGING_ACTIVATED',
    'FLAG_CONTROL_MODE_LOW',
    'FLAG_CONTROL_MODE_HIGH',
    'FLAG_COMMUNICATION_RECEPTION_IN_PROGRESS',
    'FLAG_COMMUNICATION_TRANSMISSION_IN_PROGRESS',
    'FLAG_COMMUNICATION_BAUDRATE_UPDATE',
    'FLAG_COMMUNICATION_PROTOCOL_SYNCHRONIZED_READ_IN_PROGRESS',
    'FLAG_COMMUNICATION_COLOR_PING_REQUEST',
    'FLAG_COMMUNICATION_PENDING_DATA_REGISTERED',
    'FLAG_POSITION_SENSOR_DEACTIVATED',
    'FLAG_POSITION_SENSOR_ACTIVATED',
    'FLAG_TEMPERATURE_SENSOR_CALIBRATION',
    'FLAG_ANALOG_CONVERTER_INITIALIZATION',
    'FLAG_ANALOG_CONVERTER_ACTIVATED',
]

ddErrorStrings = [
    'ERROR_POSITION_LIMIT',
    'ERROR_TORQUE_LIMIT',
    'ERROR_CURRENT_LIMIT',
    'ERROR_VOLTAGE_LIMIT',
    'ERROR_MOTOR_TEMPERATURE_LIMIT',
    'ERROR_CONTROLLER_TEMPERATURE_LIMIT',
    'ERROR_PARAMETER_RANGE',
    'ERROR_CHECKSUM',
    'ERROR_INSTRUCTION',
    'ERROR_COMMUNICATION',
    'ERROR_ANALOG_CONVERTER',
    'ERROR_POSITION_SENSOR',
    'ERROR_EEPROM',
    'ERROR_TASK_MANAGEMENT',
    'ERROR_DATA_LOSS',
]

def toBinString(flags):
    return str(flags & 1) if flags <= 1 else toBinString(flags >> 1) + str(flags & 1)

def flagsToBool(flags):
    return (flags == 1,) if flags <= 1 else flagsToBool(flags >> 1) + (flags & 1 == 1,)

def getFlagsString(bits, strings):
    boolFlags = flagsToBool(bits)
    # prepend False values to reach same size as string list
    boolFlags = (False,) * (len(strings) - len(boolFlags)) + boolFlags
    return '\n'.join(['%5s: %s' % (flag, text) for flag, text in zip(boolFlags, strings)])

memoryFields['DDServo'] = [
    {'name': 'modelNumber', 'type': 'uint16_t', 'writable': True},
    {'name': 'firmwareVersion', 'type': 'uint16_t', 'writable': True},
    {'name': 'servoId', 'type': 'uint8_t', 'writable': True},
    {'name': 'statusReturnLevel', 'type': 'uint8_t', 'writable': True},
    {'name': 'statusReturnDelayTime', 'type': 'uint16_t', 'writable': True},
    {'name': 'baudrateDivider', 'type': 'uint16_t', 'writable': True},
    {'name': 'positionOffset', 'type': 'uint16_t', 'writable': True},
    {'name': 'positionLimitClockwise', 'type': 'fxp32_t', 'writable': True},
    {'name': 'positionLimitCounterclockwise', 'type': 'fxp32_t', 'writable': True},
    {'name': 'torqueLimit', 'type': 'fxp32_t', 'writable': True},
    {'name': 'currentLimit', 'type': 'fxp32_t', 'writable': True},
    {'name': 'voltageLimitLow', 'type': 'fxp16_t', 'writable': True},
    {'name': 'voltageLimitHigh', 'type': 'fxp16_t', 'writable': True},
    {'name': 'motorTemperatureLimit', 'type': 'fxp16_t', 'writable': True},
    {'name': 'controllerTemperatureLimit', 'type': 'fxp16_t', 'writable': True},
    {'name': 'controllerTemperatureOffset', 'type': 'fxp16_t', 'writable': True},
    {'name': 'statusSignal', 'type': 'uint16_t', 'writable': True},
    {'name': 'alarmSignal', 'type': 'uint16_t', 'writable': True},
    {'name': 'alarmShutdown', 'type': 'uint16_t', 'writable': True},
    {'name': 'skipZoneParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'feedForwardControlParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'proportionalPositionControlParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'integralPositionControlParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'derivativePositionControlParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'positionComplianceParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'proportionalSpeedControlParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'integralSpeedControlParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'derivativeSpeedControlParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'speedComplianceParameter', 'type': 'fxp32_t', 'writable': True},
    {'name': 'desiredPosition', 'type': 'fxp32_t', 'writable': True},
    {'name': 'desiredSpeed', 'type': 'fxp32_t', 'writable': True},
    {'name': 'desiredAcceleration', 'type': 'fxp32_t', 'writable': True},
    {'name': 'desiredPulseWidth', 'type': 'int16_t', 'writable': True},
    {'name': 'actualPulseWidth', 'type': 'int16_t'},
    {'name': 'actualPositionMeasurement', 'type': 'uint16_t'},
    {'name': 'actualPositionStatus', 'type': 'uint16_t'},
    {'name': 'actualSystemTime', 'type': 'uint32_t'},
    {'name': 'actualPosition', 'type': 'fxp32_t'},
    {'name': 'actualSpeed', 'type': 'fxp32_t'},
    {'name': 'actualTorque', 'type': 'fxp32_t'},
    {'name': 'actualCurrent', 'type': 'fxp32_t'},
    {'name': 'actualVoltage', 'type': 'fxp16_t'},
    {'name': 'actualMotorTemperature', 'type': 'fxp16_t'},
    {'name': 'actualControllerTemperature', 'type': 'fxp16_t'},
    {'name': 'flags', 'type': 'uint16_t', 'makeToolTip': lambda(value): getFlagsString(value, ddFlagStrings)},
    {'name': 'errors', 'type': 'uint16_t', 'makeToolTip': lambda(value): getFlagsString(value, ddErrorStrings)},
    {'name': 'checksum', 'type': 'uint16_t'},
]
