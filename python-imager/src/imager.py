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

import pathlib
import random
import tempfile

import cv2


def new(typ, params):
    if typ == "dir":
        return LocalDirectoryImager(**params)
    elif typ == "opencv":
        return OpenCVImager(**params)
    else:
        raise ValueError("unrecognized imager type")


class LocalDirectoryImager:

    def __init__(self, directory="/opt/antaris/app/samples"):
        self.directory = directory

    def _sample(self):
        return random.choice(list(pathlib.Path(self.directory).glob('*')))

    def capture(self):
        src = self._sample()
        tf = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=src.suffix)
        with open(src, 'rb') as sf:
            tf.write(sf.read())
        tf.close()
        return tf.name


class OpenCVImager:

    def __init__(self, device_index=0, frame_width=640, frame_height=480):
        self.idx = device_index
        self.frame_width = frame_width
        self.frame_height = frame_height

    def capture(self):
        cap = cv2.VideoCapture(self.idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)

        ret, frame = cap.read()
        if not ret:
            raise Exception('failed to capture image')

        tf = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.jpeg')
        tf.close()

        cv2.imwrite(tf.name, frame)
        return tf.name
