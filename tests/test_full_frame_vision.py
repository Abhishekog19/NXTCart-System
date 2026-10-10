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
        adapters.Node.overrides = {'cam_root':str(fixtures.ROOT/'pc')}
        self.matcher = types.SimpleNamespace(products={'sku_a':[]},
            resolve=lambda barcode,name='': 'sku_a' if barcode in ('001','sku_a') or name == '001' else None,
            verify=lambda sku,samples: Result('MATCH', sku, .9, .8, 'matched'))
        with patch('nxtcart_vision.local_matcher.LocalMatcher', return_value=self.matcher):
            from nxtcart_vision.vision_verify_node import VisionNode, Capture
            self.node = VisionNode(); self.Capture = Capture
        self.addCleanup(self.node.destroy_node)
        self.crop = np.ones((30,40,3),np.uint8)

    def message(self, **kwargs):
        values = dict(txn_id='txn', scan_id='scan-a', sku='sku_a', barcode='001', attempt=1, action='add')
        values.update(kwargs)
        return self.msgs.VerificationRequest(**values)

    def feed(self, index, generation='cam'):
        msg = types.SimpleNamespace(frame=self.crop, header=types.SimpleNamespace(frame_id=generation,
            stamp=types.SimpleNamespace(sec=99, nanosec=index)))
        self.node.frame(msg)

    def finish(self):
        for c,f,s,e in self.node.jobs.values(): f.result(timeout=2.)
        self.node.tick()

    def test_static_frames_do_not_infer_until_weight_settles(self):
        self.node.scan(self.msgs.ScannedItem(barcode='001', scan_id='scan-a'))
        self.node.request(self.message())
        for i in range(1,8): self.feed(i)
        self.assertFalse(self.node.jobs)
        self.assertFalse(self.node.pub.sent)
        self.node.settled(self.message()); self.finish()
        result = self.node.pub.sent[-1]
        self.assertTrue(result.approved)
        self.assertEqual(result.txn_id, 'txn')
        self.assertEqual(result.scan_id, 'scan-a')

    def test_repeated_camera_stamp_not_buffered(self):
        self.feed(1); self.feed(1)
        self.assertEqual(len(self.node.frames),1)

    def test_no_scan_or_weight_never_generates_removal(self):
        for i in range(1,8): self.feed(i)
        self.node.tick()
        self.assertFalse(self.node.jobs); self.assertFalse(self.node.pub.sent)

    def test_buffer_prunes_old_frames_and_is_bounded(self):
        with patch('nxtcart_vision.vision_verify_node.time.monotonic', return_value=10.): self.feed(1)
        with patch('nxtcart_vision.vision_verify_node.time.monotonic', return_value=14.): self.feed(2)
        self.assertEqual(len(self.node.frames),1)
        for i in range(3,150): self.feed(i)
        self.assertLessEqual(len(self.node.frames),90)

    def test_settlement_can_arrive_before_request(self):
        self.feed(1)
        self.node.settled(self.message()); self.finish()
        self.node.request(self.message())
        self.assertTrue(self.node.pub.sent[-1].approved)
        self.assertFalse(self.node.pending)

    def test_duplicate_settlement_only_submits_once(self):
        self.feed(1); self.node.settled(self.message()); self.node.settled(self.message())
        self.assertEqual(len(self.node.jobs),1)
        self.finish(); self.node.settled(self.message())
        self.assertEqual(len(self.node.pub.sent),1)

    def test_no_frames_is_explicit_retry(self):
        self.node.settled(self.message())
        self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY')
        self.assertFalse(self.node.jobs)

    def test_stale_settlement_rejected(self):
        self.feed(1)
        self.node.settled(self.message(started_at=types.SimpleNamespace(sec=90,nanosec=0)))
        self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY')

    def test_post_settlement_frames_are_excluded(self):
        self.feed(1)
        self.node.settled(self.message(started_at=types.SimpleNamespace(sec=99,nanosec=0)))
        self.assertFalse(self.node.jobs)

    def test_samples_are_evenly_selected_and_copied(self):
        for i in range(1,10):
            self.crop[:]=i; self.feed(i)
        self.crop[:]=99
        self.node.settled(self.message())
        capture = self.node.jobs[('txn',1)][0]
        self.assertEqual([int(sample[0][0,0,0]) for sample in capture.samples],[1,3,5,7,9])
        self.finish()

    def test_waiting_for_weight_times_out(self):
        self.node.request(self.message())
        self.node.pending[('txn',1)].opened -= 19.
        self.node.tick()
        self.assertIn('Weight settlement',self.node.pub.sent[-1].reason)

    def test_cancellation_suppresses_running_result_and_settlement(self):
        capture=self.Capture('scan-a','sku_a','001',time.monotonic(),txn_id='txn')
        future=Future(); future.set_running_or_notify_cancel()
        self.node.jobs[('txn',1)]=(capture,future,time.monotonic(),False)
        self.node.request(self.message(action='cancel'))
        future.set_result(Result('MATCH','sku_a',.9,.8,'match')); self.node.tick()
        self.node.settled(self.message())
        self.assertEqual(len(self.node.pub.sent),0)

    def test_late_completed_future_cannot_pass(self):
        capture=self.Capture('scan-a','sku_a','001',time.monotonic(),txn_id='txn')
        future=Future(); future.set_result(Result('MATCH','sku_a',.9,.8,'match'))
        self.node.jobs[('txn',1)]=(capture,future,time.monotonic()-10.,False)
        self.node.tick(); self.assertFalse(self.node.pub.sent[-1].approved)

    def test_selected_removal_waits_for_settlement(self):
        msg=self.message(attempt=2,action='remove')
        self.node.request(msg); self.feed(1)
        self.assertFalse(self.node.jobs)
        self.node.settled(msg); self.finish()
        self.assertEqual(self.node.pub.sent[-1].attempt,2)
        self.assertEqual(self.node.pub.sent[-1].action,'item_removed')

    def test_camera_restart_invalidates_pending_capture(self):
        self.feed(1); self.node.request(self.message()); self.feed(2,'new-camera')
        self.node.settled(self.message())
        self.assertFalse(self.node.jobs)
        self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY')


class PiScanBindingTests(unittest.TestCase):
    setUp = adapters.AdapterTests.setUp
    verified = adapters.AdapterTests.verified

    def test_pi_settlement_is_transaction_bound_even_on_wrong_weight(self):
        self.node.scan_cb(self.msgs.ScannedItem(barcode='001', scan_id='scan-a'))
        request = self.node.vision_pub.sent[-1]
        self.node.weight_cb(self.msgs.WeightSample(stream_id='scale', seq=2,
            grams=250., stable=True, calibrated=True))
        event = self.node.settled_pub.sent[-1]
        self.assertEqual((event.txn_id,event.scan_id,event.attempt),
                         (request.txn_id,'scan-a',1))
        self.assertEqual(event.action,'add')
        self.assertEqual(self.node.ledger.units[0].weight_status,'FAIL')
        self.node.vision_cb(self.msgs.VisionEvent(scan_id=event.scan_id,txn_id=event.txn_id,
            barcode='001',attempt=1,action='item_placed',verdict='MATCH',approved=True))
        self.assertFalse(self.node.ledger.checkout_allowed)

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
