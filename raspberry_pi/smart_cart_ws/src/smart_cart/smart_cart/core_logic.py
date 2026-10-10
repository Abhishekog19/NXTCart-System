"""Pi authority for cart state and checkout. Inference runs only on the PC."""
import json
import os
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from std_msgs.msg import String
from smart_cart_interfaces.msg import (ScannedItem, VisionEvent, CartItem, CartState,
    VerificationRequest, WeightSample, WeightExpectation, WeightVerdict)
from .catalog import Catalog
from .verification import Journal, VerificationLedger


def retained_qos():
    return QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                      reliability=ReliabilityPolicy.RELIABLE)


class CartVerificationEngine(Node):
    def __init__(self):
        super().__init__('core_logic_engine')
        defaults = {'catalog_path': os.path.expanduser('~/nxtcart/inventory.db'),
                    'state_path': os.path.expanduser('~/nxtcart/cart_state.db'),
                    'verification_timeout': 20.0, 'sensor_timeout': 2.5,
                    'noise_g': 5.0, 'empty_tolerance_g': 10.0,
                    'upi_payee': '', 'merchant_name': 'SmartCart'}
        for name, value in defaults.items():
            self.declare_parameter(name, value)
        p = lambda name: self.get_parameter(name).value
        self.catalog = Catalog(p('catalog_path'))
        Path(p('state_path')).parent.mkdir(parents=True, exist_ok=True)
        self.ledger = VerificationLedger(Journal(p('state_path')),
            timeout=p('verification_timeout'), sensor_timeout=p('sensor_timeout'),
            noise_g=p('noise_g'), empty_tolerance_g=p('empty_tolerance_g'))
        self.last_weight_stamp = None
        self.ui_pub = self.create_publisher(CartState, '/cart/ui_display', retained_qos())
        self.alert_pub = self.create_publisher(String, '/cart/alerts', 10)
        self.vision_pub = self.create_publisher(VerificationRequest, '/cart/verification_request', 50)
        self.expect_pub = self.create_publisher(WeightExpectation, '/cart/weight_expectation', 50)
        self.settled_pub = self.create_publisher(VerificationRequest, '/cart/placement_settled', 50)
        self.quote_pub = self.create_publisher(String, '/cart/checkout_quote', 10)
        self.create_subscription(ScannedItem, '/cart/scanned_item', self.scan_cb, 50)
        self.create_subscription(VisionEvent, '/cart/vision_event', self.vision_cb, 50)
        self.create_subscription(WeightSample, '/cart/weight_sample', self.weight_cb, 50)
        self.create_subscription(WeightVerdict, '/cart/weight_verdict', self.arduino_cb, 50)
        self.create_subscription(String, '/cart/vision_health', self.health_cb, 10)
        self.create_subscription(String, '/cart/scene_anomaly', self.anomaly_cb, 10)
        self.create_subscription(String, '/cart/remove_request', self.remove_cb, 10)
        self.create_subscription(String, '/cart/checkout_request', self.checkout_cb, 10)
        self.create_timer(0.25, self.tick)
        self.get_logger().info('Cart authority ready. Scans remain open; checkout requires both gates.')

    def alert(self, text):
        msg = String(); msg.data = text
        self.alert_pub.publish(msg)

    def scan_cb(self, msg):
        product = self.catalog.lookup(msg.barcode)
        if product is None:
            self.alert('Unknown product code. Ask staff to register this product.')
            return
        self.ledger.scan(msg.scan_id, product)
        self.flush_commands(); self.publish_cart_state()

    def weight_cb(self, msg):
        now = self.get_clock().now().to_msg()
        age = (now.sec-msg.stamp.sec) + (now.nanosec-msg.stamp.nanosec)/1e9
        if not -0.1 <= age <= 0.5:
            self.ledger.scale_gap()
            self.publish_cart_state()
            return
        if self.ledger.weight(msg.stream_id, msg.seq, msg.grams, msg.stable, msg.calibrated):
            self.last_weight_stamp = msg.stamp
            self.flush_commands(); self.publish_cart_state()

    def arduino_cb(self, msg):
        self.ledger.arduino_verdict(msg.txn_id, msg.delta_g, msg.passed)
        self.flush_commands(); self.publish_cart_state()

    def vision_cb(self, msg):
        if msg.scan_id:
            if msg.action == 'item_removed' and not msg.txn_id:
                # Unscanned motion identifies a possible removed SKU, but image
                # motion alone cannot authorize reducing the customer's bill.
                self.ledger.observation_gap('Unscanned removal candidate: ' + (msg.name or 'unknown product') + '; reconcile basket contents')
                self.publish_cart_state()
                return
            unit = next((u for u in self.ledger.units if
                (u.txn_id == msg.txn_id if msg.txn_id else u.scan_id == msg.scan_id)), None)
            if unit is None or msg.barcode != unit.barcode:
                return
            self.ledger.vision(unit.txn_id, msg.attempt, unit.sku, msg.verdict,
                               msg.approved, msg.reason, msg.action)
            self.flush_commands(); self.publish_cart_state()
            return
        self.ledger.vision(msg.txn_id, msg.attempt, msg.name, msg.verdict,
                           msg.verified, msg.reason, msg.action)
        self.flush_commands(); self.publish_cart_state()

    def health_cb(self, msg):
        try:
            data = json.loads(msg.data)
            self.ledger.heartbeat(data.get('ready') is True, data.get('generation'))
        except (ValueError, AttributeError):
            self.ledger.heartbeat(False)

    def remove_cb(self, msg):
        if not self.ledger.remove(msg.data):
            self.alert('Wait for the scale to settle. Select one unit before removing it. '
                       'For restart recovery, empty the cart first.')
        else:
            self.alert('Remove the selected unit, then wait for the weight check.')
        self.flush_commands(); self.publish_cart_state()

    def anomaly_cb(self, msg):
        self.ledger.observation_gap(msg.data[:300])
        self.publish_cart_state()

    def checkout_cb(self, msg):
        self.ledger.tick(); self.flush_commands()
        try:
            request = json.loads(msg.data)
            allowed = self.ledger.checkout_allowed and request.get('revision') == self.ledger.revision
            payee = self.get_parameter('upi_payee').value
            allowed = allowed and bool(payee)
            quote = {'allowed': allowed, 'request_id': request.get('request_id'),
                     'revision': self.ledger.revision,
                     'amount': round(sum(u.price for u in self.ledger.units), 2),
                     'payee': payee, 'merchant': self.get_parameter('merchant_name').value,
                     'reason': self.ledger.checkout_reason or ('Configure merchant UPI address' if not payee else 'Cart changed; try checkout again')}
            reply = String(); reply.data = json.dumps(quote)
            self.quote_pub.publish(reply)
        except (ValueError, AttributeError):
            self.alert('Invalid checkout request')

    def flush_commands(self):
        while self.ledger.commands:
            kind, u = self.ledger.commands.pop(0)
            if kind == 'expect':
                msg = WeightExpectation()
                msg.txn_id, msg.baseline_g = u.txn_id, self.ledger.anchor
                msg.expected_g, msg.tolerance_g = u.weight, u.tolerance
                self.expect_pub.publish(msg)
                continue
            msg = VerificationRequest()
            msg.scan_id = u.scan_id
            msg.txn_id, msg.attempt, msg.barcode, msg.sku = u.txn_id, u.attempt, u.barcode, u.sku
            msg.action = 'cancel' if kind == 'cancel' else u.action
            msg.started_at = (self.last_weight_stamp if kind == 'settled' and self.last_weight_stamp
                              else self.get_clock().now().to_msg())
            (self.settled_pub if kind == 'settled' else self.vision_pub).publish(msg)

    def tick(self):
        self.ledger.tick(); self.flush_commands(); self.publish_cart_state()
        if self.ledger.issue:
            self.alert(self.ledger.issue)

    def publish_cart_state(self):
        msg = CartState()
        msg.names = [u.name for u in self.ledger.units]
        msg.total_weight = float(self.ledger.latest)
        msg.total_price = float(round(sum(u.price for u in self.ledger.units), 2))
        msg.total_items, msg.revision = len(self.ledger.units), self.ledger.revision
        msg.checkout_allowed, msg.checkout_reason = self.ledger.checkout_allowed, self.ledger.checkout_reason
        for u in self.ledger.units:
            row = CartItem()
            row.barcode, row.name, row.sku, row.txn_id = u.barcode, u.name, u.sku, u.txn_id
            row.weight, row.price, row.quantity = float(u.weight), float(u.price), 1
            row.weight_status = 'FAIL' if u.action == 'add' and u.arduino_status == 'FAIL' else u.weight_status
            row.camera_status = u.camera_status
            row.status, row.reason = u.status, u.reason
            msg.items.append(row)
        self.ui_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args); node = CartVerificationEngine()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.ledger.journal.db.close(); node.destroy_node(); rclpy.shutdown()
