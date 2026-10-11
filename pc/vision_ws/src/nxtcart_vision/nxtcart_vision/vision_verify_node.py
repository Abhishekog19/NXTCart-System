#!/usr/bin/env python3
"""Weight-triggered dense-burst foreground verification for ROS 2 Jazzy.

ROS callbacks use the default mutually-exclusive callback group. All model,
segmentation and disk I/O work runs on one bounded worker, so cv2.dnn is never
called concurrently and camera/health callbacks do not wait for inference.
"""
from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import math
import sys
import time
import uuid
from pathlib import Path
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image
from std_msgs.msg import String
from smart_cart_interfaces.msg import ScannedItem, VerificationRequest, VisionEvent


@dataclass
class Capture:
    scan_id: str
    sku: str
    barcode: str
    opened: float
    action: str = 'item_placed'
    txn_id: str = ''
    attempt: int = 1
    detected: bool = False


class VisionNode(Node):
    def __init__(self):
        super().__init__('pc_product_verifier')
        defaults = {
            'cam_root': '/home/vandan/NXTCart-System/pc',
            'model_path': '/home/vandan/NXTCart-System/pc/ml/mobilenet_v2.onnx',
            'database_path': '/home/vandan/NXTCart-System/pc/embedding_db.pkl',
            'catalog_path': '', 'embedding_layer': '', 'similarity_threshold': .72,
            'colour_threshold': .30, 'size_ratio_tolerance': 3., 'removal_margin': .04,
            'competitive_margin': .04, 'swap_threshold': .70,
            'buffer_seconds': 4.0, 'buffer_max_frames': 120,
            'burst_before': .40, 'burst_after': .15, 'baseline_before': .90,
            'baseline_tolerance': .15, 'burst_min_frames': 12, 'burst_max_gap': .08,
            'transport_grace': .75, 'camera_loss_timeout': 5.0,
            'foreground_min_area': 800., 'difference_threshold': 25,
            'roi_padding': .12, 'max_roi_fraction': .65,
            'debug_dir': '', 'debug_keep': 100,
            'result_timeout': 6., 'max_inflight': 8,
            'settlement_timeout': 18.0, 'preview': False,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        p = lambda name: self.get_parameter(name).value
        for name in ('buffer_seconds', 'result_timeout', 'settlement_timeout', 'burst_before',
                     'burst_after', 'baseline_before', 'baseline_tolerance', 'burst_max_gap',
                     'transport_grace', 'camera_loss_timeout', 'foreground_min_area'):
            if not math.isfinite(p(name)) or p(name) <= 0:
                raise ValueError(f'{name} must be finite and positive')
        for name in ('buffer_max_frames', 'burst_min_frames', 'max_inflight', 'debug_keep', 'difference_threshold'):
            if not isinstance(p(name), int) or isinstance(p(name), bool) or p(name) < 1:
                raise ValueError(f'{name} must be a positive integer')
        if (p('burst_min_frames') < 2 or p('buffer_max_frames') < p('burst_min_frames')
                or p('baseline_before') <= p('burst_before')
                or p('buffer_seconds') <= p('baseline_before') + p('burst_after') + p('transport_grace')
                or not 0 <= p('roi_padding') <= .5 or not 0 < p('max_roi_fraction') < 1
                or p('difference_threshold') > 255):
            raise ValueError('Invalid burst, baseline, buffer or foreground configuration')
        root = Path(p('cam_root')).expanduser().resolve()
        def path(value):
            item = Path(value).expanduser()
            return str(item if item.is_absolute() else root / item)
        sys.path.insert(0, str(root))
        from nxtcart_vision.local_matcher import LocalMatcher
        from nxtcart_vision.burst import DebugStore
        self.backend = LocalMatcher(path(p('model_path')), path(p('database_path')),
            path(p('catalog_path')) if p('catalog_path') else '',
            p('similarity_threshold'), p('colour_threshold'), p('size_ratio_tolerance'),
            p('removal_margin'), p('embedding_layer'),
            competitive_margin=p('competitive_margin'), swap_threshold=p('swap_threshold'))
        self.debug_store = DebugStore(path(p('debug_dir') or 'debug_frames'), p('debug_keep'))
        self.segmentation = dict(min_area=p('foreground_min_area'), threshold=p('difference_threshold'),
                                 padding=p('roi_padding'), max_roi_fraction=p('max_roi_fraction'))
        self.bridge = CvBridge()
        self.pub = self.create_publisher(VisionEvent, '/cart/vision_event', 50)
        self.health_pub = self.create_publisher(String, '/cart/vision_health', 10)
        self.anomaly_pub = self.create_publisher(String, '/cart/scene_anomaly', 10)
        self.create_subscription(Image, '/cart/camera/frame', self.frame,
            QoSProfile(depth=30, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.create_subscription(ScannedItem, '/cart/scanned_item', self.scan, 50)
        self.create_subscription(VerificationRequest, '/cart/verification_request', self.request, 50)
        self.create_subscription(VerificationRequest, '/cart/placement_settled', self.settled, 50)
        self.inference_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='onnx-verification')
        self.pending, self.bursts, self.jobs, self.done = {}, {}, {}, OrderedDict()
        self.frames = deque(maxlen=p('buffer_max_frames'))
        self.last_frame_at = self.last_health = -math.inf
        self.stamp_ns, self.camera_generation = None, None
        self.boot_id = uuid.uuid4().hex
        self.create_timer(.05, self.tick)
        self.get_logger().info(f'Weight-triggered foreground burst verification ready: {len(self.backend.products)} products')

    @staticmethod
    def key(capture):
        return capture.txn_id or capture.scan_id, capture.attempt

    def seen(self, key):
        return key in self.done or key in self.jobs or key in self.pending or key in self.bursts

    def remember(self, key):
        self.done[key] = None
        self.done.move_to_end(key)
        while len(self.done) > 4096:
            self.done.popitem(last=False)

    def scan(self, msg):
        # The Pi's VerificationRequest supplies authoritative SKU and attempt.
        # A barcode scan alone must never start inference.
        if msg.scan_id:
            self.get_logger().info(f'{msg.scan_id}: barcode received; awaiting Pi weight settlement')

    def capture_for(self, msg):
        sku = self.backend.resolve(msg.sku, msg.barcode)
        return Capture(msg.scan_id or msg.txn_id, sku or '', msg.barcode,
                       time.monotonic(), 'item_removed' if msg.action == 'remove' else 'item_placed',
                       msg.txn_id, msg.attempt)

    def request(self, msg):
        key = (msg.txn_id, msg.attempt)
        if not msg.txn_id or msg.attempt < 1:
            return
        if msg.action == 'cancel':
            self.pending.pop(key, None)
            self.bursts.pop(key, None)
            if key in self.jobs:
                c, future, started, _ = self.jobs[key]
                future.cancel()
                self.jobs[key] = c, future, started, True
            self.remember(key)
        elif msg.action in ('add', 'remove') and not self.seen(key):
            if len(self.pending) + len(self.bursts) + len(self.jobs) >= self.get_parameter('max_inflight').value:
                self.publish(self.capture_for(msg), 'RETRY', 'Waiting-for-weight queue full')
            else:
                self.pending[key] = self.capture_for(msg)

    def prune_frames(self, now):
        cutoff = now - self.get_parameter('buffer_seconds').value
        while self.frames and self.frames[0][0] < cutoff:
            self.frames.popleft()

    def settled(self, msg):
        if not msg.txn_id or msg.attempt < 1 or msg.action not in ('add', 'remove'):
            return
        key = (msg.txn_id, msg.attempt)
        if key in self.done or key in self.jobs or key in self.bursts:
            return
        capture = self.pending.pop(key, None)
        if capture is None:
            capture = self.capture_for(msg)
        if capture.scan_id != (msg.scan_id or msg.txn_id) or capture.barcode != msg.barcode or capture.sku != (self.backend.resolve(msg.sku, msg.barcode) or '') or capture.action != ('item_removed' if msg.action == 'remove' else 'item_placed'):
            self.publish(capture, 'RETRY', 'Settlement does not match requested transaction')
            return
        if not capture.sku:
            self.publish(capture, 'UNAVAILABLE', 'Unknown barcode/SKU: configure catalog_path or database aliases')
            return
        now = time.monotonic()
        self.prune_frames(now)
        end = msg.started_at.sec * 1_000_000_000 + msg.started_at.nanosec
        clock = self.get_clock().now().to_msg()
        age = (clock.sec * 1_000_000_000 + clock.nanosec - end) / 1e9
        horizon = self.get_parameter('buffer_seconds').value
        if not -.1 <= age <= horizon:
            self.publish(capture, 'RETRY', 'Stale settlement timestamp; check Pi/PC clock synchronization')
            return
        if len(self.bursts) + len(self.jobs) >= self.get_parameter('max_inflight').value:
            self.publish(capture, 'RETRY', 'Image verification queue full')
            return
        # Keep receiving post-impact frames. ROS subscriptions on separate topics
        # may arrive out of order, so do not snapshot on the settlement callback.
        wait = max(0., self.get_parameter('burst_after').value-age)
        self.bursts[key] = (capture, end, now+wait,
                            now+wait+self.get_parameter('transport_grace').value)

    def dispatch_bursts(self, now):
        from nxtcart_vision.burst import verify_burst
        p = lambda name: self.get_parameter(name).value
        for key, (capture, impact, ready_at, deadline) in list(self.bursts.items()):
            end = impact + round(p('burst_after') * 1e9)
            covered = self.stamp_ns is not None and self.stamp_ns >= end
            if now < ready_at or (not covered and now < deadline):
                continue
            del self.bursts[key]
            start = impact - round(p('burst_before') * 1e9)
            base_at = impact - round(p('baseline_before') * 1e9)
            bases = [f for f in self.frames if base_at-round(p('baseline_tolerance')*1e9) <= f[1] <= base_at]
            burst = [f for f in self.frames if start <= f[1] <= end]
            if not bases:
                self.publish(capture, 'RETRY', 'Pre-entry baseline unavailable; wait for camera buffer before placement')
                continue
            # Do not guess away packet loss: this would recreate the temporal
            # blind spot. Keep every frame, require density and both edges.
            stamps = [f[1] for f in burst]
            gaps = [b-a for a,b in zip([start]+stamps, stamps+[end])]
            if len(burst) < p('burst_min_frames') or max(gaps, default=end-start) > p('burst_max_gap')*1e9:
                self.publish(capture, 'RETRY', f'Incomplete placement burst: {len(burst)} frames; check 30 FPS camera/DDS transport')
                continue
            baseline = bases[-1]
            metadata = dict(settled_ns=impact, window_start_ns=start, window_end_ns=end,
                            baseline_ns=baseline[1], frame_count=len(burst),
                            max_gap_ms=max(gaps)/1e6)
            self.get_logger().info(f'{capture.txn_id} attempt {capture.attempt}: weight settled; '
                                   f'evaluating all {len(burst)} burst frames as foreground ROIs')
            future = self.inference_pool.submit(verify_burst, self.backend, capture,
                baseline[2], burst, dict(self.segmentation), self.debug_store, metadata)
            self.jobs[key] = capture, future, now, False

    def frame(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except (CvBridgeError, ValueError) as exc:
            self.get_logger().error(f'Image conversion failed: {exc}')
            return
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or not 8 <= frame.shape[0] <= 2160 or not 8 <= frame.shape[1] <= 3840:
            return
        stamp = msg.header.stamp.sec*1_000_000_000+msg.header.stamp.nanosec
        generation = msg.header.frame_id or 'verification_camera'
        now = time.monotonic()
        clock = self.get_clock().now().to_msg()
        age = (clock.sec*1_000_000_000 + clock.nanosec - stamp)/1e9
        if not -.5 <= age <= self.get_parameter('camera_loss_timeout').value:
            return
        if self.camera_generation == generation and self.stamp_ns is not None and stamp <= self.stamp_ns:
            return  # A replayed physical frame cannot supply another sample.
        if self.camera_generation is not None and generation != self.camera_generation:
            self.frames.clear()
            for capture in list(self.pending.values()):
                self.publish(capture, 'RETRY', 'Camera restarted while waiting for weight settlement')
            self.pending.clear()
            for capture, _, _, _ in self.bursts.values():
                self.publish(capture, 'RETRY', 'Camera restarted during burst collection')
            self.bursts.clear()
            for key, (capture, future, started, expired) in list(self.jobs.items()):
                self.publish(capture, 'RETRY', 'Camera restarted during verification')
                future.cancel()
                self.jobs[key] = capture, future, started, True
            warning = String(); warning.data = 'Verification camera restarted; reconcile basket contents'
            self.anomaly_pub.publish(warning)
        self.camera_generation, self.stamp_ns, self.last_frame_at = generation, stamp, now
        # Bound memory on a long-running cart; make a copy so cv_bridge/preview
        # cannot mutate evidence retained by the inference worker.
        scale = min(1., 640/frame.shape[1], 480/frame.shape[0])
        if scale < 1.:
            frame = cv2.resize(frame, (max(8, round(frame.shape[1]*scale)), max(8, round(frame.shape[0]*scale))))
        self.frames.append((now, stamp, frame.copy()))
        self.prune_frames(now)
        if self.get_parameter('preview').value:
            display = frame.copy()
            cv2.putText(display, f'Buffer={len(self.frames)} | waiting weight={len(self.pending)} | inference={len(self.jobs)}',
                        (8,24), cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 1)
            cv2.imshow('NXTCart weight-triggered verification', display); cv2.waitKey(1)

    def publish(self, capture, verdict, reason, result=None):
        key = self.key(capture)
        if key in self.done:
            return
        msg = VisionEvent()
        if result and result.code in ('SWAP_DETECTED', 'NO_ITEM_SEEN'):
            reason = f'{result.code}: {reason}'
        msg.scan_id, msg.approved, msg.reason = capture.scan_id, verdict == 'MATCH', reason[:500]
        msg.txn_id, msg.attempt, msg.action = capture.txn_id, capture.attempt, capture.action
        msg.barcode, msg.name = capture.barcode, (result.sku if result else capture.sku)
        msg.verdict, msg.verified, msg.detected = verdict, msg.approved, capture.detected
        if result:
            msg.appearance_score, msg.colour_score = float(result.score), float(result.colour)
        self.pub.publish(msg)
        self.remember(key)
        self.get_logger().info(f'{capture.scan_id} {msg.name}: {verdict} {msg.action}: {reason}')

    def tick(self):
        now = time.monotonic()
        self.prune_frames(now)
        for key, capture in list(self.pending.items()):
            if now-capture.opened > self.get_parameter('settlement_timeout').value:
                self.pending.pop(key)
                self.publish(capture, 'RETRY', 'Weight settlement not received before deadline')
        self.dispatch_bursts(now)
        for key, (capture, future, started, expired) in list(self.jobs.items()):
            if not expired and now-started > self.get_parameter('result_timeout').value:
                self.publish(capture, 'RETRY', 'Image inference deadline exceeded')
                future.cancel(); expired = True
                self.jobs[key] = capture, future, started, True
            if future.done():
                if not expired:
                    try:
                        outcome = future.result()
                        result = outcome.result
                        capture.detected = outcome.crop_count > 0
                        if outcome.debug_error:
                            self.get_logger().error(f'Debug artifact write failed: {outcome.debug_error}')
                        self.publish(capture, result.verdict, result.reason, result)
                    except Exception as exc:
                        self.publish(capture, 'UNAVAILABLE', f'Image verification failed: {exc}')
                del self.jobs[key]
        if now-self.last_health >= .5:
            stalled = any(expired and not future.done() for _,future,_,expired in self.jobs.values())
            msg = String()
            msg.data = json.dumps({'ready': self.camera_generation is not None and now-self.last_frame_at <= self.get_parameter('camera_loss_timeout').value and not stalled,
                'generation': self.boot_id+':'+str(self.camera_generation), 'backend': 'onnx', 'inflight': len(self.jobs), 'collecting': len(self.bursts),
                'buffered_frames': len(self.frames),
                'camera_age_seconds': round(now-self.last_frame_at, 3) if math.isfinite(self.last_frame_at) else None})
            self.health_pub.publish(msg); self.last_health = now

    def destroy_node(self):
        self.inference_pool.shutdown(wait=False, cancel_futures=True)
        if self.get_parameter('preview').value:
            cv2.destroyAllWindows()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = VisionNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
