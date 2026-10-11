# PC foreground product verification

The current architecture and complete deployment checklist are in
[WEIGHT_TRIGGERED_VISION.md](../docs/WEIGHT_TRIGGERED_VISION.md).

The PC buffers 120 camera frames at 30 FPS. Only the Pi weight settlement event
triggers a dense burst from 400 ms before to 150 ms after settlement. Foreground
ROIs are extracted against a pre-entry baseline; full frames never enter ONNX.
MobileNetV2 compares each crop against every catalog SKU, requiring target top-1,
cosine >= 0.72 and margin >= 0.04. Confident alternate products are flagged as
swaps. Weight and checkout remain controlled by the Pi.

After rebuilding the PC workspace, run from the repository root:

```bash
bash pc/run_verifier.sh catalog_path:=/path/to/products.json preview:=true
```

Models and database default to `pc/ml/mobilenet_v2.onnx` and `pc/embedding_db.pkl`.
Debug full frames, ROIs and scores are retained in `pc/debug_frames/`, bounded to
100 transactions. Override the directory with `debug_dir:=/path/to/debug`.
Runtime assets and debug images are not committed. Historical geometric and API
comparison tools are development utilities; the live ROS node calls no cloud API.
