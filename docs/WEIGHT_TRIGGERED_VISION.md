# Weight-triggered buffered vision

The PC continuously stores the last 3 seconds of `/cart/camera/frame`
(sensor_msgs/Image, BGR via cv_bridge) in a bounded deque. No background
subtractor, motion threshold, tracking box, or motion warmup controls inference.
`/cart/scanned_item` alone never invokes the model.

The Pi sends `/cart/verification_request` (VerificationRequest) to register the
transaction, then `/cart/placement_settled` (the same message type) after a stable
physical weight change. This event supplies txn_id, scan_id, attempt, barcode,
sku, add/remove action, and the Pi weight sample timestamp in started_at.
The PC snapshots up to five evenly spaced buffered frames ending at that timestamp
and compares them against the requested product using local MobileNetV2 ONNX.
One usable frame is sufficient by default. Missing/stale evidence returns RETRY.
No extra seconds of recording are required after settlement.

Settlement means landed, not correct weight: the Pi independently maintains
weight PASS/FAIL and checkout requires both weight and camera PASS. Arduino
verdicts are consumed by the Pi; the PC does not subscribe directly to them.
Selected removals also wait for their weight settlement. Unscanned weight changes
remain the Pi's responsibility; motion no longer generates removal events.

## Deployment

Use the existing model/database/catalogue setup in LENIENT_VISION_SETUP.md;
this document supersedes that guide's motion and capture behavior.
On the PC, from the repository root, rebuild and source the workspace:

```bash
source /opt/ros/jazzy/setup.bash
cd pc/vision_ws
colcon build --symlink-install
source install/setup.bash
cd ../..
bash pc/run_verifier.sh catalog_path:=/path/to/products.json preview:=true
```

Launch the Pi with the existing run_cart.sh hardware configuration. No message
schema changes are needed for this update. Keep Pi and PC clocks synchronized
with NTP/chrony and use the same ROS_DOMAIN_ID and CycloneDDS configuration.
The Pi camera and weight timestamps must share the same ROS clock.

Configuration: pc/config/verification.yaml. buffer_seconds=3,
buffer_max_frames=90, min_samples=1, max_samples=5,
settlement_timeout=18 seconds, result_timeout=6 seconds. At 640x480 and 15fps,
the buffer uses roughly 42 MB of pixel data. Higher rates are capped at 90
frames; increase that cap if necessary to retain three seconds at higher fps.
Inference is asynchronous; collection continues while earlier items are processed.
Full-frame matching can be affected by basket clutter or previously added products;
validate similarity thresholds with actual correct and incorrect products.

## Hardware test

1. Check `ros2 topic hz /cart/camera/frame` and the preview's buffer counter.
   It must increase with a completely still scene.
2. Echo `/cart/placement_settled` and `/cart/vision_event` in separate terminals.
3. Scan a product and hold it: no inference occurs. Put it in the cart: the
   stable weight event must carry that transaction ID, followed by a verdict.
4. Use a wrong-weight product: weight stays red even if the camera matches.
5. Use a visually wrong product with similar weight: verify the camera rejects
   it with your actual reference database and scene.
6. Disconnect the scale: settlement times out, no green camera verdict.
7. Disconnect/restart the camera: missing evidence produces RETRY and blocks
   checkout. Reconcile and retry; old evidence must not approve the new attempt.
8. Select a removal: only its negative-weight settlement triggers inference.
9. Cancel an item or repeat a settlement: no late or duplicate approval.

Run software regression checks with `python scripts/run_tests.py`.
