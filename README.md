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

### Run tests

```bash
pytest
```
