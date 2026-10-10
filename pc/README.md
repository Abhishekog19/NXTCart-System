> Current architecture: [weight-triggered rolling buffer](../docs/WEIGHT_TRIGGERED_VISION.md). This supersedes motion-triggered capture instructions below.

# PC full-frame image verification

Start with [LENIENT_VISION_SETUP.md](../docs/LENIENT_VISION_SETUP.md).
The active node is `vision_ws/src/nxtcart_vision/nxtcart_vision/vision_verify_node.py`.
It consumes `sensor_msgs/Image` through cv_bridge and scans through ScannedItem,
collects 3–5 motion frames without geometric tracking, and compares crops using
local MobileNetV2 ONNX. Any matching view can approve the camera gate.

From the repository root after rebuilding both ROS workspaces:

```bash
bash pc/run_verifier.sh catalog_path:=/path/to/products.json preview:=true
```

The model and database default to `pc/ml/mobilenet_v2.onnx` and
`pc/embedding_db.pkl` through the launcher. Catalogue mapping is optional only
when the database already resolves scanner barcodes. Colour and apparent-size
metadata are used when available. The Pi owns cart state, weight and checkout.

Historical geometric tracking, retired tests and prior one-off patch scripts
are retained in `legacy/`; do not apply those patches to the current node.
AI comparison/dataset tools remain development utilities; no API is called by
the live ROS node. Capture references in `pc/references/<sku>/` and use
`build_db.py` from `pc/` to rebuild an ONNX-stamped database when needed.
