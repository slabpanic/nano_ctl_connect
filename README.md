# nano_ctl_connect

面向 Python 开发者的 `nano_ctl` 运动控制后端 gRPC 客户端。

## 目录

- [项目简介](#项目简介)
- [环境要求](#环境要求)
- [安装与运行](#安装与运行)
- [使用示例](#使用示例)
- [连接与生命周期](#连接与生命周期)
- [API 参考](#api-参考)
- [IO 变量](#io-变量)
- [Protobuf 开发](#protobuf-开发)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

## 项目简介

`nano-ctl-connect` 是 `nano_ctl` MotionService 的同步 Python gRPC 客户端包，提供轴、IO、EtherCAT、对象字典、PDO、HCMP 和外接编码器接口。它不包含控制卡驱动，也不要求客户端设备安装雷赛 SDK。

典型用途是用 Python 读取或订阅轴与 IO 状态，并向后端下发轴或 IO 命令。

## 环境要求

- Python 3.10 或更新版本。
- 可访问的 `nano_ctl` gRPC 服务；默认目标为 `127.0.0.1:50051`。
- 项目使用 `grpcio` 和 `protobuf`，开发依赖包含 `grpcio-tools`。

## 安装与运行

在仓库根目录安装项目和开发依赖：

```bash
uv sync --locked
```

运行内置的读轴和订阅示例：

```bash
uv run python examples/read_and_watch.py
```

示例将连接写在代码里的 `127.0.0.1:50051`。运行前请确保该地址上已有服务。如果要连接其他主机，请在自己的代码中传入实际地址：

```python
from nano_ctl_connect import MotionClient

with MotionClient("<YOUR_NANO_CTL_HOST>:50051") as client:
    result = client.read_axes(0, [0, 1])
```

## 使用示例

读取并持续订阅轴状态：

```python
from nano_ctl_connect import MotionClient

with MotionClient("<YOUR_NANO_CTL_HOST>:50051") as client:
    result = client.read_axes(card_no=0, axes=[0, 1])
    for axis in result.axes:
        print(axis.ref.axis, axis.encoder_position, axis.current_speed)

    for batch in client.watch_axes(0, [0, 1], interval_micros=10_000):
        print(batch.sampled_at_unix_nano, [axis.done for axis in batch.axes])
```

读写 IO：

```python
from nano_ctl_connect import IOKind, MotionClient

with MotionClient("<YOUR_NANO_CTL_HOST>:50051") as client:
    inputs = client.read_io(0, IOKind.INPUT_BIT, [0, 1, 2])
    print([value.on for value in inputs.values])

    client.write_io(0, 0, IOKind.OUTPUT_BIT, on=True)
```

> [!WARNING]
> `axis_command()` 和 `write_io()` 会向后端下发控制命令。执行前请确认卡号、轴号、IO 地址和设备状态；运动命令可能驱动物理设备。

`axis_command()` 可传入 `AxisAction` 和 `MotionUnit`，例如：

```python
from nano_ctl_connect import AxisAction, MotionClient, MotionUnit

with MotionClient("<YOUR_NANO_CTL_HOST>:50051") as client:
    client.axis_command(
        0, 0, AxisAction.MOVE,
        unit=MotionUnit.ANGLE,
        position=90.0,
        speed=20.0,
        acceleration=100.0,
        deceleration=100.0,
    )
```

## 连接与生命周期

`MotionClient()` 默认读取 `NANO_CTL_GRPC_ADDR`；未设置时使用 `127.0.0.1:50051`。例如：

```bash
export NANO_CTL_GRPC_ADDR="<YOUR_NANO_CTL_HOST>:50051"
uv run python your_client.py
```

此环境变量只在构造 `MotionClient()` 时没有传入 `target` 的情况下生效。内置示例显式传入 `127.0.0.1:50051`，因此不会被该变量覆盖。

客户端默认创建明文 gRPC channel。需要 TLS 时可传入 gRPC credentials，也可传入已有 channel。客户端负责自己的 gRPC channel；服务端负责控制卡会话。`close()` 或离开 `with` 块会关闭客户端 channel，不会替其他客户端关闭服务端控制卡。

一元调用默认 deadline 为 5 秒；可通过 `default_timeout` 修改或设为 `None`。流式调用默认不设置 deadline。`wait_ready()` 可等待 channel 就绪；调用支持传递 gRPC metadata 和 `wait_for_ready`。底层 `MotionServiceStub` 可从 `client.raw` 访问。

## API 参考

`MotionClient` 提供以下主要方法：

| 类别 | 方法 |
|---|---|
| 轴状态与命令 | `read_axis`、`read_axes`、`watch_axes`、`axis_command` |
| IO 读写与订阅 | `read_io`、`read_io_array`、`watch_io`、`write_io` |
| IO 变量配置与读写 | `list_io_variables`、`put_io_variable`、`delete_io_variable`、`read_io_variable`、`write_io_variable` |
| EtherCAT 总线 | `read_bus`、`bus_command` |
| 对象字典 | `read_object_dictionary`、`write_object_dictionary` |
| PDO | `read_rxpdo`、`write_rxpdo`、`read_txpdo` |
| HCMP | `read_hcmp`、`hcmp_command` |
| 外接编码器 | `read_extra_encoder`、`extra_encoder_command` |

方法返回对应的 protobuf 响应；gRPC 调用错误以 `grpc.RpcError` 抛出。枚举类型包括 `AxisAction`、`MotionUnit`、`IOKind`、`BusAction`、`HcmpAction` 和 `ExtraEncoderAction`。

## IO 变量

IO 变量用卡号、类型和地址定位；`alias` 是显示名称。`put_io_variable()` 保存备注、反转和禁用等属性，不会直接改变硬件输出。`read_io_variable()` 返回物理值以及应用反转配置后的逻辑值；`write_io_variable()` 写逻辑输出，禁用变量或输入会被拒绝。`read_io()` / `write_io()` 使用物理值语义。

## Protobuf 开发

`proto/godmc/v1/motion.proto` 是此包使用的 schema。修改 RPC 时同步更新 schema，再生成 Python 模块：

```bash
uv run --group dev python tools/generate_proto.py
```

生成文件位于 `src/nano_ctl_connect/proto/godmc/v1/`，不要手动编辑 `motion_pb2.py` 或 `motion_pb2_grpc.py`。构建分发包：

```bash
uv build
```

## 贡献指南

- 修改服务接口时，同时提交 `proto/godmc/v1/motion.proto` 和对应生成模块。
- 运行 `uv run --group dev python tools/generate_proto.py` 重新生成 protobuf 文件。
- 提交前可运行 `uv build` 检查分发包构建。
- 当前仓库未发现测试套件或 CI workflow；新增行为时请一并补充合适的验证。

## 许可证

本项目采用 MIT License，详见 [LICENSE](./LICENSE)。
