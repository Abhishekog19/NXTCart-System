# Direct scan protocol; the Pi remains the cart/checkout authority.
string scan_id
bool approved
# Transaction fields retained for selected removals and older consumers.
string action
uint32 attempt
bool detected

# Extended fields for identity verification (anti-swap gate)
# verdict: MATCH | SUSPECT | MISMATCH | RETRY | UNAVAILABLE | UNVERIFIED
string verdict
bool verified
string barcode
string name
string txn_id
float32 appearance_score
float32 colour_score
string reason
