"""Static sanity checks on the LaTeX manuscript.

Cannot replace compilation (no TeX distribution on this host). Catches the
failure modes that are detectable without TeX: stray non-ASCII in text mode,
unbalanced environments, unbalanced braces, and tabular column-count mismatches.

Run:  py -I tools/tex_check.py
"""
import collections
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(os.path.dirname(HERE), 'NXTCart_IEEEtran.tex')

src = io.open(TEX, encoding='utf-8').read()
problems = []

# ---- 1. non-ASCII -----------------------------------------------------------
non_ascii = collections.Counter(ch for ch in src if ord(ch) > 127)
print('1. non-ASCII characters: %d distinct' % len(non_ascii))
for ch, n in non_ascii.most_common():
    print('     U+%04X %r x%d' % (ord(ch), ch, n))
if non_ascii:
    problems.append('non-ASCII present; verify each is valid in its mode '
                    '(pdflatex has defaulted to UTF-8 input since 2018, but '
                    'glyphs such as U+2264 are not valid in text mode)')

# ---- 2. environment balance -------------------------------------------------
begins = collections.Counter(re.findall(r'\\begin\{([A-Za-z]+\*?)\}', src))
ends = collections.Counter(re.findall(r'\\end\{([A-Za-z]+\*?)\}', src))
print('\n2. environment balance:')
for k in sorted(set(begins) | set(ends)):
    ok = begins[k] == ends[k]
    print('     %-16s begin=%-3d end=%-3d %s' % (k, begins[k], ends[k], '' if ok else '<-- UNBALANCED'))
    if not ok:
        problems.append('environment %s unbalanced (%d/%d)' % (k, begins[k], ends[k]))

# ---- 3. brace balance -------------------------------------------------------
stripped = re.sub(r'\\[{}]', '', src)          # drop escaped braces
stripped = re.sub(r'(?m)^%.*$', '', stripped)  # drop comment lines
op, cl = stripped.count('{'), stripped.count('}')
print('\n3. brace balance: open=%d close=%d delta=%d' % (op, cl, op - cl))
if op != cl:
    problems.append('brace delta %d' % (op - cl))

# ---- 4. tabular column counts ----------------------------------------------
print('\n4. tabular column specs vs widest row:')
for m in re.finditer(r'\\begin\{tabular\}\{@\{\}(.*?)@\{\}\}(.*?)\\end\{tabular\}',
                     src, re.S):
    spec, bodytxt = m.group(1), m.group(2)
    ncol = len(re.findall(r'p\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|[lcr]', spec))
    widest, wline = 0, ''
    for line in bodytxt.splitlines():
        if '\\\\' not in line or line.strip().startswith('%'):
            continue
        # Escaped \& is literal text, not a column separator.
        cells = re.sub(r'\\&', '', line).split('&')
        if len(cells) > widest:
            widest, wline = len(cells), line.strip()[:60]
    flag = '' if widest <= ncol else '  <-- ROW HAS MORE CELLS THAN COLUMNS'
    print('     spec=%d cols, widest row=%d cells%s' % (ncol, widest, flag))
    if widest > ncol:
        problems.append('tabular with %d cols has a %d-cell row: %s' % (ncol, widest, wline))

# ---- 5. required structure --------------------------------------------------
print('\n5. required structure:')
for needle, label in [
        (r'\documentclass[conference]{IEEEtran}', 'IEEEtran conference class'),
        (r'\begin{document}', 'begin document'),
        (r'\end{document}', 'end document'),
        (r'\maketitle', 'maketitle'),
        (r'\begin{abstract}', 'abstract'),
        (r'\begin{IEEEkeywords}', 'keywords'),
        (r'\begin{thebibliography}', 'inlined bibliography')]:
    ok = needle in src
    print('     %-28s %s' % (label, 'present' if ok else 'MISSING'))
    if not ok:
        problems.append('missing %s' % label)

# ---- 6. bibliography / citation agreement -----------------------------------
items = re.findall(r'\\bibitem\{(\w+)\}', src)
cites = set()
for m in re.finditer(r'\\cite\{([^}]*)\}', src):
    cites.update(k.strip() for k in m.group(1).split(','))
print('\n6. bibliography: %d bibitems, %d distinct \\cite keys' % (len(items), len(cites)))
dup = [k for k, n in collections.Counter(items).items() if n > 1]
missing = sorted(cites - set(items))
uncited = sorted(set(items) - cites)
print('     duplicate bibitems : %s' % (dup or 'none'))
print('     cited but undefined: %s' % (missing or 'none'))
print('     defined but uncited: %s' % (uncited or 'none'))
for lbl, lst in (('duplicate bibitem', dup), ('undefined citation', missing),
                 ('uncited bibitem', uncited)):
    if lst:
        problems.append('%s: %s' % (lbl, lst))

# ---- 7. label / ref agreement ----------------------------------------------
labels = set(re.findall(r'\\label\{([^}]*)\}', src))
refs = set(re.findall(r'\\ref\{([^}]*)\}', src))
print('\n7. labels=%d refs=%d' % (len(labels), len(refs)))
print('     dangling \\ref: %s' % (sorted(refs - labels) or 'none'))
print('     unused \\label: %s' % (sorted(labels - refs) or 'none'))
if refs - labels:
    problems.append('dangling refs: %s' % sorted(refs - labels))

# ---- report -----------------------------------------------------------------
print('\n' + '=' * 60)
if problems:
    print('STATIC CHECK: %d issue(s)' % len(problems))
    for p in problems:
        print('  - %s' % p)
else:
    print('STATIC CHECK: no issues detected')
print('NOTE: this is NOT a compilation. pdflatex has not been run.')
sys.exit(1 if problems else 0)
