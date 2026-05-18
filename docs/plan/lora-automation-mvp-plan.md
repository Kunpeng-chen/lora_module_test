# LoRa 自动化脚本 MVP 计划

## 1. 总目标

通过一组可拆分、可独立验收的 Phase，完成 LoRa 透传模组自动化脚本 MVP。

MVP 的核心闭环是：

```text
打开串口 -> 发送 AT -> 配置 A/B -> A 发数据 -> B 收数据 -> 判断一致 -> 生成报告
```

第一版 MVP 只聚焦两个 LoRa 模组的基础自动化验证：

- 单设备 AT 指令连通性验证
- A/B 双设备串口管理
- A/B 透明传输参数配置
- A 发 B 收的一致性验证
- JSON / Markdown 报告与串口日志输出

MVP 跑通后，再扩展到定点传输、广播传输、异常 AT 指令、休眠唤醒、长时间压测、AUX、功耗和射频仪表接入。

---

## 2. 拆分依据

本计划拆分为 5 个 Phase，而不是一次性完成全部 MVP，原因如下：

1. 串口通信是所有后续能力的基础，必须先形成最小可验证闭环。
2. AT 指令封装、设备对象封装和业务用例执行属于不同抽象层，适合分阶段实现。
3. 透明传输测试依赖 A/B 两个设备的配置能力，不能和底层串口能力混在同一个 PR 中完成。
4. 报告与日志属于结果沉淀能力，应在核心测试链路稳定后单独接入。
5. 每个 Phase 都可以独立提交 PR、独立测试、独立验收，符合阶段执行通用规则。

推荐执行顺序：

```text
Phase 1：单设备串口与 AT 连通性基线
    ↓
Phase 2：AT Client 与基础断言封装
    ↓
Phase 3：A/B 设备对象与透明传输配置
    ↓
Phase 4：透明传输 MVP 用例执行器
    ↓
Phase 5：报告、日志与 README 收尾
```

---

## 3. MVP 覆盖范围

### 3.1 MVP 覆盖内容

| 类型 | 用例 | 自动化价值 | MVP 是否覆盖 |
|---|---|---:|---|
| AT 基础指令 | `AT`、`+++`、`AT+HELP`、`AT+VERSION` | 高 | 是 |
| 参数配置 | `AT+SLEEP2`、`AT+MODE0`、`AT+LEVEL2`、`AT+CHANNEL00`、`AT+RESET` | 高 | 是 |
| 透明传输 | A 发 `123456789`，B 接收一致 | 高 | 是 |
| 结果报告 | 记录 pass/fail、串口日志、失败原因 | 高 | 是 |

### 3.2 MVP 暂不覆盖内容

| 暂不覆盖内容 | 原因 |
|---|---|
| 定点传输 | 需要额外封装地址、信道、HEX payload |
| 广播传输 | 需要 3 个以上设备协同 |
| AUX 波形测试 | 依赖逻辑分析仪或 GPIO 采集 |
| 功耗测试 | 依赖功耗仪 |
| 射频/距离测试 | 外部环境和仪表不稳定 |
| 24 小时长稳测试 | 第一版不适合直接做长时间任务 |
| 全量异常 AT 指令 | 数量较多，适合后续批量参数化 Phase |
| Allure / Web 平台 / 数据库 | MVP 阶段优先保证核心链路稳定 |

---

## 4. 目标目录结构

最终 MVP 目标目录结构：

```text
lora_auto/
  config/
    devices.yaml
    mvp_cases.yaml

  libs/
    serial_client.py
    at_client.py
    lora_device.py
    assertions.py
    report.py

  test_mvp.py

  reports/
    logs/
    result.json
    result.md
```

阶段实现时可以按 Phase 逐步创建，不要求 Phase 1 一次性建完所有文件。

---

## Phase 1：单设备串口与 AT 连通性基线 [√]

目标：

建立最小串口通信能力，能打开一个串口，发送 `AT`，读取返回并判断是否包含 `OK`。

当前行为：

仓库中尚未形成自动化脚本目录、串口通信封装和单设备连通性检查入口。

目标行为：

可以通过命令行指定串口，并完成单设备 AT 连通性验证。

任务：

- 新增 `lora_auto/libs/serial_client.py`
- 新增 `lora_auto/examples/check_serial.py`
- 支持打开串口、发送文本、读取返回、关闭串口
- 支持基础超时参数
- 输出最小可读执行结果：`TX`、`RX`、`PASS/FAIL`
- 增加不依赖真实串口的最小单元测试或 mock 测试

不做什么：

- 不做 YAML 用例驱动
- 不做双设备协同
- 不做透明传输测试
- 不做完整报告系统
- 不接入 pytest 复杂 fixture 或 Allure

验收标准：

- 可运行：`python lora_auto/examples/check_serial.py --port COM3`
- 成功时输出包含：`TX: AT`、`RX:`、`PASS`
- 失败时输出明确错误原因，例如串口打不开、超时未收到期望返回
- 新增测试通过
- PR 合并后检查 README；如新增了用户可运行入口，应更新 README，否则记录“已检查 README，无需更新。”

完成记录：

- 实现 PR：#1 `feat: phase1 serial at baseline`
- 合并方式：squash merge
- 合并提交：`2ccae6a62307ebfeb90a1c91e5c9a437488c8115`
- CI：`CI` workflow completed / success
- README：已检查并更新 Phase 1 串口检查、依赖安装和测试命令

建议优先级：最高

分支建议：

```text
feat/phase1-serial-at-baseline
```

PR 标题建议：

```text
feat: phase1 serial at baseline
```

README 影响：

如果新增 `check_serial.py` 可直接给用户使用，需要在 README 中增加最小连通性检查命令；如果 README 尚未建立或暂不适合更新，应在执行记录中说明已检查。

---

## Phase 2：AT Client 与基础断言封装 [√]

目标：

在 Phase 1 的串口能力之上，封装 AT 指令客户端和基础断言能力，避免后续用例直接操作底层串口。

当前行为：

串口发送和响应判断仍停留在单次脚本逻辑中，缺少可复用的 AT 指令层。

目标行为：

可以通过 `AtClient` 统一进入 AT 模式、发送 AT 指令、断言返回内容，并为后续设备对象复用。

任务：

- 新增 `lora_auto/libs/at_client.py`
- 新增 `lora_auto/libs/assertions.py`
- 实现 `enter_at()`
- 实现 `send_cmd(cmd, expected, timeout)`
- 实现基础断言：包含判断、正则匹配预留或简单封装、payload 包含判断
- 为 AT Client 增加 mock 串口测试
- 保持 Phase 1 示例入口可用

不做什么：

- 不做 A/B 双设备配置
- 不做透明传输测试
- 不做 YAML 用例执行器
- 不批量覆盖完整 AT 指令表

验收标准：

- `AtClient.send_cmd("AT", "OK")` 可返回布尔结果
- `AtClient.send_cmd("AT+VERSION", "+VERSION")` 可返回布尔结果
- mock 测试覆盖成功响应、超时响应和期望不匹配
- 既有 Phase 1 测试继续通过
- README 已更新，或已明确记录“已检查 README，无需更新。”

完成记录：

- 实现 PR：#2 `feat: phase2 at client assertions`
- 合并方式：squash merge
- 合并提交：`41b30c0b49738eb01325fc2970bc2ae291ffb602`
- CI：`CI` workflow completed / success
- README：已检查；Phase 2 未新增或改变用户可运行入口，无需更新 README

建议优先级：最高

分支建议：

```text
feat/phase2-at-client-assertions
```

PR 标题建议：

```text
feat: phase2 at client assertions
```

README 影响：

通常无需面向用户大幅更新；如果调整了 `check_serial.py` 的使用方式，需要同步 README。

---

## Phase 3：A/B 设备对象与透明传输配置 [√]

目标：

把单个 LoRa 模组抽象成设备对象，并支持 A/B 两个设备进入透明传输所需的基础参数配置。

当前行为：

AT Client 只能对单个串口发送指令，还没有设备角色、配置流程和双设备生命周期管理。

目标行为：

可以创建 A/B 两个 `LoraDevice`，分别打开串口、进入 AT 模式、配置透明传输参数并复位。

任务：

- 新增 `lora_auto/libs/lora_device.py`
- 新增 `lora_auto/config/devices.yaml` 示例
- 支持设备字段：`name`、`port`、`baudrate`、`role`
- 实现 `open()`、`close()`、`configure_transparent_mode()`
- 配置流程至少覆盖：
  - `+++`
  - `AT+SLEEP2`
  - `AT+MODE0`
  - `AT+LEVEL2`
  - `AT+CHANNEL00`
  - `AT+RESET`
- 增加 mock 测试覆盖双设备配置顺序和失败中断

不做什么：

- 不做真实 A 发 B 收校验
- 不做完整 YAML 用例执行器
- 不做报告输出
- 不处理定点、广播和空中唤醒模式

验收标准：

- 可以通过代码创建 A/B 两个设备对象
- `dev_a.configure_transparent_mode()` 和 `dev_b.configure_transparent_mode()` 可独立执行
- 任一 AT 配置失败时返回明确失败信息
- 既有 Phase 1、Phase 2 测试继续通过
- README 已更新，或已明确记录“已检查 README，无需更新。”

完成记录：

- 实现 PR：#3 `feat: phase3 lora device config`
- 合并方式：squash merge
- 合并提交：`12ad4817156fc6037b4f699b419ff2288dee6390`
- CI：`CI` workflow completed / success
- README：已检查并更新 `devices.yaml` 配置位置、字段含义和透明模式 AT 配置流程

建议优先级：高

分支建议：

```text
feat/phase3-lora-device-config
```

PR 标题建议：

```text
feat: phase3 lora device config
```

README 影响：

如果新增 `devices.yaml` 配置方式，应在 README 中说明配置文件位置和串口字段含义。

---

## Phase 4：透明传输 MVP 用例执行器 [√]

目标：

完成 MVP 的核心业务用例：A 发送 payload，B 在指定超时时间内接收，并判断收发内容一致。

当前行为：

A/B 设备可以被配置，但还没有从配置文件驱动用例执行，也没有透明传输收发校验入口。

目标行为：

可以通过 `test_mvp.py` 执行最小用例集，包括 AT 基础指令、A/B 配置和透明传输收发一致性测试。

任务：

- 新增 `lora_auto/config/mvp_cases.yaml`
- 新增 `lora_auto/test_mvp.py`
- 支持读取 `devices.yaml` 和 `mvp_cases.yaml`
- 支持三类 MVP case：
  - `at`
  - `config`
  - `transparent_transfer`
- 实现 `--config`、`--cases`、`--case`、`--log-level`、`--report-dir` 参数
- 透明传输用例流程：
  1. 清空 A/B 串口缓存
  2. A 发送 payload
  3. B 在 timeout 内读取
  4. 判断 B 接收内容包含 expected
- 增加 mock 测试覆盖用例解析、case 选择、成功收发和超时失败

不做什么：

- 不做完整报告格式
- 不做长时间压测
- 不做多设备广播
- 不做异常 AT 指令全集参数化
- 不做真实硬件 CI 依赖

验收标准：

- 可运行：`python lora_auto/test_mvp.py --config lora_auto/config/devices.yaml --cases lora_auto/config/mvp_cases.yaml`
- 可运行单条用例：`python lora_auto/test_mvp.py --case MVP-003`
- 成功时输出：`[MVP-003] 透明传输收发一致性测试 PASS`
- 失败时输出发送内容、接收内容和失败原因
- mock 测试覆盖执行器核心逻辑
- 既有测试继续通过
- README 已更新，或已明确记录“已检查 README，无需更新。”

完成记录：

- 实现 PR：#4 `feat: phase4 transparent transfer runner`
- 合并方式：squash merge
- 合并提交：`ce378f67a9b906e4f103c9775e4b1ef0074d6f6c`
- CI：`CI` workflow completed / success
- README：已检查并更新 MVP runner 命令、参数说明和透明传输输出示例

建议优先级：高

分支建议：

```text
feat/phase4-transparent-transfer-runner
```

PR 标题建议：

```text
feat: phase4 transparent transfer runner
```

README 影响：

需要在 README 中增加 MVP 执行入口、配置文件说明和单条用例执行示例。

---

## Phase 5：报告、日志与 README 收尾 [√]

目标：

为 MVP 增加结构化结果沉淀能力，输出 JSON 报告、Markdown 报告和串口日志，并完成 README 面向用户的最小使用说明。

当前行为：

执行器可以输出控制台结果，但缺少结构化报告、串口日志归档和稳定的用户使用说明。

目标行为：

每次执行后在指定报告目录下生成结果文件和日志文件，便于问题追踪和后续自动化平台接入。

任务：

- 新增 `lora_auto/libs/report.py`
- 支持输出 `reports/result.json`
- 支持输出 `reports/result.md`
- 支持输出 `reports/logs/` 下的设备串口日志
- 报告至少包含：
  - 用例 ID
  - 用例名称
  - status
  - start_time
  - end_time
  - duration
  - steps
  - failure_reason
  - log_file
- README 补齐：
  - 环境依赖
  - 串口配置
  - 单设备检查命令
  - MVP 执行命令
  - 报告输出位置
- 增加报告生成 mock 测试

不做什么：

- 不做 Allure
- 不做 Web 报告平台
- 不做数据库持久化
- 不做覆盖率门禁调整，除非仓库已有明确要求

验收标准：

- 执行 MVP 后生成 `result.json`、`result.md` 和对应日志文件
- 报告中能区分 pass/fail，并保留失败原因
- README 已同步更新 MVP 使用方式
- 既有测试继续通过
- 当前计划中对应 Phase 只有在实现 PR 合并、CI 成功、README 检查完成后才可从 `[ ]` 改为 `[√]`

完成记录：

- 实现 PR：#5 `feat: phase5 report logging readme`
- 合并方式：squash merge
- 合并提交：`f88bfbc0a753d9c4c0729415a2d2f6b1671ece0e`
- CI：`CI` workflow completed / success
- README：已检查并更新报告输出位置、JSON/Markdown 报告和日志目录说明

建议优先级：高

分支建议：

```text
feat/phase5-report-logging-readme
```

PR 标题建议：

```text
feat: phase5 report logging readme
```

README 影响：

必须更新 README，因为该 Phase 直接影响用户如何运行脚本和查看结果。

---

## 5. MVP 用例配置草案

### 5.1 `devices.yaml`

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

Linux/macOS 可改为：

```yaml
devices:
  A:
    port: "/dev/ttyUSB0"
    baudrate: 9600

  B:
    port: "/dev/ttyUSB1"
    baudrate: 9600
```

### 5.2 `mvp_cases.yaml`

```yaml
cases:
  - id: MVP-001
    name: AT 基础指令测试
    type: at
    device: A
    steps:
      - command: "AT"
        expected: "OK"
      - command: "AT+VERSION"
        expected: "+VERSION"

  - id: MVP-002
    name: A/B 模块配置为透明传输
    type: config
    devices: [A, B]
    config:
      sleep: "2"
      mode: "0"
      level: "2"
      channel: "00"

  - id: MVP-003
    name: 透明传输收发一致性测试
    type: transparent_transfer
    sender: A
    receiver: B
    payload: "123456789"
    expected: "123456789"
    timeout: 5
```

---

## 6. MVP 完成标准

MVP 全部完成需要满足：

```text
1. 能识别 A/B 两个串口
2. 能对单个模块发送 AT 并判断 OK
3. 能配置 A/B 为透明传输模式
4. 能让 A 发送数据，B 自动接收
5. 能判断收发数据是否一致
6. 失败时能看到明确原因
7. 每次执行后有日志和报告
8. README 包含最小使用说明
9. 所有 Phase 对应 PR 均已合并到 main
10. CI 均为 success
```

---

## 7. 后续扩展计划入口

MVP 完成后，后续建议单独创建新的计划文档，不混入本 MVP 计划：

| 后续方向 | 建议计划文件 |
|---|---|
| 批量 AT 指令测试 | `docs/plan/at-command-batch-test-plan.md` |
| 异常 AT 指令测试 | `docs/plan/at-error-command-test-plan.md` |
| 定点与广播传输 | `docs/plan/transfer-mode-extension-plan.md` |
| 稳定性与压测 | `docs/plan/stability-stress-test-plan.md` |
| AUX / 功耗 / 射频仪表接入 | `docs/plan/instrument-integration-plan.md` |

---

## 8. 状态维护规则

本计划状态遵循 `docs/rule/stage-execution-rules.md`。

新增 Phase 默认保持 `[ ]`。只有满足以下条件后，才允许将对应 Phase 从 `[ ]` 更新为 `[√]`：

- 对应实现 PR 已合并到 `main`
- CI 已完成且结果为 `success`
- 相关测试已覆盖
- README 已更新，或已明确记录“已检查 README，无需更新”
- 无遗留冲突 PR
- 相关计划状态已同步更新
