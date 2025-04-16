from datetime import datetime

class Message:
    def __init__(self, message):
        self.__rawMessage = message
        self.__stringParts = message.split('|')
        self.__isValid = True

        if (self.__stringParts[0] != 'FLEX'):
            self.__isValid = False
            return

        self.date = datetime.now()
        self.capcodes = self.__stringParts[4]
        self.capcodeList = self.capcodes.split(' ')
        self.message = self.__stringParts[6].strip()

        try:
            self._date = datetime.strptime(self.__stringParts[1], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            self.__isValid = False
            return

        if (
            self.message.lower().startswith('test') or
            self.message.strip() == ''
        ):
            self.__isValid = False
            return

    def isValidMessage(self):
        return self.__isValid
