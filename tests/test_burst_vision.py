"""Dense burst, foreground-only inference, ranking and shipped callback tests."""
import json
import pickle
import tempfile
import types
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
import test_ros_adapters as adapters
from nxtcart_vision.burst import DebugStore, foreground, verify_burst, BurstOutcome
from nxtcart_vision.local_matcher import LocalMatcher, Result


class ForegroundTests(unittest.TestCase):
    def setUp(self):
        self.base = np.full((480, 640, 3), 70, np.uint8)
        self.item = self.base.copy()
        self.item[200:260, 300:380] = (20, 200, 20)  # 1.56% of the scene
        self.capture = types.SimpleNamespace(sku='soap', txn_id='txn', scan_id='scan',
                                             attempt=1, action='item_placed')
        self.backend = types.SimpleNamespace(verify=Mock(return_value=Result('MATCH','soap',.9,.9,'match')))
        self.store = types.SimpleNamespace(save=Mock(return_value='debug'))

    def test_empty_scene_never_calls_embedding_matcher(self):
        result = verify_burst(self.backend, self.capture, self.base,
                              [(0,i,self.base) for i in range(17)], {}, self.store, {})
        self.backend.verify.assert_not_called()
        self.assertEqual(result.result.code, 'NO_ITEM_SEEN')
        self.assertEqual(result.result.verdict,'MISMATCH')

    def test_small_object_is_tightly_cropped_with_padding(self):
        region = foreground(self.base, self.item)
        self.assertEqual(len(region.crops),1)
        x,y,w,h=region.boxes[0]
        self.assertLess(w*h, self.base.shape[0]*self.base.shape[1]*.03)
        self.assertLess(x,300); self.assertLess(y,200)
        self.assertGreater(x+w,380); self.assertGreater(y+h,260)
        outcome=verify_burst(self.backend,self.capture,self.base,[(0,1,self.item)],{},self.store,{})
        sample=self.backend.verify.call_args.args[1][0][0]
        self.assertEqual(sample.shape, region.crops[0].shape)
        self.assertEqual(outcome.crop_count,1)

    def test_sub_800_pixel_noise_discarded(self):
        frame=self.base.copy(); frame[20:30,20:30]=255
        self.assertEqual(foreground(self.base,frame).crops,[])

    def test_global_lighting_change_is_never_full_frame_embedding(self):
        out=verify_burst(self.backend,self.capture,self.base,[(0,1,np.full_like(self.base,200))],{},self.store,{})
        self.backend.verify.assert_not_called(); self.assertNotEqual(out.result.verdict,'MATCH')

    def test_separate_hand_and_product_do_not_merge_into_full_scene(self):
        frame=self.item.copy(); frame[50:100,50:100]=200
        regions=foreground(self.base,frame)
        self.assertEqual(len(regions.crops),2)
        self.assertTrue(all(c.shape[0]*c.shape[1] < 15000 for c in regions.crops))

    def test_removal_embeds_departing_product_not_empty_basket(self):
        self.capture.action='item_removed'
        verify_burst(self.backend,self.capture,self.item,[(0,1,self.base)],{},self.store,{})
        crop=self.backend.verify.call_args.args[1][0][0]
        self.assertGreater(float(crop[:,:,1].mean()),100)

    def test_debug_disk_error_does_not_change_decision(self):
        self.store.save.side_effect=OSError('disk full')
        out=verify_burst(self.backend,self.capture,self.base,[(0,1,self.item)],{},self.store,{})
        self.assertEqual(out.result.verdict,'MATCH'); self.assertIn('disk full',out.debug_error)

    def test_debug_images_manifest_and_retention(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DebugStore(folder,keep=2)
            unrelated=Path(folder)/'keep_me'; unrelated.mkdir()
            for _ in range(3):
                out=verify_burst(self.backend,self.capture,self.base,[(0,1,self.item)],{},store,{'settled_ns':1})
                self.assertFalse(out.debug_error)
            dirs=list(Path(folder).glob('nxtcart_*'))
            self.assertEqual(len(dirs),2); self.assertTrue(unrelated.exists())
            manifest=json.loads((Path(out.debug_path)/'manifest.json').read_text())
            self.assertEqual(manifest['decision']['verdict'],'MATCH')
            self.assertEqual(len(list(Path(out.debug_path).glob('*.jpg'))),3)


class ContrastiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.query=np.zeros(1280,np.float32); self.query[0]=1
        self.crop=np.full((50,60,3),100,np.uint8)

    def matcher(self, scores):
        db={}
        for i,(sku,score) in enumerate(scores.items(),1):
            vec=np.zeros(1280,np.float32); vec[0]=score; vec[i]=np.sqrt(1-score*score)
            db[sku]=[vec]
        path=Path(self.tmp.name)/'db.pkl'; path.write_bytes(pickle.dumps(db))
        return LocalMatcher('unused',path,embedder=types.SimpleNamespace(embed=lambda c:self.query))

    def test_empty_background_similarity_666_is_rejected(self):
        self.assertEqual(self.matcher({'target':.666}).verify('target',[[self.crop]]).verdict,'MISMATCH')

    def test_target_top1_above_72_and_margin_04_passes(self):
        self.assertEqual(self.matcher({'target':.85,'other':.78}).verify('target',[[self.crop]]).verdict,'MATCH')

    def test_target_high_absolute_score_but_small_margin_rejected(self):
        result=self.matcher({'target':.88,'other':.86}).verify('target',[[self.crop]])
        self.assertEqual(result.verdict,'MISMATCH')

    def test_green_soap_swap_returns_interloper_even_if_target_above_threshold(self):
        result=self.matcher({'margo':.78,'hamam':.89}).verify('margo',[[self.crop]])
        self.assertEqual((result.verdict,result.code,result.sku),('MISMATCH','SWAP_DETECTED','hamam'))

    def test_equal_score_tie_never_passes(self):
        self.assertNotEqual(self.matcher({'target':.9,'other':.9}).verify('target',[[self.crop]]).verdict,'MATCH')

    def test_later_swap_vetoes_earlier_match_and_every_crop_is_evaluated(self):
        a=np.zeros(1280,np.float32); a[0]=1
        b=np.zeros(1280,np.float32); b[1]=1
        path=Path(self.tmp.name)/'db.pkl'; path.write_bytes(pickle.dumps({'target':[a],'other':[b]}))
        embed=Mock(side_effect=[a,b])
        matcher=LocalMatcher('unused',path,embedder=types.SimpleNamespace(embed=embed))
        result=matcher.verify('target',[[self.crop],[self.crop]])
        self.assertEqual(result.code,'SWAP_DETECTED'); self.assertEqual(embed.call_count,2)
        self.assertEqual(len(result.evaluations),2)


class BurstNodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        stubs=adapters.ros_stubs(); self.msgs=stubs['smart_cart_interfaces.msg']
        self.stub_patch=patch.dict('sys.modules',stubs); self.stub_patch.start(); self.addCleanup(self.stub_patch.stop)
        adapters.Node.overrides={'cam_root':str(adapters.ROOT/'pc'),'debug_dir':self.tmp.name}
        self.backend=types.SimpleNamespace(products={'sku':[]},
            resolve=lambda a,b='':'sku' if a in ('sku','001') or b=='001' else None,
            verify=Mock(return_value=Result('MATCH','sku',.9,.8,'matched','MATCH')))
        with patch('nxtcart_vision.local_matcher.LocalMatcher',return_value=self.backend):
            from nxtcart_vision.vision_verify_node import VisionNode, Capture
            self.node=VisionNode(); self.Capture=Capture
        self.addCleanup(self.node.destroy_node)
        self.now=100.
        self.clock_patch=patch('nxtcart_vision.vision_verify_node.time.monotonic',side_effect=lambda:self.now)
        self.clock_patch.start(); self.addCleanup(self.clock_patch.stop)
        self.node.get_clock=lambda:types.SimpleNamespace(now=lambda:types.SimpleNamespace(to_msg=lambda:self.stamp(self.now)))
        self.base=np.full((480,640,3),60,np.uint8)
        self.item=self.base.copy(); self.item[200:260,300:380]=(0,210,0)

    @staticmethod
    def stamp(seconds):
        ns=round(seconds*1e9)
        return types.SimpleNamespace(sec=ns//1_000_000_000,nanosec=ns%1_000_000_000)

    def message(self,**kw):
        values=dict(txn_id='txn',scan_id='scan',sku='sku',barcode='001',attempt=1,action='add',started_at=self.stamp(100.))
        values.update(kw); return self.msgs.VerificationRequest(**values)

    def feed(self,seconds,frame=None,generation='cam'):
        self.now=max(self.now,seconds)
        self.node.frame(types.SimpleNamespace(frame=self.base if frame is None else frame,
            header=types.SimpleNamespace(frame_id=generation,stamp=self.stamp(seconds))))

    def burst(self,static=False,omit=None,baseline=True):
        if baseline:self.feed(99.1)
        for i in range(18):
            if omit and i in omit:continue
            self.feed(99.6+i/30, self.base if static or i not in (9,10,11,12) else self.item)

    def finish(self):
        self.now=max(self.now,100.3)
        self.node.tick()
        for capture,future,started,expired in list(self.node.jobs.values()):future.result(timeout=5)
        self.node.tick()

    def test_scan_and_motion_alone_never_trigger_inference(self):
        self.node.scan(self.msgs.ScannedItem(barcode='001',scan_id='scan'))
        self.node.request(self.message()); self.burst(); self.finish()
        self.backend.verify.assert_not_called(); self.assertFalse(self.node.pub.sent)

    def test_dense_burst_preserves_fast_drop_and_only_embeds_crops(self):
        self.burst(); self.node.settled(self.message()); self.finish()
        samples=self.backend.verify.call_args.args[1]
        self.assertEqual(len(samples),17)  # all 30 FPS samples, no decimation
        self.assertEqual(sum(bool(s) for s in samples),4)
        self.assertTrue(all(c.shape[0]*c.shape[1]<15000 for s in samples for c in s))
        self.assertTrue(self.node.pub.sent[-1].approved)

    def test_static_scene_returns_no_item_and_never_embeds(self):
        self.burst(static=True); self.node.settled(self.message()); self.finish()
        self.backend.verify.assert_not_called()
        self.assertEqual(self.node.pub.sent[-1].verdict,'MISMATCH')
        self.assertIn('NO_ITEM_SEEN',self.node.pub.sent[-1].reason)

    def test_settlement_waits_for_post_impact_frames(self):
        self.feed(99.1)
        for i in range(13):self.feed(99.6+i/30,self.item)
        self.node.settled(self.message()); self.node.tick()
        self.assertFalse(self.node.jobs); self.assertTrue(self.node.bursts)
        for i in range(13,18):self.feed(99.6+i/30,self.item)
        self.finish(); self.assertTrue(self.node.pub.sent[-1].approved)

    def test_wifi_delivery_late_but_within_grace_is_used(self):
        self.node.settled(self.message()); self.now=100.4; self.node.tick()
        self.assertFalse(self.node.pub.sent)
        self.burst(); self.finish(); self.assertTrue(self.node.pub.sent[-1].approved)

    def test_packet_loss_gap_never_silently_decimated(self):
        self.burst(omit={8,9,10,11}); self.node.settled(self.message()); self.finish()
        self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY'); self.backend.verify.assert_not_called()

    def test_missing_baseline_is_retry_not_full_frame_fallback(self):
        self.burst(baseline=False); self.node.settled(self.message()); self.finish()
        self.assertIn('baseline',self.node.pub.sent[-1].reason); self.backend.verify.assert_not_called()

    def test_post_frames_never_arrive_times_out_burst(self):
        self.feed(99.1); self.node.settled(self.message()); self.now=101.; self.finish()
        self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY')

    def test_reordered_request_and_duplicate_settlement_do_not_repeat_job(self):
        self.burst(); self.node.settled(self.message()); self.node.request(self.message())
        self.node.settled(self.message()); self.finish(); self.node.settled(self.message())
        self.assertEqual(len(self.node.pub.sent),1); self.assertFalse(self.node.pending)

    def test_cancel_during_post_frame_wait_suppresses_verdict(self):
        self.node.settled(self.message()); self.node.request(self.message(action='cancel'))
        self.burst(); self.finish(); self.assertFalse(self.node.pub.sent)

    def test_cancel_running_and_late_result_cannot_approve(self):
        capture=self.Capture('scan','sku','001',100.,txn_id='txn')
        future=Future(); future.set_running_or_notify_cancel()
        self.node.jobs[('txn',1)]=(capture,future,100.,False)
        self.node.request(self.message(action='cancel'))
        future.set_result(BurstOutcome(Result('MATCH','sku'),1)); self.node.tick()
        self.assertFalse(self.node.pub.sent)

    def test_completed_but_over_deadline_result_fails_closed(self):
        capture=self.Capture('scan','sku','001',90.,txn_id='txn')
        future=Future(); future.set_result(BurstOutcome(Result('MATCH','sku'),1))
        self.node.jobs[('txn',1)]=(capture,future,90.,False); self.node.tick()
        self.assertFalse(self.node.pub.sent[-1].approved)

    def test_camera_restart_invalidates_pending_burst(self):
        self.feed(99.1); self.node.settled(self.message()); self.feed(100.1,generation='new')
        self.finish(); self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY')

    def test_duplicate_camera_stamp_rejected_and_memory_bounded(self):
        self.feed(99.1); self.feed(99.1); self.assertEqual(len(self.node.frames),1)
        for i in range(150):self.feed(99.2+i/1000)
        self.assertEqual(len(self.node.frames),120)

    def test_camera_health_tolerates_five_seconds_even_if_buffer_pruned(self):
        self.feed(100.)
        for age in (1.1,4.5,5.0):
            self.now=100.+age; self.node.tick()
            self.assertTrue(json.loads(self.node.health_pub.sent[-1].data)['ready'])
        self.now=105.6; self.node.tick()
        self.assertFalse(json.loads(self.node.health_pub.sent[-1].data)['ready'])

    def test_unknown_identity_and_stale_settlement_rejected(self):
        self.node.settled(self.message(started_at=self.stamp(90.)))
        self.assertEqual(self.node.pub.sent[-1].verdict,'RETRY')
        self.node.settled(self.message(txn_id='bad',sku='missing',barcode='999'))
        self.assertEqual(self.node.pub.sent[-1].verdict,'UNAVAILABLE')

    def test_selected_removal_waits_for_weight_and_preserves_attempt(self):
        self.node.request(self.message(action='remove',attempt=2))
        self.feed(99.1,self.item)
        for i in range(18):self.feed(99.6+i/30)
        self.finish(); self.assertFalse(self.node.pub.sent)
        self.node.settled(self.message(action='remove',attempt=2)); self.finish()
        self.assertEqual(self.node.pub.sent[-1].action,'item_removed')
        self.assertEqual(self.node.pub.sent[-1].attempt,2)

    def test_queue_capacity_and_settlement_identity_fail_closed(self):
        for i in range(8):self.node.request(self.message(txn_id=f'txn{i}'))
        self.node.request(self.message(txn_id='overflow'))
        self.assertEqual(len(self.node.pending),8)
        self.assertFalse(self.node.pub.sent[-1].approved)
        self.node.settled(self.message(txn_id='txn0',scan_id='different'))
        self.assertIn('does not match',self.node.pub.sent[-1].reason)


class CameraNodeTests(unittest.TestCase):
    def setUp(self):
        stubs=adapters.ros_stubs()
        self.bridge=types.SimpleNamespace(cv2_to_imgmsg=lambda frame,encoding:
            types.SimpleNamespace(header=types.SimpleNamespace(),frame=frame))
        stubs['cv_bridge'].CvBridge=lambda:self.bridge
        self.patcher=patch.dict('sys.modules',stubs); self.patcher.start(); self.addCleanup(self.patcher.stop)
        adapters.Node.overrides={}
        # Load under a unique name so any previous camera mock cannot leak in.
        import importlib.util
        spec=importlib.util.spec_from_file_location('burst_camera_test',
            adapters.PI/'smart_cart_ws/src/smart_cart/smart_cart/camera_stream_node.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.node=module.CameraStreamNode(); self.addCleanup(self.node.destroy_node)
        self.logger=Mock(); self.node.get_logger=lambda:self.logger
        self.cap=Mock(); self.cap.isOpened.return_value=True
        self.cap.set.return_value=True; self.cap.get.return_value=30.
        self.cap.read.return_value=(True,np.zeros((480,640,3),np.uint8))
        self.capture_patch=patch.object(module.cv2,'VideoCapture',return_value=self.cap)
        self.capture_patch.start(); self.addCleanup(self.capture_patch.stop)

    def test_defaults_driver_fps_buffer_size_and_node_timestamp(self):
        self.node.tick()
        self.cap.set.assert_any_call(cv2.CAP_PROP_FPS,30.)
        self.cap.set.assert_any_call(cv2.CAP_PROP_BUFFERSIZE,1)
        self.cap.set.assert_any_call(cv2.CAP_PROP_FRAME_WIDTH,640)
        self.cap.set.assert_any_call(cv2.CAP_PROP_FRAME_HEIGHT,480)
        self.assertEqual(self.node.pub.sent[-1].header.stamp.sec,100)

    def test_failed_open_releases_and_backoff_prevents_busy_loop(self):
        self.cap.isOpened.return_value=False
        self.node.tick(); self.node.tick()
        self.cap.release.assert_called_once(); self.assertFalse(self.node.pub.sent)

    def test_failed_read_reconnects_with_new_generation(self):
        self.node.tick(); first=self.node.pub.sent[-1].header.frame_id
        self.cap.read.return_value=(False,None); self.node.tick()
        self.assertIsNone(self.node.cap)
        self.node.last_open=-float('inf'); self.cap.read.return_value=(True,np.zeros((480,640,3),np.uint8))
        self.node.tick()
        self.assertNotEqual(self.node.pub.sent[-1].header.frame_id,first)

