# LoRa 正式测试用例设计计划

## 1. 总目标

在 LoRa 自动化脚本 MVP 已完成的基础上，将 LoRa 透传模组测试表推进为正式测试用例体系。

正式测试阶段逐步覆盖：

- 主测试用例：`MAIN-*`
- AT 正常指令用例：`AT-*`
- AT 异常指令用例：`ERRAT-*`
- 出货/回归用例：`SHIP-*`、`SHIPAT-*`
- 迭代回归用例：`ITER-*`、`ITERAT-*`
- 休眠、M0/M1、AUX、压力、功耗、射频、距离等半自动或人工证据型用例

整体推进原则：

```text
正式用例模型 -> AT 精确返回数据化 -> AT 执行器 -> 异常 AT -> 传输模式 -> 设备模式前置规则 -> 出货/迭代 -> 半自动与仪表证据
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
| 异常 AT 错误码格式 | 统一使用 `ERROR=<code>`，例如 `ERROR=101` |
| 执行前模式规则 | 每次 AT、配置、传输 I/O 前先判断当前模式，再切换到目标模式 |

## 3. 拆分依据

本计划按 Phase 推进，原因如下：

1. 正式测试表覆盖范围广，包含全自动、半自动、人工仪表记录三类用例，必须分层推进。
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
Phase 6.1：统一设备模式探测与切换规则
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

目标：建立正式测试阶段的基础结构，先完成 schema、loader 和少量样例用例，不执行真实硬件。

完成内容：

- 新增正式用例目录：`lora_auto/config/formal/`
- 新增样例 YAML：`main_cases.yaml`、`at_cases.yaml`、`error_at_cases.yaml`、`ship_cases.yaml`、`iter_cases.yaml`
- 首批录入样例用例：`MAIN-001`、`AT-001`、`ERRAT-001`、`SHIP-001`、`ITER-001`
- 新增正式用例 loader 与 schema 校验测试
- 校验用例 ID 唯一、必填字段完整、自动化等级合法、优先级合法

验收标准：

- `pytest` 全部通过
- 样例 YAML 可被 loader 正确加载
- 缺失必填字段或重复 case ID 时测试失败
- destructive 用例可表达，但默认不允许自动执行

---

## Phase 2：AT 正常指令精确返回建模 [√]

目标：将 `AT-001` ~ `AT-020` 录入正式用例 YAML，并根据 UART 应用指导手册补充精确 expected。

完成内容：

- 在 `at_cases.yaml` 中录入 `AT-001` ~ `AT-020`
- 每条 AT 用例包含 `command`、`expected`、`manual_ref`
- expected 断言类型明确，例如 `contains`、`contains_all`、`regex`、`exact`
- `AT+RESET` 标记为 `state_changing: true`
- `AT+DEFAULT` 标记为 `destructive: true`、`state_changing: true`、`run_policy: manual_confirm`、`automation_level: semi_auto`

验收标准：

- `AT-001` ~ `AT-020` 全部可被 loader 读取
- `AT+DEFAULT` 默认不会被 auto runner 选择
- 精确返回来源于 UART 应用指导手册

---

## Phase 3：AT 正常指令执行器 [√]

目标：让 Phase 2 中数据化的 AT 正常指令用例可执行。

完成内容：

- 新增正式测试入口：

```bash
python lora_auto/test_formal.py --suite at
python lora_auto/test_formal.py --case AT-001
python lora_auto/test_formal.py --suite at --dry-run
```

- 支持加载 `lora_auto/config/formal/at_cases.yaml`
- 支持 `enter_at`、`send_at`、`reset`、`exit_at` 等动作
- 支持 `contains`、`contains_all`、`regex`、`exact` 等断言模式
- 支持 dry-run，仅输出将要执行的步骤，不访问硬件
- 复用报告结构：`reports/result.json`、`reports/result.md`、`reports/logs/<case_id>_runner.log`

验收标准：

- `pytest` 全部通过
- mock 串口下可执行 `AT-001`
- dry-run 可列出 AT suite 执行计划
- destructive 或 manual_confirm 用例不会被默认自动执行

---

## Phase 4：异常 AT 指令数据化与执行 [√]

目标：覆盖 `ERRAT-001` ~ `ERRAT-057`，统一断言错误码并验证异常命令后模块仍健康。

完成内容：

- 在 `error_at_cases.yaml` 中录入 `ERRAT-001` ~ `ERRAT-057`
- 所有异常 AT 用例统一断言 `ERROR=101`
- 每条异常命令后追加 `AT -> OK` 健康检查
- 正式 runner 支持 `error_at` suite
- 报告区分：收到预期错误码 PASS、未收到错误码 FAIL、健康检查失败 FAIL

验收标准：

- 57 条 ERRAT 用例全部可加载
- mock 下可断言 `ERROR=101`
- 每条异常 AT 用例都包含健康检查
- 使用标准格式 `ERROR=<code>`，不使用手册 typo `EEROR`

---

## Phase 5：传输模式用例数据化 [√]

目标：将 `MAIN-001` ~ `MAIN-006` 录入正式用例 YAML，覆盖高时效和空中唤醒下的透明、定点、广播三类传输。

完成内容：

- 在 `main_cases.yaml` 中录入 `MAIN-001` ~ `MAIN-006`
- 建模传输类型：`transparent_transfer`、`fixed_transfer`、`broadcast_transfer`
- 建模工作模式：`SLEEP2` 高时效模式、`SLEEP1` 空中唤醒模式
- 建模无 KEY / 共享 KEY 两轮测试
- KEY 场景要求所有参与设备设置相同 KEY：透明 A/B、定点 A/B、广播 A/B/C
- 定点和广播传输使用结构化 payload 字段
- 当前所有传输 payload 使用：`ABCDEFGHIJKLMNOPQRSTUVWXYZ`

验收标准：

- `MAIN-001` ~ `MAIN-006` 全部可加载
- 每条用例明确 `devices` 和角色
- 定点 payload 可解析为 `target_mac + channel + data`
- 广播 payload 可解析为 `channel + data`
- KEY 场景明确所有参与设备都设置相同 KEY

---

## Phase 6：传输模式执行器 [√]

目标：让 `MAIN-001` ~ `MAIN-006` 可执行，覆盖透明、定点、广播传输。

完成内容：

- 正式 runner 支持：
  - 透明传输：A -> B
  - 定点传输：A -> B
  - 广播传输：A -> B/C
  - 高时效：`SLEEP2`
  - 空中唤醒：`SLEEP1`
  - 无 KEY / 共享 KEY 两轮
- 支持三设备配置：A/B/C
- 支持传输配置：sleep、mode、level、channel、mac、key
- 支持 payload 组包：`send_plain_payload`、`send_fixed_payload`、`send_broadcast_payload`
- 支持多接收端断言：`multi_receiver_assert`
- 支持 HEX 写入

不做什么：

- 不做 M0/M1 引脚切换
- 不做 AUX 波形
- 不做长时间压力
- 不做功耗或射频

验收标准：

- `pytest` 全部通过
- mock 下 `MAIN-001`、`MAIN-002`、`MAIN-003` 可执行
- 广播用例支持 B/C 两个接收端
- KEY 场景中所有参与设备都设置相同 KEY 后再发送

---

## Phase 6.1：统一设备模式探测与切换规则 [√]

目标：

为所有 AT、配置、传输 I/O 操作建立统一的设备模式前置规则：先探测当前是否处于 AT 模式，再根据目标操作切换到 AT 模式或工作/透传模式。

背景：

传输类用例在真实硬件上容易受到设备残留状态影响。例如设备仍在 AT 模式时直接写 payload，会被当作 AT 文本或无效输入；设备已在 AT 模式时重复发送 `+++`，也可能造成状态反转。因此需要统一状态机能力，而不是在单个 case 中临时处理。

目标行为：

- 执行 AT 指令、异常 AT、参数配置前，确保设备处于 AT 模式。
- 执行透明、定点、广播 payload 发送或接收前，确保设备处于工作/透传模式。
- `AT -> OK` 作为 AT 模式探测依据。
- 探测为 AT 模式时，不重复发送 `+++` 进入 AT。
- 探测为非 AT 模式时，按目标操作进入 AT 或保持/切换到工作模式。

完成内容：

- 新增 `LoraDevice.detect_mode()`：通过 `AT -> OK` 判断当前是否处于 AT 模式。
- 新增 `LoraDevice.ensure_at_mode()`：AT/配置操作前统一确保 AT 模式。
- 新增 `LoraDevice.ensure_work_mode()`：传输 payload I/O 前统一确保工作/透传模式。
- `LoraDevice.configure_transparent_mode()` 已改为配置前先探测当前模式，再进入 AT 配置。
- `AtClient.enter_at()` 已改为先发送 `AT` 探测；若已在 AT 模式则不再发送 `+++`。
- 正式 runner 在传输 payload I/O 前显式调用 `ensure_work_mode()`：
  - sender 清 buffer 前
  - receiver 清 buffer 前
  - `receive_payload` 读取前
  - `multi_receiver_assert` 每个接收端读取前
- 测试覆盖：
  - 已在 AT 模式
  - 当前在工作/透传模式
  - 工作模式下进入 AT
  - AT 模式下退出到工作/透传模式
  - 配置前自动探测并进入 AT
  - `MAIN-001`、`MAIN-002`、`MAIN-003`、`MAIN-005` 传输 I/O 前调用 `ensure_work_mode()`

不做什么：

- 不新增 YAML case。
- 不新增命令行参数。
- 不引入 M0/M1 GPIO 控制。
- 不引入 AUX 观测。
- 不改变 README 使用命令。

验收标准：

- `pytest` 全部通过。
- `AtClient.enter_at()` 已在 AT 模式时只返回 `AT -> OK` 探测结果，不重复发送 `+++`。
- 需要 AT/config 的路径执行前具备 AT 模式前置。
- 正式传输 runner 在 payload 发送和接收前显式执行工作模式前置。
- README 检查后无需更新，因为用户命令和配置方式未变化。

实现记录：

- PR #24：`feat: add device mode preflight helpers`
- PR #25：`feat: probe before entering AT mode`
- PR #26：`feat: ensure work mode before formal transfer IO`

建议优先级：高

分支建议：

```text
docs/add-phase-6-1-plan-record
```

PR 标题建议：

```text
docs: add Phase 6.1 mode preflight record
```

README 影响：

无需更新。该阶段不改变用户命令或配置入口。

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

目标：覆盖休眠唤醒、M0/M1 模式切换和 AUX 状态观测相关用例。

任务：

- 覆盖 `MAIN-007`、`MAIN-009`、`MAIN-010`、`MAIN-011`、`SHIP-003`、`ITER-003`
- 新增 step 类型：`manual_observe`、`manual_set_gpio`、`record_evidence`
- 自动断言可稳定从串口观察到的文本：`enter sleep`、`exit sleep`
- AUX、M0/M1 结果必须记录 evidence，不能无证据自动 PASS

不做什么：

- 不强依赖逻辑分析仪。
- 不强依赖 GPIO 控制板。
- 不把人工观察硬编码为自动 PASS。

验收标准：

- 半自动用例可生成待人工确认步骤。
- 人工确认结果或 evidence 路径可进入报告。
- 缺少必要 evidence 时，用例不能自动 PASS。
- 支持状态：`manual_required` 或 `semi_auto_pending`。

---

## Phase 9：压力测试与长稳测试 [ ]

目标：覆盖长时间透传、AT 指令溢出、透明传输数据溢出、定点传输数据对发和长时间休眠唤醒。

任务：

- 覆盖 `MAIN-008`、`MAIN-012`、`MAIN-013`、`MAIN-014`、`MAIN-015`
- 建模字段：`duration`、`interval_ms`、`payload_size`、`level_sweep`、`sent_count`、`received_count`、`loss_count`、`error_count`、`after_stress_health_check`
- 支持开发阶段缩短时长，例如 `--duration` 覆盖默认值
- 长稳测试不进入普通 CI

不做什么：

- 不默认执行 24 小时测试。
- 不阻塞普通 pytest。
- 不将压力测试结果混入普通快速测试报告，除非用户显式运行。

验收标准：

- 支持独立压力入口或正式 runner 的 stress suite。
- 支持短时 smoke 模式。
- 报告记录发送数、接收数、丢包数、错误数、最终健康检查结果。
- PASS 判定阈值可配置，不写死在 runner 中。

---

## Phase 10：功耗、射频、距离、工作电压证据模型 [ ]

目标：覆盖工作电压、射频指标、距离和功耗测试，为后续仪表接入保留数据结构。

任务：

- 覆盖 `MAIN-016` ~ `MAIN-030`
- 建模 evidence 字段：`power_record`、`rf_record`、`voltage_record`、`distance_record`、`manual_note`
- 支持记录：`min`、`typical`、`max`、`unit`、`condition`、`instrument`
- 没有规格阈值时，只记录测量值，不自动判定 PASS/FAIL

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

---

## 5. 当前下一步

当前建议优先推进：

```text
Phase 7：出货/迭代回归套件 [ ]
```

原因：

1. Phase 1 ~ Phase 6.1 已完成并合并到 main。
2. 正式用例模型、AT 正常指令、异常 AT、主传输用例、传输执行器和设备模式前置规则已具备基础闭环。
3. Phase 7 可在现有正式 runner 基础上补齐出货与迭代回归 suite。
4. 兼容性测试可先作为 `semi_auto`，固件烧录作为人工前置条件，不阻塞自动化主流程。
