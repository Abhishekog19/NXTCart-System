import json, sys

catalogue_path, out_path = sys.argv[1], sys.argv[2]
cat = {e['ref']: e for e in json.load(open(catalogue_path, encoding='utf-8'))}

# IEEE number assignment, in order of first appearance in the manuscript.
ORDER = ("R49 R50 R51 R81 R82 R84 R85 R02 R01 R07 R52 R31 R54 R61 R10 R18 R11 R12 R83 R06 "
         "R47 R48 R17 R04 R05 R03 R26 R09 R24 R21 R27 R42 R38 R39 R63 R08 R30 R58 R59 R62 "
         "R45 R46 R37 R53 R60 R34 R35 R36 R72 R74 R75 R79 R78 R77 R66 R80").split()
NUM = {r: i for i, r in enumerate(ORDER, 1)}

# role: C = cited as direct comparator/method; B = cited as background/context;
#       I = cited as implementation source; X = excluded (not cited)
ROLE_REASON = {
 # ---------------- cited ----------------
 "R49": ("B", "Frames the retail-identification literature and the recognition/verification distinction in Sec. I-A and II-D."),
 "R50": ("B", "Second survey anchor for the same framing; used only for scope, not for any numeric claim."),
 "R51": ("C", "Defines the expected-product verification task with abstention, the formulation NXTCart adopts. Abstract-level only."),
 "R81": ("B", "Industry deployment context only. Explicitly labelled a vendor claim in the text."),
 "R82": ("B", "Industry deployment context only. Explicitly labelled a vendor claim in the text."),
 "R84": ("C", "Closest early barcode+weight+image cart; cited in Sec. I-B as the reason the modality combination is NOT claimed novel."),
 "R85": ("C", "Earliest load-cell + image-comparison cart located; same anti-novelty role as R84."),
 "R02": ("C", "RP4, full text read. Direct weight-reconciliation comparator; its future work proposes exactly NXTCart's visual gate. Table I row; citation-quality issues recorded in Sec. II-B."),
 "R01": ("C", "RP1, full text read. Closest method comparator (weight-triggered, decision-level fusion). Table I row; citation inconsistencies recorded in Sec. II-C."),
 "R07": ("C", "RP8, full text read. Closest methodological comparator for crop -> frozen embedding -> nearest reference; its 40-class P@1 is the key calibration for our expectations."),
 "R52": ("C", "Class-verification comparator for self-checkout; supports the verification-vs-identification distinction. Abstract-level only."),
 "R31": ("I", "Original architecture of the frozen feature extractor actually used. Weights, preprocessing and embedding layer documented separately in Sec. VI-A."),
 "R54": ("I", "ROS 2 design/architecture reference for the distributed implementation."),
 "R61": ("C", "Selective-classification theory underpinning the abstain-rather-than-decide rule and the risk-coverage reporting requirement."),
 "R10": ("B", "RFID cart lineage; establishes that wireless cart billing predates camera verification."),
 "R18": ("B", "Earlier RFID/ZigBee automatic-billing cart in the same lineage."),
 "R11": ("C", "RP2, full text read. Table I row; its internal 125 kHz vs 860-960 MHz conflict is recorded in Sec. II-A."),
 "R12": ("C", "RP3, full text read. Table I row; its own conclusion (prices items without considering brands) is used to separate category pricing from branded-SKU verification."),
 "R83": ("B", "Historical Springer cart comparator; cited with the publisher's corrected five-author attribution."),
 "R06": ("B", "Secure-shopping architecture and communication protocol; used for system requirements, not as proof that RFID resolves substitution."),
 "R47": ("B", "Weight-sensor cart/rack lineage."),
 "R48": ("B", "Anti-theft cart combining RFID/ZigBee with weight."),
 "R17": ("B", "Early theft-control cart prototype."),
 "R04": ("C", "RP6, full text read. Table I row; the clearest example of category-level produce recognition (3 classes, 70 %) versus branded-SKU verification."),
 "R05": ("C", "RP7, full text read. Table I row; its 'Unknown item' checkout block is prior art for our unreconciled-mass block."),
 "R03": ("C", "RP5, full text read. Table I row; closest design comparator and an explicit example of an unevaluated anti-switching claim."),
 "R26": ("C", "RP9, full text read. Table I row; recent multimodal cart whose reported results are a qualitative interface walkthrough."),
 "R09": ("B", "Edge/cloud cart baseline for placement of inference and network dependency."),
 "R24": ("B", "RFID/cloud cart baseline."),
 "R21": ("B", "Context for proposed-but-unimplemented extensions (tracking, inventory forecasting) in Sec. X."),
 "R27": ("C", "RP10, full text read. Table I row; its F1 = 0.4783 calibrates expectations for fine-grained retail identification from video."),
 "R42": ("B", "Core fine-grained checkout benchmark; named as the reference benchmark family, not used for any NXTCart number."),
 "R38": ("B", "Densely packed retail detection; defines the recognition task NXTCart does not perform."),
 "R39": ("B", "Grocery dataset anchor for the same purpose."),
 "R63": ("B", "Synthetic / digital-twin training data; relevant to the synthetic-to-real gap discussion."),
 "R08": ("C", "Multi-camera retail classification; viewpoint and lookalike confusion, relevant to camera-placement limits."),
 "R30": ("C", "Context-aware fine-grained retail classification; lookalike confusion prior art."),
 "R58": ("B", "Named in Sec. II-D and Sec. X as a candidate replacement backbone; not implemented."),
 "R59": ("B", "Same role as R58."),
 "R62": ("B", "Current SKU-level retrieval with open VLMs; named as a future comparator. Cited as the verified arXiv version only."),
 "R45": ("C", "FAIM: strongest open prior art on vision+weight interaction in retail. Abstract-level only; full text pending."),
 "R46": ("C", "AIM3S: multimodal retail sensing. Abstract-level only; cited with the full-paper DOI, not the two-page demo DOI."),
 "R37": ("B", "Classical fusion tutorial, used to frame why NXTCart deliberately does NOT fuse."),
 "R53": ("B", "Modern fusion review, same role as R37."),
 "R60": ("C", "Calibration: why a cosine similarity is not a probability of correct verification."),
 "R34": ("B", "Original YOLO; background for the detector-based cart literature. Explicitly not evidence about YOLOv8/v11 or about NXTCart."),
 "R35": ("B", "SORT; tracking background, cited to explain why NXTCart reports no tracking metrics."),
 "R36": ("B", "DeepSORT; same role as R35."),
 "R72": ("I", "Primary reference for best-effort image delivery and why frame loss is an explicit design parameter."),
 "R74": ("I", "Manufacturer datasheet for the ADC actually used. Cited for gain/sample-rate facts only; ADC bit depth is not mechanism accuracy."),
 "R75": ("I", "The scale library actually named by the firmware and the setup guide."),
 "R79": ("I", "Persistent calibration storage used by the firmware."),
 "R78": ("I", "The barcode/QR decoding dependency actually used."),
 "R77": ("I", "The ONNX / OpenCV DNN inference path actually used."),
 "R66": ("I", "Standard reference for the binary morphology operations in Eqs. (11)-(14)."),
 "R80": ("I", "Payment-system context; supports the request-versus-settlement distinction in Sec. IX-F."),
 # ---------------- excluded ----------------
 "R13": ("X", "Raspberry Pi / RFID cart; adds no dimension to Table I beyond R10/R24 and was not read in full. Metadata verified; retained for a future systematic review."),
 "R14": ("X", "Generic AI/IoT cart integration; metadata-only, no distinguishing mechanism relevant to expected-SKU verification."),
 "R15": ("X", "RFID trolley billing with load cell; redundant with R47/R48 for the weight-centric lineage."),
 "R16": ("X", "RFID/cloud billing design; redundant with R24."),
 "R19": ("X", "Early multi-tag RFID auto-checkout; superseded for our purposes by R10/R18."),
 "R20": ("X", "3S-cart: modular sensing and shopper interaction; promotion/navigation focus is peripheral to billing integrity."),
 "R22": ("X", "Item prediction / next-buy navigation; out of scope (NXTCart performs no recommendation or prediction)."),
 "R23": ("X", "Radar self-following cart; locomotion and navigation are out of scope."),
 "R25": ("X", "Anti-theft billing cart; metadata-only and redundant with R48/R17 in the anti-theft lineage."),
 "R28": ("X", "ACO image-enhancement variant; redundant with R27 for the conveyor-ACO comparison."),
 "R29": ("X", "Iterative knowledge distillation for ACO; a training method for a task NXTCart does not perform."),
 "R32": ("X", "MobileNetV3; not the model in the code. Citing it would misrepresent the implementation."),
 "R33": ("X", "ResNet; not used in the live path."),
 "R40": ("X", "In-situ grocery recognition from in-vitro training data; dataset coverage already carried by R38/R39/R42/R63."),
 "R41": ("X", "M5Product multimodal e-commerce pretraining; e-commerce imagery is a different domain from cart insertion."),
 "R43": ("X", "MVTec D2S; redundant with R38 for dense retail segmentation."),
 "R44": ("X", "MEP-3M; e-commerce domain, same reason as R41. Also the dataset mis-attributed inside RP1's reference list."),
 "R55": ("X", "ByteTrack; NXTCart contains no tracker, so a third tracking citation adds nothing."),
 "R56": ("X", "HOTA; a multi-object-tracking metric for a task NXTCart does not perform and does not report."),
 "R57": ("X", "EfficientNet; not used in the live path."),
 "R64": ("X", "Freiburg Groceries; dataset coverage already sufficient."),
 "R65": ("X", "AI City Challenge 2023 Track 4 data documentation; the 2022 edition is the one R27 reports against."),
 "R67": ("X", "Deep Learning (Goodfellow et al.); no specific claim in the manuscript needs a general textbook."),
 "R68": ("X", "Pattern Recognition and Machine Learning; same reason as R67."),
 "R69": ("X", "RFID Handbook; NXTCart has no RFID implementation, and the RFID limitations cited are drawn from the cart papers themselves."),
 "R70": ("X", "Handbook of Multisensor Data Fusion; R37 and R53 already carry the fusion framing."),
 "R71": ("X", "Introduction to Embedded Systems; no specific claim needs it."),
 "R73": ("X", "ROS 2 security setup; the cited behaviour is the ABSENCE of DDS security, stated as a limitation in Sec. IX-F rather than as a configured feature. Add this citation only if security is actually enabled."),
 "R76": ("X", "GS1 General Specifications; the manuscript makes no claim about barcode symbology or GTIN structure. The catalogue maps whatever string the decoder returns, so the standard is not load-bearing."),
}

DISPOSITION = {
    "C": "**Cited [{n}]** - direct comparator / method",
    "B": "**Cited [{n}]** - background / context",
    "I": "**Cited [{n}]** - implementation source",
    "X": "**Excluded** (not cited)",
}


def depth(e):
    # The 10 supplied PDFs were read in full during this manuscript pass.
    # The catalogue's own `evidence` field predates RP4-RP10 being supplied
    # (it only records RP1-RP3 as read), so override it here rather than
    # under-reporting the review depth actually achieved.
    if e['ref'] in SUPPLIED:
        return "**Full text read** (supplied PDF)"
    ev = (e.get('evidence') or '').lower()
    if 'supplied full text reviewed' in ev:
        return "**Full text read**"
    if 'dataset page' in ev:
        return "Metadata + dataset page"
    if 'publisher abstract' in ev or 'author/publisher abstract' in ev:
        return "Metadata + abstract"
    if 'primary abstract/landing page' in ev:
        return "Abstract / landing page"
    if 'indexed ros documentation' in ev:
        return "Official docs (indexed mirror)"
    if 'full text pending' in ev:
        return "Metadata only - **full text pending**"
    return (e.get('evidence') or '')[:48]


# RPn -> Rnn mapping: RP1-RP3 from SUPPLIED_PAPER_AUDIT.md, RP4-RP10 identified
# in this pass by matching each PDF's printed DOI against the catalogue.
SUPPLIED = {"R01": "RP1", "R11": "RP2", "R12": "RP3", "R02": "RP4", "R03": "RP5",
            "R04": "RP6", "R05": "RP7", "R07": "RP8", "R26": "RP9", "R27": "RP10"}

rows_cited, rows_excl = [], []
for ref in sorted(cat, key=lambda r: int(r[1:])):
    e = cat[ref]
    role, reason = ROLE_REASON[ref]
    disp = DISPOSITION[role].format(n=NUM.get(ref))
    ieee = e.get('ieee_id') or ''
    if ieee:
        ident = "IEEE " + ieee
    elif e.get('doi'):
        ident = "DOI " + e['doi']
    else:
        ident = "no DOI/ID"
    pdf = SUPPLIED.get(ref, "")
    title = e['title'].replace('|', r'\|')
    rows = rows_cited if role != "X" else rows_excl
    rows.append("| {ref}{pdf} | {yr} | {pr} | {kind} | {title} | {ident} | {depth} | {disp} | {reason} |".format(
        ref=ref, pdf=(" **(" + pdf + ")**" if pdf else ""), yr=e['year'], pr=e['priority'],
        kind=e['kind'], title=title, ident=ident, depth=depth(e), disp=disp, reason=reason))

hdr = ("| Ref | Year | Pri. | Kind | Title | Identifier | Review depth | Disposition | Reason |\n"
       "|---|---|---|---|---|---|---|---|---|")
with open(out_path, 'w', encoding='utf-8') as f:
    f.write("<!--CITED_TABLE-->\n" + hdr + "\n" + "\n".join(rows_cited) + "\n\n")
    f.write("<!--EXCLUDED_TABLE-->\n" + hdr + "\n" + "\n".join(rows_excl) + "\n")

print("cited:", len(rows_cited), "excluded:", len(rows_excl),
      "total:", len(rows_cited) + len(rows_excl))
print("numbers assigned:", len(NUM), "max:", max(NUM.values()))
missing = [r for r in cat if r not in ROLE_REASON]
print("catalogue refs with no disposition:", missing)
unused = [r for r in ORDER if r not in cat]
print("cited refs not in catalogue:", unused)
