"""Legacy entry point intentionally refuses destructive dummy catalogue replacement."""
if __name__ == '__main__':
    raise SystemExit('Use raspberry_pi/import_catalog.py products.json --db ~/nxtcart/inventory.db. '
                     'This script no longer deletes inventory or inserts dummy prices.')
