# lora_module_test

A Python-based testing tool for LoRa modules, providing an easy way to validate communication and performance.

## Install dependencies

```bash
pip install -r requirements.txt
```

## Phase 1: serial AT baseline

Phase 1 provides a minimal serial connectivity check for a single LoRa module.

### Check a module over serial

The checker enters AT mode first by sending `+++\r\n` and waiting for `Entry AT`, then sends the requested AT command with `\r\n` appended. After the requested AT command passes, it exits AT mode by sending `+++\r\n` and waiting for `Exit AT`. The exit flow also drains the short reset banner window, such as `Power on`, and clears serial buffers so stale reset output does not affect the next step.

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

If the module is already in AT mode, skip the entry step:

```bash
python lora_auto/examples/check_serial.py --port COM3 --skip-enter-at
```

To keep the module in AT mode after a successful check, skip the exit step:

```bash
python lora_auto/examples/check_serial.py --port COM3 --skip-exit-at
```

Successful output contains:

```text
TX: +++
RX: Entry AT
TX: AT
RX: OK
PASS
TX: +++
RX: Exit AT
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

The Phase 3 transparent-mode configuration flow clears stale serial buffers first, then uses these AT commands internally. Each AT command is sent with `\r\n` appended:

```text
+++
AT+SLEEP2
AT+MODE0
AT+LEVEL2
AT+CHANNEL00
AT+RESET
```

After `AT+RESET` returns `OK`, the reset flow also drains delayed boot-banner output such as `Power on` and clears serial buffers before the next case starts.

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
| `--report-dir` | Report output directory. |

For `at` cases, the runner enters AT mode first, runs the configured AT steps, then exits AT mode before the next case. The AT exit flow drains reset banner output and clears stale serial buffers. If the config case fails, the transparent-transfer case is reported as `BLOCKED` instead of continuing with invalid preconditions.

For `transparent_transfer` cases, the runner clears sender and receiver buffers before sending, then reads until the expected payload appears or the timeout expires. Failure output includes the sent payload, received text, received hex bytes, and received byte count to make stale boot banners, empty reads, and garbled serial data easier to distinguish.

Successful transparent-transfer output contains:

```text
[MVP-003] 透明传输收发一致性测试 PASS
```

Failure output includes a failure reason, including the sent and received payload details when transparent transfer validation fails. Blocked output includes the failed prerequisite reason.

## Phase 5: reports and logs

Phase 5 writes structured reports and per-case logs after each MVP run.

Default output location:

```text
reports/
  result.json
  result.md
  logs/
    MVP-001_runner.log
    MVP-002_runner.log
    MVP-003_runner.log
```

Use a custom output directory:

```bash
python lora_auto/test_mvp.py --report-dir reports/local-run
```

The JSON report contains a summary and full case entries. The Markdown report contains a summary table and case result table.

## Formal test case model baseline

The formal test case baseline introduces a structured YAML model for the later full formal test system. It does not execute serial ports or hardware yet.

Formal case files are split by suite under:

```text
lora_auto/config/formal/
  main_cases.yaml
  at_cases.yaml
  error_at_cases.yaml
  ship_cases.yaml
  iter_cases.yaml
```

Phase 1 intentionally includes only one sample from each suite: `MAIN-001`, `AT-001`, `ERRAT-001`, `SHIP-001`, and `ITER-001`. The loader in `lora_auto/libs/formal_cases.py` validates required fields, case ID uniqueness, priority values, automation levels, run policies, and destructive-case safety. Destructive cases can be represented, but they must not use `run_policy: auto`; use `manual_confirm` or `skip_by_default` instead.

Phase 2 expands `at_cases.yaml` to `AT-001` through `AT-020`. These AT cases are data/model definitions sourced from `docs/manual/dx-lr31-900t22s-uart-application-guide.md`, and each case records its command, expected assertion, and manual reference. Expected assertions use explicit modes such as `contains`, `contains_all`, or `regex`.

State-changing AT cases are not selected for automatic execution by default. `AT+RESET` is marked `semi_auto` with `run_policy: manual_confirm`; `AT+DEFAULT` is additionally marked `destructive: true` and must remain manual-confirm only.

Phase 3 adds a formal AT runner entrypoint for the normal AT suite:

```bash
python lora_auto/test_formal.py --suite at
python lora_auto/test_formal.py --case AT-001
python lora_auto/test_formal.py --suite at --dry-run
```

By default, the runner only selects safe automatic cases: `automation_level: auto`, `run_policy: auto`, non-destructive metadata, and no state-changing steps. Before executing query-style AT cases, the runner probes `AT -> OK`; if needed it enters AT mode with `+++ -> Entry AT` and verifies with `AT -> OK`.

Phase 4 adds the formal abnormal AT suite:

```bash
python lora_auto/test_formal.py --suite error_at
python lora_auto/test_formal.py --case ERRAT-001
python lora_auto/test_formal.py --suite error_at --dry-run
```

The `error_at` suite expands `ERRAT-001` through `ERRAT-057` from `lora_auto/config/formal/error_at_cases.yaml`. expect `ERROR=101`. Receiving the configured error code is a PASS condition for the negative command step. Each negative command is followed by a post-check `AT -> OK`; missing the expected error code or failing the post-check makes the case FAIL. The runner uses the normalized `ERROR=<code>` spelling rather than the manual typo `EEROR`.

Reports are written with the existing report layout:

```text
reports/
  result.json
  result.md
  logs/<case_id>_runner.log
```

This baseline is data/model preparation plus the first AT and abnormal-AT execution paths only. Transfer execution, stress tests, and measurement evidence flow are planned as later phases.

## Run tests

```bash
pytest
```
