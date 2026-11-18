"""Exercise real Qt hover/geometry with fake shell services, without Bluetooth.

Run: python tests/run_qml_hover.py
Requires Qt 6 qmltestrunner. Shell popup rendering and IPC are intentionally stubbed.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
runner = "/usr/lib/qt6/bin/qmltestrunner"
if not Path(runner).exists():
    runner = shutil.which("qmltestrunner")
with tempfile.TemporaryDirectory(prefix="oneplus-hover-") as directory:
    staging = Path(directory)
    shutil.copytree(root / "tests/qml", staging, dirs_exist_ok=True)
    for name in ("BarWidget.qml", "BarModel.js", "EqCurveEditor.qml", "EqCurve.js"):
        shutil.copy(root / name, staging / name)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
               QT_QUICK_CONTROLS_STYLE="Basic", QT_LOGGING_TO_CONSOLE="1",
               QT_FORCE_STDERR_LOGGING="1")
    subprocess.run([runner, "-input", str(staging), "-import", str(staging / "imports")],
                   env=env, check=True)
