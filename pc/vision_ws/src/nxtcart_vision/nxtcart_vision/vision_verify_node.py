#!/usr/bin/env python3
"""ROS 2 Jazzy full-frame, lenient MobileNetV2 product verification.

No amber/green checkpoints, per-frame association, MERGED rejection, API calls,
or weight-settle wait. Three to five distinct motion frames are sampled; any
candidate matching the scanned SKU may approve its camera gate. Unscanned
motion is classified as a removal candidate, not proof of physical direction.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import json
import math
import sys
import time
import uuid
from pathlib import Path
import cv2
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
    samples: list = field(default_factory=list)
    last_sample: float = -math.inf


class VisionNode(Node):
    def __init__(self):
        super().__init__('pc_product_verifier')
        defaults = {
            'cam_root': '/home/vandan/NXTCart-System/pc',
            'model_path': '/home/vandan/NXTCart-System/pc/ml/mobilenet_v2.onnx',
            'database_path': '/home/vandan/NXTCart-System/pc/embedding_db.pkl',
            'catalog_path': '', 'embedding_layer': '', 'similarity_threshold': .65,
            'colour_threshold': .30, 'size_ratio_tolerance': 3., 'removal_margin': .03,
            'capture_seconds': 2.5, 'sample_interval': .08, 'min_samples': 3,
            'max_samples': 5, 'result_timeout': 6., 'max_inflight': 8,
            'min_motion_area': 100., 'warmup_frames': 15,
            'removal_grace_seconds': 2., 'quiet_seconds': .8, 'preview': False,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        p = lambda name: self.get_parameter(name).value
        for name in ('capture_seconds', 'sample_interval', 'result_timeout', 'min_motion_area', 'removal_grace_seconds', 'quiet_seconds'):
            if not math.isfinite(p(name)) or p(name) <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if not 3 <= p('min_samples') <= p('max_samples') <= 5 or p('max_inflight') < 1 or p('warmup_frames') < 1:
            raise ValueError('Use 3..5 samples, positive queue size and warmup frames')
        sys.path.insert(0, str(Path(p('cam_root')).expanduser()))
        from nxtcart_vision.local_matcher import LocalMatcher
        from nxtcart_vision.motion import MotionDetector
        self.backend = LocalMatcher(p('model_path'), p('database_path'), p('catalog_path'),
            p('similarity_threshold'), p('colour_threshold'), p('size_ratio_tolerance'),
            p('removal_margin'), p('embedding_layer'))
        self.detector = MotionDetector(p('min_motion_area'), p('warmup_frames'))
        self.bridge = CvBridge()
        self.pub = self.create_publisher(VisionEvent, '/cart/vision_event', 50)
        self.health_pub = self.create_publisher(String, '/cart/vision_health', 10)
        self.anomaly_pub = self.create_publisher(String, '/cart/scene_anomaly', 10)
        self.create_subscription(Image, '/cart/camera/frame', self.frame,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.create_subscription(ScannedItem, '/cart/scanned_item', self.scan, 50)
        # Pi-selected removals/cancellation retain the existing transaction flow.
        # Adds are triggered only by ScannedItem, so each scan is processed once.
        self.create_subscription(VerificationRequest, '/cart/verification_request', self.request, 50)
        self.inference_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='onnx-verification')
        self.active, self.jobs, self.done = None, {}, OrderedDict()
        self.last_frame_at = self.last_health = self.last_authorized = -math.inf
        self.last_motion = -math.inf
        self.stamp_ns, self.camera_generation = None, None
        self.boot_id, self.idle_armed = uuid.uuid4().hex, False
        self.create_timer(.05, self.tick)
        self.get_logger().info(f'Full-frame ONNX verification ready: {len(self.backend.products)} products; no geometric zones or weight wait')

    @staticmethod
    def key(capture):
        return capture.txn_id or capture.scan_id, capture.attempt

    def seen(self, key):
        return key in self.done or key in self.jobs or (self.active is not None and self.key(self.active) == key)

    def remember(self, key):
        self.done[key] = None
        self.done.move_to_end(key)
        while len(self.done) > 4096:
            self.done.popitem(last=False)

    def scan(self, msg):
        if not msg.scan_id or self.seen((msg.scan_id, 1)):
            return
        self.finish_capture()  # Capture the next item while earlier inference runs.
        now = time.monotonic()
        sku = self.backend.resolve(msg.barcode, msg.name)
        capture = Capture(msg.scan_id, sku or '', msg.barcode, now)
        self.last_authorized, self.idle_armed = now, False
        if not sku:
            self.publish(capture, 'UNAVAILABLE', 'Unknown barcode/SKU: configure catalog_path or database aliases')
            return
        self.active = capture

    def request(self, msg):
        if msg.action == 'cancel':
            # The Pi supplies scan_id in the new request schema for cancelling
            # an add; selected removals continue to use txn_id + attempt.
            keys = {(msg.txn_id, msg.attempt), (msg.scan_id, 1)}
            for key in keys:
                if not key[0]:
                    continue
                if self.active and self.key(self.active) == key:
                    self.active = None
                if key in self.jobs:
                    c, future, started, _ = self.jobs[key]
                    future.cancel()
                    self.jobs[key] = (c, future, started, True)
                self.remember(key)
            return
        if msg.action != 'remove' or not msg.txn_id or self.seen((msg.txn_id, msg.attempt)):
            return
        self.finish_capture()
        now = time.monotonic()
        sku = self.backend.resolve(msg.sku, msg.barcode)
        capture = Capture(msg.scan_id or msg.txn_id, sku or '', msg.barcode, now,
                          'item_removed', msg.txn_id, msg.attempt)
        self.last_authorized, self.idle_armed = now, False
        if not sku:
            self.publish(capture, 'UNAVAILABLE', 'Selected removal SKU has no reference embeddings')
        else:
            self.active = capture

    def frame(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except (CvBridgeError, ValueError) as exc:
            self.get_logger().error(f'Image conversion failed: {exc}')
            return
        if frame is None or frame.ndim != 3 or frame.shape[2] != 3 or not 8 <= frame.shape[0] <= 2160 or not 8 <= frame.shape[1] <= 3840:
            return
        stamp = msg.header.stamp.sec*1_000_000_000+msg.header.stamp.nanosec
        generation = msg.header.frame_id or 'verification_camera'
        now = time.monotonic()
        if self.camera_generation == generation and self.stamp_ns is not None and stamp <= self.stamp_ns:
            return  # A replayed physical frame cannot supply another sample.
        if self.camera_generation is not None and generation != self.camera_generation:
            if self.active:
                self.publish(self.active, 'RETRY', 'Camera restarted during capture')
                self.active = None
            from nxtcart_vision.motion import MotionDetector
            self.detector = MotionDetector(self.get_parameter('min_motion_area').value,
                                           self.get_parameter('warmup_frames').value)
            warning = String(); warning.data = 'Verification camera restarted; reconcile basket contents'
            self.anomaly_pub.publish(warning)
        self.camera_generation, self.stamp_ns, self.last_frame_at = generation, stamp, now
        if self.active and now-self.active.opened >= self.get_parameter('capture_seconds').value:
            self.finish_capture()
        crops = self.detector.detect(frame)
        if crops:
            self.last_motion = now
            if self.active is None and self.idle_armed and now-self.last_authorized >= self.get_parameter('removal_grace_seconds').value:
                # No scan: assume OUT for classification, while the Pi retains
                # responsibility for weight reconciliation and billing changes.
                self.active = Capture('removal-'+uuid.uuid4().hex, '', '', now, 'item_removed')
                self.idle_armed = False
            if self.active and now-self.active.last_sample >= self.get_parameter('sample_interval').value:
                self.active.samples.append(crops)
                self.active.last_sample = now
                if len(self.active.samples) >= self.get_parameter('max_samples').value:
                    self.finish_capture()
        elif self.active is None and self.detector.ready and now-self.last_motion >= self.get_parameter('quiet_seconds').value:
            self.idle_armed = True
        if self.get_parameter('preview').value:
            for x,y,w,h in self.detector.boxes:
                cv2.rectangle(frame, (x,y), (x+w,y+h), (0,200,255), 1)
            label = f'Full-frame motion | samples={len(self.active.samples) if self.active else 0} | inference={len(self.jobs)}'
            cv2.putText(frame, label, (8,24), cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 1)
            cv2.imshow('NXTCart full-frame verification', frame); cv2.waitKey(1)

    def finish_capture(self):
        capture, self.active = self.active, None
        if capture is None:
            return
        self.last_authorized = time.monotonic()
        self.idle_armed = False
        if len(capture.samples) < self.get_parameter('min_samples').value:
            self.publish(capture, 'RETRY', f'Only {len(capture.samples)} motion frames captured; need at least 3')
        elif len(self.jobs) >= self.get_parameter('max_inflight').value:
            self.publish(capture, 'RETRY', 'Image verification queue full')
        else:
            future = self.inference_pool.submit(self.backend.verify, capture.sku, capture.samples)
            self.jobs[self.key(capture)] = capture, future, time.monotonic(), False

    def publish(self, capture, verdict, reason, result=None):
        key = self.key(capture)
        if key in self.done:
            return
        msg = VisionEvent()
        msg.scan_id, msg.approved, msg.reason = capture.scan_id, verdict == 'MATCH', reason[:500]
        msg.txn_id, msg.attempt, msg.action = capture.txn_id, capture.attempt, capture.action
        msg.barcode, msg.name = capture.barcode, (result.sku if result else capture.sku)
        msg.verdict, msg.verified, msg.detected = verdict, msg.approved, bool(capture.samples)
        if result:
            msg.appearance_score, msg.colour_score = float(result.score), float(result.colour)
        self.pub.publish(msg)
        self.remember(key)
        self.get_logger().info(f'{capture.scan_id} {msg.name}: {verdict} {msg.action}: {reason}')

    def tick(self):
        now = time.monotonic()
        if self.active and now-self.active.opened >= self.get_parameter('capture_seconds').value:
            self.finish_capture()
        for key, (capture, future, started, expired) in list(self.jobs.items()):
            if not expired and now-started > self.get_parameter('result_timeout').value:
                self.publish(capture, 'RETRY', 'Image inference deadline exceeded')
                future.cancel(); expired = True
                self.jobs[key] = capture, future, started, True
            if future.done():
                if not expired:
                    try:
                        result = future.result()
                        self.publish(capture, result.verdict, result.reason, result)
                    except Exception as exc:
                        self.publish(capture, 'UNAVAILABLE', f'Image verification failed: {exc}')
                del self.jobs[key]
        if now-self.last_health >= .5:
            stalled = any(expired and not future.done() for _,future,_,expired in self.jobs.values())
            msg = String()
            msg.data = json.dumps({'ready': self.detector.ready and now-self.last_frame_at < 1. and not stalled,
                'generation': self.boot_id+':'+str(self.camera_generation), 'backend': 'onnx', 'inflight': len(self.jobs)})
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
