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


def new():
    return LocalDirectoryImager("/opt/antaris/python-imager/samples")


class LocalDirectoryImager:

    def __init__(self, directory):
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
