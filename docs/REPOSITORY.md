# Repository and deployment notes

This source tree combines the current NXTCart-Cam vision code and Cart-RestCode
Pi/Arduino integration with a new Git history. The original source folders and
the unrelated Abhishekog19/NXTCART app are unchanged. This project's public
repository is NXTCart-System; the project name is NXTCart.

| Previous location | Current location |
| --- | --- |
| NXTCart-Cam/ml/ | pc/ml/ |
| NXTCart-Cam/pc/vision_ws/ | pc/vision_ws/ |
| Vision demos, reference/dataset tools and comparisons | pc/ |
| Historical vision documentation | pc/docs/ |
| Cart-RestCode/smart_cart_ws/ | raspberry_pi/smart_cart_ws/ |
| Cart-RestCode/arduino/ | arduino/ |
| Integration and regression tests | tests/ |

Tests, reference capture, preflight, launch defaults, interface synchronization
and setup instructions use the new layout. Clone to `~/NXTCart` for the guide's
literal commands; the launch wrappers also support other clone locations.

Virtual environments, nested Git repositories, ROS build/install/log output,
previous backup copies, caches, runtime databases, reference photographs,
generated embeddings, downloaded models and credentials are excluded. Application
source, firmware, wire definitions, tests, catalogue example and development
utilities are included. Capture references and import measured catalogue data
before testing real products.

The software runner verifies source wiring with stubbed ROS messages and no
paid API requests. It does not certify live DDS, radio latency, sensor calibration,
recognition accuracy or native ROS/Arduino builds. Complete the actual-product
matrix in [SYSTEM_SETUP.md](SYSTEM_SETUP.md). Unattended commerce additionally
needs payment-provider authorization and confirmed settlement.
