# lora_module_test

LoRa module test tool for serial AT checks, MVP transfer cases, formal AT cases, abnormal AT cases, and formal transfer cases.

## Install

```bash
pip install -r requirements.txt
```

## Configure devices

Default device config:

```text
lora_auto/config/devices.yaml
```

Example:

```yaml
devices:
  A:
    port: "COM3"
    baudrate: 9600
    role: sender
  B:
    port: "COM4"
    baudrate: 9600
    role: receiver
  C:
    port: "COM5"
    baudrate: 9600
    role: receiver
```

A/B are enough for AT, MVP, transparent, and fixed-transfer cases. Add C for broadcast-transfer cases. On Linux/macOS, replace `COM3`, `COM4`, and `COM5` with serial ports such as `/dev/ttyUSB0`, `/dev/ttyUSB1`, and `/dev/ttyUSB2`.

## Check one module over serial

```bash
python lora_auto/examples/check_serial.py --port COM3
```

With explicit options:

```bash
python lora_auto/examples/check_serial.py --port COM3 --baudrate 9600 --command AT --expected OK
```

## Run MVP cases

Run all MVP cases:

```bash
python lora_auto/test_mvp.py --config lora_auto/config/devices.yaml --cases lora_auto/config/mvp_cases.yaml
```

Run one MVP case:

```bash
python lora_auto/test_mvp.py --case MVP-003
```

Write reports to a custom directory:

```bash
python lora_auto/test_mvp.py --report-dir reports/local-run
```

## Run formal AT cases

Run the normal AT suite:

```bash
python lora_auto/test_formal.py --suite at
```

Run one normal AT case:

```bash
python lora_auto/test_formal.py --case AT-001
```

Preview the normal AT suite without hardware access:

```bash
python lora_auto/test_formal.py --suite at --dry-run
```

## Run abnormal AT cases

Run the abnormal AT suite:

```bash
python lora_auto/test_formal.py --suite error_at
```

Run one abnormal AT case:

```bash
python lora_auto/test_formal.py --case ERRAT-001
```

Preview the abnormal AT suite without hardware access:

```bash
python lora_auto/test_formal.py --suite error_at --dry-run
```

Abnormal AT cases pass when the expected `ERROR=<code>` is received and the follow-up `AT` health check succeeds.

## Run formal transfer cases

Run all formal transfer cases:

```bash
python lora_auto/test_formal.py --suite main
```

Run one transfer case:

```bash
python lora_auto/test_formal.py --case MAIN-001
```

Preview transfer cases without hardware access:

```bash
python lora_auto/test_formal.py --suite main --dry-run
```

`MAIN-001` through `MAIN-006` cover transparent, fixed, and broadcast transfer. Broadcast cases require devices A, B, and C in `devices.yaml`.

## Reports

Default report output:

```text
reports/
  result.json
  result.md
  logs/<case_id>_runner.log
```

## Case files

```text
lora_auto/config/mvp_cases.yaml
lora_auto/config/formal/
  main_cases.yaml
  at_cases.yaml
  error_at_cases.yaml
  ship_cases.yaml
  iter_cases.yaml
```

## Run tests

```bash
pytest
```
