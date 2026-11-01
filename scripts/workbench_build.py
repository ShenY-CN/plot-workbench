"""Build the independent desktop installer, preserving upstream engine contracts.

Requires Python build dependencies, pnpm and Rust, plus the native Windows SDK
or Apple Silicon macOS build tools.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from build_desktop import build_workerd, stage_private_python  # noqa: E402
from build_worker_runtime import BuildError, check_runtime_dir  # noqa: E402
from tavotto.engine.brand import DESKTOP_BUNDLE_ID, WORKBENCH_VERSION  # noqa: E402

LOCK = ROOT / "packaging" / "workbench-runtime-lock.json"


def validate_packaging(conf: dict) -> None:
    """Validate the desktop configuration consumed by this particular build."""
    if conf.get("identifier") != DESKTOP_BUNDLE_ID:
        raise ValueError("Desktop application ID differs from the fork's brand")
    if conf.get("version") != WORKBENCH_VERSION:
        raise ValueError("Desktop version differs from engine.brand.WORKBENCH_VERSION")
    bundle = conf.get("bundle", {})
    if bundle.get("createUpdaterArtifacts") is not False or conf.get("plugins", {}).get("updater"):
        raise ValueError("Plot Workbench does not use automatic or upstream updates")
    resources = bundle.get("resources", {})
    if (
        resources.get("../LICENSE") != "LICENSE"
        or resources.get("../docs/workbench/ATTRIBUTION.txt") != "ATTRIBUTION.txt"
    ):
        raise ValueError("The installer must include AGPL license and upstream attribution")


def run(argv: list[str], **kwargs) -> None:
    print("$ " + " ".join(argv), flush=True)
    subprocess.run(argv, cwd=ROOT, check=True, **kwargs)


def runtime_current() -> bool:
    manifest = ROOT / "runtime" / "runtime-manifest.json"
    try:
        info = check_runtime_dir(manifest, require_smoke=True)
        return info["build"]["lock_sha256"] == hashlib.sha256(LOCK.read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError, BuildError):
        return False


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tauri", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32" and not (sys.platform == "darwin" and platform.machine() == "arm64"):
        raise SystemExit("Build on Windows x64 or native Apple Silicon macOS.")
    os.environ["TAVOTTO_NO_TELEMETRY"] = "1"
    os.environ["TAVOTTO_NO_UPDATE_CHECK"] = "1"
    os.environ["TAVOTTO_REQUIRE_RUNTIME"] = "1"
    os.environ["TAVOTTO_REQUIRE_PRIVATE_PYTHON"] = "1"
    conf = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    validate_packaging(conf)
    if not args.skip_frontend:
        run([sys.executable, "scripts/build_frontend.py"])
    build_workerd()
    if not runtime_current():
        run([sys.executable, "scripts/build_worker_runtime.py", "--lock", str(LOCK), "--clean"])
    run([sys.executable, "scripts/fetch_fonts.py"])
    run([sys.executable, "scripts/fetch_fonts.py", "--check"])
    stage_private_python(False)
    run([sys.executable, "-m", "PyInstaller", "packaging/tavotto.spec", "--noconfirm"])
    suffix = ".exe" if sys.platform == "win32" else ""
    sidecar = ROOT / "dist" / "Tavotto" / f"Tavotto{suffix}"
    for item in (
        sidecar,
        sidecar.parent / f"tavotto-cli{suffix}",
        sidecar.parent / "_internal" / f"tavotto-workerd{suffix}",
    ):
        if not item.is_file():
            raise SystemExit(f"Missing frozen artifact: {item}")
    run([str(sidecar.parent / f"tavotto-cli{suffix}"), "doctor", "--json"])
    if args.skip_tauri:
        return
    pnpm = shutil.which("pnpm.cmd") or shutil.which("pnpm")
    if not pnpm:
        raise SystemExit("pnpm is missing")
    if sys.platform == "darwin":
        bundle, extension = "app,dmg", ".dmg"
        bundle_dir = ROOT / "src-tauri/target/release/bundle/dmg"
        output_name = f"Plot-Workbench-{WORKBENCH_VERSION}-macOS-arm64.dmg"
    else:
        bundle, extension = "nsis", ".exe"
        bundle_dir = ROOT / "src-tauri/target/release/bundle/nsis"
        output_name = f"Plot-Workbench-{WORKBENCH_VERSION}-Windows-x64-Setup.exe"
    run([pnpm, "dlx", "@tauri-apps/cli@2.11.4", "build", "--bundles", bundle])
    installers = list(bundle_dir.glob(f"*{extension}"))
    if len(installers) != 1:
        raise SystemExit(f"Expected one installer, found {len(installers)}")
    out = ROOT / "dist" / output_name
    shutil.copy2(installers[0], out)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_name(out.name + ".sha256").write_text(f"{digest}  {out.name}\n", encoding="ascii")
    print(f"Installer: {out}\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
