"""Consistency audit for the NXTCart manuscript deliverables.

Checks, against paper/NXTCart_Manuscript.md unless stated:
  1. Every reference [1]..[N] in the reference list is cited in the body.
  2. Every in-text citation resolves to a reference list entry.
  3. Reference numbering is gapless and duplicate-free.
  4. Equation numbers are sequential.
  5. Table numbers (roman) are sequential and every in-text table reference resolves.
  6. The cited .bib contains exactly the cited refs.
  7. The disposition supplement accounts for every catalogue ref exactly once.
Run:  py -I tools/audit.py
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.dirname(HERE)
CATALOGUE = os.path.join(
    PAPER, '..', '..', 'NXTCart-Cam', 'research', 'resource_catalogue.json')

ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI',
         'XII', 'XIII', 'XIV', 'XV']

failures = []
notes = []


def check(ok, label, detail=''):
    (notes if ok else failures).append(
        '%s %s%s' % ('PASS' if ok else 'FAIL', label, (' -- ' + detail) if detail else ''))


def read(name):
    with io.open(os.path.join(PAPER, name), encoding='utf-8') as f:
        return f.read()


ms = read('NXTCart_Manuscript.md')
body, _, reflist = ms.partition('\n## References\n')
check(bool(reflist), 'manuscript has a References section')

# ---- 1-3. references -------------------------------------------------------
defined = [int(m.group(1)) for m in re.finditer(r'^\[(\d+)\] ', reflist, re.M)]
check(defined == sorted(defined), 'reference list is in ascending order')
check(len(defined) == len(set(defined)), 'no duplicate reference numbers',
      'dupes: %s' % [n for n in set(defined) if defined.count(n) > 1])
check(defined == list(range(1, len(defined) + 1)),
      'reference numbering is gapless 1..%d' % len(defined),
      'got %s' % defined[:5])

# In-text citations: [n] or [n], [m] or [n]-[m]; exclude the reference list and
# the grep-able placeholder markers. Numbering starts at 1, so a leading 0
# means a mathematical interval such as [0,1] or [0, 2160], not a citation.
cited = set()
for m in re.finditer(r'\[([1-9]\d*)\](?:[,–-]\s*\[([1-9]\d*)\])?', body):
    a = int(m.group(1))
    cited.add(a)
    if m.group(2):
        b = int(m.group(2))
        cited.add(b)
        # a dash range cites everything between
        if '–' in m.group(0) or '-' in m.group(0).replace('], [', ''):
            cited.update(range(a, b + 1))

uncited = sorted(set(defined) - cited)
check(not uncited, 'every reference is cited in the body', 'uncited: %s' % uncited)
dangling = sorted(c for c in cited if c not in set(defined))
check(not dangling, 'every in-text citation resolves', 'dangling: %s' % dangling)

# ---- 4. equations ----------------------------------------------------------
eqs = [int(m.group(1)) for m in re.finditer(r'\((\d{1,2})\)\s*$', body, re.M)]
eqs_seq = sorted(set(eqs))
check(eqs_seq == list(range(1, max(eqs_seq) + 1)) if eqs_seq else False,
      'equation numbers are sequential 1..%d' % (max(eqs_seq) if eqs_seq else 0),
      'found %s' % eqs_seq)

# ---- 5. tables -------------------------------------------------------------
declared = re.findall(r'\*\*TABLE ([IVX]+)\.', ms)
expected = ROMAN[:len(declared)]
check(declared == expected, 'table captions are sequential I..%s' % (expected[-1] if expected else '-'),
      'declared %s' % declared)
inline = set(re.findall(r'(?<!\*)\bTABLE ([IVX]+)\b', ms)) - set(declared)
check(not inline, 'every in-text TABLE reference resolves to a caption',
      'unresolved: %s' % sorted(inline))

# ---- 6. bibliography -------------------------------------------------------
bib = read('nxtcart_cited.bib')
bib_refs = re.findall(r'@\w+\{NXTCart(R\d\d),', bib)
bib_nums = [int(m) for m in re.findall(r'^% \[(\d+)\] = R\d\d$', bib, re.M)]
check(len(bib_refs) == len(defined),
      'bib entry count (%d) equals reference count (%d)' % (len(bib_refs), len(defined)))
check(len(set(bib_refs)) == len(bib_refs), 'no duplicate bib entries')
check(bib_nums == list(range(1, len(bib_nums) + 1)),
      'bib comment numbering matches 1..%d' % len(bib_nums))

# ---- 7. disposition --------------------------------------------------------
disp = read('NXTCart_S1_Resource_Disposition.md')
with io.open(os.path.abspath(CATALOGUE), encoding='utf-8') as f:
    cat_refs = {e['ref'] for e in json.load(f)}
rows = re.findall(r'^\| (R\d\d)(?: \*\*\(RP\d+\)\*\*)? \|', disp, re.M)
check(len(rows) == len(cat_refs),
      'disposition has one row per catalogue ref (%d of %d)' % (len(rows), len(cat_refs)))
check(set(rows) == cat_refs, 'disposition refs match the catalogue exactly',
      'missing: %s / extra: %s' % (sorted(cat_refs - set(rows)), sorted(set(rows) - cat_refs)))
check(len(set(rows)) == len(rows), 'no duplicate disposition rows')

disp_cited = set(re.findall(r'^\| (R\d\d)(?: \*\*\(RP\d+\)\*\*)? \|.*\*\*Cited \[(?:\d+)\]',
                            disp, re.M))
check(disp_cited == set(bib_refs),
      'disposition "Cited" set equals the bib set (%d vs %d)' % (len(disp_cited), len(bib_refs)),
      'only in disposition: %s / only in bib: %s'
      % (sorted(disp_cited - set(bib_refs)), sorted(set(bib_refs) - disp_cited)))
disp_nums = [int(n) for n in re.findall(r'\*\*Cited \[(\d+)\]', disp)]
check(sorted(disp_nums) == list(range(1, len(defined) + 1)),
      'disposition citation numbers cover 1..%d exactly once' % len(defined))

# ---- 8. forbidden obsolete descriptions ------------------------------------
FORBIDDEN = [
    (r'five-frame sampling(?!,? JPEG)', 'five-frame sampling'),
    (r'\bJPEG transport\b', 'JPEG transport'),
    (r'\bAPI inference\b', 'API inference'),
]
for pat, label in FORBIDDEN:
    hits = [m.start() for m in re.finditer(pat, body)]
    ctx = []
    for h in hits:
        # Wide window: a disclaimer ("remain stale ... superseded by") can sit a
        # clause or two before the phrase it disclaims.
        seg = body[max(0, h - 260):h + 80].replace('\n', ' ')
        ctx.append(seg)
    # These phrases are permitted ONLY inside an explicit "not"/"retired" context.
    bad = [c for c in ctx if not re.search(
        r'\bnot\b|retired|supersed|obsolete|belong to earlier|do not|never|stale', c, re.I)]
    check(not bad, 'obsolete phrase "%s" appears only in disclaiming context' % label,
          'bare use: %s' % bad[:1])

# ---- 9. placeholder visibility ---------------------------------------------
tbm = len(re.findall(r'\[TO BE MEASURED', ms)) + len(re.findall(r'\[TO BE RECORDED', ms))
check(tbm > 0, 'pending-measurement placeholders are present and greppable',
      '%d markers' % tbm)
notes.append('INFO %d pending-measurement markers in the manuscript' % tbm)
notes.append('INFO %d references, %d equations, %d tables'
             % (len(defined), max(eqs_seq) if eqs_seq else 0, len(declared)))

# ---- report ----------------------------------------------------------------
for line in notes:
    print(line)
print()
for line in failures:
    print(line)
print()
print('AUDIT %s (%d checks, %d failures)'
      % ('PASSED' if not failures else 'FAILED', len(notes) + len(failures), len(failures)))
sys.exit(1 if failures else 0)
