"""Rotation, foreground merges and calibrated view boundaries."""
import unittest
import cv2
import numpy as np
import test_system as fixtures
from ml.detector import Detection
from ml.frame_source import FrameMeta
from ml.item_follower import ItemFollower, FollowStatus


def silhouette(width, height, angle=0):
    mask = np.zeros((480, 640), dtype=np.uint8)
    corners = cv2.boxPoints(((160., 200.), (float(width), float(height)), float(angle)))
    cv2.fillConvexPoly(mask, np.rint(corners).astype(np.int32), 255)
    x, y, w, h = cv2.boundingRect(mask)
    return Detection((x, y, w, h), mask[y:y+h, x:x+w].copy())


class ForegroundGeometryTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.random.default_rng(8).integers(0, 256, (480, 640, 3), dtype=np.uint8)
        self.follower = ItemFollower((640, 480))

    def test_rotation_does_not_turn_empty_box_corners_into_a_merge(self):
        initial, rotated = silhouette(80, 160), silhouette(80, 160, 45)
        self.assertGreater(rotated.area / initial.area, 1.35)
        self.follower.update([initial], self.frame, FrameMeta(1, 1.))
        status = self.follower.update([rotated], self.frame, FrameMeta(2, 1.067))
        self.assertNotIn(status, FollowStatus.BROKEN)
        self.assertLess(self.follower.area_ratio, 1.05)
        self.assertEqual(self.follower.observed_seq, 2)

    def test_actual_foreground_growth_still_rejects_hand_or_object_merge(self):
        self.follower.update([silhouette(80, 160)], self.frame, FrameMeta(1, 1.))
        status = self.follower.update([silhouette(120, 200)], self.frame, FrameMeta(2, 1.067))
        self.assertEqual(status, FollowStatus.MERGED)
        self.assertIn('foreground area grew', self.follower.failure_reason)
        self.assertIsNone(self.follower.current_crop)

    def test_missing_mask_cannot_switch_geometry_units_after_lock(self):
        initial = silhouette(80, 160)
        self.follower.update([initial], self.frame, FrameMeta(1, 1.))
        status = self.follower.update([Detection(initial.bbox)], self.frame, FrameMeta(2, 1.067))
        self.assertEqual(status, FollowStatus.LOST)

    def test_box_only_detectors_keep_the_merge_guard(self):
        self.follower.update([Detection((80, 100, 80, 80))], self.frame, FrameMeta(1, 1.))
        status = self.follower.update([Detection((60, 80, 160, 160))], self.frame, FrameMeta(2, 1.067))
        self.assertEqual(status, FollowStatus.MERGED)

    def test_invalid_merge_configuration_rejected(self):
        for value in (0., 1., float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ItemFollower((640, 480), merge_area_ratio=value)
