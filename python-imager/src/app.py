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
import functools
import json
import logging
import pathlib
import os
import signal
import sys
import time

from satos_payload_sdk import app_framework

import imager


logger = logging.getLogger()


class ImagerController:
    def __init__(self, imgr):
        self.imgr = imgr
        self.capture_count = 0

    def _parse_params(self, val):
        cfg = {}
        for part in val.split(' '):
            if part.startswith('delay'):
                cfg['delay'] = int(part[5:])
        return dict(cfg)

    def _capture_and_stage(self, ctx, capture_func):
        src = capture_func()
        src_last = pathlib.Path(src).name

        ts = int(datetime.datetime.now().timestamp())
        filename = f"{ts}-{src_last}"
        absdst = f"/opt/antaris/outbound/{filename}"

        with open(src, 'rb') as sf:
            with open(absdst, 'wb') as df:
                df.write(sf.read())

        self.capture_count += 1

        logger.info(f"captured image: file={filename}")

        ctx.client.stage_file_download(filename)

    def handle_capture_strip(self, ctx):
        tspan = ctx._handler._seq_deadline - time.time()
        logger.info("capturing strip image")
        time.sleep(tspan-2)
        capture_func = functools.partial(self.imgr.capture_strip, tspan)
        self._capture_and_stage(ctx, capture_func)

    def handle_capture_adhoc(self, ctx):
        self._capture_and_stage(ctx, self.imgr.capture_spot)

    def handle_capture_repeat(self, ctx):
        cfg = self._parse_params(ctx.params)
        delay_sec = cfg.get('delay', 5)

        while True:
            if ctx.stop_requested:
                logger.info("sequence handler stopping")
                return

            if ctx.deadline_reached:
                logger.info("sequence deadline reached")
                return

            self._capture_and_stage(ctx, self.imgr.capture_spot)

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

        logger.info(f"wrote diagnostics: file={dst}")

        ctx.client.stage_file_download(dst)


if __name__ == '__main__':
    DEBUG = os.environ.get('DEBUG')
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)

    typ = os.environ.get('IMAGER_TYPE', 'dir')
    params = json.loads(os.environ.get('IMAGER_PARAMS', '{}'))
    imgr = imager.new(typ, params)

    ctl = ImagerController(imgr)

    pa = app_framework.PayloadApplication()
    pa.mount_sequence("CaptureAdhoc", ctl.handle_capture_adhoc)
    pa.mount_sequence("CaptureSpot", ctl.handle_capture_adhoc)
    pa.mount_sequence("CaptureRepeat", ctl.handle_capture_repeat)
    pa.mount_sequence("CaptureStrip", ctl.handle_capture_strip)
    pa.mount_sequence("DumpDiagnostics", ctl.handle_dump_diagnostics)

    signal.signal(signal.SIGTERM, lambda x, y: pa.request_stop())
    signal.signal(signal.SIGINT, lambda x, y: pa.request_stop())

    try:
        pa.run()
    except Exception as exc:
        logger.exception("payload app failed")
        sys.exit(1)
