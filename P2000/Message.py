from datetime import datetime

class Message:
    def __init__(self, message):
        self.rawMessage = message.strip()
        self.__stringParts = message.split('|')
        self.__isValid = True

        if (self.__stringParts[0] != 'FLEX'):
            self.__isValid = False
            return

        self.date = datetime.now()
        self.capcodes = []
        for capcode in self.__stringParts[4].split(' '):
            capcode = capcode[-7:]
            # Capcodes larger than 2000000 are usually monitoring groups so they can be ignores
            if int(capcode) > 2000000:
                continue

            self.capcodes.append(capcode)

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

    def isImportant(self):
        return 'GRIP' in self.message
