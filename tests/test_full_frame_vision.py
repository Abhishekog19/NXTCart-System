"""Full-frame matching, motion tolerance and real ROS callback wiring tests."""
import pickle
import tempfile
import time
import types
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
import test_system as fixtures
import test_ros_adapters as adapters
from nxtcart_vision.local_matcher import LocalMatcher, Result
from nxtcart_vision.motion import MotionDetector


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=fixtures.ROOT/'tests')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'db.pkl'
        self.a = np.zeros(1280, np.float32); self.a[0] = 1
        self.b = np.zeros(1280, np.float32); self.b[1] = 1
        self.good = np.zeros((40,80,3), np.uint8); self.good[:,:,1] = 255
        self.bad = np.zeros((40,80,3), np.uint8)
        self.embedder = types.SimpleNamespace(embed=lambda crop: self.a if crop[:,:,1].mean() > 200 else self.b)

    def matcher(self, data, **kwargs):
        self.path.write_bytes(pickle.dumps(data))
        return LocalMatcher('unused', self.path, embedder=self.embedder, **kwargs)

    def test_any_of_five_frames_may_approve_despite_blurred_wrong_views(self):
        matcher = self.matcher({'sku': [self.a]})
        result = matcher.verify('sku', [[self.bad], [self.bad], [self.good], [self.bad], [self.bad]])
        self.assertEqual(result.verdict, 'MATCH')
        self.assertAlmostEqual(result.score, 1.)

    def test_all_wrong_frames_reject(self):
        matcher = self.matcher({'sku': [self.a]})
        self.assertEqual(matcher.verify('sku', [[self.bad]]*3).verdict, 'MISMATCH')

    def test_existing_wrapped_database_and_reference_normalization(self):
        matcher = self.matcher({'backend':'onnx-mbv2-1280', 'dim':1280, 'products':{'sku':[self.a*9]}})
        self.assertEqual(matcher.verify('sku', [[self.good]]*3).verdict, 'MATCH')

    def test_color_and_size_metadata_are_used_when_present(self):
        matcher = self.matcher({'sku': {'embeddings':[self.a], 'expected_color':[255,0,0], 'expected_size':[80,40]}}, colour_threshold=.8)
        self.assertEqual(matcher.verify('sku', [[self.good]]*3).verdict, 'MISMATCH')
        matcher = self.matcher({'sku': {'embeddings':[self.a], 'expected_size':[10,500]}}, size_ratio_tolerance=2.)
        self.assertEqual(matcher.verify('sku', [[self.good]]*3).verdict, 'MISMATCH')

    def test_existing_colour_histogram_format_matches(self):
        from ml.verifier import colour_hist
        matcher = self.matcher({'backend':'onnx-mbv2-1280','products':{'sku':[self.a]},
            'colours':{'sku':[colour_hist(self.good)]},'colour_format':2})
        self.assertEqual(matcher.verify('sku', [[self.good]]*3).verdict, 'MATCH')
        self.assertEqual(matcher.verify('sku', [[self.bad],[self.good],[self.bad]]).verdict, 'MATCH')

    def test_unknown_sku_is_unavailable(self):
        self.assertEqual(self.matcher({'sku':[self.a]}).verify('missing', [[self.good]]*3).verdict, 'UNAVAILABLE')

    def test_wrong_dimension_nan_zero_and_backend_are_rejected(self):
        cases = [{'sku':[np.ones(1000)]}, {'sku':[np.full(1280,np.nan)]}, {'sku':[np.zeros(1280)]},
                 {'backend':'tflite-mbv2quant-1280','products':{'sku':[self.a]}}]
        for raw in cases:
            with self.subTest(raw_type=list(raw)), self.assertRaises(ValueError): self.matcher(raw)

    def test_catalogue_maps_barcode_to_reference_folder(self):
        catalog = Path(self.tmp.name)/'catalog.json'
        catalog.write_text('[{"sku":"instant_noodles","barcode":"001","name":"Instant noodles"}]')
        matcher = self.matcher({'instant_noodles':[self.a]}, catalog_path=str(catalog))
        self.assertEqual(matcher.resolve('001'), 'instant_noodles')
        self.assertEqual(matcher.resolve('', 'Instant noodles'), 'instant_noodles')

    def test_removal_classifies_database_and_rejects_ties(self):
        matcher = self.matcher({'a':[self.a], 'b':[self.b]})
        self.assertEqual(matcher.verify('', [[self.good]]*3).sku, 'a')
        matcher = self.matcher({'a':[self.a], 'b':[self.a]})
        self.assertNotEqual(matcher.verify('', [[self.good]]*3).verdict, 'MATCH')


class MotionTests(unittest.TestCase):
    def detector(self, mask):
        detector = MotionDetector(min_area=40, warmup_frames=1)
        detector.background = types.SimpleNamespace(apply=lambda frame, learningRate: mask.copy())
        return detector

    def test_multiple_contours_generate_candidates_without_error(self):
        mask = np.zeros((240,320), np.uint8)
        mask[20:90,20:90] = 255; mask[140:200,220:290] = 255
        frame = np.zeros((240,320,3),np.uint8)
        frame[20:90,20:90] = (0,0,255); frame[140:200,220:290] = (100,150,180)
        detector = self.detector(mask); crops = detector.detect(frame)
        self.assertEqual(len(detector.boxes), 2)
        self.assertEqual(len(crops), 3)  # both regions plus merged view

    def test_shadow_label_is_ignored(self):
        detector = self.detector(np.full((240,320),127,np.uint8))
        self.assertEqual(detector.detect(np.zeros((240,320,3),np.uint8)), [])

    def test_growing_or_off_center_object_has_no_merged_or_zone_gate(self):
        mask = np.zeros((240,320),np.uint8); mask[180:220,260:310] = 255
        detector = self.detector(mask)
        self.assertTrue(detector.detect(np.zeros((240,320,3),np.uint8)))
        mask[10:230,5:315] = 255
        self.assertTrue(detector.detect(np.zeros((240,320,3),np.uint8)))


class NodeTests(unittest.TestCase):
    def setUp(self):
        stubs = adapters.ros_stubs(); self.msgs = stubs['smart_cart_interfaces.msg']
        self.stub_patch = patch.dict('sys.modules', stubs); self.stub_patch.start(); self.addCleanup(self.stub_patch.stop)
        adapters.Node.overrides = {'cam_root':str(fixtures.ROOT/'pc'), 'min_samples':3, 'max_samples':3}
        self.matcher = types.SimpleNamespace(products={'sku_a':[]},
            resolve=lambda barcode,name='': 'sku_a' if barcode in ('001','sku_a') or name == '001' else None,
            verify=lambda sku,samples: Result('MATCH', sku or 'sku_a', .9, .8, 'matched'))
        with patch('nxtcart_vision.local_matcher.LocalMatcher', return_value=self.matcher):
            from nxtcart_vision.vision_verify_node import VisionNode, Capture
            self.node = VisionNode(); self.Capture = Capture
        self.addCleanup(self.node.destroy_node)
        self.crop = np.ones((30,40,3),np.uint8)
        self.node.detector = types.SimpleNamespace(ready=True, boxes=[], detect=lambda frame:[self.crop])

    def feed(self, index):
        msg = types.SimpleNamespace(frame=self.crop, header=types.SimpleNamespace(frame_id='cam',
            stamp=types.SimpleNamespace(sec=100, nanosec=index)))
        self.node.frame(msg)

    def test_scan_sends_three_frames_to_local_model_without_weight_topic(self):
        self.node.scan(self.msgs.ScannedItem(barcode='001', scan_id='scan-a'))
        for i in range(1,4):
            self.node.active.last_sample = -float('inf'); self.feed(i)
        future = self.node.jobs[('scan-a',1)][1]; future.result(timeout=2.)
        self.node.tick()
        result = self.node.pub.sent[-1]
        self.assertTrue(result.approved)
        self.assertEqual(result.scan_id,'scan-a')
        self.assertEqual(result.action,'item_placed')

    def test_repeated_camera_stamp_cannot_supply_second_sample(self):
        self.node.scan(self.msgs.ScannedItem(barcode='001', scan_id='scan-a'))
        self.feed(1); self.node.active.last_sample = -float('inf'); self.feed(1)
        self.assertEqual(len(self.node.active.samples),1)

    def test_partial_occlusion_does_not_cancel_collected_samples(self):
        self.node.scan(self.msgs.ScannedItem(barcode='001', scan_id='scan-a'))
        self.feed(1)
        self.node.detector.detect = lambda frame:[]; self.feed(2)
        self.assertIsNotNone(self.node.active)
        self.assertEqual(len(self.node.active.samples),1)

    def test_duplicate_scan_id_is_not_reprocessed(self):
        scan = self.msgs.ScannedItem(barcode='001', scan_id='scan-a')
        self.node.scan(scan); active = self.node.active; self.node.scan(scan)
        self.assertIs(active,self.node.active)

    def test_no_motion_expires_without_matching_or_waiting_for_weight(self):
        self.node.scan(self.msgs.ScannedItem(barcode='001', scan_id='scan-a'))
        self.node.active.opened -= 3.; self.node.tick()
        self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY')

    def test_unscanned_motion_emits_one_removal_candidate_per_episode(self):
        self.node.idle_armed=True
        for i in range(1,4):
            if self.node.active: self.node.active.last_sample=-float('inf')
            self.feed(i)
        key = next(iter(self.node.jobs)); self.node.jobs[key][1].result(timeout=2.); self.node.tick()
        self.assertEqual(self.node.pub.sent[-1].action,'item_removed')
        self.assertEqual(self.node.pub.sent[-1].name,'sku_a')
        self.assertEqual(self.node.pub.sent[-1].txn_id,'')
        self.feed(4); self.assertIsNone(self.node.active)

    def test_cancellation_suppresses_running_result(self):
        capture=self.Capture('scan-a','sku_a','001',time.monotonic())
        future=Future(); future.set_running_or_notify_cancel()
        self.node.jobs[('scan-a',1)]=(capture,future,time.monotonic(),False)
        self.node.request(self.msgs.VerificationRequest(txn_id='txn',scan_id='scan-a',attempt=1,action='cancel'))
        future.set_result(Result('MATCH','sku_a',.9,.8,'match')); self.node.tick()
        self.assertEqual(len(self.node.pub.sent),0)

    def test_late_completed_future_cannot_pass(self):
        capture=self.Capture('scan-a','sku_a','001',time.monotonic())
        future=Future(); future.set_result(Result('MATCH','sku_a',.9,.8,'match'))
        self.node.jobs[('scan-a',1)]=(capture,future,time.monotonic()-10.,False)
        self.node.tick(); self.assertFalse(self.node.pub.sent[-1].approved)

    def test_selected_removal_keeps_pi_transaction_identity(self):
        self.node.request(self.msgs.VerificationRequest(txn_id='txn',scan_id='scan-a',sku='sku_a',
            barcode='001',attempt=2,action='remove'))
        self.assertEqual(self.node.active.txn_id,'txn')
        self.assertEqual(self.node.active.attempt,2)
        self.assertEqual(self.node.active.action,'item_removed')


class PiScanBindingTests(unittest.TestCase):
    setUp = adapters.AdapterTests.setUp
    verified = adapters.AdapterTests.verified

    def test_new_scan_id_verdict_updates_pi_camera_gate_only(self):
        self.node.scan_cb(self.msgs.ScannedItem(barcode='001',scan_id='direct'))
        unit=self.node.ledger.units[0]
        self.node.vision_cb(self.msgs.VisionEvent(scan_id='direct',approved=True,barcode='001',
            attempt=1,action='item_placed',verdict='MATCH',name='001'))
        self.assertEqual(unit.camera_status,'PASS')
        self.assertFalse(self.node.ledger.checkout_allowed)

    def test_unrequested_removal_never_deletes_a_billed_unit(self):
        self.verified()
        self.node.vision_cb(self.msgs.VisionEvent(scan_id='removal-1',approved=True,
            action='item_removed',verdict='MATCH',name='sku_a'))
        self.assertEqual(len(self.node.ledger.units),1)
        self.assertFalse(self.node.ledger.checkout_allowed)

    def test_selected_removal_accepts_database_keyed_by_barcode(self):
        request = self.verified()
        self.node.remove_cb(types.SimpleNamespace(data=request.txn_id))
        self.node.weight_cb(self.msgs.WeightSample(stream_id='scale', seq=3,
            grams=0., stable=True, calibrated=True))
        self.node.vision_cb(self.msgs.VisionEvent(scan_id='scan-a', txn_id=request.txn_id,
            attempt=2, barcode='001', name='001', approved=True, action='item_removed', verdict='MATCH'))
        self.assertEqual(len(self.node.ledger.units),0)
