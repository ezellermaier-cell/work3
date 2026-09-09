import sys
import subprocess
from pathlib import Path

TASK_NAME = "CBJobsDaily3PM"

def get_executable():
    return Path(sys.executable).resolve()

def install_daily_task():
    exe = get_executable()
    task_cmd = f'"{exe}" --autorun'
    cmd = [
        "schtasks",
        "/Create",
        "/F",
        "/SC", "DAILY",
        "/TN", TASK_NAME,
        "/TR", task_cmd,
        "/ST", "15:00",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, shell=False
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()

def remove_daily_task():
    result = subprocess.run(
        ["schtasks", "/Delete", "/F", "/TN", TASK_NAME],
        capture_output=True, text=True, shell=False
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()

def task_exists():
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True, text=True, shell=False
    )
    return result.returncode == 0
