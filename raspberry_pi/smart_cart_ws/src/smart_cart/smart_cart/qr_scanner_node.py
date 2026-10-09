"""Handle webcam: QR and barcode scans; re-arm after code leaves view."""
import time
import uuid
import cv2
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from pyzbar.pyzbar import decode
from smart_cart_interfaces.msg import ScannedItem
from .scan_gate import ScanGate


class QRScannerNode(Node):
    def __init__(self):
        super().__init__('qr_scanner_node')
        self.declare_parameter('camera_source', '/dev/video0')
        self.declare_parameter('rearm_seconds', 0.8)
        src = str(self.get_parameter('camera_source').value)
        self.source = int(src) if src.isdigit() else src
        self.cap, self.last_open = None, -100.0
        self.gate = ScanGate(self.get_parameter('rearm_seconds').value)
        self.pub = self.create_publisher(ScannedItem, '/cart/scanned_item', 50)
        self.alert_pub = self.create_publisher(String, '/cart/alerts', 10)
        self.create_timer(0.1, self.scan_loop)

    def scan_loop(self):
        now = time.monotonic()
        if self.cap is None or not self.cap.isOpened():
            self.gate.gap()
            if now-self.last_open < 2.0:
                return
            self.last_open = now
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_V4L2)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok, frame = self.cap.read()
        if not ok:
            self.gate.gap()
            self.cap.release(); return
        codes = set()
        for obj in decode(frame):
            try:
                value = obj.data.decode('utf-8').strip()
                if value and len(value) <= 128:
                    codes.add(value)
            except UnicodeDecodeError:
                continue
        accepted = self.gate.observe(codes, now)
        if len(codes) > 1:
            alert = String(); alert.data = 'Present one product code at a time'
            self.alert_pub.publish(alert)
            return
        if accepted:
            msg = ScannedItem(); msg.barcode = accepted; msg.scan_id = uuid.uuid4().hex
            self.pub.publish(msg)

    def destroy_node(self):
        if self.cap:
            self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args); node = QRScannerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()
