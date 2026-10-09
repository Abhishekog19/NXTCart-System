"""Serial bridge: no synthetic samples, no stale republishing, automatic reconnect."""
import queue
import threading
import time
import uuid
import serial
import rclpy
from rclpy.node import Node
from smart_cart_interfaces.msg import WeightSample, WeightVerdict, WeightExpectation
from .serial_protocol import parse_line


class ArduinoWeightNode(Node):
    def __init__(self):
        super().__init__('real_weight_node')
        self.declare_parameter('serial_port', '/dev/ttyACM0'); self.declare_parameter('baud_rate', 115200)
        self.pub = self.create_publisher(WeightSample, '/cart/weight_sample', 50)
        self.verdict_pub = self.create_publisher(WeightVerdict, '/cart/weight_verdict', 50)
        self.create_subscription(WeightExpectation, '/cart/weight_expectation', self.expect, 50)
        self.inbox, self.outbox = queue.Queue(maxsize=20), queue.Queue(maxsize=20)
        self.delivery_generation = uuid.uuid4().hex
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.read_loop, daemon=True); self.thread.start()
        self.create_timer(0.02, self.tick)

    def expect(self, msg):
        packet = f'E,{msg.txn_id},{msg.baseline_g:.3f},{msg.expected_g:.3f},{msg.tolerance_g:.3f}\n'
        try:
            self.outbox.put_nowait((time.monotonic(), packet.encode('ascii')))
        except queue.Full:
            self.get_logger().error('Arduino command queue full; verification will time out')

    def read_loop(self):
        while not self.stop.is_set():
            try:
                with serial.Serial(self.get_parameter('serial_port').value,
                                   self.get_parameter('baud_rate').value, timeout=0.1,
                                   write_timeout=0.2) as port:
                    stream = uuid.uuid4().hex; port.reset_input_buffer()
                    while not self.outbox.empty():
                        self.outbox.get_nowait()
                    previous_seq = -1
                    while not self.stop.is_set():
                        if not self.outbox.empty():
                            queued_at, command = self.outbox.get_nowait()
                            if time.monotonic()-queued_at <= 0.5:
                                port.write(command)
                        line = port.readline(256)
                        if not line:
                            continue
                        try:
                            packet = parse_line(line.decode('ascii'))
                            if packet[0] == 'sample':
                                if packet[1] <= previous_seq:
                                    stream = uuid.uuid4().hex
                                previous_seq = packet[1]
                            self.inbox.put_nowait((stream, packet, time.monotonic(), self.get_clock().now().to_msg()))
                        except queue.Full:
                            # Losing an observation invalidates continuity, even if
                            # subsequent samples arrive before the sensor timeout.
                            stream = uuid.uuid4().hex
                        except (ValueError, UnicodeError):
                            continue
            except (serial.SerialException, OSError) as exc:
                self.get_logger().error(f'Scale disconnected: {exc}'); self.stop.wait(2.0)

    def tick(self):
        while not self.inbox.empty():
            stream, packet, received_at, stamp = self.inbox.get_nowait()
            if time.monotonic()-received_at > 0.5:
                self.delivery_generation = uuid.uuid4().hex
                continue
            if packet[0] == 'sample':
                msg = WeightSample()
                msg.stream_id, msg.seq, msg.grams, msg.stable, msg.calibrated = stream+':'+self.delivery_generation, *packet[1:]
                msg.stamp = stamp; self.pub.publish(msg)
            else:
                msg = WeightVerdict(); msg.txn_id, msg.delta_g, msg.passed = packet[1:]
                self.verdict_pub.publish(msg)

    def destroy_node(self):
        self.stop.set(); self.thread.join(timeout=2.0); super().destroy_node()


def main(args=None):
    rclpy.init(args=args); node = ArduinoWeightNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node(); rclpy.shutdown()
