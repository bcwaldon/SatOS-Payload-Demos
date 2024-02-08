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

import logging
import math
import pathlib
import random
import tempfile

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


logger = logging.getLogger()


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


class WebTileImager:

    def __init__(self, zoom_level=12, swath_km=20):
        self.zoom_level = zoom_level
        self.swath_km = swath_km

    # Returns a random point from within a predefined region.
    def rand_point(self):
        return shapely.Point((
            float(random.randint(-124000, -120000))/1000.,
            float(random.randint(44000, 51000))/1000.,
        ))

    # Construct a bounding box around a provided point, using the
    # configured swath to determine width and height.
    def scene_bounds(self, point):
        lat_km2deg = 1 / 110.574
        lat_swath_deg = self.swath_km * lat_km2deg

        deg2rad = math.pi / 180
        lon_km2deg = 1 / (111.320 * math.cos(point.y * deg2rad))
        lon_swath_deg = self.swath_km * lon_km2deg

        x_bounds = (point.x - lon_swath_deg/2, point.x + lon_swath_deg/2)
        y_bounds = (point.y - lat_swath_deg/2, point.y + lat_swath_deg/2)

        return x_bounds, y_bounds

    def capture(self, point=None):
        bands = 3

        point = point or self.rand_point()

        logger.info(f"capturing imagery at coordinates: lat={point.y}, lon={point.x}")

        x_bounds, y_bounds = self.scene_bounds(point)

        tile_src = cartopy.io.img_tiles.GoogleTiles(style='satellite')
        bbox = cartopy.crs.GOOGLE_MERCATOR.transform_points(cartopy.crs.PlateCarree(), x=np.array(x_bounds), y=np.array(y_bounds))[:, :-1].flatten()
        geom = shapely.box(*bbox)

        # emulating SSO inclination - will use attitude information in future
        geom = shapely.affinity.rotate(geom, random.choice([-8, 8]))

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
