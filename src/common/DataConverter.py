# -*- coding: utf-8 -*-
import binascii, struct

class DataConverter:
    formatCharacter = {
        'int32_t' : 'i',
        'int' : 'i',
        'signed int' : 'i',

        'fxp32_t' : 'i', # fixed point integer as Q16.16
        'fxp16_t' : 'h', # fixed point integer as Q10.6

        'uint32_t' : 'I',
        'uint' : 'I',
        'unsigned int' : 'I',

        'int8_t' : 'b',
        'char' : 'b',
        'signed char' : 'b',

        'uint8_t' : 'B',
        'uchar' : 'B',
        'unsigned char' : 'B',

        'int16_t' : 'h',
        'short' : 'h',
        'signed short' : 'h',
        'short int' : 'h',
        'signed short int' : 'h',

        'uint16_t' : 'H',
        'ushort' : 'H',
        'unsigned short' : 'H',
        'short unsigned int' : 'H',

        'float' : 'f',

        'double' : 'd',
    }

    def __init__(self, bigEndian=True, encoding='none'):
        self.setBigEndian(bigEndian)

        for typeName in self.formatCharacter.keys():
            if typeName.find(' ') == -1:
                setattr(self, typeName, lambda binString, decode=False, typeName=typeName: self.fromString(binString, typeName, decode))
                setattr(self, '%sToString' % typeName, lambda value, encode=False, typeName=typeName: self.toString(value, typeName, encode))

        self.hexEncode = binascii.hexlify
        self.hexDecode = binascii.unhexlify
        if encoding == 'hex':
            self.encode = binascii.hexlify
            self.decode = binascii.unhexlify
        elif encoding == 'base64':
            self.encode = lambda (binString): binascii.b2a_base64(binString)[:-1] # strip the trailing newline
            self.decode = binascii.a2b_base64
        elif encoding == 'none':
            self.encode = lambda (binString): binString # do nothing
            self.decode = lambda (binString): binString # do nothing
        else:
            print 'dataConvertion: unknown encoding!'

    def setLittleEndian(self, littleEndian=True):
        self.setBigEndian(not littleEndian)

    def setBigEndian(self, bigEndian=True):
        if bigEndian:
            self.endianCharacter = '>'
        else:
            self.endianCharacter = '<'

    def getByteSize(self, typeName):
        return struct.calcsize(self.formatCharacter.get(typeName, 'i'))

    def fromString(self, binString, typeName=None, decode=False):
        if decode:
            binString = self.decode(binString)
        if not typeName: # default to int
            typeName = 'int'
        elif typeName[-1] == '*': # treat pointers as unsigned int
            typeName = 'uint'
        typeName = typeName.split('[')[0] # remove array size information
        try:
            result = struct.unpack_from(self.endianCharacter + self.formatCharacter.get(typeName, 'i'), binString)[0]
        except:
            return None
        if typeName == 'fxp32_t':
            result = float(result) / (1 << 16)
        elif typeName == 'fxp16_t':
            result = float(result) / (1 << 6)
        return result

    def toString(self, value, typeName=None, encode=False):
        if typeName == None: # default to the type that of the python variable
            typeName = type(value)
        elif typeName[-1] == '*': # treat pointers as unsigned int
            typeName = 'uint'
        typeName = typeName.split('[')[0] # remove array size information
        if typeName == 'fxp32_t':
            value = int(round(value * (1 << 16)))
        elif typeName == 'fxp16_t':
            value = int(round(value * (1 << 6)))
        return self.structToString(self.formatCharacter.get(typeName, 'i'), [value], encode)

    def structToString(self, structFormatString, valueList, encode=False):
        string = struct.pack(self.endianCharacter + structFormatString, *valueList)
        if encode:
            string = self.encode(string)
        return string

    def structFromString(self, structFormatString, binString, decode=False):
        if decode:
            binString = self.decode(binString)
        valueList = struct.unpack_from(self.endianCharacter + structFormatString, binString)
        return valueList

if __name__ == '__main__':
    converter = DataConverter()
    value = -23
    string = converter.toString(value, 'char', True)
    print '%d = %s = %d' % (value, string, converter.fromString(string, 'char', True))

    value = 42
    string = converter.charToString(value, True)
    print '%d = %s = %d' % (value, string, converter.char(string, True))

    for typeName in ['uint8_t', 'short', 'fxp32_t']:
        print 'sizeof(%s) = %d' % (typeName, converter.getByteSize(typeName))
