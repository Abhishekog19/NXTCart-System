"""Strict Arduino parsing; legacy lines cannot masquerade as stable evidence."""
import math


def parse_line(line):
    parts = line.strip().split(',')
    if len(parts) == 5 and parts[0] == 'W':
        seq, grams = int(parts[1]), float(parts[2])
        if seq < 0 or not math.isfinite(grams) or parts[3] not in ('0', '1') or parts[4] not in ('0', '1'):
            raise ValueError('invalid weight packet')
        return ('sample', seq, grams, parts[3] == '1', parts[4] == '1')
    if len(parts) == 4 and parts[0] == 'V':
        grams = float(parts[2])
        if not parts[1] or not math.isfinite(grams) or parts[3] not in ('PASS', 'FAIL'):
            raise ValueError('invalid verdict packet')
        return ('verdict', parts[1], grams, parts[3] == 'PASS')
    raise ValueError('unknown serial packet')
