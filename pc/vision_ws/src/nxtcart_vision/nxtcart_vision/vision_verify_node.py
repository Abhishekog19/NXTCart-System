#!/usr/bin/env python3
"""Weight-triggered ROS 2 image verification with a bounded rolling frame buffer.

Frames are collected continuously, including static and blurred views. Only the
Pi's transaction-bound placement_settled event starts ONNX inference. No motion
segmentation, geometric tracking or unscanned-motion removal inference is used.
"""
from collections import OrderedDict, deque
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


class VisionNode(Node):
    def __init__(self):
        super().__init__('pc_product_verifier')
        defaults = {
            'cam_root': '/home/vandan/NXTCart-System/pc',
            'model_path': '/home/vandan/NXTCart-System/pc/ml/mobilenet_v2.onnx',
            'database_path': '/home/vandan/NXTCart-System/pc/embedding_db.pkl',
            'catalog_path': '', 'embedding_layer': '', 'similarity_threshold': .65,
            'colour_threshold': .30, 'size_ratio_tolerance': 3., 'removal_margin': .03,
            'buffer_seconds': 3.0, 'buffer_max_frames': 90, 'min_samples': 1,
            'max_samples': 5, 'result_timeout': 6., 'max_inflight': 8,
            'settlement_timeout': 18.0, 'preview': False,
        }
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        p = lambda name: self.get_parameter(name).value
        for name in ('buffer_seconds', 'result_timeout', 'settlement_timeout'):
            if not math.isfinite(p(name)) or p(name) <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if not 1 <= p('min_samples') <= p('max_samples') <= 5 or p('max_inflight') < 1 or p('buffer_max_frames') < p('max_samples'):
            raise ValueError('Use 1..5 samples and a positive, sufficiently large buffer/queue')
        sys.path.insert(0, str(Path(p('cam_root')).expanduser()))
        from nxtcart_vision.local_matcher import LocalMatcher
        self.backend = LocalMatcher(p('model_path'), p('database_path'), p('catalog_path'),
            p('similarity_threshold'), p('colour_threshold'), p('size_ratio_tolerance'),
            p('removal_margin'), p('embedding_layer'))
        self.bridge = CvBridge()
        self.pub = self.create_publisher(VisionEvent, '/cart/vision_event', 50)
        self.health_pub = self.create_publisher(String, '/cart/vision_health', 10)
        self.anomaly_pub = self.create_publisher(String, '/cart/scene_anomaly', 10)
        self.create_subscription(Image, '/cart/camera/frame', self.frame,
            QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT))
        self.create_subscription(ScannedItem, '/cart/scanned_item', self.scan, 50)
        self.create_subscription(VerificationRequest, '/cart/verification_request', self.request, 50)
        self.create_subscription(VerificationRequest, '/cart/placement_settled', self.settled, 50)
        self.inference_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='onnx-verification')
        self.pending, self.jobs, self.done = {}, {}, OrderedDict()
        self.frames = deque(maxlen=p('buffer_max_frames'))
        self.last_frame_at = self.last_health = -math.inf
        self.stamp_ns, self.camera_generation = None, None
        self.boot_id = uuid.uuid4().hex
        self.create_timer(.05, self.tick)
        self.get_logger().info(f'Weight-triggered ONNX verification ready: {len(self.backend.products)} products')

    @staticmethod
    def key(capture):
        return capture.txn_id or capture.scan_id, capture.attempt

    def seen(self, key):
        return key in self.done or key in self.jobs or key in self.pending

    def remember(self, key):
        self.done[key] = None
        self.done.move_to_end(key)
        while len(self.done) > 4096:
            self.done.popitem(last=False)

    def scan(self, msg):
        # The Pi's VerificationRequest supplies authoritative SKU and attempt.
        # A barcode scan alone must never start inference.
        pass

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
            if key in self.jobs:
                c, future, started, _ = self.jobs[key]
                future.cancel()
                self.jobs[key] = c, future, started, True
            self.remember(key)
        elif msg.action in ('add', 'remove') and not self.seen(key):
            if len(self.pending) >= self.get_parameter('max_inflight').value:
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
        if key in self.done or key in self.jobs:
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
        # Camera and settlement timestamps both originate on the Pi. Limit the
        # snapshot to the physical landing, never a subsequent item's frames.
        eligible = [frame for received, stamp, frame in self.frames
                    if end - int(horizon * 1e9) <= stamp <= end]
        count = min(len(eligible), self.get_parameter('max_samples').value)
        if count:
            indexes = [round(i * (len(eligible)-1) / (count-1)) for i in range(count)] if count > 1 else [len(eligible)-1]
            capture.samples = [[eligible[i]] for i in indexes]
        if len(capture.samples) < self.get_parameter('min_samples').value:
            self.publish(capture, 'RETRY', 'No usable buffered frames before settlement; check camera stream and timestamps')
        elif len(self.jobs) >= self.get_parameter('max_inflight').value:
            self.publish(capture, 'RETRY', 'Image verification queue full')
        else:
            self.get_logger().info(f'{capture.txn_id} attempt {capture.attempt}: weight settled; verifying {len(capture.samples)} buffered frames')
            future = self.inference_pool.submit(self.backend.verify, capture.sku, capture.samples)
            self.jobs[key] = capture, future, now, False

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
            self.frames.clear()
            for capture in list(self.pending.values()):
                self.publish(capture, 'RETRY', 'Camera restarted while waiting for weight settlement')
            self.pending.clear()
            for key, (capture, future, started, expired) in list(self.jobs.items()):
                self.publish(capture, 'RETRY', 'Camera restarted during verification')
                future.cancel()
                self.jobs[key] = capture, future, started, True
            warning = String(); warning.data = 'Verification camera restarted; reconcile basket contents'
            self.anomaly_pub.publish(warning)
        self.camera_generation, self.stamp_ns, self.last_frame_at = generation, stamp, now
        # Bound memory on a long-running cart; make a copy so cv_bridge/preview
        # cannot mutate evidence retained by the inference worker.
        if frame.shape[1] > 640:
            frame = cv2.resize(frame, (640, max(8, round(frame.shape[0]*640/frame.shape[1]))))
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
        self.prune_frames(now)
        for key, capture in list(self.pending.items()):
            if now-capture.opened > self.get_parameter('settlement_timeout').value:
                self.pending.pop(key)
                self.publish(capture, 'RETRY', 'Weight settlement not received before deadline')
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
            msg.data = json.dumps({'ready': bool(self.frames) and now-self.last_frame_at < 1. and not stalled,
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
