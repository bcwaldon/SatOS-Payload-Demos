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

import json
import logging
import math
import pathlib
import random
import tempfile
import time

import cartopy.crs
import cartopy.io.img_tiles
import cv2
import PIL
import numpy as np
import rasterio.control
import rasterio.crs
import rasterio.transform
import rasterio.io
import rasterio.mask
import shapely

parent_dir = str(pathlib.Path(__file__).parent.resolve())
track_filename = parent_dir + '/track.json'

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO)


def new(typ, params):
    if typ == "dir":
        return LocalDirectoryImager(**params)
    elif typ == "opencv":
        return OpenCVImager(**params)
    elif typ == "webtile":
        return WebTileImager(**params)
    else:
        raise ValueError("unrecognized imager type")


class LocalDirectoryImager:

    def __init__(self, directory="/opt/antaris/app/samples"):
        self.directory = directory

    def _sample(self):
        return random.choice(list(pathlib.Path(self.directory).glob('*')))

    def capture_spot(self):
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

    def capture_spot(self):
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


class WebTileImager:

    EPOCH=1712138400
    ALT=460
    INC=98
    RAAN=0
    TA=340
    TSPAN=7200

    def __init__(self, zoom_level=12, swath_km=20):
        self.zoom_level = zoom_level
        self.swath_km = swath_km
        self.started_at = time.time()

        with open(track_filename) as f:
            self.track = json.loads(f.read())

    def _track(self, epoch, tspan):
        end_epoch = epoch + tspan

        idxs = []
        for i, ts in enumerate(self.track['timeseries']):
            if ts < epoch:
                continue
            if ts > end_epoch:
                break

            idxs.append(i)

        lla_track = self.track['lla_track']
        if len(idxs) == 1:
            coords = [lla_track[idxs[0]]]
        else:
            coords = lla_track[idxs[0]:idxs[-1]+1]

        points = [shapely.Point((c[1], c[0])) for c in coords]
        return points

    def _epoch(self, now):
        elapsed = now - self.started_at
        return self.EPOCH + elapsed

    def position(self, now):
        cur_epoch = self._epoch(now)

        points = self._track(cur_epoch, tspan=20) # assumes 10sec time step in points
        if len(points) < 2:
            raise ValueError("failed generating track data for position")

        cur_heading_north = points[1].y > points[0].y

        return points[0], cur_heading_north

    def track_segment(self, now, tspan):
        cur_epoch = self._epoch(now)
        points = self._track(cur_epoch, tspan=tspan)
        return points

    def _capture_image(self, geom):
        bands = 3

        tile_src = cartopy.io.img_tiles.GoogleTiles(style='satellite')
        dat, extent, _ = tile_src.image_for_domain(geom, self.zoom_level)

        # pixels are in reverse order in X-axis, so must flip
        dat = np.flip(dat, axis=0)

        px_height = dat.shape[0]
        px_width = dat.shape[1]
        px_bands = dat.shape[2]

        x_min, x_max, y_min, y_max = extent

        crs = rasterio.crs.CRS.from_string("EPSG:3857")
        transform = rasterio.transform.from_gcps([
            rasterio.control.GroundControlPoint(row=0, col=0, x=x_min, y=y_max),
            rasterio.control.GroundControlPoint(row=0, col=px_width, x=x_max, y=y_max),
            rasterio.control.GroundControlPoint(row=px_height, col=0, x=x_min, y=y_min),
            rasterio.control.GroundControlPoint(row=px_height, col=px_width, x=x_max, y=y_min),
        ])

        with rasterio.io.MemoryFile() as memfile:
            kwargs = dict(
               driver='GTiff',
               height=px_height,
               width=px_width,
               count=bands,
               nodata=None,
               dtype='uint8',
               crs=crs,
               transform=transform,
            )

            with memfile.open(**kwargs) as dataset:
                for i in range(bands):
                    dataset.write_band(i+1, dat[:,:,i])

                clipped, _ = rasterio.mask.mask(dataset, [geom], crop=True)

                stacked = np.dstack([clipped[i,:,:] for i in range(bands)])

                tf = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.png')
                tf.close()

                img = PIL.Image.fromarray(stacked, mode="RGB")
                img.save(tf.name)

                return tf.name

    def _calc_poly(self, points):
        tpoints = cartopy.crs.GOOGLE_MERCATOR.transform_points(cartopy.crs.PlateCarree(), x=np.array([p.x for p in points]), y=np.array([p.y for p in points]))[:, :-1]

        if len(tpoints) == 1:
            geom = shapely.Point([tpoints[0]])
        else:
            geom = shapely.LineString(tpoints)

        poly = shapely.buffer(geom, self.swath_km*1000/2, cap_style='square')
        return poly

    def capture_spot(self):
        point, north = self.position(time.time())
        poly = self._calc_poly([point])

        # emulating SSO inclination - will use attitude information in future
        poly = shapely.affinity.rotate(poly, 15 if north else -15)

        img = self._capture_image(poly)

        logger.info(f"captured spot image: coords=[{point.y}, {point.x}]")

        return img

    def capture_strip(self, deadline, loc):
        logger.info(f"capturing strip image: deadline={deadline} loc={loc}")

        now = time.time()
        tspan = deadline - now
        if tspan > 60:
            logger.info(f"limiting tspan to 60sec")
            tspan = 60

        points = self.track_segment(now, tspan)
        poly = self._calc_poly(points)
        img = self._capture_image(poly)

        if len(points) > 1:
            logger.debug(f"captured strip image: start=[{points[0].y},{points[0].x}] end=[{points[-1].y}, {points[-1].x}]")
        else:
            logger.debug(f"captured small strip image: point=[{points[0].y},{points[0].x}]")

        return img


if __name__ == '__main__':
    import requests

    req = {
        "oe": {
            "altitude": WebTileImager.ALT,
            "inclination": WebTileImager.INC,
            "RAAN": WebTileImager.RAAN,
            "TA": WebTileImager.TA,
        },
        "epoch": WebTileImager.EPOCH,
        "tspan": WebTileImager.TSPAN,
    }

    resp = requests.post("http://delta:8080/orbit/all_points", json=req)
    with open(track_filename, 'w') as f:
        f.write(resp.text)

    logger.info("updated track file")
