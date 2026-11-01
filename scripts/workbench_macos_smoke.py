"""Exercise the installed macOS sidecar with a clean, isolated environment."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench_installer_smoke import workbench_smoke


def main():
    if sys.platform != "darwin" or len(sys.argv) != 2:
        raise SystemExit(
            "Usage on macOS: python scripts/workbench_macos_smoke.py /path/to/Plot\\ Workbench.app"
        )
    app = Path(sys.argv[1]).resolve(strict=True)
    resources = app / "Contents" / "Resources"
    sidecar = resources / "sidecar" / "Tavotto" / "Tavotto"
    for path in (sidecar, resources / "LICENSE", resources / "ATTRIBUTION.txt"):
        if not path.is_file():
            raise SystemExit(f"Missing installed resource: {path}")
    env = os.environ.copy()
    for key in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONUSERBASE",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "TAVOTTO_WORKER_PYTHON",
        "TAVOTTO_RUNTIME_DIR",
        "TAVOTTO_WORKERD_BIN",
        "TAVOTTO_SIDECAR_EXE",
    ):
        env.pop(key, None)
    env.update(
        PATH="/usr/bin:/bin:/usr/sbin:/sbin", TAVOTTO_NO_TELEMETRY="1", TAVOTTO_NO_UPDATE_CHECK="1"
    )
    with tempfile.TemporaryDirectory(prefix="plot-workbench-") as tmp:
        work = Path(tmp) / "中文 路径"
        work.mkdir()
        workbench_smoke(sidecar, env, work / "workbench")
        subprocess.run(
            [
                sys.executable,
                "scripts/smoke_app.py",
                "--exe",
                str(sidecar),
                "--figures",
                "examples/runtime_check",
                "--expect-source",
                "bundled",
                "--expect-runtime",
                "--expect-control-plane",
                "workerd",
                "--expect-packages",
                "numpy,pandas,scipy,seaborn,PIL,matplotlib,openpyxl,xlrd",
                "--workdir",
                str(work),
            ],
            env=env,
            check=True,
        )


if __name__ == "__main__":
    main()
