# LoRa 正式测试用例设计计划

## 1. 总目标

在 LoRa 自动化脚本 MVP 已完成的基础上，将上传的 LoRa 透传模组测试表推进为正式测试用例体系。

正式测试阶段不再只验证 MVP 闭环，而是逐步覆盖：

- 主测试用例：`MAIN-*`
- AT 正常指令用例：`AT-*`
- AT 异常指令用例：`ERRAT-*`
- 出货/回归用例：`SHIP-*`、`SHIPAT-*`
- 迭代回归用例：`ITER-*`、`ITERAT-*`
- 休眠、M0/M1、AUX、压力、功耗、射频、距离等半自动或人工证据型用例

整体推进原则：

```text
正式用例模型 -> AT 精确返回数据化 -> AT 执行器 -> 异常 AT -> 传输模式 -> 出货/迭代 -> 半自动与仪表证据
```

## 2. 已确认决策

| 问题 | 决策 |
|---|---|
| 正式用例文件结构 | 按类型拆分为多个 YAML，不使用一个巨大总文件 |
| Phase 1 是否录入全量用例 | 只录入样例用例，先建立 schema / loader / 计划基线 |
| AT 正常指令断言标准 | 以 `docs/manual/dx-lr31-900t22s-uart-application-guide.md` 补精确返回 |
| `AT+DEFAULT` 是否自动执行 | 不允许自动执行，必须标记为 destructive / manual_confirm |
| 广播测试是否有 C 模块 | 存在 C 模块，广播用例按 A/B/C 设计 |
| KEY 设置策略 | 收发端都设置；广播场景 A/B/C 都设置相同 KEY |
| 异常 AT 错误码格式 | 统一使用 `ERROR=<code>`，例如 `ERROR=104`、`ERROR=105` |

## 3. 拆分依据

本计划拆分为 10 个 Phase，而不是一次性完成正式测试体系，原因如下：

1. 正式测试表覆盖范围很广，包含全自动、半自动、人工仪表记录三类用例，必须分层推进。
2. 用例数据化、执行器实现、硬件行为扩展、仪表证据接入属于不同风险等级，不能混在同一个 PR 中。
3. AT 正常指令、异常指令、传输模式、出货回归、压力测试和功耗射频测试的断言模型不同，适合独立验收。
4. 高风险或长时间运行类测试不能进入普通 CI 或阻塞快速开发流程。
5. 每个 Phase 均应能独立提交 PR、独立测试、独立验收。

推荐执行顺序：

```text
Phase 1：正式测试用例模型与计划基线
    ↓
Phase 2：AT 正常指令精确返回建模
    ↓
Phase 3：AT 正常指令执行器
    ↓
Phase 4：异常 AT 指令数据化与执行
    ↓
Phase 5：传输模式用例数据化
    ↓
Phase 6：传输模式执行器
    ↓
Phase 7：出货/迭代回归套件
    ↓
Phase 8：休眠、M0/M1、AUX 半自动化
    ↓
Phase 9：压力测试与长稳测试
    ↓
Phase 10：功耗、射频、距离、工作电压证据模型
```

## 4. 统一用例模型草案

正式用例建议统一使用以下字段。后续 Phase 可按需要扩展，但不应破坏已存在字段语义。

```yaml
id: string
suite: string
feature: string
scenario: string
priority: P0|P1|P2
automation_level: auto|semi_auto|manual
devices: [A, B, C, D]
preconditions:
  - string
steps:
  - action: string
    device: string|null
    command: string|null
    expected: object|null
expected:
  - string
result_policy:
  pass_when:
    - string
  fail_when:
    - string
evidence:
  serial_log: path|null
  logic_analyzer: path|null
  power_record: path|null
  rf_record: path|null
  manual_note: path|null
metadata:
  source: string
  manual_ref: string|null
  destructive: bool
  state_changing: bool
  run_policy: auto|manual_confirm|skip_by_default
```

建议目录结构：

```text
lora_auto/config/formal/
  main_cases.yaml
  at_cases.yaml
  error_at_cases.yaml
  ship_cases.yaml
  iter_cases.yaml
```

---

## Phase 1：正式测试用例模型与计划基线 [√]

目标：

建立正式测试阶段的基础结构，先完成 schema、loader 和少量样例用例，不执行真实硬件。

当前行为：

仓库已有 MVP 用例与 runner，覆盖 AT 基础、A/B 透明传输配置、A 发 B 收透明传输，但 `MAIN-*`、`AT-*`、`ERRAT-*`、`SHIP-*`、`ITER-*` 尚未进入正式数据模型。

目标行为：

新增正式测试计划文档和拆分后的正式用例 YAML 目录。第一阶段只录入样例用例，用于验证模型和 loader。

任务：

- 新增正式用例目录：`lora_auto/config/formal/`
- 新增样例 YAML 文件：
  - `main_cases.yaml`
  - `at_cases.yaml`
  - `error_at_cases.yaml`
  - `ship_cases.yaml`
  - `iter_cases.yaml`
- 首批只录入样例用例：
  - `MAIN-001`
  - `AT-001`
  - `ERRAT-001`
  - `SHIP-001`
  - `ITER-001`
- 新增正式用例 loader 与 schema 校验测试。
- 校验用例 ID 唯一、必填字段完整、自动化等级合法、优先级合法。

不做什么：

- 不录入全部正式测试表用例。
- 不执行真实串口或硬件。
- 不实现正式 runner。
- 不修改 MVP runner 行为。
- 不标记任何后续 Phase 完成。

验收标准：

- `pytest` 全部通过。
- 样例 YAML 可被 loader 正确加载。
- 缺失必填字段时测试失败。
- 重复 case ID 时测试失败。
- `AT+DEFAULT` 这类 destructive 用例可以被模型表达，但默认不允许自动执行。

建议优先级：最高

分支建议：

```text
feat/formal-case-schema-baseline
```

PR 标题建议：

```text
feat: formal test case schema baseline
```

README 影响：

如果新增正式用例目录和 loader，应在 README 中补充正式测试用例结构；如果仅新增计划文档，则 README 可检查后记录无需更新。

---

## Phase 2：AT 正常指令精确返回建模 [ ]

目标：

将 `AT-001` ~ `AT-020` 录入正式用例 YAML，并根据 UART 应用指导手册补充精确 expected。

当前行为：

MVP 只验证基础 `AT` 和配置流程中使用到的部分 AT 命令；测试表中很多 AT 用例仍是“输入有效、输出生效”的人工描述。

目标行为：

`AT-001` ~ `AT-020` 均具备可执行所需的命令、断言、状态变化标记和手册来源引用。

任务：

- 在 `at_cases.yaml` 中录入 `AT-001` ~ `AT-020`。
- 每条用例包含精确 expected：
  - `AT` -> `OK`
  - `+++` -> `Entry AT` 或 `Exit AT`，退出时可能跟随 `Power On`
  - `AT+BAUD` -> `+BAUD=<baud>`
  - `AT+PARI` -> `+PARI=<param>`
  - `AT+MODE` -> `+MODE=<param>`
  - `AT+SLEEP` -> `+SLEEP=<param>`
  - `AT+LEVEL` -> `+LEVEL=<param>`
  - `AT+CHANNEL` -> `+CHANNEL=<param>`
  - `AT+MAC` -> `+MAC=<param>,<param>`
  - `AT+POWE` -> `+POWE=<param>`
  - `AT+PACKET` -> `+PACKET=<param>`
  - `AT+KEY<param>` -> `+KEY=<param>` + `OK`
  - `AT+SWITCH` -> `+SWITCH=<param>`
  - `AT+LBT` -> `+LBT=<param>`
  - `AT+LRSSI` -> `+LRSSI=<param>`
  - `AT+DRSSI` -> `+DRSSI=<param>`
  - `AT+ERSSI` -> `+ERSSI=<param>`
  - `AT+RESET` -> `OK`，随后可能跟随 `Power On`
  - `AT+DEFAULT` -> `OK`，随后可能跟随 `Power On`，但不允许自动执行
- 为每条用例标注 `manual_ref`，指向 `docs/manual/dx-lr31-900t22s-uart-application-guide.md` 对应章节。
- 将 `AT+RESET` 标记为 `state_changing: true`。
- 将 `AT+DEFAULT` 标记为：
  - `state_changing: true`
  - `destructive: true`
  - `run_policy: manual_confirm`
  - `automation_level: semi_auto`

不做什么：

- 不实现正式 runner。
- 不真实执行 AT 指令。
- 不自动执行 `AT+DEFAULT`。
- 不录入异常 AT 指令。

验收标准：

- `AT-001` ~ `AT-020` 全部可被 loader 读取。
- 每条 AT 用例都包含 `command`、`expected`、`manual_ref`。
- `AT+DEFAULT` 默认不会被 auto runner 选择。
- expected 的断言类型明确，例如 `contains`、`contains_all`、`regex`。

建议优先级：最高

分支建议：

```text
feat/formal-at-case-model
```

PR 标题建议：

```text
feat: model formal AT command cases
```

README 影响：

如果新增全量 AT YAML，应说明 AT 用例 expected 来源于 UART 应用指导手册。

---

## Phase 3：AT 正常指令执行器 [ ]

目标：

让 Phase 2 中数据化的 AT 正常指令用例可执行。

当前行为：

MVP runner 只支持 MVP case type：`at`、`config`、`transparent_transfer`，不适合承载正式批量 AT 用例。

目标行为：

新增正式测试 runner 的 AT 执行能力，支持按 suite 或 case ID 执行 AT 正常指令。

任务：

- 新增正式测试入口，例如：

```bash
python lora_auto/test_formal.py --suite at
python lora_auto/test_formal.py --case AT-001
python lora_auto/test_formal.py --suite at --dry-run
```

- 支持加载 `lora_auto/config/formal/at_cases.yaml`。
- 支持 `enter_at`、`send_at`、`reset`、`exit_at` 等动作。
- 支持 `contains`、`contains_all`、`regex`、`exact` 等断言模式。
- 支持 dry-run，仅输出将要执行的步骤，不访问硬件。
- 复用现有报告结构：
  - `reports/result.json`
  - `reports/result.md`
  - `reports/logs/<case_id>_runner.log`

不做什么：

- 不执行 `AT+DEFAULT`。
- 不执行异常 AT 指令。
- 不执行传输类用例。
- 不引入多设备协同。

验收标准：

- `pytest` 全部通过。
- mock 串口下可执行 `AT-001`。
- dry-run 可列出 AT suite 执行计划。
- destructive 或 manual_confirm 用例不会被默认自动执行。
- 报告结构与 MVP 报告兼容，或清晰记录扩展字段。

建议优先级：高

分支建议：

```text
feat/formal-at-runner
```

PR 标题建议：

```text
feat: run formal AT command cases
```

README 影响：

需要新增正式 runner 的使用示例。

---

## Phase 4：异常 AT 指令数据化与执行 [ ]

目标：

覆盖 `ERRAT-001` ~ `ERRAT-057`，统一断言错误码并验证异常命令后模块仍健康。

当前行为：

仓库没有负向 AT 批量测试能力。

目标行为：

57 条异常 AT 用例全部参数化，执行时断言 `ERROR=104` 或 `ERROR=105`，并在每条异常命令后追加 `AT` 健康检查。

任务：

- 在 `error_at_cases.yaml` 中录入 `ERRAT-001` ~ `ERRAT-057`。
- `ERRAT-001` ~ `ERRAT-013` 断言 `ERROR=104`。
- `ERRAT-014` ~ `ERRAT-057` 断言 `ERROR=105`。
- 每条异常命令后追加 post-check：

```yaml
post_check:
  command: AT
  expected:
    mode: contains
    value: OK
```

- 正式 runner 支持 `error_at` suite。
- 报告中区分：
  - 收到预期错误码：PASS
  - 未收到错误码：FAIL
  - 错误码后健康检查失败：FAIL

不做什么：

- 不做随机 fuzz。
- 不做 AT 指令压力测试。
- 不改变 AT 正常指令执行逻辑。

验收标准：

- 57 条 ERRAT 用例全部可加载。
- mock 下可断言 `ERROR=104` / `ERROR=105`。
- 每条异常 AT 用例都包含健康检查。
- `ERROR=<code>` 为唯一标准格式，不使用手册中的 `EEROR` 拼写。

建议优先级：高

分支建议：

```text
feat/formal-error-at-cases
```

PR 标题建议：

```text
feat: add formal error AT cases
```

README 影响：

需要说明异常 AT 用例将预期错误码视为 PASS，并说明健康检查规则。

---

## Phase 5：传输模式用例数据化 [ ]

目标：

将 `MAIN-001` ~ `MAIN-006` 录入正式用例 YAML，覆盖高时效和空中唤醒下的透明、定点、广播三类传输。

当前行为：

MVP 只覆盖 A/B 高时效透明传输。

目标行为：

`MAIN-001` ~ `MAIN-006` 均以结构化方式描述配置、payload 组包、接收端断言、KEY 场景和设备需求。

任务：

- 在 `main_cases.yaml` 中录入 `MAIN-001` ~ `MAIN-006`。
- 建模三种传输类型：
  - `transparent_transfer`
  - `fixed_transfer`
  - `broadcast_transfer`
- 建模两种工作模式：
  - `SLEEP2`：高时效模式
  - `SLEEP1`：空中唤醒模式
- 建模无 KEY / 有 KEY 两轮测试。
- KEY 场景要求所有参与设备设置相同 KEY：
  - 透明：A/B
  - 定点：A/B
  - 广播：A/B/C
- 定点传输使用结构化字段，不直接硬编码完整 HEX：

```yaml
target_mac: "00,02"
channel: "01"
payload: "12345678"
encoding: fixed_hex_frame
```

- 广播传输使用结构化字段：

```yaml
channel: "01"
payload: "12345678"
encoding: broadcast_hex_frame
receivers: [B, C]
```

不做什么：

- 不执行真实传输。
- 不做长时间透传。
- 不做压力测试。
- 不做 AUX 或 GPIO 观测。

验收标准：

- `MAIN-001` ~ `MAIN-006` 全部可加载。
- 每条用例明确 `devices` 和角色。
- 定点 payload 可解析为 `target_mac + channel + data`。
- 广播 payload 可解析为 `channel + data`。
- KEY 场景明确所有参与设备都设置相同 KEY。

建议优先级：高

分支建议：

```text
feat/formal-transfer-case-model
```

PR 标题建议：

```text
feat: model formal transfer cases
```

README 影响：

如新增传输 YAML，需要说明定点和广播 payload 的结构化字段。

---

## Phase 6：传输模式执行器 [ ]

目标：

让 `MAIN-001` ~ `MAIN-006` 可执行，覆盖透明、定点、广播传输。

当前行为：

MVP 已支持 A/B 透明传输。

目标行为：

正式 runner 支持：

- 透明传输：A -> B
- 定点传输：A -> B
- 广播传输：A -> B/C
- 高时效：`SLEEP2`
- 空中唤醒：`SLEEP1`
- 无 KEY / 有 KEY 两轮

任务：

- 支持三设备配置：A/B/C。
- 配置文件定义物理设备，case 定义本次角色。
- 新增或扩展传输配置能力：
  - `configure_sleep`
  - `configure_mode`
  - `configure_level`
  - `configure_channel`
  - `configure_mac`
  - `configure_key`
- 新增 payload 组包能力：
  - `send_plain_payload`
  - `send_fixed_payload`
  - `send_broadcast_payload`
- 新增多接收端断言：
  - `multi_receiver_assert`
- 支持 HEX 写入。

不做什么：

- 不做 M0/M1 引脚切换。
- 不做 AUX 波形。
- 不做长时间压力。
- 不做功耗或射频。

验收标准：

- `pytest` 全部通过。
- mock 下 MAIN-001、MAIN-002、MAIN-003 可执行。
- 真实硬件至少能跑通 MAIN-001。
- 广播用例支持 B/C 两个接收端。
- KEY 场景中所有参与设备都设置相同 KEY 后再发送。

建议优先级：高

分支建议：

```text
feat/formal-transfer-runner
```

PR 标题建议：

```text
feat: run formal transfer cases
```

README 影响：

需要说明 A/B/C 配置、传输 suite 执行方式和 HEX payload 行为。

---

## Phase 7：出货/迭代回归套件 [ ]

目标：

覆盖 `SHIP-*`、`SHIPAT-*`、`ITER-*`、`ITERAT-*`，形成可按 suite 运行的出货和迭代回归集合。

当前行为：

没有独立的出货/迭代 suite。

目标行为：

支持：

```bash
python lora_auto/test_formal.py --suite ship
python lora_auto/test_formal.py --suite iter
```

任务：

- 在 `ship_cases.yaml` 中录入：
  - `SHIP-001` ~ `SHIP-004`
  - `SHIPAT-001` ~ `SHIPAT-005`
- 在 `iter_cases.yaml` 中录入：
  - `ITER-001` ~ `ITER-004`
  - `ITERAT-001` ~ `ITERAT-006`
- 支持出货/迭代 suite 过滤。
- 版本号、型号、IQ、CRC 断言应配置化，不写死在 runner 中。
- 兼容性测试先作为 `semi_auto`，固件烧录作为人工前置条件。

不做什么：

- 不自动烧录固件。
- 不自动切换不同版本模块。
- 不强制执行跨版本兼容性全流程。

验收标准：

- 出货/迭代用例可加载。
- 基础 AT 用例可通过正式 runner 执行。
- 兼容性测试可记录人工前置条件和 evidence。
- `AT+NAME`、`AT+VERSION`、`AT+IQ`、`AT+CRC` 的 expected 来源明确。

建议优先级：普通

分支建议：

```text
feat/formal-ship-iter-suites
```

PR 标题建议：

```text
feat: add formal ship and iteration suites
```

README 影响：

需要说明出货/迭代 suite 的执行方式和兼容性测试的人工前置条件。

---

## Phase 8：休眠、M0/M1、AUX 半自动化 [ ]

目标：

覆盖休眠唤醒、M0/M1 模式切换和 AUX 状态观测相关用例。

当前行为：

仓库没有 GPIO、M0/M1 或 AUX 观测能力。

目标行为：

串口可自动执行的步骤自动化；GPIO、M0/M1、AUX 观测先通过 `semi_auto` 和 evidence 记录表达。

任务：

- 覆盖以下用例：
  - `MAIN-007`
  - `MAIN-009`
  - `MAIN-010`
  - `MAIN-011`
  - `SHIP-003`
  - `ITER-003`
- 新增 step 类型：
  - `manual_observe`
  - `manual_set_gpio`
  - `record_evidence`
- 自动断言可稳定从串口观察到的文本：
  - `enter sleep`
  - `exit sleep`
- AUX、M0/M1 结果必须记录 evidence，不能无证据自动 PASS。

不做什么：

- 不强依赖逻辑分析仪。
- 不强依赖 GPIO 控制板。
- 不把人工观察硬编码为自动 PASS。

验收标准：

- 半自动用例可生成待人工确认步骤。
- 人工确认结果或 evidence 路径可进入报告。
- 缺少必要 evidence 时，用例不能自动 PASS。
- 支持状态：`manual_required` 或 `semi_auto_pending`。

建议优先级：普通

分支建议：

```text
feat/formal-semi-auto-hardware-steps
```

PR 标题建议：

```text
feat: add semi-auto hardware observation steps
```

README 影响：

需要说明半自动用例如何记录 evidence，以及无 evidence 时不会自动 PASS。

---

## Phase 9：压力测试与长稳测试 [ ]

目标：

覆盖长时间透传、AT 指令溢出、透明传输数据溢出、定点传输数据对发和长时间休眠唤醒。

当前行为：

MVP 只做单次 payload，不支持长时间运行或统计型报告。

目标行为：

新增长稳/压力测试模型和执行入口，支持持续时间、发送间隔、payload 长度、LEVEL sweep、错误统计和健康检查。

任务：

- 覆盖以下用例：
  - `MAIN-008`
  - `MAIN-012`
  - `MAIN-013`
  - `MAIN-014`
  - `MAIN-015`
- 建模字段：
  - `duration`
  - `interval_ms`
  - `payload_size`
  - `level_sweep`
  - `sent_count`
  - `received_count`
  - `loss_count`
  - `error_count`
  - `after_stress_health_check`
- 支持开发阶段缩短时长，例如 `--duration` 覆盖默认值。
- 长稳测试不进入普通 CI。

不做什么：

- 不默认执行 24 小时测试。
- 不阻塞普通 pytest。
- 不将压力测试结果混入普通快速测试报告，除非用户显式运行。

验收标准：

- 支持独立压力入口或正式 runner 的 stress suite。
- 支持短时 smoke 模式。
- 报告记录发送数、接收数、丢包数、错误数、最终健康检查结果。
- PASS 判定阈值可配置，不写死在 runner 中。

建议优先级：普通

分支建议：

```text
feat/formal-stress-test-model
```

PR 标题建议：

```text
feat: add formal stress test model
```

README 影响：

需要说明压力测试不在普通 CI 中默认运行，以及如何覆盖 duration。

---

## Phase 10：功耗、射频、距离、工作电压证据模型 [ ]

目标：

覆盖工作电压、射频指标、距离和功耗测试，为后续仪表接入保留数据结构。

当前行为：

仓库没有功耗仪、射频仪表、DC 电源或距离测试的数据接入模型。

目标行为：

先完成 evidence 模型和人工记录结构，不直接接入仪表。

任务：

- 覆盖以下用例：
  - `MAIN-016` ~ `MAIN-030`
- 建模 evidence 字段：
  - `power_record`
  - `rf_record`
  - `voltage_record`
  - `distance_record`
  - `manual_note`
- 支持记录：
  - `min`
  - `typical`
  - `max`
  - `unit`
  - `condition`
  - `instrument`
- 没有规格阈值时，只记录测量值，不自动判定 PASS/FAIL。

不做什么：

- 不直接接入功耗仪。
- 不直接接入频谱仪。
- 不直接判定距离指标。
- 不把无阈值的人工记录自动设为 PASS。

验收标准：

- 人工或仪表记录可以进入报告。
- 每条 manual case 都有 evidence 字段。
- 缺少必要 evidence 时不能 PASS。
- 后续可扩展 SCPI、pyvisa、serial、socket 等仪表接入，不破坏当前模型。

建议优先级：普通

分支建议：

```text
feat/formal-measurement-evidence-model
```

PR 标题建议：

```text
feat: add formal measurement evidence model
```

README 影响：

需要说明 manual / measurement case 的 evidence 规则。

---

## 5. 当前下一步

当前建议优先推进：

```text
Phase 2：AT 正常指令精确返回建模 [ ]
```

原因：

1. Phase 1 已合并到 main，正式用例目录、样例 YAML、loader/schema 校验测试和 README 说明已完成。
2. Phase 2 是后续正式 AT runner 的数据基础。
3. 先补齐 `AT-001` ~ `AT-020` 的精确 expected 和 manual_ref，可降低 Phase 3 执行器实现风险。
4. `AT+DEFAULT` 等破坏性/状态变更指令需要在数据层先明确 `destructive`、`state_changing` 和 `manual_confirm` 策略。

Phase 2 完成并合并后，再推进 Phase 3：AT 正常指令执行器。
