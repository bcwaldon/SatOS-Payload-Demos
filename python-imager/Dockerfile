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

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y wget python3 python3-pip python3-opencv

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install grpcio grpcio-tools opencv-python

RUN mkdir -p /opt/antaris/python-imager

ENV SDK_VERSION=1.1.1

WORKDIR /opt/antaris
RUN wget --content-disposition https://github.com/antaris-inc/SatOS-Payload-SDK/archive/refs/tags/v$SDK_VERSION.tar.gz
RUN ls -lh . && tar -xzvf SatOS-Payload-SDK-$SDK_VERSION.tar.gz

ADD samples /opt/antaris/python-imager/samples
ADD src /opt/antaris/python-imager/src
ADD entrypoint.sh /opt/antaris/python-imager/entrypoint.sh

ENV PYTHONPATH=/opt/antaris/python-imager/src:/opt/antaris/SatOS-Payload-SDK-$SDK_VERSION/lib/python:/opt/antaris/SatOS-Payload-SDK-$SDK_VERSION/lib/python/gen
CMD /opt/antaris/python-imager/entrypoint.sh
