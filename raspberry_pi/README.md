# Raspberry Pi runtime

This folder owns both USB webcams, QR scanning, image transport, Arduino serial
communication, catalogue, durable cart state, touchscreen and checkout gating.
It does not run ML models or API calls.

Follow [the setup guide](../docs/SYSTEM_SETUP.md), then run
`bash raspberry_pi/run_cart.sh` from the repository root with your device paths.
Import measured product data using `python raspberry_pi/import_catalog.py
products.json --db ~/nxtcart/inventory.db`. Replace all example catalogue values
with real measurements and prices.

`smart_cart_ws/src/smart_cart_interfaces/` is the canonical ROS contract. Run
`python scripts/sync_interfaces.py` after message edits and rebuild both hosts.
Launch one cart authority only.
