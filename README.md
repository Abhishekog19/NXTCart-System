# NXTCart

Dual-webcam shopping cart with independent weight and product-image verification.
Scans appear immediately. Weight and camera checks update in the background;
flagged items do not stop shopping, but every unit must pass before checkout.

## Repository layout

| Folder | Runs on | Purpose |
| --- | --- | --- |
| [`raspberry_pi/`](raspberry_pi/) | Raspberry Pi | Both USB cameras, QR decoding, Arduino bridge, catalogue, durable cart state, touchscreen and checkout permission |
| [`arduino/`](arduino/) | Arduino | HX711 measurements, calibration, stability and expected-weight checks |
| [`pc/`](pc/) | PC | Image tracking, crops and verification using local ML or a configurable vision API |
| [`tests/`](tests/) | Development / CI | Cart, ROS adapter and fault regression tests |
| [`scripts/`](scripts/) | Development | Interface synchronization and test runner |
| [`docs/`](docs/) | Both hosts | Setup and hardware acceptance |

**Only image processing and verification run on the PC.** The Pi owns cart state
and checkout permission. API keys stay on the PC. The existing touchscreen theme
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
bash pc/run_verifier.sh backend:=local

# Pi, in the touchscreen desktop session
bash raspberry_pi/run_cart.sh \
  qr_camera:=/dev/v4l/by-id/YOUR_SCANNER-video-index0 \
  verification_camera:=/dev/v4l/by-id/YOUR_VERIFIER-video-index0 \
  serial_port:=/dev/serial/by-id/YOUR_ARDUINO \
  upi_payee:=YOUR_REAL_MERCHANT_UPI_ADDRESS
```

Select `backend:=ai` with an image-capable endpoint and model to evaluate a
vision API. The Pi contract is unchanged. References, embeddings, downloaded
models, measured catalogues, runtime databases and credentials are local assets;
capture/import/build them using the setup guide.

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
