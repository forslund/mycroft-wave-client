# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.

import sys

from threading import Thread, Lock, Event

from os.path import exists
from mycroft.stt import STTFactory
from mycroft.configuration import ConfigurationManager
from mycroft.util import getLogger
from mycroft.messagebus.client.ws import WebsocketClient
from mycroft.messagebus.message import Message
import speech_recognition as sr
import time
from os import remove

authors = ["forslund", "jarbas"]

logger = getLogger("WavFileClient")
ws = None

config = ConfigurationManager.get()


def connect():
    ws.run_forever()


def read_wave_file(wave_file_path):
    '''
    reads the wave file at provided path and return the expected
    Audio format
    '''
    # use the audio file as the audio source
    r = sr.Recognizer()
    with sr.AudioFile(wave_file_path) as source:
        audio = r.record(source)
    return audio


class FileConsumer(Thread):
    def __init__(self, file_location='/tmp/mycroft_in.wav', emitter=None):
        super(FileConsumer, self).__init__()
        self.path = file_location
        self.stop_event = Event()
        self.stt = None
        self.emitter = emitter

    def run(self):
        logger.info("Creating SST interface")
        self.stt = STTFactory.create()
        self.emitter.on("stt.request", self.handle_external_request)
        while not self.stop_event.is_set():
            logger.info('Looping')
            if exists(self.path):
                audio = read_wave_file(self.path)
                text = self.stt.execute(audio).lower().strip()
                logger.info(text)
                remove(self.path)
            time.sleep(0.5)

    def handle_external_request(self, message):
        file = message.data.get("File")
        if self.stt is None:
            error = "STT initialization failure"
            self.emitter.emit(
                Message("stt.error", {"error": error}))
        elif not file:
            error = "No file provided for transcription"
            self.emitter.emit(
                Message("stt.error", {"error": error}))
        elif not exists(file):
            error = "Invalid file path provided for transcription"
            self.emitter.emit(
                Message("stt.error", {"error": error}))
        else:
            audio = read_wave_file(file)
            transcript = self.stt.execute(audio).lower().strip()
            self.emitter.emit(Message("stt.reply",
                                      {"transcription": transcript}))

    def stop(self):
        self.stop_event.set()


def main():
    global ws
    global config
    ws = WebsocketClient()
    config = ConfigurationManager.get()
    ConfigurationManager.init(ws)
    event_thread = Thread(target=connect)
    event_thread.setDaemon(True)
    event_thread.start()
    config = config.get("wav_client", {"path": "/tmp/mycroft_in.wav"})
    try:
        file_consumer = FileConsumer(file_location=config["path"], emitter=ws)
        file_consumer.start()
        while True:
            time.sleep(100)
    except KeyboardInterrupt, e:
        logger.exception(e)
        file_consumer.stop()
        file_consumer.join()
        sys.exit()


if __name__ == "__main__":
    main()
