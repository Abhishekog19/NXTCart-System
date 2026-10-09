"""Validate first, then upsert measured product data without erasing inventory."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/'smart_cart_ws'/'src'/'smart_cart'))
from smart_cart.catalog import import_catalog

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('json_path')
    parser.add_argument('--db', default=str(Path.home()/'nxtcart'/'inventory.db'))
    args = parser.parse_args()
    import_catalog(args.json_path, args.db)
    print(f'Validated catalogue imported into {args.db}')
