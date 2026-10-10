> Current architecture: [weight-triggered rolling buffer](WEIGHT_TRIGGERED_VISION.md). This supersedes motion-triggered capture instructions below.

# Full-frame local ONNX verification

This is the current PC vision workflow, replacing geometric scan/cart zones.
The Pi owns cart state, weight and payment gating; the PC processes images only.
The rewrite is based on collaborator commit `4777e1b`.

## Behavior

The PC subscribes to `/cart/scanned_item` (`ScannedItem`) and
`/cart/camera/frame` (`sensor_msgs/msg/Image`, BGR8 via `cv_bridge`). MOG2 runs
over the entire image, removes its shadow-labelled pixels and finds foreground
contours. Several contours produce individual colour-prominent crops and a union
crop. Neither multiple regions nor a growing region is an error. There are no
scan/cart boxes, no per-frame identity association and no required visible path.

After a scan, sample up to five distinct motion frames, at least 0.08 seconds
apart, within 2.5 seconds. At least three frames are needed. Brief missing or
blurred views do not cancel the collection. One crop in any sampled frame may
approve the image gate when its cosine similarity reaches 0.65 and any available
colour/aspect-ratio metadata agrees. No settled-weight event or API is awaited.
The Pi still independently requires the correct weight and the Arduino verdict.

This deliberately lenient any-view policy can accept an earlier correct view
even if something changes while the product is hidden. It verifies sampled
appearance; it cannot prove uninterrupted identity through cardboard occlusion.
Use genuine placements and wrong-product swaps to tune the similarity threshold.
Colour prominence helps select crops but does not reliably segment human hands.

Without a recent scan, a new motion episode is treated as a removal candidate.
The PC compares its crops against all database SKUs and publishes `item_removed`
with the identified SKU (or a non-accepting result). A quiet interval re-arms
this detector to avoid repeated events for the same movement. Motion does not
establish direction: the Pi flags unrequested removal candidates for physical
reconciliation; it never silently discounts a row. Pi-selected removals retain
their transaction ID/attempt and require a matching negative weight step.

## One-time migration on BOTH hosts

Stop both launches before changing message types. Do not run the old JPEG
publisher and the new Image publisher on the same topic.

```bash
cd ~/NXTCart-System
git pull --ff-only
sudo apt update
sudo apt install ros-jazzy-cv-bridge ros-jazzy-sensor-msgs python3-opencv python3-numpy
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

Pi build (the wrapper uses `install-v2`):

```bash
cd ~/NXTCart-System/raspberry_pi/smart_cart_ws
colcon --log-base log-v2 build --build-base build-v2 --install-base install-v2 --symlink-install
```

PC build:

```bash
cd ~/NXTCart-System/pc/vision_ws
colcon build --symlink-install
```

Open fresh terminals and source the new workspaces through the launch wrappers.
`VisionEvent` now includes `scan_id` and `approved`; existing action, attempt,
transaction and score fields are retained. `VerificationRequest` also includes
`scan_id` so the Pi can cancel a pending direct-scan request. The two copies of
the interface package must match; run `python3 scripts/sync_interfaces.py` after
future schema changes, then rebuild BOTH hosts.

Raw BGR8 at 640x480 and 15 fps is approximately 13.8 MB/s (111 Mb/s) before DDS
overhead. This is heavier than JPEG. Use adequate Wi-Fi or a wired test link;
reduce the Pi camera's `width`, `height`, and `fps` parameters when necessary.
The PC uses best-effort depth-one image reception and tolerates dropped frames.

## Model and database

The standalone node defaults to exactly:

```text
/home/vandan/NXTCart-System/pc/ml/mobilenet_v2.onnx
/home/vandan/NXTCart-System/pc/embedding_db.pkl
```

The launch wrapper derives these paths from its own `pc/` folder, so other
usernames/checkout locations work. Override `model_path`, `database_path`, or
`embedding_layer` when needed. The model is loaded with `cv2.dnn.readNetFromONNX`
and runs on CPU. The classifier's 1000-class output is not used: the loader finds
a 1280-value pooling output. Preprocessing matches `build_db.py`: BGR to RGB,
224x224, divide by 255, ImageNet mean/std normalization, NCHW, L2 normalize.

Supported trusted-local pickle formats:

```python
# Existing build_db.py wrapper (compatible without a rebuild if ONNX-stamped):
{"backend": "onnx-mbv2-1280", "dim": 1280,
 "products": {"instant_noodles": [embedding_1280, ...]},
 "colours": {"instant_noodles": [histogram_80, ...]}, "colour_format": 2}

# Plain mapping; vectors must have been built with the SAME ONNX preprocessing:
{"8901234567890": [embedding_1280, ...]}

# Mapping with optional explicit metadata:
{"instant_noodles": {
    "embeddings": [embedding_1280, ...],
    "barcode": "8901234567890", "name": "Instant noodles",
    "expected_size": [120, 80],       # width,height in reference crop pixels
    "expected_color_bgr": [30, 180, 220],
    "color_histograms": [histogram_80, ...]
}}
```

Size comparison uses orientation-independent aspect ratio with a configurable
3x tolerance. A single uncalibrated camera cannot determine physical dimensions
from pixels. Colour/size checks apply only when that metadata exists; the code
does not invent missing sizes. Invalid/nonfinite/zero embeddings and incompatible
backend stamps fail startup. Only load pickle files you generated/trust.

If the database is keyed by SKU names but QR codes are numeric barcodes, supply
the SAME measured catalogue JSON used on the Pi using `catalog_path`. This maps
`barcode` to `sku` without relying on an empty scanner `name` field. Embeddings
may also use the barcode as the database key directly.

## Start and observe

PC (local ONNX only; no API key or backend switch):

```bash
cd ~/NXTCart-System
bash pc/run_verifier.sh catalog_path:=/home/vandan/NXTCart-System/products.json preview:=true
```

Omit `catalog_path` only when the scan already resolves to a database key or
database metadata supplies the barcode alias. Keep the basket empty during the
initial 15-frame background warmup. The preview shows motion proposal boxes,
sample count and queued jobs; it has no required geometric checkpoints.

Pi:

```bash
cd ~/NXTCart-System
bash raspberry_pi/run_cart.sh \
  qr_camera:=/dev/v4l/by-id/YOUR_SCANNER-video-index0 \
  verification_camera:=/dev/v4l/by-id/YOUR_VERIFIER-video-index0 \
  serial_port:=/dev/serial/by-id/YOUR_ARDUINO \
  upi_payee:=YOUR_REAL_MERCHANT_UPI_ADDRESS
```

Diagnostics:

```bash
ros2 topic type /cart/camera/frame       # sensor_msgs/msg/Image
ros2 topic hz /cart/camera/frame
ros2 topic echo /cart/scanned_item
ros2 topic echo /cart/vision_event
ros2 topic echo /cart/vision_health
```

An add result carries the original `scan_id`, `approved`, `reason`,
`action=item_placed` and scores. An unsolicited removal uses a generated
`removal-...` scan ID, `action=item_removed`, and the identified SKU in `name`.
The Pi binds add results by scan ID and barcode; a stale or cancelled result
cannot verify a different unit. Weight failures still block payment.

Parameters live in `pc/config/verification.yaml`. Tune `similarity_threshold`,
`min_motion_area`, `capture_seconds`, `sample_interval`, `colour_threshold` and
`size_ratio_tolerance`. `min_samples`/`max_samples` must remain within 3..5.
There is one inference worker with a bounded queue; model errors and deadlines
produce non-accepting results rather than silently succeeding.

## Validate

```bash
python3 scripts/run_tests.py
```

The suite covers multiple contours, shadow labels, partial occlusion, any-view
acceptance, no-match rejection, metadata, barcode aliases, replay/cancel/deadline
handling, removal candidates and Pi weight gating. It uses ROS stubs; native
Jazzy builds and live DDS/hardware still need verification on your two hosts.
Test correct items, equal-weight wrong items, packet rotations, ordinary hand
motion, cardboard occlusion, repeated SKUs, no-motion scans and actual removals.

Implementation references: [ROS cv_bridge](https://index.ros.org/p/cv_bridge/)
and [OpenCV DNN](https://docs.opencv.org/4.13.0/d6/d0f/group__dnn.html).
