import unittest

import imager


class TestWebTileImager(unittest.TestCase):

    def test_capture_spot(self):
        imgr = imager.WebTileImager()
        import pdb; pdb.set_trace()
        imgr.capture_spot()

        imgr.started_at -= 880
        imgr.capture_spot()


    def test_capture_strip(self):
        imgr = imager.WebTileImager()
        imgr.capture_strip(30)
