# NXTCart

Dual-webcam shopping cart with independent weight and product-image verification.
Scans appear immediately. Weight and camera checks update in the background;
flagged items do not stop shopping, but every unit must pass before checkout.

## Repository layout

| Folder | Runs on | Purpose |
| --- | --- | --- |
| [`raspberry_pi/`](raspberry_pi/) | Raspberry Pi | Both USB cameras, QR decoding, Arduino bridge, catalogue, durable cart state, touchscreen and checkout permission |
| [`arduino/`](arduino/) | Arduino | HX711 measurements, calibration, stability and expected-weight checks |
| [`pc/`](pc/) | PC | Image tracking, crops and verification using local MobileNetV2 ONNX |
| [`tests/`](tests/) | Development / CI | Cart, ROS adapter and fault regression tests |
| [`scripts/`](scripts/) | Development | Interface synchronization and test runner |
| [`docs/`](docs/) | Both hosts | Setup and hardware acceptance |

**Only image processing and verification run on the PC.** The Pi owns cart state
and checkout permission. The live vision pipeline makes no API calls. The existing touchscreen theme
is retained with compact per-item verification indicators.

## Setup

Follow the complete [setup and hardware acceptance guide](docs/SYSTEM_SETUP.md)
for ROS 2 Jazzy, HX711 calibration, USB device selection, catalogue import,
reference photography, both ROS builds and actual-product tests.

```bash
git clone https://github.com/Abhishekog19/NXTCart-System.git ~/NXTCart
cd ~/NXTCart
```

After completing setup:

```bash
# PC
bash pc/run_verifier.sh catalog_path:=/path/to/products.json

# Pi, in the touchscreen desktop session
bash raspberry_pi/run_cart.sh \
  qr_camera:=/dev/v4l/by-id/YOUR_SCANNER-video-index0 \
  verification_camera:=/dev/v4l/by-id/YOUR_VERIFIER-video-index0 \
  serial_port:=/dev/serial/by-id/YOUR_ARDUINO \
  upi_payee:=YOUR_REAL_MERCHANT_UPI_ADDRESS
```

The current vision pipeline samples 3–5 full-frame motion views and accepts any
matching view, tolerating contours, shadows and short occlusions. It has no
scan/cart boxes and does not wait for weight before image inference. See the
[full-frame migration and launch guide](docs/LENIENT_VISION_SETUP.md) before
updating either host: the image topic and verdict interfaces changed.
References, generated embeddings, ONNX models and measured catalogues remain
local assets. API comparison utilities are retained as offline experiments.

## Software checks

Use a development environment separate from the Pi ROS system interpreter:

```bash
python -m pip install -r requirements-dev.txt
python scripts/run_tests.py
```

The runner checks syntax, ROS message consistency and deployment boundaries,
then runs integration/regression tests, AI-reference tests and headless image
checks. No hardware, model download or paid API request is needed. ROS callbacks
use message-schema stubs; live DDS and actual hardware acceptance remain required.
Checkout currently gates a UPI QR, without provider-confirmed payment settlement.

Pi message definitions are canonical. After editing them, run
`python scripts/sync_interfaces.py`, commit both copies, and rebuild both hosts.
Standalone experiments and historical notes remain in `pc/` and `pc/docs/`;
they are not launched by the integrated runtime. See [repository notes](docs/REPOSITORY.md).

The old geometric `MERGED`/multiple-region checks are retired. Use the
[full-frame setup guide](docs/LENIENT_VISION_SETUP.md) for current tuning.
