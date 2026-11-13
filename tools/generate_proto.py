"""Regenerate Python protobuf modules from the vendored nano_ctl schema."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = ROOT / "proto"
PROTO_FILE = PROTO_ROOT / "godmc" / "v1" / "motion.proto"
OUTPUT = ROOT / "src" / "nano_ctl_connect" / "proto"
GRPC_MODULE = OUTPUT / "godmc" / "v1" / "motion_pb2_grpc.py"
PB2_MODULE = OUTPUT / "godmc" / "v1" / "motion_pb2.py"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"--proto_path={PROTO_ROOT}",
            f"--python_out={OUTPUT}",
            f"--grpc_python_out={OUTPUT}",
            str(PROTO_FILE),
        ],
        cwd=ROOT,
        check=True,
    )

    # protoc derives imports from the proto package path. Keep the generated
    # modules inside nano_ctl_connect rather than requiring a top-level godmc.
    content = GRPC_MODULE.read_text(encoding="utf-8")
    content = content.replace(
        "from godmc.v1 import motion_pb2 as godmc_dot_v1_dot_motion__pb2",
        "from . import motion_pb2 as godmc_dot_v1_dot_motion__pb2",
    )
    GRPC_MODULE.write_text(content, encoding="utf-8")

    # Keep protobuf classes' module names importable for pickle and typing.
    content = PB2_MODULE.read_text(encoding="utf-8")
    content = content.replace(
        "'godmc.v1.motion_pb2'",
        "'nano_ctl_connect.proto.godmc.v1.motion_pb2'",
    )
    PB2_MODULE.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
