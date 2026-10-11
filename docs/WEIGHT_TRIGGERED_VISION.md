# Weight-triggered foreground burst verification

This is the current ROS vision architecture. It supersedes full-frame matching,
five-frame decimation, and the older geometric tracking instructions.

## Runtime flow

1. Pi camera requests 640x480 at 30 FPS, with driver buffer size 1. Every BGR
   Image receives the Pi ROS clock timestamp immediately after camera read.
2. The PC continuously retains up to 120 frames (at most four seconds) as
   `(monotonic_receive_time, source_stamp_ns, frame)` in a deque. Scans alone
   never start inference. The Pi's verification request supplies transaction,
   barcode, SKU, scan ID, action, and attempt.
3. `/cart/placement_settled` starts collection of the complete source-timestamp
   window `[settled - 0.40 s, settled + 0.15 s]`. The PC waits for the post-window
   frames, allowing another 0.75 seconds for network delivery. Every received
   frame in the window is retained, with no five-frame sampling. At 30 FPS this
   is normally 16-17 frames. Fewer than 12, or a gap exceeding 80 ms including
   window edges, returns RETRY instead of silently losing the drop.
4. A baseline is selected at or just before `settled - 0.90 s`, within 150 ms.
   Missing baselines return RETRY. Each burst frame is differenced against the
   baseline, thresholded, opened/closed, and split into foreground contours.
   Contours below 800 pixels are discarded. Each remaining ROI gets 12% padding.
   Global scene changes or scene-sized bounding boxes are rejected. There is
   no full-frame embedding fallback and no BackgroundSubtractor trigger.
5. Only cropped ROIs reach MobileNetV2. Every ROI is scored against every SKU.
   Approval requires target top-1, cosine at least 0.72, competitor margin at
   least 0.04, and available colour/apparent-size checks. An alternate SKU with
   score at least 0.70 produces MISMATCH with `SWAP_DETECTED` and the observed
   SKU. A confident swap anywhere in the burst vetoes an earlier matching crop.
   With no foreground crops, MISMATCH reports `NO_ITEM_SEEN`.
6. The Pi binds the returned verdict to the transaction and attempt. Weight
   approval remains independent. A camera MATCH cannot clear wrong weight.
   Selected removals use the baseline's departing-product pixels; unsolicited
   weight changes remain the Pi's reconciliation responsibility.

Segmentation, inference and debug writes run in one worker. ROS callbacks remain
in their mutually-exclusive group; no worker publishes or mutates node state.
The queue, frame buffer and completed-ID cache are bounded. Canceled, restarted,
timed-out and duplicate transactions cannot publish late approvals. Heartbeats
continue during inference and tolerate camera age up to 5.0 seconds even after
old frames have been pruned. True camera restarts still invalidate continuity.
The existing Pi timeout for loss of the entire PC heartbeat is separate.

## Update and run

Stop both launch processes before updating. On **both machines**:

```bash
cd ~/NXTCart-System
git pull --ff-only origin main
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=42
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

Keep Pi and PC clocks synchronized (NTP/chrony), and preserve the existing
CycloneDDS network configuration. Both sources use the Pi clock; source stamps
must also be within the PC freshness tolerance. Never mix simulation time with
wall-clock camera/scale stamps.

On the **PC**:

```bash
sudo apt install ros-jazzy-cv-bridge ros-jazzy-sensor-msgs python3-opencv python3-numpy
cd ~/NXTCart-System/pc/vision_ws
colcon build --symlink-install
source install/setup.bash
cd ../..
bash pc/run_verifier.sh catalog_path:=/home/vandan/NXTCart-System/products.json preview:=true
```

The launcher resolves the model to `pc/ml/mobilenet_v2.onnx` and database to
`pc/embedding_db.pkl`. Use the local trusted ONNX database (1280-D pooling
embeddings and the existing 80-bin HSV format). Reference pictures should be
product crops from multiple orientations, not bedroom/cart scenes. Rebuild
the database with `pc/build_db.py` after replacing contaminated references.
Missing/invalid model or database files fail startup explicitly. Catalogue
mapping is necessary when barcodes differ from embedding database keys.

On the **Pi**:

```bash
cd ~/NXTCart-System/raspberry_pi/smart_cart_ws
colcon --log-base log-v2 build --build-base build-v2 --install-base install-v2 --symlink-install
source install-v2/setup.bash
cd ../..
bash raspberry_pi/run_cart.sh
```

Pass your existing serial-port, camera-device, catalogue and payment arguments
to `run_cart.sh` as before. No UI or ROS message schema changes are required.
Both workspaces need the rebuilt Python code. Do not run the retired PC patch
scripts or the geometric tracker.

## Configuration and diagnostic artifacts

`pc/config/verification.yaml` contains thresholds, burst timing, five-second
camera loss timeout, and queue limits. The previous `min_samples`, `max_samples`
and motion settings no longer control the live node.

Debug output defaults to `pc/debug_frames/` under cam_root (on Vandan's PC:
`/home/vandan/NXTCart-System/pc/debug_frames/`). Override with the `debug_dir`
launch argument. Each worker evaluation writes a baseline image, all evaluated
full frames, all ROIs, and manifest.json containing source timestamps, bounding
boxes, per-crop target/top-1/runner-up scores, margins, verdicts and reason codes.
Filenames include target SKU, predicted SKU, score and verdict. These are
diagnostic model results; a later cancellation/timeout can suppress publication.
The last 100 diagnostic transactions are retained by default (`debug_keep`).
Only this writer's generated directories are pruned. Debug data is git-ignored.
An unwritable/full disk is logged without changing the vision decision.

A 120-frame 640x480 BGR ring uses about 111 MB of pixels; worker snapshots and
ROS buffers add overhead on the PC. Raw 30 FPS transport is approximately
27.6 MB/s (221 Mb/s), before DDS overhead. Use a network capable of delivering
that stream. Reducing to 15 FPS will fail the dense-burst acceptance check;
the software cannot manufacture missing frames or force unsupported camera FPS.

The current Pi settlement timestamp marks a **stable scale sample**, not a
hardware impact interrupt. Measure impact-to-stable delay in real drops. If
that delay pushes the descent outside the configured window, the debug frames
will show it; tune the burst/baseline timing together or add a separately defined
impact timestamp before assuming this window covers the fall. Do not lower
confidence thresholds to mask missing evidence. Baseline differencing cannot
reliably separate a fully occluded product from a hand or prove hidden swaps.
Apparent aspect ratio is not a calibrated measurement of physical product size.

## Acceptance checks

```bash
ros2 topic hz /cart/camera/frame
ros2 topic echo /cart/placement_settled
ros2 topic echo /cart/vision_event
ros2 topic echo /cart/vision_health
```

Run the commands in separate terminals. Wait at least two seconds for baseline
history before the first placement.

1. Scan and hold an item: no ONNX job until settlement.
2. Trigger a settlement with an unchanged scene: NO_ITEM_SEEN; no model call.
3. Drop the correct item quickly: manifest shows the full contiguous burst and
   tightly bounded ROIs containing the product, then a qualified MATCH.
4. Scan Margo and drop Hamam (or another same-weight lookalike): inspect all-SKU
   scores and require MISMATCH/SWAP_DETECTED with the observed product identity.
5. Try correct packaging with wrong weight: the UI stays flagged and payment
   stays blocked even when camera matches.
6. Test blur, hands, shadows, other items already in the basket, lighting changes
   and obstruction; uncertain evidence must not produce green approval.
7. Pause only camera delivery for 1-4 seconds while heartbeats continue: already
   verified items are not invalidated by the PC camera health flag. Beyond five
   seconds or after a real camera restart, reconciliation must be required.
8. Drop camera packets during a transaction: incomplete bursts return RETRY.
9. Cancel, resend settlement, restart the camera, or delay inference: no duplicate
   or late approval. Test selected removal and confirm both gates before billing
   changes. Continue scanning after a flagged product; checkout remains gated.

Software verification: `python scripts/run_tests.py`. Tests use actual OpenCV
segmentation and ROS message-schema stubs; they do not replace hardware/DDS tests.
Foreground morphology follows the [OpenCV operations documentation](https://docs.opencv.org/4.13.0/d9/d61/tutorial_py_morphological_ops.html).
