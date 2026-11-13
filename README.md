# nano_ctl_connect

`nano_ctl_connect` 是 `nano_ctl` 的 Python gRPC 客户端包，包含 `MotionService` 全部 RPC 的 protobuf 生成模块和同步 `MotionClient` 封装。该项目只负责 gRPC 客户端，不包含控制卡驱动，也不要求在客户端设备上安装雷赛 SDK。

## 环境要求

- Python 3.10 或更新版本。
- 推荐使用 uv 按 `uv.lock` 安装和锁定依赖。
- 连接可访问的 `nano_ctl` gRPC 服务，默认端口 `50051`。

`MotionClient` 默认使用明文 gRPC；生产环境需要 TLS 时传入 gRPC credentials 或预先配置好的 channel。默认目标地址可由 `NANO_CTL_GRPC_ADDR` 覆盖，格式为 `host:port`。

## 创建开发环境

在项目根目录执行：

```sh
uv sync --locked
```

这会依据 `uv.lock` 创建 `.venv` 并安装当前项目和开发依赖。没有 uv 时可先用系统 Python 安装 uv，再重试该命令。运行自带示例：

```sh
NANO_CTL_GRPC_ADDR=127.0.0.1:50051 uv run python examples/read_and_watch.py
```

作为另一个 uv 项目的本地依赖，可在其 `pyproject.toml` 中加入：

```toml
[project]
dependencies = ["nano-ctl-connect"]

[tool.uv.sources]
nano-ctl-connect = { path = "../nano_ctl_connect", editable = true }
```

## 服务与控制卡生命周期

`nano_ctl` 后端启动时自动开卡，成功后才接受 gRPC 请求，退出前自动关闭 SDK 会话。Python SDK 不负责开卡、关卡或硬件初始化，也无需额外调用 REST 开卡接口。创建 `MotionClient` 后可直接调用读写方法；`wait_ready()` 仅等待 gRPC 通道就绪，`close()` / 退出 `with` 仅释放客户端通道，不影响后端和其他客户端使用控制卡。

## 基本调用

```python
from nano_ctl_connect import AxisAction, IOKind, MotionClient, MotionUnit

with MotionClient("192.168.1.20:50051", default_timeout=3.0) as client:
    axes = client.read_axes(card_no=0, axes=[0, 1, 2])
    print([axis.current_speed for axis in axes.axes])

    inputs = client.read_io(0, IOKind.INPUT_BIT, [0, 1, 2])
    client.write_io(0, 0, IOKind.OUTPUT_BIT, on=True)

    client.axis_command(
        0, 0, AxisAction.MOVE,
        unit=MotionUnit.ANGLE,
        position=90.0,
        speed=20.0,
        acceleration=100.0,
        deceleration=100.0,
    )
```

一元调用默认 deadline 为 5 秒，可通过 `default_timeout` 修改；流式调用默认无 deadline。关闭 client 会关闭 channel 并取消活动中的流。调用返回 protobuf 响应，底层 `MotionServiceStub` 可通过 `client.raw` 访问。gRPC 错误保持为 `grpc.RpcError`，包括状态码和详情。

## API 覆盖

| Python 方法 | gRPC 能力 |
|---|---|
| `read_axis`、`read_axes`、`watch_axes`、`axis_command` | 轴状态、批量/流式采集与轴命令 |
| `read_io`、`read_io_array`、`watch_io`、`write_io` | 变量读取、批量/流式采集与写入 |
| `read_bus`、`bus_command` | EtherCAT 状态和控制 |
| `read_object_dictionary`、`write_object_dictionary` | OD 读写 |
| `read_rxpdo`、`write_rxpdo`、`read_txpdo` | PDO 读写 |
| `read_hcmp`、`hcmp_command` | HCMP 查询和控制 |
| `read_extra_encoder`、`extra_encoder_command` | 外接编码器查询和控制 |

## 修改 protobuf 接口

目录中的 `proto/godmc/v1/motion.proto` 是服务端 schema 的本地副本；修改 RPC 时先把服务端 `api/proto/godmc/v1/motion.proto` 的变更同步到此文件，再生成 Python 模块。若项目不在同一个工作区，可直接在本地副本上修改。生成器版本固定在开发组 `grpcio-tools==1.84.0`：

```sh
uv run --group dev python tools/generate_proto.py
```

生成代码位于 `src/nano_ctl_connect/proto/godmc/v1/`，不要手改 `motion_pb2.py` 或 `motion_pb2_grpc.py`。提交 schema 和生成文件时应一并更新。

## 构建与发布

```sh
uv build
```

产物写入 `dist/`。新机器迁移时保留 `pyproject.toml`、`uv.lock`、`src/`、`proto/`、`tools/` 和 `examples/`；不要复制 `.venv/`、`dist/`、`build/`、`*.egg-info/` 或 Python 缓存。Python 依赖与环境可在新设备上通过 `uv sync --locked` 重建。

## 目录结构

```text
nano_ctl_connect/
├── examples/                         # 可运行客户端示例
├── proto/godmc/v1/motion.proto       # 服务协议快照
├── src/nano_ctl_connect/
│   ├── client.py                     # 同步 MotionClient
│   ├── proto/godmc/v1/               # 生成的 gRPC/protobuf 模块
│   └── py.typed                      # PEP 561 类型包标记
├── tools/generate_proto.py           # protobuf 生成脚本
├── pyproject.toml                    # 包元数据和依赖组
├── uv.lock                           # Python 依赖锁文件
└── README.md                         # 开发、调用和发布说明
```

## IO 变量别名

别名使用作用域、卡号、类型与地址共同定位；旧系统中存在重名变量，因此名称仅用于显示。`system_hardware` 表示全局硬件，其他作用域为旧项目 ID。

```python
from nano_ctl_connect import MotionClient, IOKind

with MotionClient() as client:
    variables = client.list_io_aliases("system_hardware", card_no=0)
    for variable in variables.aliases:
        print(variable.alias, variable.ref.address, variable.reverse)

    # 属性修改只保存配置，不会改变输出。
    client.put_io_alias(0, IOKind.OUTPUT_BIT, 8, "运行指示灯", reverse=True)
    sample = client.read_io_alias(0, IOKind.OUTPUT_BIT, 8)
    print(sample.logical_on, sample.value.raw_value)  # 逻辑值、物理电平
    # 显式调试输出时调用：
    # client.write_io_alias(0, IOKind.OUTPUT_BIT, 8, on=True)
```

别名读写由后端应用反转与禁用配置。`read_io` / `write_io` 继续使用物理值语义。`put_io_alias` 接受 `remarks`、`reverse`、`disabled`、`scope`；`delete_io_alias` 只删除配置。所有新方法沿用超时、metadata 和 wait-for-ready 参数。
