# lora_module_test

LoRa module test tool for serial AT checks, MVP transfer cases, formal AT cases, and abnormal AT cases.

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
```

On Linux/macOS, replace `COM3` and `COM4` with serial ports such as `/dev/ttyUSB0` and `/dev/ttyUSB1`.

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

`main_cases.yaml` currently contains transfer-mode case data. Formal transfer execution will be added later.

## Run tests

```bash
pytest
```
