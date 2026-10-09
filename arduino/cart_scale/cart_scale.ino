// HX711 (bogde/HX711 library). DT=3, SCK=2. All weights are GROSS grams.
// Calibration is explicitly saved in EEPROM; NEVER auto-tare at boot.
// Serial 115200: W,seq,grams,stable,calibrated and V,txn,delta,PASS|FAIL.
// Pi command: E,txn,baseline_g,expected_g,tolerance_g
// Bench calibration ONLY: ZERO with empty cart; CAL,500 with known 500g load.
#include <HX711.h>
#include <EEPROM.h>
#include <math.h>

HX711 scale;
struct Calibration { unsigned long magic; long offset; float factor; } cal;
const unsigned long MAGIC = 0x4E585432;
const byte WINDOW = 6;
float samples[WINDOW];
byte count = 0, cursor = 0;
unsigned long seq = 0, lastSample = 0, expectedAt = 0;
const float STABLE_SPAN_G = 4.0; // measure and tune on mounted cart
const float CHANGE_G = 5.0;
char input[160]; byte used = 0;
char txn[65] = "";
float baseline = 0, expected = 0, tolerance = 0;
bool calibrated = false, haveZero = false;

void verdict(float delta, bool pass) {
  if (!txn[0]) return;
  Serial.print("V,"); Serial.print(txn); Serial.print(','); Serial.print(delta, 3);
  Serial.println(pass ? ",PASS" : ",FAIL"); txn[0] = 0;
}

void command(char *line) {
  if (!strcmp(line, "ZERO")) {
    if (!scale.is_ready()) return;
    cal.offset = scale.read_average(10); scale.set_offset(cal.offset);
    haveZero = true; calibrated = false; count = 0; txn[0] = 0;
    Serial.println("INFO,ZERO accepted. Add known mass and send CAL,grams"); return;
  }
  if (!strncmp(line, "CAL,", 4)) {
    float known = atof(line + 4);
    if (!haveZero || !isfinite(known) || known <= 0 || !scale.is_ready()) return;
    cal.factor = (scale.read_average(10) - cal.offset) / known;
    if (!isfinite(cal.factor) || fabs(cal.factor) < 0.001) return;
    cal.magic = MAGIC; EEPROM.put(0, cal); scale.set_scale(cal.factor);
    calibrated = true; count = 0;
    Serial.println("INFO,Calibration saved. Remove known mass"); return;
  }
  if (!strncmp(line, "E,", 2)) {
    char *token = strtok(line, ","); token = strtok(NULL, ",");
    if (!token || strlen(token) > 64) return;
    char newTxn[65]; strcpy(newTxn, token);
    token = strtok(NULL, ","); if (!token) return; float b = atof(token);
    token = strtok(NULL, ","); if (!token) return; float e = atof(token);
    token = strtok(NULL, ","); if (!token) return; float t = atof(token);
    if (!isfinite(b) || !isfinite(e) || !isfinite(t) || e <= 0 || t <= 0 || t >= e) return;
    verdict(0, false); // a second unsettled expectation invalidates the first
    strcpy(txn, newTxn); baseline = b; expected = e; tolerance = t; expectedAt = millis();
  }
}

void setup() {
  Serial.begin(115200); scale.begin(3, 2); EEPROM.get(0, cal);
  calibrated = cal.magic == MAGIC && isfinite(cal.factor) && fabs(cal.factor) >= 0.001;
  if (calibrated) { scale.set_scale(cal.factor); scale.set_offset(cal.offset); }
  else { scale.set_scale(1); scale.set_offset(0); }
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') { input[used] = 0; command(input); used = 0; }
    else if (c != '\r') { if (used < sizeof(input)-1) input[used++] = c; else used = 0; }
  }
  unsigned long now = millis();
  if (txn[0] && now-expectedAt > 20000UL) verdict(0, false);
  if (now-lastSample < 100 || !scale.is_ready()) return;
  lastSample = now;
  float grams = scale.get_units(1);
  if (!isfinite(grams)) return;
  samples[cursor] = grams; cursor = (cursor+1) % WINDOW; if (count < WINDOW) count++;
  float low = samples[0], high = samples[0], total = 0;
  for (byte i=0; i<count; i++) { low = min(low, samples[i]); high = max(high, samples[i]); total += samples[i]; }
  bool stable = calibrated && count == WINDOW && high-low <= STABLE_SPAN_G;
  float reading = stable ? total/count : grams;
  Serial.print("W,"); Serial.print(++seq); Serial.print(','); Serial.print(reading, 3);
  Serial.print(','); Serial.print(stable ? 1 : 0); Serial.print(','); Serial.println(calibrated ? 1 : 0);
  if (stable && txn[0] && fabs(reading-baseline) > CHANGE_G) {
    float delta = reading-baseline; verdict(delta, fabs(delta-expected) <= tolerance);
  }
}
