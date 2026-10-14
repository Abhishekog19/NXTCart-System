# Supplementary S2 — Missing-Measurement and Missing-Fact Checklist

**Required before submission.** Companion to `NXTCart_Manuscript.md`. Every row is something the
manuscript currently marks `[TO BE MEASURED: …]` or `[TO BE RECORDED: …]`, or an author/venue
placeholder. Nothing in this list may be filled in by estimation, by analogy to a cited paper, or by
reusing another system's published figure.

Repository revision under review: `28aa58d3ceff6a7d03a2d208d9d4065606af85f8` (11 October 2026).

**Gate rule.** The manuscript is submittable as a system-design and protocol paper with every
measurement row still open, *provided* the placeholders remain visible and the title, abstract and
Section VIII continue to state that results are pending. The manuscript becomes **non-submittable**
the moment a placeholder is deleted without the corresponding measurement, because the surrounding
prose then reads as a completed evaluation.

`grep -n "TO BE MEASURED\|TO BE RECORDED\|\[AUTHOR\|\[INSTITUTION\|\[ACKNOWLEDGMENT\|\[CORRESPONDING\|\[DEPARTMENT\|\[NAMES\|\[CONTRIBUTION\|\[email\|\[domain\|\[CITY\|\[COUNTRY" paper/*.md paper/*.tex`

---

## A. Blocking before *any* submission (administrative)

| # | Item | Where | Status |
|---|---|---|---|
| A1 | Author names, order and affiliations | Title block, both files | ☐ Placeholder |
| A2 | Corresponding author and e-mail addresses | Title block, both files | ☐ Placeholder |
| A3 | Funding sources and grant numbers; confirm each funder has approved acknowledgment | Acknowledgment | ☐ Placeholder |
| A4 | Non-author contributors named, with their consent | Acknowledgment | ☐ Placeholder |
| A5 | Target venue confirmed and its template applied (page limit, reference style, anonymity rules) | Whole document | ☐ Not set |
| A6 | Page count verified against the venue limit (target 8–10 IEEE pages before supplements) | Whole document | ☐ Unverified — abridge TABLE I / TABLE IX first; see S3 |
| A7 | LaTeX compiles cleanly, twice, with `IEEEtran.cls` | `NXTCart_IEEEtran.tex` | ☐ **Not verified** — no TeX distribution on the authoring host |
| A8 | Figures 1–6 exported to PDF and `\includegraphics` lines uncommented | `NXTCart_IEEEtran.tex` | ☐ Placeholder boxes in place |
| A9 | Ethics / data-protection statement if human subjects push the cart during trials (video of shoppers is personal data) | New subsection | ☐ Not addressed |
| A10 | Code and data availability statement, and a decision on releasing the diagnostic manifests | New subsection | ☐ Not decided |

## B. Blocking before any **accuracy or security** claim

These must be measured before a single number replaces a placeholder in Sections VIII–X.

| # | Measurement | Protocol ref | Instrument needed | Status |
|---|---|---|---|---|
| B1 | **Impact-to-settlement delay `Δ_s = t_settled − t_impact`**, distribution over ≥ 200 drops, stratified by mass decile | §V-G, §VII-G | Independent impact reference (contact microphone or accelerometer on the basket, logged on the Pi clock) | ☐ **Highest priority** — the whole configuration depends on it |
| B2 | Fraction of settlements where `Δ_s ≥ 0.90 s` (baseline-contamination rate) | §V-G | Derived from B1 + manifests | ☐ Open |
| B3 | Achieved camera publish rate and receive rate (FPS) | §VI-A, §VII-E | `ros2 topic hz` on both ends | ☐ Open — 30 FPS is a *driver request* only |
| B4 | Realised burst frame count and max intra-burst gap distributions | §VII-E | `manifest.json` fields `frame_count`, `max_gap_ms` | ☐ Open |
| B5 | Burst admissibility rate (fraction passing the density and gap tests) | §VII-E | Verdict log | ☐ Open |
| B6 | Measured wire bandwidth on the image topic | §V-A, §VII-G | Interface packet counter — **not** the analytical 221 Mb/s | ☐ Open |
| B7 | PC resident memory and CPU; Pi CPU | §VII-E | Sampled during a session — **not** the analytical 110.6 MB ring figure | ☐ Open |
| B8 | Embedding time per ROI, and verdict latency p50/p95 (`t_verdict − t_settled`) | §VII-E | Worker instrumentation + Pi log | ☐ Open |
| B9 | End-to-end latency p50/p95 (`t_verdict − t_scan`) | §VII-E | Pi log | ☐ Open |
| B10 | False accept rate per adversarial class (S3, S4, S5, S6, S10) | §VII-D/E | Operator ground truth | ☐ Open |
| B11 | Honest false reject rate and retry rate, reported **separately** | §VII-E | Operator ground truth | ☐ Open |
| B12 | **False accusation rate** — honest placements yielding `SWAP_DETECTED` | §V-E, §VII-E | Operator ground truth | ☐ Open — the sharpest identified risk |
| B13 | Substitution detection rate *with the correct observed SKU* | §VII-E | Operator ground truth | ☐ Open |
| B14 | Exact basket correctness and exact total correctness, per session | §VII-A/E | Operator ground truth | ☐ Open |
| B15 | Intervention rate (sessions requiring empty-cart reconciliation or staff action) | §VII-E | Session log | ☐ Open |
| B16 | Risk–coverage curve as `(θ, μ, θ_swap)` vary | §VII-E | Offline replay over recorded bursts | ☐ Open — required instead of a single operating point |
| B17 | HX711/load-cell accuracy, linearity, hysteresis, creep and drift on the **mounted** basket, at several basket positions | §VI-A, §IX-C | Class M1 or better reference masses | ☐ Open |
| B18 | Per-SKU gross packaged mass measured across **multiple physical units**, with the spread used to set `tolerance_g` | §III-A, §VII | Reference scale | ☐ Open — printed net contents are not a scale reference |
| B19 | Pi↔PC clock offset and drift across a shopping session | §VI-E | chrony tracking log | ☐ Open |
| B20 | Scanner decode rate, read range and duplicate-scan behaviour under motion and lighting change | §VI-C | Operator trials | ☐ Open |

## C. Blocking before any **deployment** claim

| # | Item | Where | Status |
|---|---|---|---|
| C1 | Native `colcon build` on both ROS 2 Jazzy workspaces | §VIII-B | ☐ **Not done** — no colcon on the authoring host |
| C2 | Arduino sketch compiles and uploads to the actual board | §VIII-B | ☐ **Not done** — no Arduino toolchain on the authoring host |
| C3 | Live DDS acceptance: topic discovery, `ros2 topic hz`, sustained delivery on the real LAN | §VIII-B | ☐ Not done — tests use message-schema stubs |
| C4 | Re-run the suites on the ROS target's OpenCV (`>=4.10,<5`), not the authoring host's 5.0.0 | §VIII-A/B | ☐ Not done |
| C5 | Exact Pi model, RAM and OS build; PC CPU, core count and RAM | TABLE V | ☐ `[TO BE RECORDED]` |
| C6 | Load-cell capacity, accuracy class, excitation and mounting stiffness | TABLE V | ☐ Not recorded — not fixed by the code |
| C7 | Camera make/model, sensor, lens FOV and whether MJPG is required to reach 30 FPS | TABLE V | ☐ Not recorded |
| C8 | Pinned versions: OpenCV, NumPy, `bogde/HX711` commit, pyzbar, native ZBar, ONNX model SHA-256 | TABLE V, §VII-F | ☐ Not recorded |
| C9 | Catalogue size at which each operating point was measured (ranking degrades with `\|K\|`) | §IX-J | ☐ Not recorded |
| C10 | Payment-provider order authorisation and confirmed-settlement webhook | §IX-F | ☐ **Not implemented** — UPI QR is a request only |
| C11 | DDS security enabled, or the threat accepted in writing | §IX-F | ☐ Not implemented |

## D. Facts asserted in the manuscript that must be re-verified if the code changes

These are currently **correct** against revision `28aa58d`. They are listed because they are the rows
that silently rot.

| # | Assertion | Source of truth | Re-check trigger |
|---|---|---|---|
| D1 | All 24 configured values in TABLE VI | `pc/config/verification.yaml` | Any config edit |
| D2 | Pi ledger constants (20.0 s, 2.5 s, 5.0 g, 10.0 g, 200 units, 0.8 s) | `pi_sensors.launch.py`, `verification.py`, `qr_scanner_node.py` | Any launch-default edit |
| D3 | Firmware constants (`WINDOW=6`, `STABLE_SPAN_G=4.0`, `CHANGE_G=5.0`, ~100 ms gating, 20 s expectation timeout) | `arduino/cart_scale/cart_scale.ino` | Any firmware edit — **invalidates the §V-G analysis** |
| D4 | The settlement timestamp is the Pi's *serial-receive* stamp of the first stable sample | `real_weight_node.py`, `core_logic.py::flush_commands` | Any change to stamping |
| D5 | `NO_ITEM_SEEN` is tested **before** `SCENE_CHANGED` | `burst.py::verify_burst` | Any reordering of that branch |
| D6 | The Pi collapses the four-valued image verdict to a binary gate; `RETRY` is not auto-retried | `verification.py::vision` | Any change to verdict handling |
| D7 | Swap precedence `swaps ≻ matches ≻ failures` | `local_matcher.py::verify` | Any change to the pool selection |
| D8 | Removal crops come from the **baseline** image | `burst.py::verify_burst` argument order | Any change to the removal path |
| D9 | The 80-bin colour format (18×4 chroma + 8 achromatic) and its thresholds | `pc/ml/verifier.py`, `pc/ml/config.py` | Any colour-format version bump |
| D10 | Preprocessing is identical in `build_db.py` and the live matcher | `pc/ml/embedding_extractor.py`, `local_matcher.py::MobileNetONNX.embed` | Any change to either |
| D11 | Only `vision_verify_node` and `capture_references` are PC entry points | `pc/vision_ws/src/nxtcart_vision/setup.py` | Any new entry point |
| D12 | Test counts: 103 + 4 + scripted suite; 12 tests target retired components | `python scripts/run_tests.py` | Any test added or removed |
| D13 | `buffer_seconds > baseline_before + burst_after + transport_grace` and `buffer_max_frames = 4 s × 30 FPS` | Start-up validation in `vision_verify_node.py` | Any timing change |
| D14 | Deployment-boundary import check is enforced in CI | `scripts/run_tests.py::source_checks` | Any change to the runner |

## E. Documentation debt that would confuse a reproducer

Not required for submission, but a reader following the repository will hit these. The manuscript
already records them in §VI-G. **All four are documentation-only or test-only**: none touches the
running cart, so fixing them cannot change runtime behaviour.

| # | Issue | Location |
|---|---|---|
| E1 | README still describes the retired "3–5 full-frame motion views" pipeline while its own first line points at the current guide | `README.md` lines 49–55, 77–78 |
| E2 | Setup guide still describes JPEG transport, `scanner_region`/`cart_region` parameters, a nine-frame scan-to-rest journey and an `ai` backend | `docs/SYSTEM_SETUP.md` §§6–7 |
| E3 | `CameraFrame.msg` (JPEG payload) is retained in both interface copies but unused by the live runtime | `smart_cart_interfaces/msg/CameraFrame.msg` |
| E4 | `tests/test_full_frame_vision.py::MotionTests`, `tests/test_tracking_calibration.py` and `test_system.py::JourneyTests` exercise retired components but run in the default suite | `tests/` |

> **No runtime change is proposed anywhere in these deliverables.** An earlier draft of this list
> carried a fifth item suggesting the `NO_ITEM_SEEN` / `SCENE_CHANGED` branch order in
> `burst.py::verify_burst` be reordered. That suggestion has been withdrawn at the project owner's
> direction: the current order fails closed (it refuses, never approves), the cart's behaviour is
> accepted as-is, and the owner will revisit the reason-code labelling if they ever decide it matters.
> The branch order is still described factually in the manuscript (§V-H and TABLE IV) because an
> accurate system description requires it, but it is **not** listed as a defect or an action item.

## F. Numbers that are analytical, not measured — keep them labelled

If any of these loses its "analytical" qualifier it becomes an invented measurement.

| Value | Status | Must not be written as |
|---|---|---|
| 110.6 MB frame ring | Arithmetic: 120 × 640 × 480 × 3 B | "measured memory use" |
| 27.6 MB/s ≈ 221 Mb/s | Arithmetic: 640 × 480 × 3 × 30 B/s, raw payload only | "measured bandwidth" |
| 16–17 frames per admissible burst | Expected at the *requested* 30 FPS | "observed frame count" |
| `Δ_stab ≈ 0.5–0.6 s` | Derived from `WINDOW=6` at ~10 Hz | "measured settling time" |
| 0.30–0.40 s decay budget | Derived from `δ_base − Δ_stab` | "measured margin" |
| ≈9.5 % upper bound at 30 trials / 0 failures | Clopper–Pearson, one-sided 95 % | "measured failure rate" |

## G. Third-party figures that must stay attributed

Reported in the manuscript as prior-art results under their own conditions. Never reuse as NXTCart
results, and never compare directly unless task, class count, split, event definition and hardware
are comparable.

| Figure | Source | Attributed in |
|---|---|---|
| 98.7 % top-1, 0.8 % misID, 0.3 s/item, V 93.5 / V+W 96.1 / V+R 97.3 | [9] / RP1 | §II-C, TABLE I |
| 0.87 % avg mass error; 94.0 % acc., 95.8 % prec., 92.0 % rec.; ~420 ms; FPR <4 % vs 28 % | [8] / RP4 | §II-B, TABLE I |
| 79.67 % / 49.79 % @10 cls; 67.53 % / 38.07 % @40 cls; 24.65–81.09 ms; forgetting <10 %; IoU ≈0.68 | [10] / RP8 | §II-D, TABLE I, §VIII-C |
| F1 = 0.4783, 116 IDs, 116 500 synthetic composites | [31] / RP10 | §II-D, TABLE I |
| 3 classes, 70 % detection accuracy, cell to 5 kg | [24] / RP6 | §II-C, TABLE I |

## H. Developer-reported figures found in code comments — **excluded** from the manuscript

`pc/ml/embedding_extractor.py` contains developer notes reporting ~6.5 ms per ONNX embedding versus
~1619 ms for the TFLite fallback, and a leave-one-out comparison over the `references/` folder
(19/20 top-1 for both backends; separation −0.079 ONNX vs −0.132 TFLite).

**These are deliberately not cited as results in the manuscript.** Reasons: the protocol, hardware,
reference count (*n* = 20) and separation metric are undocumented; the comparison concerns a backend
choice rather than the burst pipeline; and leave-one-out over the reference set is not a held-out
evaluation. If the authors wish to use them, they must be re-run under the Section VII protocol and
reported as a separate, clearly identified backend experiment with its own protocol description.

---

## Suggested order of work

1. **B1** (impact-to-settlement delay). Everything about the vision configuration is downstream of it.
2. **B3, B4, B5** (transport reality) — cheap, and they determine whether bursts are admissible at all.
3. **B17, B18** (mass channel calibrated on multiple physical units) — gates every mass claim.
4. **C1, C2, C3** (native builds and live DDS) — until these pass, nothing else can be run on hardware.
5. **B10–B16** (the decision-quality campaign), with tuning frozen first per §VII-F.
6. **A1–A10** administrative, last, once the content is fixed.
