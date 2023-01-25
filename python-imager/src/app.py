# Copyright 2023 Antaris, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import logging
import pathlib
import os
import sys
import time

import framework
import imager


# Instantly "captures" an image and places it in the staged
# download directory.
class SequenceHandlerAlpha(framework.BaseSequenceHandler):
    sequence_id = "Sequence_A"

    def handle(self, params):
        ctl = imager.new()
        src = ctl.capture()
        src_last = pathlib.Path(src).name

        dt = datetime.datetime.now().isoformat()
        dst = f"/opt/antaris/outbound/{dt}-{src_last}"

        with open(src, 'rb') as sf:
            with open(dst, 'wb') as df:
                df.write(sf.read())

        self.logger.info(f"captured image: file={dst}")

        self.channel_client.stage_file_download(dst)


# Attempts to get current location from PC then wait until deadline before exiting.
# Not quite working with pc-sim.
class SequenceHandlerBravo(framework.BaseSequenceHandler):
    sequence_id = "Sequence_B"

    def handle(self, params):
        params = self.channel_client.get_current_location()
        loc = {"lat": params.latitude, "lng": params.longitude, "alt": params.altitude}

        self.logger.info("get_current_location succeeded: loc=%s" % loc)

        while True:
            if self.is_stopping():
                self.logger.info("sequence handler stopping")
                return

            if self.deadline_reached():
                self.logger.info("sequence deadline reached")
                return

            self.logger.info("sequence still running")

            time.sleep(3)



sequence_handlers = [
    SequenceHandlerAlpha,
    SequenceHandlerBravo
]


if __name__ == '__main__':
    DEBUG = os.environ.get('DEBUG')
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
    logger = logging.getLogger()

    pa = framework.PayloadApplication(sequence_handlers, logger)
    try:
        pa.run()
    except Exception as exc:
        logger.exception("payload app failed")
        sys.exit(1)
