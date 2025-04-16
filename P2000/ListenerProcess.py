from typing import *
import subprocess
from P2000.Message import Message

class ListenerProcess(object):
    def __init__(self):
        self.__callbacks = []

    def subscribe(self, callbackFunction: Callable):
        self.__callbacks.append(callbackFunction)

    def startProcess(self):
        rtlfm = subprocess.Popen(
            ['rtl_fm', '-f', '169.65M', '-M', 'fm', '-s', '22050', '-p', '83', '-g', '30'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )
        multimon = subprocess.Popen(
            ['multimon-ng', '-a', 'FLEX', '-t', 'raw', '/dev/stdin'],
            stdin=rtlfm.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        for line in multimon.stdout:
            lineStr = line.decode('utf-8')
            message = Message(lineStr)

            if message.isValidMessage() == False:
                continue

            for callback in self.__callbacks:
                callback(message)