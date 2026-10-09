"""Hardware-independent, persistent per-unit verification. No camera inference here.

Only the current transaction's two PASS results can produce green. Shopping
continues through failures; payment always requires a fresh, reconciled scale.
One physical placement at a time is provable with one aggregate load cell.
Overlapping unsettled placements are explicitly ambiguous, never guessed.
"""
import json
import math
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass


@dataclass
class Unit:
    txn_id: str
    barcode: str
    name: str
    sku: str
    weight: float
    price: float
    tolerance: float
    created: float
    weight_status: str = 'PENDING'
    camera_status: str = 'PENDING'
    reason: str = ''
    measured_g: float = 0.0
    action: str = 'add'
    attempt: int = 1
    arduino_status: str = 'PENDING'
    awaiting_weight: bool = True

    @property
    def status(self):
        if self.action == 'remove':
            return 'FLAGGED' if 'FAIL' in (self.weight_status, self.camera_status) else 'REMOVING'
        if 'FAIL' in (self.weight_status, self.camera_status, self.arduino_status):
            return 'FLAGGED'
        if self.weight_status == self.camera_status == 'PASS':
            return 'VERIFIED'
        return 'VERIFYING'


class Journal:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at REAL, event TEXT, payload TEXT)')

    def load(self):
        row = self.db.execute('SELECT payload FROM state WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None

    def save(self, state, event):
        payload = json.dumps(state, allow_nan=False)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO state VALUES (1,?)', (payload,))
            self.db.execute('INSERT INTO audit(at,event,payload) VALUES (?,?,?)',
                            (time.time(), event, payload))


class VerificationLedger:
    def __init__(self, journal, clock=time.monotonic, timeout=20.0, sensor_timeout=2.5,
                 noise_g=5.0, empty_tolerance_g=10.0, max_units=200):
        self.journal, self.clock = journal, clock
        self.timeout, self.sensor_timeout, self.noise_g = timeout, sensor_timeout, noise_g
        self.empty_tolerance_g, self.max_units = empty_tolerance_g, max_units
        saved = journal.load() or {}
        self.units = [Unit(**u) for u in saved.get('units', [])]
        self.seen_scans = set(saved.get('seen_scans', []))
        self.revision = saved.get('revision', 0)
        self.anchor = saved.get('anchor', 0.0)
        self.latest = self.anchor
        self.last_weight_at = -math.inf
        self.scale_stable = False
        self.calibrated = False
        self.stream = None
        self.seq = -1
        self.ready = False
        self.issue = saved.get('issue', '')
        self.pc_at = -math.inf
        self.pc_ok = False
        self.pc_generation = None
        self.recovery = bool(self.units or saved.get('issue'))
        self.commands = []
        # A restart must never resurrect an unfinished transaction as green.
        for u in self.units:
            if u.status != 'VERIFIED':
                u.weight_status = u.camera_status = 'FAIL'
                u.reason = 'Interrupted verification: remove this unit and scan again'
                u.action = 'add'
                u.awaiting_weight = False

    def commit(self, event):
        self.revision += 1
        self.journal.save({'units': [asdict(u) for u in self.units],
                           'seen_scans': sorted(self.seen_scans), 'anchor': self.anchor,
                           'revision': self.revision, 'issue': self.issue}, event)

    def observation_gap(self, reason):
        if not self.units or self.recovery:
            return
        self.recovery, self.ready, self.issue = True, False, reason
        for u in self.units:
            u.camera_status, u.reason = 'FAIL', reason
        self.commit('observation_gap')

    def scale_gap(self):
        if not self.units or self.recovery:
            return
        self.recovery, self.ready = True, False
        self.issue = 'Scale interrupted: empty the cart and select Remove to reconcile'
        for u in self.units:
            u.weight_status, u.awaiting_weight, u.reason = 'FAIL', False, self.issue
        self.commit('scale_gap')

    def heartbeat(self, ok=True, generation=None):
        changed = generation and self.pc_generation and generation != self.pc_generation
        if changed or (self.pc_ok and (not ok or self.clock()-self.pc_at >= self.sensor_timeout)):
            self.observation_gap('Camera observation interrupted: empty the cart and select Remove to reconcile')
        if generation:
            self.pc_generation = generation
        self.pc_at, self.pc_ok = self.clock(), bool(ok)

    def scan(self, scan_id, product):
        self.tick()
        if not scan_id or scan_id in self.seen_scans:
            return None
        if len(self.units) >= self.max_units:
            self.issue = 'Cart capacity reached; remove items before adding more'
            self.commit('capacity')
            return None
        self.seen_scans.add(scan_id)
        u = Unit(uuid.uuid4().hex, product.barcode, product.name, product.sku,
                 product.expected_weight, product.price, product.tolerance_g, self.clock())
        self.units.append(u)
        if not self.sensor_ok or not self.ready:
            u.weight_status = 'FAIL'
            u.awaiting_weight = False
            u.reason = 'Scale unavailable or not ready; remove this unit and scan again'
        if any(v.action == 'remove' for v in self.units):
            u.weight_status = 'FAIL'
            u.awaiting_weight = False
            u.reason = 'Placement overlapped a removal; remove this unit and scan again'
        pending = [v for v in self.units if v.awaiting_weight and v.action == 'add']
        if len(pending) > 1:
            for v in pending:
                v.weight_status = 'FAIL'
                v.awaiting_weight = False
                v.reason = 'Overlapping placements: scale cannot assign weight to individual items'
            self.issue = 'Overlapping placements; remove flagged units and scan individually'
        else:
            if u.weight_status == 'PENDING':
                self.commands.append(('expect', u))
        self.commands.append(('vision', u))
        self.commit('scan')
        return u

    @property
    def sensor_ok(self):
        return self.calibrated and self.clock() - self.last_weight_at < self.sensor_timeout

    def weight(self, stream, seq, grams, stable, calibrated):
        if not math.isfinite(grams) or not stream or (stream == self.stream and seq <= self.seq):
            return False
        self.tick()
        now = self.clock()
        restarted = self.stream is not None and self.stream != stream
        was_fresh = self.sensor_ok
        self.stream, self.seq = stream, seq
        self.latest, self.last_weight_at = grams, now
        self.calibrated, self.scale_stable = bool(calibrated), bool(stable)
        if restarted or (not was_fresh and self.ready):
            self.scale_gap()
            self.ready = False
            self.recovery = True
            self.issue = 'Scale reconnected: remove all units to reconcile the empty cart'
            for u in self.units:
                if u.weight_status == 'PENDING':
                    u.weight_status = 'FAIL'
                    u.reason = self.issue
            self.commit('scale_reconnect')
        if not calibrated or not stable:
            return True
        if not self.ready:
            # Never silently tare a loaded cart or adopt a nonzero startup load.
            if abs(grams) <= self.empty_tolerance_g and not self.units:
                self.ready, self.recovery, self.issue, self.anchor = True, False, '', grams
                self.commit('empty_scale_ready')
            elif self.units and not self.recovery:
                self.issue = 'Cart must be empty at initial startup'
            return True
        delta = grams - self.anchor
        if abs(delta) <= self.noise_g:
            if not self.units and abs(grams) <= self.empty_tolerance_g and self.issue:
                self.issue = ''
                self.commit('empty_reconciled')
            return True
        accounted = sum(u.measured_g for u in self.units)
        if self.issue.startswith('Unassigned weight') and not any(u.awaiting_weight or u.action == 'remove' for u in self.units) and abs(grams-accounted) <= self.empty_tolerance_g:
            self.anchor, self.issue = grams, ''
            self.commit('unexpected_mass_restored')
            return True
        removes = [u for u in self.units if u.action == 'remove']
        pending = [u for u in self.units if u.action == 'add' and u.awaiting_weight]
        if removes:
            u = removes[0]
            expected = -(u.measured_g or u.weight)
            if u.weight_status == 'PENDING' and abs(delta - expected) <= u.tolerance and delta < -self.noise_g:
                u.weight_status = 'PASS'
                self.anchor = grams
                self.commands.append(('settled', u))
                self.finish_removal(u)
                self.commit('removal_weight')
            else:
                u.weight_status = 'FAIL'
                self.recovery, self.ready = True, False
                self.issue = 'Unexpected change during removal: empty the cart and select Remove to reconcile'
                u.reason = self.issue
                self.commit('removal_mismatch')
            return True
        if len(pending) == 1 and delta > self.noise_g:
            u = pending[0]
            u.measured_g = delta
            u.awaiting_weight = False
            u.weight_status = ('PASS' if u.arduino_status == 'PASS' else 'CHECKING') if abs(delta - u.weight) <= u.tolerance else 'FAIL'
            if u.arduino_status == 'FAIL':
                u.weight_status = 'FAIL'
            if u.weight_status == 'FAIL':
                u.reason = f'Weight mismatch: expected {u.weight:.1f} g, measured {delta:.1f} g'
            # Advance physical baseline even on a failure, so later shopping works.
            self.anchor = grams
            self.commands.append(('settled', u))
            self.commit('weight_' + u.weight_status.lower())
        else:
            self.issue = f'Unassigned weight change ({delta:+.1f} g); reconcile cart before payment'
            # Do not assign this evidence to a future scan.
            self.anchor = grams
            self.commit('unassigned_weight')
        return True

    def arduino_verdict(self, txn_id, delta_g, passed):
        self.tick()
        # Independent guard: Arduino may veto a Pi pass, never override a failure.
        u = next((v for v in self.units if v.txn_id == txn_id and v.action == 'add'), None)
        if u and u.arduino_status != 'FAIL' and (u.awaiting_weight or u.weight_status == 'CHECKING'):
            u.arduino_status = 'PASS' if passed and math.isfinite(delta_g) and abs(delta_g-u.weight) <= u.tolerance else 'FAIL'
            if u.arduino_status == 'FAIL':
                u.weight_status = 'FAIL'
                u.reason = 'Arduino weight mismatch; remove this unit and scan again'
            elif u.weight_status == 'CHECKING':
                u.weight_status = 'PASS'
            self.commit('arduino_verdict')

    def vision(self, txn_id, attempt, sku, verdict, verified, reason, action='item_placed'):
        self.tick()
        u = next((v for v in self.units if v.txn_id == txn_id), None)
        if not u or u.attempt != attempt or u.camera_status != 'PENDING':
            return False
        if sku != u.sku or action != ('item_removed' if u.action == 'remove' else 'item_placed'):
            return False
        u.camera_status = 'PASS' if verdict == 'MATCH' and verified else 'FAIL'
        if u.camera_status == 'FAIL':
            u.reason = reason or 'Camera could not verify this product'
            if u.action == 'remove':
                self.recovery, self.ready = True, False
                self.issue = 'Removal identity uncertain: empty the cart and select Remove to reconcile'
        if u.action == 'remove':
            self.finish_removal(u)
        self.commit('camera_' + u.camera_status.lower())
        return True

    def finish_removal(self, u):
        if u.action == 'remove' and u.weight_status == u.camera_status == 'PASS':
            self.units.remove(u)
            self.clear_capacity_issue()
            if not self.units and abs(self.latest) <= self.empty_tolerance_g:
                self.issue = ''

    def clear_capacity_issue(self):
        if len(self.units) < self.max_units and self.issue == 'Cart capacity reached; remove items before adding more':
            self.issue = ''

    def remove(self, txn_id):
        self.tick()
        u = next((v for v in self.units if v.txn_id == txn_id), None)
        if not u:
            return False
        if self.recovery:
            if self.sensor_ok and self.scale_stable and abs(self.latest) <= self.empty_tolerance_g:
                for old in self.units:
                    self.commands.append(('cancel', old))
                self.units.clear()
                self.ready, self.recovery, self.issue, self.anchor = True, False, '', self.latest
                self.commit('recovery_empty')
                return True
            return False
        if any(v.action == 'remove' for v in self.units):
            return False
        # Removing a scan that never landed is safe only with a stable reconciled scale.
        if not u.measured_g and self.sensor_ok and self.scale_stable and abs(self.latest-self.anchor) <= self.noise_g:
            if u.weight_status != 'PASS':
                self.units.remove(u)
                self.clear_capacity_issue()
                self.commands.append(('cancel', u))
                self.commit('cancel_unplaced')
                return True
        if any(v.awaiting_weight or v.weight_status in ('PENDING', 'CHECKING') for v in self.units if v is not u):
            return False
        if not self.sensor_ok or not self.scale_stable:
            return False
        u.action, u.created = 'remove', self.clock()
        u.attempt += 1
        u.weight_status = u.camera_status = 'PENDING'
        u.awaiting_weight = False
        u.reason = ''
        self.commands.append(('vision', u))
        self.commit('remove_requested')
        return True

    def tick(self):
        if self.ready and not self.sensor_ok:
            self.scale_gap()
        if self.pc_ok and self.clock()-self.pc_at >= self.sensor_timeout:
            self.pc_ok = False
            self.observation_gap('PC disconnected: empty the cart and select Remove to reconcile')
        changed = False
        for u in self.units:
            if self.clock()-u.created <= self.timeout:
                continue
            if u.action == 'remove' and (u.weight_status == 'PENDING' or u.camera_status == 'PENDING'):
                u.weight_status = u.camera_status = 'FAIL'
                u.reason = 'Removal timed out; empty the cart and select Remove to reconcile'
                self.recovery, self.ready = True, False
                self.issue = u.reason
                self.commands.append(('cancel', u))
                changed = True
            elif u.awaiting_weight or u.weight_status in ('PENDING', 'CHECKING') or u.camera_status == 'PENDING':
                if u.weight_status in ('PENDING', 'CHECKING'):
                    u.weight_status = 'FAIL'
                u.awaiting_weight = False
                if u.camera_status == 'PENDING':
                    u.camera_status = 'FAIL'
                u.reason = u.reason or 'Verification timed out; remove this unit and scan again'
                self.commands.append(('cancel', u))
                changed = True
        if changed:
            self.commit('timeout')

    @property
    def checkout_reason(self):
        if not self.units:
            return 'Cart is empty'
        if not self.ready or self.recovery:
            return 'Scale recovery: empty the cart and select Remove to reconcile'
        if not self.sensor_ok or not self.scale_stable:
            return 'Waiting for a fresh stable scale reading'
        if not self.pc_ok or self.clock()-self.pc_at > self.sensor_timeout:
            return 'Camera verification service unavailable'
        if self.issue:
            return self.issue
        if any(u.status != 'VERIFIED' for u in self.units):
            return 'Every item must pass weight and camera verification before payment'
        expected = sum(u.measured_g for u in self.units)
        if abs(self.latest-expected) > self.empty_tolerance_g:
            return 'Cart weight is not reconciled with verified items'
        return ''

    @property
    def checkout_allowed(self):
        return not self.checkout_reason
