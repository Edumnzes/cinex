"""Create (or reuse) the Python venv used by the Cinex skill.

Usage:  python setup_env.py [venv_dir]      (default: ~/reelsenv)
Prints the venv python path and the bundled ffmpeg path.

Why a short path: `python -m venv` fails inside very long Windows paths (ensurepip breaks),
so the venv lives directly under the user's home.
"""
import os, subprocess, sys
from pathlib import Path

venv = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "reelsenv")
py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not py.exists():
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
pkgs = ["faster-whisper", "imageio-ffmpeg", "opencv-python", "pillow", "numpy", "truststore"]
subprocess.run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", *pkgs], check=True)
ff = subprocess.run([str(py), "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    capture_output=True, text=True, check=True).stdout.strip()
print("PYTHON", py)
print("FFMPEG", ff)
