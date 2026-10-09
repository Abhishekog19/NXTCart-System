"""Authoritative catalogue shared by the scanner and the Pi coordinator."""
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager, closing


@dataclass(frozen=True)
class Product:
    barcode: str
    name: str
    expected_weight: float
    price: float
    sku: str
    tolerance_g: float


def validate(row):
    p = Product(str(row['barcode']), str(row['name']), float(row['expected_weight']),
                float(row['price']), str(row['sku']), float(row['tolerance_g']))
    if not p.barcode or not p.name or not p.sku or p.sku in ('.', '..') or any(c in p.sku for c in '/\\'):
        raise ValueError('barcode, name and a single reference-folder SKU are required')
    if not all(math.isfinite(x) for x in (p.expected_weight, p.price, p.tolerance_g)):
        raise ValueError('catalogue contains non-finite values')
    if p.expected_weight <= 0 or p.price <= 0 or not 0 < p.tolerance_g < p.expected_weight:
        raise ValueError('set measured gross weight, real price and a smaller positive tolerance')
    return p


class Catalog:
    def __init__(self, path):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f'Import your product catalogue first: {self.path}')
        with self.connect() as db:
            for row in db.execute('SELECT * FROM items'):
                validate(row)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(f'{self.path.as_uri()}?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def lookup(self, barcode):
        with self.connect() as db:
            row = db.execute('SELECT * FROM items WHERE barcode=?', (barcode,)).fetchone()
            return validate(row) if row else None


def import_catalog(source, destination):
    rows = json.loads(Path(source).read_text(encoding='utf-8'))
    if not isinstance(rows, list) or not rows:
        raise ValueError('catalogue must be a nonempty JSON array')
    products = [validate(row) for row in rows]
    if len({p.barcode for p in products}) != len(products):
        raise ValueError('duplicate barcode')
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(destination)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS items (barcode TEXT PRIMARY KEY, name TEXT, expected_weight REAL)')
        columns = {r[1] for r in db.execute('PRAGMA table_info(items)')}
        for name, kind in [('price', 'REAL'), ('sku', 'TEXT'), ('tolerance_g', 'REAL')]:
            if name not in columns:
                db.execute(f'ALTER TABLE items ADD COLUMN {name} {kind}')
        for p in products:
            db.execute('INSERT INTO items (barcode,name,expected_weight,price,sku,tolerance_g) '
                       'VALUES (?,?,?,?,?,?) ON CONFLICT(barcode) DO UPDATE SET '
                       'name=excluded.name,expected_weight=excluded.expected_weight,price=excluded.price,'
                       'sku=excluded.sku,tolerance_g=excluded.tolerance_g',
                       (p.barcode, p.name, p.expected_weight, p.price, p.sku, p.tolerance_g))
