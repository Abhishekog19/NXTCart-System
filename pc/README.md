# PC image verification

This folder is the PC deployment unit. `vision_ws/` receives camera frames and
transactions through ROS 2. `ml/` tracks the image journey, selects clear crops
and compares them against the scanned SKU's references. Cart state, prices,
weight acceptance, QR scanning, display and checkout belong to the Pi.

Follow [the setup guide](../docs/SYSTEM_SETUP.md), then run from the repo root:

```bash
bash pc/run_verifier.sh backend:=local
```

For an API choose `backend:=ai`, `ai_model` and `ai_base_url`, keeping credentials
in the PC environment. The launcher sets `NXTCART_CAM_PATH` to this folder.

References belong in `pc/references/<sku>/`. From `pc/`, run `python build_db.py`
and `python preflight.py /path/to/products.json --backend local`.

Demos and `ml/lane.py`, `ml/cart.py` and related modules are retained research
utilities. Their experimental cart logic is not launched by the ROS service.
`legacy/test_cart_logic.py` targets an earlier Pi contract and is excluded from
the current runner. Historical documents are in `docs/`; the authoritative
integrated workflow is [../docs/SYSTEM_SETUP.md](../docs/SYSTEM_SETUP.md).
