"""Pi USB camera: 640x480 BGR at 30 FPS, timestamped at capture, no inference."""
import math
import time
import uuid

import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError


class CameraStreamNode(Node):
    def __init__(self):
        super().__init__('verification_camera')
        for name, value in {'camera_source': '/dev/video2', 'fps': 30.0,
                            'width': 640, 'height': 480}.items():
            self.declare_parameter(name, value)
        src = str(self.get_parameter('camera_source').value)
        self.source = int(src) if src.isdigit() else src
        self.fps = float(self.get_parameter('fps').value)
        self.width, self.height = (self.get_parameter(k).value for k in ('width', 'height'))
        if not math.isfinite(self.fps) or not 5 <= self.fps <= 30:
            raise ValueError('fps must be between 5 and 30')
        if any(not isinstance(v, int) or not 8 <= v <= 1920 for v in (self.width, self.height)):
            raise ValueError('Camera dimensions must be integers in 8..1920')
        self.cap, self.last_open = None, -math.inf
        self.stream_id = uuid.uuid4().hex
        self.bridge = CvBridge()
        self.pub = self.create_publisher(Image, '/cart/camera/frame', qos_profile_sensor_data)
        self.create_timer(1.0/self.fps, self.tick)

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def tick(self):
        try:
            if self.cap is None or not self.cap.isOpened():
                if time.monotonic()-self.last_open < 2.0:
                    return
                self.release()
                self.last_open = time.monotonic()
                self.cap = cv2.VideoCapture(self.source, cv2.CAP_V4L2)
                if not self.cap.isOpened():
                    self.get_logger().error(f'Cannot open verification camera {self.source}')
                    self.release()
                    return
                for key, value in ((cv2.CAP_PROP_FRAME_WIDTH, self.width),
                                   (cv2.CAP_PROP_FRAME_HEIGHT, self.height),
                                   (cv2.CAP_PROP_FPS, self.fps),
                                   (cv2.CAP_PROP_BUFFERSIZE, 1)):
                    if not self.cap.set(key, value):
                        self.get_logger().warning(f'Camera driver did not accept property {key}={value}')
                self.stream_id = uuid.uuid4().hex
                self.get_logger().info(f'Camera opened: requested {self.width}x{self.height} at {self.fps} FPS; '
                                       f'driver reports {self.cap.get(cv2.CAP_PROP_FPS):.1f} FPS')
            ok, frame = self.cap.read()
            stamp = self.get_clock().now().to_msg()
            if not ok or frame is None:
                self.get_logger().error('Verification camera read failed; reconnecting')
                self.release()
                self.last_open = time.monotonic()
                return
            msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            msg.header.stamp = stamp
            msg.header.frame_id = 'verification_camera/' + self.stream_id
            self.pub.publish(msg)
        except (cv2.error, CvBridgeError, OSError, ValueError) as exc:
            self.get_logger().error(f'Camera stream error: {exc}')
            self.release()
            self.last_open = time.monotonic()

    def destroy_node(self):
        self.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = CameraStreamNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
