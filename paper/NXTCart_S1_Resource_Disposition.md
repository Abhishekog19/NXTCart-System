# Supplementary S1 — Resource Disposition for All 85 Catalogue Entries

Companion to `NXTCart_Manuscript.md`. Accounts for **every** resource in the supplied research
catalogue (`NXTCart-Cam/research/resource_catalogue.json`, 85 entries, checked 12 October 2026).

## How to read this

Each entry has exactly one **disposition**:

| Disposition | Meaning |
|---|---|
| **Cited [n] — direct comparator / method** | Appears in the manuscript reference list at IEEE number *n*, and carries a specific comparative or methodological claim (most also occupy a row in TABLE I). |
| **Cited [n] — background / context** | Appears at IEEE number *n*, supporting scope, lineage or framing. Industry pages in this class are labelled as vendor claims in the text. |
| **Cited [n] — implementation source** | Appears at IEEE number *n*, cited for an implementation fact (datasheet, library, official documentation, textbook method). |
| **Excluded (not cited)** | Deliberately not cited, with the reason given. |

The **review depth** column states how far each source was actually examined. It is the honest limit
of this review, not a claim about the source's quality:

| Review depth | Count | Meaning |
|---|---|---|
| **Full text read** (supplied PDF) | 10 | RP1–RP10 were read in full in this pass. |
| Abstract / landing page | 42 | Title, authors, venue and abstract or primary landing page inspected. |
| Metadata only — **full text pending** | 23 | Publisher-deposited metadata verified; **full text not read**. |
| Metadata + abstract | 5 | Publisher metadata plus the publisher's own abstract. |
| Metadata + dataset page | 3 | Publisher metadata plus the official/author dataset page. |
| Official docs (indexed mirror) | 2 | ROS documentation; the canonical URL returned an automated access block, which was not bypassed. |
| **Total** | **85** | |

**No claim in the manuscript depends on an unread full text.** Where a metadata-only or abstract-only
source is cited for a comparative statement (notably [3], [11], [41], [42]), the manuscript's
TABLE I marks it `MD` and the accompanying text is restricted to what the abstract supports.

## Supplied-PDF identification

`SUPPLIED_PAPER_AUDIT.md` in the research pack identifies only RP1–RP3. The remaining seven PDFs
were identified in this pass by matching each file's printed DOI against the catalogue:

| PDF | Catalogue ref | DOI printed in the PDF | Audit coverage |
|---|---|---|---|
| RP1 | R01 | `10.1109/ICCTIT68197.2025.11406732` | In `SUPPLIED_PAPER_AUDIT.md` |
| RP2 | R11 | `10.1109/ICICICT54557.2022.9917860` | In `SUPPLIED_PAPER_AUDIT.md` |
| RP3 | R12 | `10.1109/ICSTSN53084.2022.9761346` | In `SUPPLIED_PAPER_AUDIT.md` |
| RP4 | R02 | `10.1109/ICKECS70176.2026.11527873` | **Not audited** — reviewed here (see §Citation-quality notes) |
| RP5 | R03 | `10.1109/ICACCM61117.2024.11059075` | **Not audited** — reviewed here |
| RP6 | R04 | *(no DOI printed; ICCSP 2019, matched by exact title and venue)* | **Not audited** — reviewed here |
| RP7 | R05 | `10.1109/ISAECT64333.2024.10799859` | **Not audited** — reviewed here |
| RP8 | R07 | `10.1109/ICOIACT67584.2025.11344991` | **Not audited** — reviewed here |
| RP9 | R26 | `10.1109/ICCBI68589.2026.11619726` | **Not audited** — reviewed here |
| RP10 | R27 | `10.1109/CVPRW56347.2022.00350` | **Not audited** — reviewed here |

Because the audit predates RP4–RP10, the catalogue's own `evidence` field still records several of
these as "full text pending". The review-depth column below **overrides** that field for the ten
supplied PDFs rather than under-reporting the depth actually achieved.

## Deduplication

Deduplication was checked on three keys, as instructed: DOI (normalised to lowercase), IEEE document
ID, and exact title. **No duplicates were found among the 85 entries** — 85 distinct refs, 85
distinct titles, and no DOI or IEEE ID appearing twice. Two near-collisions were already resolved by
the catalogue's compilers and are preserved as single entries: R46 (AIM3S) carries the full-paper DOI
`10.1145/3360322.3360834` rather than the separate two-page demonstration DOI, and R56 (HOTA) uses
its 2021 print-issue year rather than its 2020 online year.

---

## Part A — Cited in the manuscript (56 entries)

Every row below appears in the manuscript reference list, and every manuscript reference appears
below. Numbering is by order of first appearance, `[1]`–`[56]`.

| Ref | Year | Pri. | Kind | Title | Identifier | Review depth | Disposition | Reason |
|---|---|---|---|---|---|---|---|---|
| R01 **(RP1)** | 2025 | P1 | paper | Intelligent Shopping Cart Product Recognition System Based on Computer Vision and Multi-Sensor Fusion | IEEE 11406732 | **Full text read** (supplied PDF) | **Cited [9]** - direct comparator / method | RP1, full text read. Closest method comparator (weight-triggered, decision-level fusion). Table I row; citation inconsistencies recorded in Sec. II-C. |
| R02 **(RP4)** | 2026 | P1 | paper | A Weight-Reconciliation Algorithm for Fraud Detection in Smart Shopping Carts | IEEE 11527873 | **Full text read** (supplied PDF) | **Cited [8]** - direct comparator / method | RP4, full text read. Direct weight-reconciliation comparator; its future work proposes exactly NXTCart's visual gate. Table I row; citation-quality issues recorded in Sec. II-B. |
| R03 **(RP5)** | 2024 | P1 | paper | TAV-Cart: Transaction Assistance and Validation Cart System for Effortless Shopping and Checkout | IEEE 11059075 | **Full text read** (supplied PDF) | **Cited [26]** - direct comparator / method | RP5, full text read. Table I row; closest design comparator and an explicit example of an unevaluated anti-switching claim. |
| R04 **(RP6)** | 2019 | P1 | paper | Deep Learning based Automated Billing Cart | IEEE 8697995 | **Full text read** (supplied PDF) | **Cited [24]** - direct comparator / method | RP6, full text read. Table I row; the clearest example of category-level produce recognition (3 classes, 70 %) versus branded-SKU verification. |
| R05 **(RP7)** | 2024 | P1 | paper | Smart Shopping Cart With Machine Learning, Navigation, and Weighing Technologies | IEEE 10799859 | **Full text read** (supplied PDF) | **Cited [25]** - direct comparator / method | RP7, full text read. Table I row; its 'Unknown item' checkout block is prior art for our unreconciled-mass block. |
| R06 | 2017 | P1 | paper | IoT Applications on Secure Smart Shopping System | IEEE 7932080 | Metadata only - **full text pending** | **Cited [20]** - background / context | Secure-shopping architecture and communication protocol; used for system requirements, not as proof that RFID resolves substitution. |
| R07 **(RP8)** | 2025 | P1 | paper | A Few-Shot Learning Pipeline for Retail Product Recognition Using Object Detection and Metric Embeddings | IEEE 11344991 | **Full text read** (supplied PDF) | **Cited [10]** - direct comparator / method | RP8, full text read. Closest methodological comparator for crop -> frozen embedding -> nearest reference; its 40-class P@1 is the key calibration for our expectations. |
| R08 | 2022 | P1 | paper | A Retail Object Classification Method Using Multiple Cameras for Vision-Based Unmanned Kiosks | IEEE 9912319 | Abstract / landing page | **Cited [36]** - direct comparator / method | Multi-camera retail classification; viewpoint and lookalike confusion, relevant to camera-placement limits. |
| R09 | 2020 | P1 | paper | Smart Shopping Carts Based on Mobile Computing and Deep Learning Cloud Services | IEEE 9120574 | Abstract / landing page | **Cited [28]** - background / context | Edge/cloud cart baseline for placement of inference and network dependency. |
| R10 | 2020 | P1 | paper | IoT-Based Smart Shopping Cart Using Radio Frequency Identification | IEEE 9060814 | Metadata only - **full text pending** | **Cited [15]** - background / context | RFID cart lineage; establishes that wireless cart billing predates camera verification. |
| R11 **(RP2)** | 2022 | P1 | paper | Design and Development of a Smart Shopping Cart System | IEEE 9917860 | **Full text read** (supplied PDF) | **Cited [17]** - direct comparator / method | RP2, full text read. Table I row; its internal 125 kHz vs 860-960 MHz conflict is recorded in Sec. II-A. |
| R12 **(RP3)** | 2022 | P1 | paper | AIoT-based Smart Cart System | IEEE 9761346 | **Full text read** (supplied PDF) | **Cited [18]** - direct comparator / method | RP3, full text read. Table I row; its own conclusion (prices items without considering brands) is used to separate category pricing from branded-SKU verification. |
| R17 | 2016 | P2 | paper | Development of e-shopping cart with theft control mechanism: No queue | IEEE 7873753 | Metadata only - **full text pending** | **Cited [23]** - background / context | Early theft-control cart prototype. |
| R18 | 2014 | P2 | paper | Smart shopping cart with automatic billing system through RFID and ZigBee | IEEE 7033996 | Metadata only - **full text pending** | **Cited [16]** - background / context | Earlier RFID/ZigBee automatic-billing cart in the same lineage. |
| R21 | 2025 | P3 | paper | AI-Driven Smart Shopping Carts With Real-Time Tracking and Inventory Forecasting for Enhanced Retail Efficiency | IEEE 10937485 | Abstract / landing page | **Cited [30]** - background / context | Context for proposed-but-unimplemented extensions (tracking, inventory forecasting) in Sec. X. |
| R24 | 2016 | P2 | paper | RFID-Cloud smart cart system | IEEE 7732405 | Abstract / landing page | **Cited [29]** - background / context | RFID/cloud cart baseline. |
| R26 **(RP9)** | 2026 | P1 | paper | Multi-Modal Product Recognition and In-Store Navigation using an Intelligent Shopping Cart | IEEE 11619726 | **Full text read** (supplied PDF) | **Cited [27]** - direct comparator / method | RP9, full text read. Table I row; recent multimodal cart whose reported results are a qualitative interface walkthrough. |
| R27 **(RP10)** | 2022 | P1 | paper | DeepACO: A Robust Deep Learning-based Automatic Checkout System | IEEE 9857462 | **Full text read** (supplied PDF) | **Cited [31]** - direct comparator / method | RP10, full text read. Table I row; its F1 = 0.4783 calibrates expectations for fine-grained retail identification from video. |
| R30 | 2016 | P2 | paper | Context-aware hybrid classification system for fine-grained retail product recognition | IEEE 7528213 | Abstract / landing page | **Cited [37]** - direct comparator / method | Context-aware fine-grained retail classification; lookalike confusion prior art. |
| R31 | 2018 | P1 | paper | MobileNetV2: Inverted Residuals and Linear Bottlenecks | IEEE 8578572 | Metadata only - **full text pending** | **Cited [12]** - implementation source | Original architecture of the frozen feature extractor actually used. Weights, preprocessing and embedding layer documented separately in Sec. VI-A. |
| R34 | 2016 | P3 | paper | You Only Look Once: Unified, Real-Time Object Detection | IEEE 7780460 | Metadata only - **full text pending** | **Cited [46]** - background / context | Original YOLO; background for the detector-based cart literature. Explicitly not evidence about YOLOv8/v11 or about NXTCart. |
| R35 | 2016 | P2 | paper | Simple online and realtime tracking | IEEE 7533003 | Metadata only - **full text pending** | **Cited [47]** - background / context | SORT; tracking background, cited to explain why NXTCart reports no tracking metrics. |
| R36 | 2017 | P2 | paper | Simple online and realtime tracking with a deep association metric | IEEE 8296962 | Abstract / landing page | **Cited [48]** - background / context | DeepSORT; same role as R35. |
| R37 | 1997 | P2 | paper | An introduction to multisensor data fusion | IEEE 554205 | Abstract / landing page | **Cited [43]** - background / context | Classical fusion tutorial, used to frame why NXTCart deliberately does NOT fuse. |
| R38 | 2019 | P2 | paper | Precise Detection in Densely Packed Scenes | IEEE 8953496 | Abstract / landing page | **Cited [33]** - background / context | Densely packed retail detection; defines the recognition task NXTCart does not perform. |
| R39 | 2019 | P2 | paper | A Hierarchical Grocery Store Image Dataset With Visual and Semantic Labels | IEEE 8658240 | Metadata only - **full text pending** | **Cited [34]** - background / context | Grocery dataset anchor for the same purpose. |
| R42 | 2022 | P1 | paper | RPC: a large-scale and fine-grained retail product checkout dataset | DOI 10.1007/s11432-022-3513-y | Metadata + dataset page | **Cited [32]** - background / context | Core fine-grained checkout benchmark; named as the reference benchmark family, not used for any NXTCart number. |
| R45 | 2020 | P1 | paper | FAIM: Vision and Weight Sensing Fusion Framework for Autonomous Inventory Monitoring in Convenience Stores | DOI 10.3389/fbuil.2020.568372 | Abstract / landing page | **Cited [41]** - direct comparator / method | FAIM: strongest open prior art on vision+weight interaction in retail. Abstract-level only; full text pending. |
| R46 | 2019 | P1 | paper | AIM3S: Autonomous Inventory Monitoring through Multi-Modal Sensing for Cashier-Less Convenience Stores | DOI 10.1145/3360322.3360834 | Metadata only - **full text pending** | **Cited [42]** - direct comparator / method | AIM3S: multimodal retail sensing. Abstract-level only; cited with the full-paper DOI, not the two-page demo DOI. |
| R47 | 2018 | P2 | paper | Design and Development of Weight Sensors Based Smart Shopping Cart and Rack System for Shopping Malls | DOI 10.1016/j.matpr.2017.12.367 | Metadata only - **full text pending** | **Cited [21]** - background / context | Weight-sensor cart/rack lineage. |
| R48 | 2016 | P2 | paper | Smart Cart with Automatic Billing, Product Information, Product Recommendation Using RFID & Zigbee with Anti-Theft | DOI 10.1016/j.procs.2016.03.107 | Metadata only - **full text pending** | **Cited [22]** - background / context | Anti-theft cart combining RFID/ZigBee with weight. |
| R49 | 2019 | P1 | paper | A comprehensive survey on computer vision based approaches for automatic identification of products in retail store | DOI 10.1016/j.imavis.2019.03.005 | Metadata + abstract | **Cited [1]** - background / context | Frames the retail-identification literature and the recognition/verification distinction in Sec. I-A and II-D. |
| R50 | 2020 | P1 | paper | Deep Learning for Retail Product Recognition: Challenges and Techniques | DOI 10.1155/2020/8875910 | Abstract / landing page | **Cited [2]** - background / context | Second survey anchor for the same framing; used only for scope, not for any numeric claim. |
| R51 | 2022 | P1 | paper | Product verification using OCR classification and Mondrian conformal prediction | DOI 10.1016/j.eswa.2021.115942 | Metadata + abstract | **Cited [3]** - direct comparator / method | Defines the expected-product verification task with abstention, the formulation NXTCart adopts. Abstract-level only. |
| R52 | 2024 | P1 | paper | Centre‐loss—A preferred class verification approach over sample‐to‐sample in self‐checkout products datasets | DOI 10.1049/cvi2.12302 | Metadata + abstract | **Cited [11]** - direct comparator / method | Class-verification comparator for self-checkout; supports the verification-vs-identification distinction. Abstract-level only. |
| R53 | 2013 | P2 | paper | Multisensor data fusion: A review of the state-of-the-art | DOI 10.1016/j.inffus.2011.08.001 | Metadata only - **full text pending** | **Cited [44]** - background / context | Modern fusion review, same role as R37. |
| R54 | 2022 | P1 | paper | Robot Operating System 2: Design, architecture, and uses in the wild | DOI 10.1126/scirobotics.abm6074 | Metadata only - **full text pending** | **Cited [13]** - implementation source | ROS 2 design/architecture reference for the distributed implementation. |
| R58 | 2021 | P2 | paper | Learning Transferable Visual Models From Natural Language Supervision | no DOI/ID | Abstract / landing page | **Cited [38]** - background / context | Named in Sec. II-D and Sec. X as a candidate replacement backbone; not implemented. |
| R59 | 2023 | P2 | paper | DINOv2: Learning Robust Visual Features without Supervision | no DOI/ID | Abstract / landing page | **Cited [39]** - background / context | Same role as R58. |
| R60 | 2017 | P1 | paper | On Calibration of Modern Neural Networks | no DOI/ID | Abstract / landing page | **Cited [45]** - direct comparator / method | Calibration: why a cosine similarity is not a probability of correct verification. |
| R61 | 2017 | P1 | paper | Selective Classification for Deep Neural Networks | no DOI/ID | Abstract / landing page | **Cited [14]** - direct comparator / method | Selective-classification theory underpinning the abstain-rather-than-decide rule and the risk-coverage reporting requirement. |
| R62 | 2026 | P1 | paper | What Matters for Grocery Product Retrieval with Open Source Vision Language Models | no DOI/ID | Abstract / landing page | **Cited [40]** - background / context | Current SKU-level retrieval with open VLMs; named as a future comparator. Cited as the verified arXiv version only. |
| R63 | 2023 | P2 | paper | Training with Product Digital Twins for AutoRetail Checkout | no DOI/ID | Abstract / landing page | **Cited [35]** - background / context | Synthetic / digital-twin training data; relevant to the synthetic-to-real gap discussion. |
| R66 | 2022 | P2 | book | Computer Vision: Algorithms and Applications | DOI 10.1007/978-3-030-34372-9 | Abstract / landing page | **Cited [55]** - implementation source | Standard reference for the binary morphology operations in Eqs. (11)-(14). |
| R72 | living | P1 | documentation | ROS 2 Jazzy: About Quality of Service settings | no DOI/ID | Official docs (indexed mirror) | **Cited [49]** - implementation source | Primary reference for best-effort image delivery and why frame loss is an explicit design parameter. |
| R74 | undated | P1 | datasheet | HX711: 24-Bit Analog-to-Digital Converter for Weigh Scales | no DOI/ID | Abstract / landing page | **Cited [50]** - implementation source | Manufacturer datasheet for the ADC actually used. Cited for gain/sample-rate facts only; ADC bit depth is not mechanism accuracy. |
| R75 | living | P1 | software | HX711 Arduino library | no DOI/ID | Abstract / landing page | **Cited [51]** - implementation source | The scale library actually named by the firmware and the setup guide. |
| R77 | living | P1 | documentation | OpenCV: Deep Learning in OpenCV | no DOI/ID | Abstract / landing page | **Cited [54]** - implementation source | The ONNX / OpenCV DNN inference path actually used. |
| R78 | living | P1 | software | pyzbar: barcode and QR decoding | no DOI/ID | Abstract / landing page | **Cited [53]** - implementation source | The barcode/QR decoding dependency actually used. |
| R79 | living | P2 | documentation | Arduino: A guide to EEPROM | no DOI/ID | Abstract / landing page | **Cited [52]** - implementation source | Persistent calibration storage used by the firmware. |
| R80 | living | P2 | documentation | NPCI: UPI Frequently Asked Questions | no DOI/ID | Abstract / landing page | **Cited [56]** - implementation source | Payment-system context; supports the request-versus-settlement distinction in Sec. IX-F. |
| R81 | living | P3 | industry page | Caper Carts: official product overview | no DOI/ID | Abstract / landing page | **Cited [4]** - background / context | Industry deployment context only. Explicitly labelled a vendor claim in the text. |
| R82 | 2026 | P3 | industry page | Amazon: 5 ways the newest Dash Cart can save time and money | no DOI/ID | Abstract / landing page | **Cited [5]** - background / context | Industry deployment context only. Explicitly labelled a vendor claim in the text. |
| R83 | 2018 | P1 | paper | An IOT Based Smart Shopping Cart for Smart Shopping | DOI 10.1007/978-981-10-9059-2_33 | Metadata + abstract | **Cited [19]** - background / context | Historical Springer cart comparator; cited with the publisher's corrected five-author attribution. |
| R84 | 2018 | P1 | paper | An IoT-Based Smart Shopping Cart Using the Contemporary Barcode Scanner | DOI 10.1007/978-981-10-8575-8_6 | Metadata + abstract | **Cited [6]** - direct comparator / method | Closest early barcode+weight+image cart; cited in Sec. I-B as the reason the modality combination is NOT claimed novel. |
| R85 | 2013 | P1 | paper | Smart Shopping Cart for Automated Billing Purpose using Wireless Sensor Networks | no DOI/ID | Abstract / landing page | **Cited [7]** - direct comparator / method | Earliest load-cell + image-comparison cart located; same anti-novelty role as R84. |

**Cited-set composition:** 23 direct comparator/method citations, 25 background/context citations, and
8 implementation-source citations.

---

## Part B — Excluded, with reasons (29 entries)

These were considered and deliberately not cited. The catalogue is a candidate pool, not a mandatory
citation list; a source is cited only where it supports a specific statement. Exclusion here is a
scoping decision, **not** a judgement on quality.

| Ref | Year | Pri. | Kind | Title | Identifier | Review depth | Disposition | Reason |
|---|---|---|---|---|---|---|---|---|
| R13 | 2022 | P2 | paper | Fast and Low-Cost, Wireless Controlled Smart Shopping Cart with Raspberry Pi and RFID Technology | IEEE 9998221 | Metadata only - **full text pending** | **Excluded** (not cited) | Raspberry Pi / RFID cart; adds no dimension to Table I beyond R10/R24 and was not read in full. Metadata verified; retained for a future systematic review. |
| R14 | 2023 | P2 | paper | Advanced Smart Shopping Cart with Integration of AI and IoT | IEEE 10212323 | Metadata only - **full text pending** | **Excluded** (not cited) | Generic AI/IoT cart integration; metadata-only, no distinguishing mechanism relevant to expected-SKU verification. |
| R15 | 2025 | P2 | paper | RFID based Smart Trolley Billing System using IoT | IEEE 10984823 | Abstract / landing page | **Excluded** (not cited) | RFID trolley billing with load cell; redundant with R47/R48 for the weight-centric lineage. |
| R16 | 2024 | P2 | paper | RFID-Powered Intelligent Shopping Cart: Streamlined Checkout and Automated Billing | IEEE 10503373 | Abstract / landing page | **Excluded** (not cited) | RFID/cloud billing design; redundant with R24. |
| R19 | 2011 | P3 | paper | Auto-checkout system for retails using Radio Frequency Identification (RFID) technology | IEEE 5991855 | Metadata only - **full text pending** | **Excluded** (not cited) | Early multi-tag RFID auto-checkout; superseded for our purposes by R10/R18. |
| R20 | 2016 | P3 | paper | 3S-cart: A Lightweight, Interactive Sensor-Based Cart for Smart Shopping in Supermarkets | IEEE 7501897 | Abstract / landing page | **Excluded** (not cited) | 3S-cart: modular sensing and shopper interaction; promotion/navigation focus is peripheral to billing integrity. |
| R22 | 2025 | P3 | paper | Next Buy Navigator: Smart Shopping Cart with Item Prediction | IEEE 11263715 | Abstract / landing page | **Excluded** (not cited) | Item prediction / next-buy navigation; out of scope (NXTCart performs no recommendation or prediction). |
| R23 | 2023 | P3 | paper | Radar Self-Following Shopping Cart Based on Multi-Sensor Fusion | IEEE 10189849 | Metadata only - **full text pending** | **Excluded** (not cited) | Radar self-following cart; locomotion and navigation are out of scope. |
| R25 | 2026 | P2 | paper | The Smart Cart with Automatic Billing and Anti-Theft | IEEE 11709931 | Metadata only - **full text pending** | **Excluded** (not cited) | Anti-theft billing cart; metadata-only and redundant with R48/R17 in the anti-theft lineage. |
| R28 | 2023 | P2 | paper | Improving Deep Learning-based Automatic Checkout System Using Image Enhancement Techniques | IEEE 10208503 | Abstract / landing page | **Excluded** (not cited) | ACO image-enhancement variant; redundant with R27 for the conveyor-ACO comparison. |
| R29 | 2021 | P2 | paper | Iterative Knowledge Distillation for Automatic Check-Out | IEEE 9257112 | Abstract / landing page | **Excluded** (not cited) | Iterative knowledge distillation for ACO; a training method for a task NXTCart does not perform. |
| R32 | 2019 | P3 | paper | Searching for MobileNetV3 | IEEE 9008835 | Metadata only - **full text pending** | **Excluded** (not cited) | MobileNetV3; not the model in the code. Citing it would misrepresent the implementation. |
| R33 | 2016 | P3 | paper | Deep Residual Learning for Image Recognition | IEEE 7780459 | Metadata only - **full text pending** | **Excluded** (not cited) | ResNet; not used in the live path. |
| R40 | 2007 | P2 | paper | Recognizing Groceries in situ Using in vitro Training Data | IEEE 4270484 | Abstract / landing page | **Excluded** (not cited) | In-situ grocery recognition from in-vitro training data; dataset coverage already carried by R38/R39/R42/R63. |
| R41 | 2022 | P3 | paper | M5Product: Self-harmonized Contrastive Learning for E-commercial Multi-modal Pretraining | IEEE 9878412 | Metadata only - **full text pending** | **Excluded** (not cited) | M5Product multimodal e-commerce pretraining; e-commerce imagery is a different domain from cart insertion. |
| R43 | 2018 | P2 | paper | MVTec D2S: Densely Segmented Supermarket Dataset | DOI 10.1007/978-3-030-01249-6_35 | Metadata + dataset page | **Excluded** (not cited) | MVTec D2S; redundant with R38 for dense retail segmentation. |
| R44 | 2023 | P3 | paper | MEP-3M: A large-scale multi-modal E-commerce product dataset | DOI 10.1016/j.patcog.2023.109519 | Metadata + dataset page | **Excluded** (not cited) | MEP-3M; e-commerce domain, same reason as R41. Also the dataset mis-attributed inside RP1's reference list. |
| R55 | 2022 | P2 | paper | ByteTrack: Multi-object Tracking by Associating Every Detection Box | DOI 10.1007/978-3-031-20047-2_1 | Metadata only - **full text pending** | **Excluded** (not cited) | ByteTrack; NXTCart contains no tracker, so a third tracking citation adds nothing. |
| R56 | 2021 | P2 | paper | HOTA: A Higher Order Metric for Evaluating Multi-object Tracking | DOI 10.1007/s11263-020-01375-2 | Metadata only - **full text pending** | **Excluded** (not cited) | HOTA; a multi-object-tracking metric for a task NXTCart does not perform and does not report. |
| R57 | 2019 | P3 | paper | EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | EfficientNet; not used in the live path. |
| R64 | 2016 | P2 | paper | The Freiburg Groceries Dataset | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | Freiburg Groceries; dataset coverage already sufficient. |
| R65 | 2023 | P2 | dataset documentation | AI City Challenge 2023: Track 4 data and evaluation | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | AI City Challenge 2023 Track 4 data documentation; the 2022 edition is the one R27 reports against. |
| R67 | 2016 | P2 | book | Deep Learning | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | Deep Learning (Goodfellow et al.); no specific claim in the manuscript needs a general textbook. |
| R68 | 2006 | P2 | book | Pattern Recognition and Machine Learning | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | Pattern Recognition and Machine Learning; same reason as R67. |
| R69 | 2010 | P3 | book | RFID Handbook: Fundamentals and Applications in Contactless Smart Cards, Radio Frequency Identification and Near-Field Communication | DOI 10.1002/9780470665121 | Abstract / landing page | **Excluded** (not cited) | RFID Handbook; NXTCart has no RFID implementation, and the RFID limitations cited are drawn from the cart papers themselves. |
| R70 | 2009 | P2 | book | Handbook of Multisensor Data Fusion: Theory and Practice | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | Handbook of Multisensor Data Fusion; R37 and R53 already carry the fusion framing. |
| R71 | 2016 | P2 | book | Introduction to Embedded Systems: A Cyber-Physical Systems Approach | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | Introduction to Embedded Systems; no specific claim needs it. |
| R73 | living | P2 | documentation | ROS 2 Jazzy: Setting up security | no DOI/ID | Official docs (indexed mirror) | **Excluded** (not cited) | ROS 2 security setup; the cited behaviour is the ABSENCE of DDS security, stated as a limitation in Sec. IX-F rather than as a configured feature. Add this citation only if security is actually enabled. |
| R76 | 2026 | P1 | standard | GS1 General Specifications | no DOI/ID | Abstract / landing page | **Excluded** (not cited) | GS1 General Specifications; the manuscript makes no claim about barcode symbology or GTIN structure. The catalogue maps whatever string the decoder returns, so the standard is not load-bearing. |

**Exclusion reason groups:**

| Group | Refs | Count |
|---|---|---|
| Redundant within an already-represented lineage (RFID carts, anti-theft carts, ACO variants, retail datasets) | R13, R14, R15, R16, R19, R25, R28, R40, R43, R64, R65 | 11 |
| Out of scope for this system (navigation, locomotion, recommendation, prediction) | R20, R22, R23 | 3 |
| Architecture or method **not present in the live code** — citing it would misrepresent the implementation | R29, R32, R33, R55, R56, R57 | 6 |
| Different domain (e-commerce catalogue imagery rather than cart insertion) | R41, R44 | 2 |
| General textbook with no specific load-bearing claim | R67, R68, R69, R70, R71 | 5 |
| Documents an **absent** feature rather than a configured one | R73 (DDS security is not enabled; stated as a limitation) | 1 |
| Standard not load-bearing for any claim made | R76 (GS1: no symbology or GTIN-structure claim) | 1 |

---

## Citation-quality notes recorded during this pass

The supplied-paper audit flagged problems in RP1–RP3. The same scrutiny was applied to RP4–RP10;
these are the additional observations, recorded so that no mismatch propagates into the NXTCart
reference list. They are observations about internal consistency, **not** refutations of the papers'
methods or results.

**R02 / RP4 (weight reconciliation).**
1. The abstract states "a weight detection accuracy of 96 %". This is not directly derivable from the
   paper's Table I (average error 0.87 %, which implies a considerably higher figure) nor from its
   Table III (accuracy 94.0 %). Comparisons should quote the table values, which are internally
   consistent with its confusion matrix (46 TP, 4 FN, 2 FP, 48 TN → 94.0 % accuracy, 95.8 % precision,
   92.0 % recall).
2. Several reference-list entries could not be resolved to identifiable venues: an "IEEE Transactions
   on Retail Automation" (ref [18]) does not correspond to a known IEEE periodical, and ref [13] cites
   *IEEE Access*, vol. 8, with a placeholder-looking page range 12345–12356. Ref [1] attributes a
   shrinkage paper to the *Journal of Retailing and Consumer Services* with details that could not be
   confirmed.
3. **Action taken:** cited for its own described method and reported results only; its citation graph
   was not followed, and none of its references was imported into the NXTCart bibliography.

**R03 / RP5 (TAV-Cart).** Carries an unreplaced IEEE template placeholder in the copyright line
(`XXX-X-XXXX-XXXX-X/XX/$XX.00 ©20XX IEEE`). The paper contains no quantitative evaluation and says so
("presented as an initial concept"). **Action taken:** cited as a design comparator with "None —
explicitly an initial concept" in the measured-task column; its anti-switching assertion is quoted as
an unevaluated claim, never as evidence.

**R07 / RP8 (few-shot pipeline).** Its Table I reports an accuracy–speed trade-off across four
backbone/geometry configurations; the extracted values used in the manuscript (79.67 % / 49.79 % at
10 classes, 67.53 % / 38.07 % at 40 classes, 24.65–81.09 ms, forgetting < 10 %, IoU ≈ 0.68) come from
the ViT-hyperbolic configuration the paper identifies as best. **Action taken:** the configuration is
named wherever these numbers are used.

**R26 / RP9 (multimodal cart).** The pathfinding cost function `f(n) = g(n) + h(n)` and its
explanation appear twice, in Sections III-C and III-D, with the second occurrence introduced under an
"AI-Driven Visual Surveillance" heading. The results section is an interface walkthrough; the only
statement about detection performance is qualitative. **Action taken:** "Qualitative walkthrough; no
numbers reported" in the measured-task column.

**R04 / RP6, R05 / RP7, R27 / RP10.** No internal inconsistencies observed that affect how they are
cited. R27's reported figure is a challenge-leaderboard result (F1 = 0.4783, test set A) and is
labelled as such.

---

## Provenance and limits of this review

* Bibliographic details in the tables above are taken verbatim from the verified research pack; they
  were not re-typed. The generator is `paper/tools/make_disposition.py`, which reads
  `resource_catalogue.json` directly, so title, year, venue, kind, priority and identifier cannot
  drift from the source of record.
* DOIs are the Crossref-normalised lowercase forms. DOIs are case-insensitive and resolve as written.
* IEEE document IDs were extracted by the research pack from registered primary Xplore URLs; the DOI
  suffix was **not** assumed to be the document ID.
* Several live Xplore pages returned a JavaScript/robot check during catalogue construction. Those
  checks were not bypassed. Metadata verification does **not** imply full-text access.
* **This is not a systematic review.** No protocol-registered database query, date range, screening
  log, or forward/backward citation-saturation search was performed. The manuscript states this in
  its limitations section (§IX-L). To upgrade it, define databases and date range, inclusion and
  exclusion rules, query strings and a screening log, and run forward/backward citation searches on
  the direct comparators (R01, R02, R03, R07, R26, R27, R45, R46, R51, R52, R83, R84, R85) until
  additional searches stop finding relevant work.
* No paywalled full text was downloaded or redistributed in producing this supplement. The ten
  supplied PDFs were read where the user provided them and are unchanged.
