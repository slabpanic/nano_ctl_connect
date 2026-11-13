"""Synchronous client for the nano_ctl MotionService."""

from __future__ import annotations

import os
from enum import IntEnum
from typing import Any, Iterator, Sequence

import grpc

from .proto.godmc.v1 import motion_pb2 as pb
from .proto.godmc.v1 import motion_pb2_grpc

Metadata = Sequence[tuple[str, str]]


class AxisAction(IntEnum):
    ENABLE = pb.AXIS_ACTION_ENABLE
    DISABLE = pb.AXIS_ACTION_DISABLE
    STOP = pb.AXIS_ACTION_STOP
    EMERGENCY_STOP = pb.AXIS_ACTION_EMERGENCY_STOP
    CLEAR_FAULT = pb.AXIS_ACTION_CLEAR_FAULT
    CLEAR_STOP_REASON = pb.AXIS_ACTION_CLEAR_STOP_REASON
    ZERO_POSITION = pb.AXIS_ACTION_ZERO_POSITION
    JOG = pb.AXIS_ACTION_JOG
    MOVE = pb.AXIS_ACTION_MOVE
    HOME = pb.AXIS_ACTION_HOME
    HOME_STOP = pb.AXIS_ACTION_HOME_STOP
    CHANGE_SPEED = pb.AXIS_ACTION_CHANGE_SPEED
    CHANGE_TARGET = pb.AXIS_ACTION_CHANGE_TARGET
    SET_EQUIVALENCE = pb.AXIS_ACTION_SET_EQUIVALENCE
    SET_OFFSET = pb.AXIS_ACTION_SET_OFFSET


class MotionUnit(IntEnum):
    POSITION = pb.MOTION_UNIT_POSITION
    ANGLE = pb.MOTION_UNIT_ANGLE


class IOKind(IntEnum):
    INPUT_BIT = pb.IO_KIND_INPUT_BIT
    OUTPUT_BIT = pb.IO_KIND_OUTPUT_BIT
    INPUT_PORT = pb.IO_KIND_INPUT_PORT
    OUTPUT_PORT = pb.IO_KIND_OUTPUT_PORT
    ANALOG_INPUT = pb.IO_KIND_ANALOG_INPUT
    ANALOG_OUTPUT = pb.IO_KIND_ANALOG_OUTPUT


class BusAction(IntEnum):
    STOP = pb.BUS_ACTION_STOP
    CLEAR_ERROR = pb.BUS_ACTION_CLEAR_ERROR


class HcmpAction(IntEnum):
    SET_CONFIG = pb.HCMP_ACTION_SET_CONFIG
    SET_LINEAR = pb.HCMP_ACTION_SET_LINEAR
    ADD_POINT = pb.HCMP_ACTION_ADD_POINT
    CLEAR_POINTS = pb.HCMP_ACTION_CLEAR_POINTS


class ExtraEncoderAction(IntEnum):
    SET_MODE = pb.EXTRA_ENCODER_ACTION_SET_MODE
    SET_POSITION = pb.EXTRA_ENCODER_ACTION_SET_POSITION


def _enum_number(value: IntEnum | int | str, enum_type: type[IntEnum], prefix: str) -> int:
    if isinstance(value, str):
        name = value.strip().upper().replace("-", "_")
        if name.startswith(prefix + "_"):
            name = name[len(prefix) + 1 :]
        try:
            return int(enum_type[name])
        except KeyError as exc:
            raise ValueError(f"unsupported {prefix.lower()} value: {value!r}") from exc
    try:
        return int(enum_type(value))
    except ValueError as exc:
        raise ValueError(f"unsupported {prefix.lower()} value: {value!r}") from exc


class MotionClient:
    """Convenience wrapper around nano_ctl's generated gRPC stub.

    The backend opens hardware on startup and closes it on shutdown. This
    client owns only its gRPC channel; connecting and closing it never change
    the server's hardware session.

    Args:
        target: gRPC target, for example ``"127.0.0.1:50051"``. Defaults to
            ``NANO_CTL_GRPC_ADDR`` or ``"127.0.0.1:50051"``.
        channel: Optional existing channel. When supplied, ``target`` and
            ``credentials`` are ignored.
        credentials: TLS credentials. Omit for an insecure channel.
        options: Core gRPC channel options.
        default_timeout: Deadline for unary calls. Set to ``None`` for no
            default deadline. Streaming calls have no deadline unless given.
        wait_for_ready: Optional default gRPC wait-for-ready behavior.
    """

    def __init__(
        self,
        target: str | None = None,
        *,
        channel: grpc.Channel | None = None,
        credentials: grpc.ChannelCredentials | None = None,
        options: Sequence[tuple[str, Any]] | None = None,
        default_timeout: float | None = 5.0,
        wait_for_ready: bool | None = None,
    ) -> None:
        if channel is not None and credentials is not None:
            raise ValueError("credentials cannot be used with a supplied channel")
        if channel is not None:
            self._channel = channel
        else:
            target = target or os.environ.get("NANO_CTL_GRPC_ADDR", "127.0.0.1:50051")
            if credentials is not None:
                self._channel = grpc.secure_channel(target, credentials, options=options)
            else:
                self._channel = grpc.insecure_channel(target, options=options)
        self._stub = motion_pb2_grpc.MotionServiceStub(self._channel)
        self.default_timeout = default_timeout
        self.wait_for_ready = wait_for_ready

    @property
    def channel(self) -> grpc.Channel:
        """The underlying gRPC channel."""
        return self._channel

    @property
    def raw(self) -> motion_pb2_grpc.MotionServiceStub:
        """The generated stub for calls not wrapped by this client."""
        return self._stub

    def close(self) -> None:
        """Close this client channel and streams; hardware stays owned by the server."""
        self._channel.close()

    def wait_ready(self, timeout: float | None = None) -> None:
        """Wait until the channel is ready, raising ``grpc.FutureTimeoutError`` on timeout."""
        if timeout is None:
            timeout = self.default_timeout
        grpc.channel_ready_future(self._channel).result(timeout=timeout)

    def __enter__(self) -> MotionClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _invoke(
        self,
        rpc: Any,
        request: Any,
        *,
        timeout: float | None,
        metadata: Metadata | None,
        wait_for_ready: bool | None,
        streaming: bool = False,
    ) -> Any:
        if not streaming and timeout is None:
            timeout = self.default_timeout
        if wait_for_ready is None:
            wait_for_ready = self.wait_for_ready
        kwargs: dict[str, Any] = {"timeout": timeout, "metadata": metadata}
        if wait_for_ready is not None:
            kwargs["wait_for_ready"] = wait_for_ready
        return rpc(request, **kwargs)

    def read_axis(
        self,
        card_no: int,
        axis: int,
        *,
        fields_mask: int = 0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.AxisSnapshot:
        return self._invoke(
            self._stub.ReadAxis,
            pb.AxisRef(card_no=card_no, axis=axis, fields_mask=fields_mask),
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_axes(
        self,
        card_no: int,
        axes: Sequence[int],
        *,
        fields_mask: int = 0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.AxisBatch:
        request = pb.AxesRequest(card_no=card_no, axes=axes, fields_mask=fields_mask)
        return self._invoke(
            self._stub.ReadAxes,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def watch_axes(
        self,
        card_no: int,
        axes: Sequence[int],
        *,
        interval_micros: int = 10_000,
        fields_mask: int = 0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> Iterator[pb.AxisBatch]:
        request = pb.AxesRequest(
            card_no=card_no,
            axes=axes,
            interval_micros=interval_micros,
            fields_mask=fields_mask,
        )
        return self._invoke(
            self._stub.WatchAxes,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
            streaming=True,
        )

    def axis_command(
        self,
        card_no: int,
        axis: int,
        action: AxisAction | int | str,
        *,
        unit: MotionUnit | int | str = MotionUnit.POSITION,
        position: float = 0.0,
        speed: float = 0.0,
        acceleration: float = 0.0,
        deceleration: float = 0.0,
        direction: int = 0,
        position_mode: int = 0,
        stop_mode: int = 0,
        home_method: int = 0,
        secondary_speed: float = 0.0,
        offset: float = 0.0,
        probe_function: int = 0,
        equivalence: float = 0.0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        request = pb.AxisCommandRequest(
            ref=pb.AxisRef(card_no=card_no, axis=axis),
            action=_enum_number(action, AxisAction, "AXIS_ACTION"),
            unit=_enum_number(unit, MotionUnit, "MOTION_UNIT"),
            position=position,
            speed=speed,
            acceleration=acceleration,
            deceleration=deceleration,
            direction=direction,
            position_mode=position_mode,
            stop_mode=stop_mode,
            home_method=home_method,
            secondary_speed=secondary_speed,
            offset=offset,
            probe_function=probe_function,
            equivalence=equivalence,
        )
        return self._invoke(
            self._stub.AxisCommand,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_io(
        self,
        card_no: int,
        kind: IOKind | int | str,
        addresses: Sequence[int],
        *,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IOBatch:
        request = pb.IOReadRequest(
            card_no=card_no,
            kind=_enum_number(kind, IOKind, "IO_KIND"),
            addresses=addresses,
        )
        return self._invoke(
            self._stub.ReadIO,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def list_io_variables(
        self,
        *,
        card_no: int | None = None,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IOVariableList:
        """List saved IO variables, optionally limited to a card."""
        request = pb.IOVariablesRequest()
        if card_no is not None:
            request.card_no = card_no
        return self._invoke(self._stub.ListIOVariables, request, timeout=timeout,
                            metadata=metadata, wait_for_ready=wait_for_ready)

    def put_io_variable(
        self,
        card_no: int,
        kind: IOKind | int | str,
        address: int,
        alias: str,
        *,
        remarks: str = "",
        reverse: bool = False,
        disabled: bool = False,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IOVariable:
        """Save metadata only. This never changes a hardware output."""
        request = pb.IOVariable(ref=self._io_variable_ref(card_no, kind, address),
                             alias=alias, remarks=remarks, reverse=reverse, disabled=disabled)
        return self._invoke(self._stub.PutIOVariable, request, timeout=timeout,
                            metadata=metadata, wait_for_ready=wait_for_ready)

    @staticmethod
    def _io_variable_ref(card_no: int, kind: IOKind | int | str, address: int) -> pb.IOVariableRef:
        return pb.IOVariableRef(card_no=card_no,
                             kind=_enum_number(kind, IOKind, "IO_KIND"), address=address)

    def delete_io_variable(
        self,
        card_no: int,
        kind: IOKind | int | str,
        address: int,
        *,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.Empty:
        return self._invoke(self._stub.DeleteIOVariable, self._io_variable_ref(card_no, kind, address),
                            timeout=timeout, metadata=metadata, wait_for_ready=wait_for_ready)

    def read_io_variable(
        self,
        card_no: int,
        kind: IOKind | int | str,
        address: int,
        *,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IOVariableValue:
        """Read physical data plus logical_on, applying the saved reverse flag."""
        return self._invoke(self._stub.ReadIOVariable, self._io_variable_ref(card_no, kind, address),
                            timeout=timeout, metadata=metadata, wait_for_ready=wait_for_ready)

    def write_io_variable(
        self,
        card_no: int,
        kind: IOKind | int | str,
        address: int,
        *,
        on: bool = False,
        raw_value: int = 0,
        reverse_time_millis: int = 0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        """Write a logical output. Disabled variables and inputs are rejected."""
        request = pb.IOVariableWriteRequest(ref=self._io_variable_ref(card_no, kind, address),
                                         on=on, raw_value=raw_value,
                                         reverse_time_millis=reverse_time_millis)
        return self._invoke(self._stub.WriteIOVariable, request, timeout=timeout,
                            metadata=metadata, wait_for_ready=wait_for_ready)

    def read_io_array(
        self,
        card_no: int,
        port_num: int = 2,
        *,
        length: int,
        outputs: bool = False,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IOBatch:
        request = pb.IOArrayReadRequest(
            card_no=card_no,
            port_num=port_num,
            length=length,
            outputs=outputs,
        )
        return self._invoke(
            self._stub.ReadIOArray,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def watch_io(
        self,
        card_no: int,
        kind: IOKind | int | str,
        addresses: Sequence[int],
        *,
        interval_micros: int = 10_000,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> Iterator[pb.IOBatch]:
        request = pb.IOReadRequest(
            card_no=card_no,
            kind=_enum_number(kind, IOKind, "IO_KIND"),
            addresses=addresses,
            interval_micros=interval_micros,
        )
        return self._invoke(
            self._stub.WatchIO,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
            streaming=True,
        )

    def write_io(
        self,
        card_no: int,
        address: int,
        kind: IOKind | int | str,
        *,
        raw_value: int = 0,
        analog_value: float = 0.0,
        on: bool = False,
        reverse_time_millis: int = 0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        request = pb.IOWriteRequest(
            card_no=card_no,
            address=address,
            kind=_enum_number(kind, IOKind, "IO_KIND"),
            raw_value=raw_value,
            analog_value=analog_value,
            on=on,
            reverse_time_millis=reverse_time_millis,
        )
        return self._invoke(
            self._stub.WriteIO,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_bus(
        self,
        card_no: int,
        port_num: int = 2,
        *,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.BusSnapshot:
        return self._invoke(
            self._stub.ReadBus,
            pb.BusRef(card_no=card_no, port_num=port_num),
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def bus_command(
        self,
        card_no: int,
        action: BusAction | int | str,
        port_num: int = 2,
        *,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        request = pb.BusCommandRequest(
            ref=pb.BusRef(card_no=card_no, port_num=port_num),
            action=_enum_number(action, BusAction, "BUS_ACTION"),
        )
        return self._invoke(
            self._stub.BusCommand,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_object_dictionary(
        self,
        card_no: int,
        node: int,
        index: int,
        sub_index: int,
        *,
        port_num: int = 2,
        value_length: int = 4,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IntValue:
        request = pb.ODRequest(
            card_no=card_no,
            port_num=port_num,
            node=node,
            index=index,
            sub_index=sub_index,
            value_length=value_length,
        )
        return self._invoke(
            self._stub.ReadObjectDictionary,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def write_object_dictionary(
        self,
        card_no: int,
        node: int,
        index: int,
        sub_index: int,
        value: int,
        *,
        port_num: int = 2,
        value_length: int = 4,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        request = pb.ODWriteRequest(
            ref=pb.ODRequest(
                card_no=card_no,
                port_num=port_num,
                node=node,
                index=index,
                sub_index=sub_index,
                value_length=value_length,
            ),
            value=value,
        )
        return self._invoke(
            self._stub.WriteObjectDictionary,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_rxpdo(
        self,
        card_no: int,
        address: int,
        *,
        port_num: int = 2,
        data_length: int = 4,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IntValue:
        return self._read_pdo(
            self._stub.ReadRxPDO,
            card_no,
            address,
            port_num=port_num,
            data_length=data_length,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_txpdo(
        self,
        card_no: int,
        address: int,
        *,
        port_num: int = 2,
        data_length: int = 4,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.IntValue:
        return self._read_pdo(
            self._stub.ReadTxPDO,
            card_no,
            address,
            port_num=port_num,
            data_length=data_length,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def _read_pdo(
        self,
        rpc: Any,
        card_no: int,
        address: int,
        *,
        port_num: int,
        data_length: int,
        timeout: float | None,
        metadata: Metadata | None,
        wait_for_ready: bool | None,
    ) -> pb.IntValue:
        return self._invoke(
            rpc,
            pb.PDORequest(
                card_no=card_no,
                port_num=port_num,
                address=address,
                data_length=data_length,
            ),
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def write_rxpdo(
        self,
        card_no: int,
        address: int,
        value: int,
        *,
        port_num: int = 2,
        data_length: int = 4,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        request = pb.PDOWriteRequest(
            ref=pb.PDORequest(
                card_no=card_no,
                port_num=port_num,
                address=address,
                data_length=data_length,
            ),
            value=value,
        )
        return self._invoke(
            self._stub.WriteRxPDO,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_hcmp(
        self,
        card_no: int,
        channel: int,
        *,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.HcmpSnapshot:
        return self._invoke(
            self._stub.ReadHcmp,
            pb.HcmpRef(card_no=card_no, channel=channel),
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def hcmp_command(
        self,
        card_no: int,
        channel: int,
        action: HcmpAction | int | str,
        *,
        mode: int = 0,
        axis: int = 0,
        source: int = 0,
        logic: int = 0,
        time: int = 0,
        increment: int = 0,
        count: int = 0,
        position: int = 0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        request = pb.HcmpCommandRequest(
            ref=pb.HcmpRef(card_no=card_no, channel=channel),
            action=_enum_number(action, HcmpAction, "HCMP_ACTION"),
            mode=mode,
            axis=axis,
            source=source,
            logic=logic,
            time=time,
            increment=increment,
            count=count,
            position=position,
        )
        return self._invoke(
            self._stub.HcmpCommand,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def read_extra_encoder(
        self,
        card_no: int,
        channel: int,
        *,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.ExtraEncoderSnapshot:
        return self._invoke(
            self._stub.ReadExtraEncoder,
            pb.ExtraEncoderRef(card_no=card_no, channel=channel),
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )

    def extra_encoder_command(
        self,
        card_no: int,
        channel: int,
        action: ExtraEncoderAction | int | str,
        *,
        input_mode: int = 0,
        multiplier: int = 0,
        position: int = 0,
        timeout: float | None = None,
        metadata: Metadata | None = None,
        wait_for_ready: bool | None = None,
    ) -> pb.CommandResult:
        request = pb.ExtraEncoderCommandRequest(
            ref=pb.ExtraEncoderRef(card_no=card_no, channel=channel),
            action=_enum_number(action, ExtraEncoderAction, "EXTRA_ENCODER_ACTION"),
            input_mode=input_mode,
            multiplier=multiplier,
            position=position,
        )
        return self._invoke(
            self._stub.ExtraEncoderCommand,
            request,
            timeout=timeout,
            metadata=metadata,
            wait_for_ready=wait_for_ready,
        )
