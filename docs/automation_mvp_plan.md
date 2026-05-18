# LoRa 透传模组自动化脚本 MVP 设计计划

## 1. MVP 目标

第一版 MVP 只解决一个核心问题：

> 通过 Python 脚本自动控制两个 LoRa 模组，完成 AT 指令校验、基础参数配置、透明传输收发验证，并生成测试报告。

MVP 跑通后，再逐步扩展到定点传输、广播传输、异常 AT 指令、休眠唤醒、长时间压测、AUX、功耗和射频仪表接入。

---

## 2. MVP 覆盖范围

### 2.1 优先覆盖用例

| 类型 | 用例 | 自动化价值 | MVP 是否覆盖 |
|---|---|---:|---|
| AT 基础指令 | `AT`、`+++`、`AT+HELP`、`AT+VERSION` | 高 | 是 |
| 参数配置 | `AT+SLEEP2`、`AT+MODE0`、`AT+LEVEL2`、`AT+CHANNEL00`、`AT+RESET` | 高 | 是 |
| 透明传输 | A 发 `123456789`，B 接收一致 | 高 | 是 |
| 结果报告 | 记录 pass/fail、串口日志、失败原因 | 高 | 是 |

### 2.2 MVP 暂不覆盖

| 暂不覆盖内容 | 原因 |
|---|---|
| 定点传输 | 需要额外封装地址、信道、HEX payload |
| 广播传输 | 需要 3 个以上设备协同 |
| AUX 波形测试 | 依赖逻辑分析仪或 GPIO 采集 |
| 功耗测试 | 依赖功耗仪 |
| 射频/距离测试 | 外部环境和仪表不稳定 |
| 24 小时长稳测试 | 第一版不适合直接做长时间任务 |
| 全量异常 AT 指令 | 数量较多，适合第二阶段批量参数化 |

---

## 3. 目录结构

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

---

## 4. 核心模块设计

### 4.1 `serial_client.py`

负责最底层串口读写。

| 功能 | 说明 |
|---|---|
| 打开串口 | 根据配置打开 COM 口 |
| 发送数据 | 支持字符串和 HEX |
| 接收数据 | 支持 timeout |
| 清空缓存 | 每条用例执行前清理历史数据 |
| 保存日志 | 所有 TX/RX 落盘 |

建议接口：

```python
class SerialClient:
    def __init__(self, port, baudrate=9600, timeout=2):
        pass

    def open(self):
        pass

    def close(self):
        pass

    def write_text(self, text: str):
        pass

    def write_hex(self, hex_str: str):
        pass

    def read_until(self, expected: str, timeout: float = 2.0) -> str:
        pass

    def read_all(self, timeout: float = 2.0) -> str:
        pass

    def clear_buffer(self):
        pass
```

### 4.2 `at_client.py`

专门处理 AT 命令。

| 功能 | 说明 |
|---|---|
| 进入 AT 模式 | 发送 `+++`，等待 `Entry AT` |
| 发送 AT 指令 | 发送命令并读取返回 |
| 断言返回 | 判断是否包含期望内容 |
| 重启等待 | 发送 `AT+RESET` 后等待模块恢复 |

建议接口：

```python
class AtClient:
    def __init__(self, serial_client):
        self.serial = serial_client

    def enter_at(self) -> bool:
        pass

    def send_cmd(self, cmd: str, expected: str = "OK", timeout: float = 2.0) -> bool:
        pass

    def reset(self):
        pass
```

### 4.3 `lora_device.py`

封装一个 LoRa 模组对象。

| 功能 | 说明 |
|---|---|
| 绑定设备角色 | A、B、C |
| 初始化参数 | 模式、等级、信道、功率等 |
| 发送透传数据 | 向另一个模块发送 payload |
| 接收数据 | 读取串口收到的数据 |

建议接口：

```python
class LoraDevice:
    def __init__(self, name, port, baudrate):
        self.name = name
        self.serial = SerialClient(port, baudrate)
        self.at = AtClient(self.serial)

    def open(self):
        pass

    def close(self):
        pass

    def configure_transparent_mode(self, sleep="2", level="2", channel="00"):
        pass

    def send_payload(self, payload: str):
        pass

    def wait_payload(self, expected: str, timeout: float = 5.0) -> bool:
        pass
```

### 4.4 `assertions.py`

MVP 只需要 3 类断言：

| 断言 | 示例 |
|---|---|
| 返回值包含 | `OK in response` |
| 返回值正则匹配 | `+VERSION=V1.2.4` |
| 收发数据一致 | A 发送 `123456789`，B 接收 `123456789` |

```python
def assert_contains(response: str, expected: str) -> bool:
    return expected in response


def assert_payload_equal(sent: str, received: str) -> bool:
    return sent in received
```

### 4.5 `report.py`

MVP 报告字段：

```json
{
  "case_id": "MVP-001",
  "case_name": "透明传输测试",
  "status": "pass",
  "start_time": "2026-05-18 10:00:00",
  "end_time": "2026-05-18 10:00:08",
  "duration": 8.2,
  "steps": [
    {
      "name": "配置 A 模块",
      "status": "pass",
      "detail": "AT+MODE0 OK"
    }
  ],
  "failure_reason": null,
  "log_file": "reports/logs/MVP-001.log"
}
```

第一版建议同时输出：

```text
reports/
  result.json
  result.md
  logs/
    MVP-001_A.log
    MVP-001_B.log
```

---

## 5. MVP 用例配置设计

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

## 6. MVP 执行流程

### 6.1 总流程

```text
1. 读取 devices.yaml
2. 打开 A、B 两个串口
3. 执行 AT 基础指令测试
4. A、B 进入 AT 模式
5. 配置 A、B：
   - AT+SLEEP2
   - AT+MODE0
   - AT+LEVEL2
   - AT+CHANNEL00
   - AT+RESET
6. 等待模块重启
7. A 发送 payload
8. B 接收 payload
9. 判断收发是否一致
10. 输出 result.json / result.md / 串口日志
11. 关闭串口
```

### 6.2 单条透明传输用例流程

```text
Case: MVP-003 透明传输收发一致性测试

前置条件：
- A/B 均已配置为透明传输模式
- A/B 信道一致
- A/B LEVEL 一致
- A/B 波特率一致

步骤：
1. 清空 A/B 串口缓存
2. A 发送 123456789
3. B 在 5 秒内监听串口数据
4. 判断 B 是否收到 123456789

期望结果：
- B 收到的数据包含 123456789
- A/B 串口无异常断开
- 用例状态为 pass
```

---

## 7. 技术选型

| 项目 | 建议 |
|---|---|
| 语言 | Python |
| 串口库 | `pyserial` |
| 配置文件 | YAML |
| 测试框架 | 第一版可不用 pytest，直接 runner 执行 |
| 报告 | JSON + Markdown |
| 日志 | Python logging |
| 并发 | MVP 暂不需要，多串口顺序控制即可 |

第一版不建议引入 Allure、pytest-xdist、数据库或 Web 平台。先保证核心链路稳定。

---

## 8. 开发任务拆分

### 第 1 步：串口通信打通

目标：能打开 COM 口，发送 `AT`，收到 `OK`。

交付物：

```text
libs/serial_client.py
examples/check_serial.py
```

验收标准：

```bash
python examples/check_serial.py --port COM3
```

输出：

```text
TX: AT
RX: OK
PASS
```

### 第 2 步：AT 指令封装

目标：用 `AtClient` 统一发送 AT 指令。

交付物：

```text
libs/at_client.py
```

验收标准：

```python
at.send_cmd("AT", "OK")
at.send_cmd("AT+VERSION", "+VERSION")
```

均返回 `True`。

### 第 3 步：设备对象封装

目标：把 A/B 两个模块抽象成 `LoraDevice`。

交付物：

```text
libs/lora_device.py
```

验收标准：

```python
dev_a.configure_transparent_mode()
dev_b.configure_transparent_mode()
```

能够自动完成：

```text
+++
AT+SLEEP2
AT+MODE0
AT+LEVEL2
AT+CHANNEL00
AT+RESET
```

### 第 4 步：透明传输测试

目标：A 发送，B 接收，自动判断一致性。

交付物：

```text
test_mvp.py
```

验收标准：

```text
[MVP-003] 透明传输收发一致性测试 PASS
```

失败时必须输出：

```text
发送内容：123456789
接收内容：xxxx
失败原因：receiver did not receive expected payload within 5s
```

### 第 5 步：报告生成

目标：每次执行后生成结构化结果。

交付物：

```text
reports/result.json
reports/result.md
reports/logs/
```

Markdown 报告示例：

```markdown
# LoRa 自动化测试报告

## 测试概览

| 总数 | 通过 | 失败 | 阻塞 |
|---:|---:|---:|---:|
| 3 | 3 | 0 | 0 |

## 用例结果

| 用例ID | 用例名称 | 结果 | 耗时 | 失败原因 |
|---|---|---|---:|---|
| MVP-001 | AT 基础指令测试 | PASS | 1.2s | - |
| MVP-002 | A/B 模块配置为透明传输 | PASS | 5.4s | - |
| MVP-003 | 透明传输收发一致性测试 | PASS | 0.8s | - |
```

---

## 9. 主入口设计

建议主入口叫：

```text
test_mvp.py
```

运行方式：

```bash
python test_mvp.py --config config/devices.yaml --cases config/mvp_cases.yaml
```

指定单条用例：

```bash
python test_mvp.py --case MVP-003
```

建议支持参数：

| 参数 | 作用 |
|---|---|
| `--config` | 设备串口配置 |
| `--cases` | 用例配置 |
| `--case` | 只跑某个用例 |
| `--log-level` | 日志等级 |
| `--report-dir` | 报告输出目录 |

---

## 10. MVP 完成标准

只要满足下面这些，就算 MVP 成功：

```text
1. 能识别 A/B 两个串口
2. 能对单个模块发送 AT 并判断 OK
3. 能配置 A/B 为透明传输模式
4. 能让 A 发送数据，B 自动接收
5. 能判断收发数据是否一致
6. 失败时能看到明确原因
7. 每次执行后有日志和报告
```

---

## 11. 推荐开发顺序

```text
阶段 1：单设备 AT 通信
    ↓
阶段 2：双设备串口管理
    ↓
阶段 3：A/B 透明传输
    ↓
阶段 4：YAML 用例驱动
    ↓
阶段 5：报告和日志
    ↓
阶段 6：扩展到 AT 异常指令批量测试
```

---

## 12. MVP 后续扩展路线

### 第二版：批量 AT 指令测试

覆盖：

```text
AT-001 ~ AT-020
ERRAT-001 ~ ERRAT-057
SHIPAT / ITERAT 指令
```

新增能力：

```text
- expected 支持正则
- error code 断言
- 参数化批量执行
- 指令重试
```

### 第三版：传输模式扩展

覆盖：

```text
MAIN-001 透明传输
MAIN-002 定点传输
MAIN-003 广播传输
MAIN-004 空中唤醒透明传输
MAIN-005 空中唤醒定点传输
MAIN-006 空中唤醒广播传输
```

新增能力：

```text
- HEX payload 编码/解码
- MAC 地址配置
- 多设备协同
- A/B/C 三模块接收校验
```

### 第四版：稳定性和压测

覆盖：

```text
MAIN-008 长时间透传
MAIN-012 指令溢出
MAIN-013 数据溢出
MAIN-014 定点数据对发
```

新增能力：

```text
- 定时发送
- 统计丢包率
- 统计吞吐量
- 异常复位检测
- 日志轮转
- 中断恢复
```

### 第五版：硬件与仪表接入

覆盖：

```text
AUX
M0/M1
功耗
射频
距离
```

新增能力：

```text
- GPIO 控制
- 逻辑分析仪采集
- 功耗仪驱动
- 频谱仪/综测仪接口
- 半自动人工确认步骤
```

---

## 13. 最小落地建议

第一版真正写代码时，只需要先建这些文件：

```text
lora_auto/
  config/
    devices.yaml
    mvp_cases.yaml

  libs/
    serial_client.py
    at_client.py
    lora_device.py
    report.py

  test_mvp.py

  reports/
```

核心链路：

```text
打开串口 → 发送 AT → 配置 A/B → A 发数据 → B 收数据 → 判断一致 → 生成报告
```

这条链路一旦稳定，后续的 AT 指令集、错误指令集、定点传输、广播传输，本质上都是在这个框架上增加 YAML 用例和少量业务封装。
