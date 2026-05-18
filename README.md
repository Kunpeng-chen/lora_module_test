# lora_module_test

A Python-based testing tool for LoRa modules, providing an easy way to validate communication and performance.

## Phase 1: serial AT baseline

Phase 1 provides a minimal serial connectivity check for a single LoRa module.

### Install dependencies

```bash
pip install -r requirements.txt
```

### Check a module over serial

Windows example:

```bash
python lora_auto/examples/check_serial.py --port COM3
```

Linux/macOS example:

```bash
python lora_auto/examples/check_serial.py --port /dev/ttyUSB0
```

Optional arguments:

```bash
python lora_auto/examples/check_serial.py --port COM3 --baudrate 9600 --timeout 2 --command AT --expected OK
```

Successful output contains:

```text
TX: AT
RX: OK
PASS
```

## Phase 3: A/B device configuration baseline

Phase 3 adds a device abstraction and an example A/B serial configuration file.

Example config file:

```text
lora_auto/config/devices.yaml
```

Default Windows-style example:

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

For Linux/macOS, replace `port` values with serial device paths such as `/dev/ttyUSB0` and `/dev/ttyUSB1`.

Field meanings:

| Field | Description |
|---|---|
| `port` | Serial port connected to the LoRa module. |
| `baudrate` | Serial baudrate used by the module. |
| `role` | Logical test role, for example `sender` or `receiver`. |

The Phase 3 transparent-mode configuration flow uses these AT commands internally:

```text
+++
AT+SLEEP2
AT+MODE0
AT+LEVEL2
AT+CHANNEL00
AT+RESET
```

## Phase 4: MVP case runner

Phase 4 adds a minimal YAML-driven runner for three MVP case types:

- `at`
- `config`
- `transparent_transfer`

Example cases file:

```text
lora_auto/config/mvp_cases.yaml
```

Run all MVP cases:

```bash
python lora_auto/test_mvp.py --config lora_auto/config/devices.yaml --cases lora_auto/config/mvp_cases.yaml
```

Run a single case:

```bash
python lora_auto/test_mvp.py --case MVP-003
```

Useful options:

| Option | Description |
|---|---|
| `--config` | Device config YAML path. |
| `--cases` | MVP cases YAML path. |
| `--case` | Run only one case ID. |
| `--log-level` | Python logging level. |
| `--report-dir` | Reserved for report output in later phases. |

Successful transparent-transfer output contains:

```text
[MVP-003] 透明传输收发一致性测试 PASS
```

Failure output includes a failure reason, including the sent and received payload details when transparent transfer validation fails.

## Run tests

```bash
pytest
```
