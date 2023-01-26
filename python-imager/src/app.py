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
import json
import logging
import pathlib
import os
import sys
import time

import framework
import imager


class ImagerController:
    def __init__(self, imgr, logger):
        self.imgr = imgr
        self.logger = logger
        self.capture_count = 0

    def _parse_params(self, val):
        cfg = {}
        for part in val.split(' '):
            if part.startswith('delay'):
                cfg['delay'] = int(part[5:])
        return dict(cfg)

    def _capture_and_stage(self, ctx):
        src = self.imgr.capture()
        src_last = pathlib.Path(src).name

        dt = datetime.datetime.now().isoformat()
        dst = f"/opt/antaris/outbound/{dt}-{src_last}"

        with open(src, 'rb') as sf:
            with open(dst, 'wb') as df:
                df.write(sf.read())

        self.capture_count += 1

        self.logger.info(f"captured image: file={dst}")

        ctx.client.stage_file_download(dst)

    # Capture a single image and stage for download.
    def handle_capture_adhoc(self, ctx):
        self._capture_and_stage(ctx)

    def handle_capture_repeat(self, ctx):
        cfg = self._parse_params(ctx.params)
        delay_sec = cfg.get('delay', 5)

        while True:
            if ctx.is_stopping():
                self.logger.info("sequence handler stopping")
                return

            if ctx.deadline_reached():
                self.logger.info("sequence deadline reached")
                return

            self._capture_and_stage(ctx)

            time.sleep(delay_sec)


    def handle_dump_diagnostics(self, ctx):
        dt = datetime.datetime.now().isoformat()
        ret_loc = ctx.client.get_current_location()

        diag = {
            'created_at': dt,
            'state': 'OK',
            'location': {
                'lat': ret_loc.latitude,
                'lng': ret_loc.longitude,
                'alt': ret_loc.altitude,
            },
            'capture_count': self.capture_count,
        }

        dst = f"/opt/antaris/outbound/{dt}-diag.json"
        with open(dst, 'w') as df:
            df.write(json.dumps(diag))

        self.logger.info(f"wrote diagnostics: file={dst}")

        ctx.client.stage_file_download(dst)


if __name__ == '__main__':
    DEBUG = os.environ.get('DEBUG')
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)
    logger = logging.getLogger()

    typ = os.environ.get('IMAGER_TYPE', 'dir')
    params = json.loads(os.environ.get('IMAGER_PARAMS', '{}'))
    imgr = imager.new(typ, params)

    ctl = ImagerController(imgr, logger)

    pa = framework.PayloadApplication(logger)
    #NOTE(bcwaldon): sequence names currently hardcoded per pc-sim
    pa.mount("CaptureAdhoc", ctl.handle_capture_adhoc)
    pa.mount("CaptureRepeat", ctl.handle_capture_repeat)
    pa.mount("DumpDiagnostics", ctl.handle_dump_diagnostics)

    try:
        pa.run()
    except Exception as exc:
        logger.exception("payload app failed")
        sys.exit(1)
