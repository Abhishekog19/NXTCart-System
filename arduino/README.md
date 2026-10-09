# HX711 firmware

Upload [`cart_scale/cart_scale.ino`](cart_scale/cart_scale.ino) using Arduino IDE
and the bogde/HX711 library. DT is pin 3 and SCK pin 2. Readings are grams;
calibration is persisted in EEPROM and the sketch never auto-tares at startup.

Stop the Pi bridge. In Serial Monitor at 115200 baud with newline endings, send
`ZERO` with the mounted basket empty. Add a known mass and send `CAL,500` for
an actual 500 g mass. Remove it and verify empty return and several known loads.

Pi command: `E,transaction_id,baseline_g,expected_g,tolerance_g`.
Board responses: `W,sequence,grams,stable,calibrated` and
`V,transaction_id,delta_g,PASS|FAIL`.
See [the full guide](../docs/SYSTEM_SETUP.md) for hardware acceptance.
