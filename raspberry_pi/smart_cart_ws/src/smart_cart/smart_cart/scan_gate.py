"""A code re-arms only after a continuous observed absence, never an outage."""
class ScanGate:
    def __init__(self, rearm_seconds=.8):
        self.rearm_seconds = rearm_seconds
        self.blocked = {}

    def gap(self):
        for code in self.blocked:
            self.blocked[code] = None

    def observe(self, codes, now):
        for code, absent_since in list(self.blocked.items()):
            if code in codes:
                self.blocked[code] = None
            elif absent_since is None:
                self.blocked[code] = now
            elif now-absent_since >= self.rearm_seconds:
                del self.blocked[code]
        if len(codes) > 1:
            for code in codes:
                self.blocked[code] = None
            return None
        if len(codes) == 1:
            code = next(iter(codes))
            if code not in self.blocked:
                self.blocked[code] = None
                return code
        return None
