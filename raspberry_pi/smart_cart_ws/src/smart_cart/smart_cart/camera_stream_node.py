"""Opposite USB webcam: sensor_msgs/Image transport, with no ML on the Pi."""
import time
import uuid
import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class CameraStreamNode(Node):
    def __init__(self):
        super().__init__('verification_camera')
        for name, value in {'camera_source': '/dev/video2', 'fps': 15.0, 'width': 640,
                            'height': 480}.items():
            self.declare_parameter(name, value)
        src = str(self.get_parameter('camera_source').value)
        self.source = int(src) if src.isdigit() else src
        self.cap, self.last_open, self.seq = None, -100.0, 0
        self.stream_id = uuid.uuid4().hex
        self.bridge = CvBridge()
        self.pub = self.create_publisher(Image, '/cart/camera/frame', qos_profile_sensor_data)
        fps = float(self.get_parameter('fps').value)
        if not 5 <= fps <= 30:
            raise ValueError('fps must be between 5 and 30')
        self.create_timer(1.0/fps, self.tick)

    def tick(self):
        if self.cap is None or not self.cap.isOpened():
            if time.monotonic()-self.last_open < 2.0:
                return
            self.last_open = time.monotonic()
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_V4L2)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.get_parameter('width').value)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.get_parameter('height').value)
            self.cap.set(cv2.CAP_PROP_FPS, self.get_parameter('fps').value)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.stream_id, self.seq = uuid.uuid4().hex, 0
        ok, frame = self.cap.read(); stamp = self.get_clock().now().to_msg()
        if not ok:
            self.cap.release(); return
        self.seq += 1
        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = stamp
        msg.header.frame_id = 'verification_camera/' + self.stream_id
        self.pub.publish(msg)

    def destroy_node(self):
        if self.cap:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args); node = CameraStreamNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()
