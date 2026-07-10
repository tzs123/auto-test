"""平台全局配置加载（config/settings.yaml）。"""
import os
import socket
import yaml


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_ROOT, "config", "settings.yaml")


def _load() -> dict:
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _detect_host_ip() -> str:
    try:
        import subprocess
        result = subprocess.run(
            ["ifconfig", "en0"],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "inet " in line and "127.0.0.1" not in line:
                ip = line.strip().split()[1]
                if ip and ip.count(".") == 3:
                    return ip
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


SETTINGS = _load()

# 路径快捷访问
ROOT = _ROOT
RESULTS_DIR = os.path.join(ROOT, SETTINGS["executor"]["results_dir"])
REPORT_DIR = os.path.join(ROOT, SETTINGS["executor"]["report_dir"])
SCREENSHOTS_DIR = os.path.join(ROOT, SETTINGS["executor"]["screenshots_dir"])
LOGS_DIR = os.path.join(ROOT, SETTINGS["executor"]["logs_dir"])
RUNTIME_DIR = os.path.join(ROOT, SETTINGS["executor"]["runtime_dir"])
DB_PATH = os.path.join(RUNTIME_DIR, "platform.db")
JOBS_FILE = os.path.join(RUNTIME_DIR, "jobs.json")

FEISHU = SETTINGS.get("feishu", {})
REDIS_CFG = SETTINGS.get("redis", {})
SERVER_CFG = SETTINGS.get("server", {})
ALLURE_CLI = SETTINGS.get("allure", {}).get("cli", "allure")

_config_external_url = SERVER_CFG.get("external_url", "").rstrip("/")
if _config_external_url:
    EXTERNAL_URL = _config_external_url
else:
    _detected_ip = _detect_host_ip()
    _port = SERVER_CFG.get("port", 8000)
    EXTERNAL_URL = f"http://{_detected_ip}:{_port}"


def ensure_dirs():
    for d in (RESULTS_DIR, REPORT_DIR, SCREENSHOTS_DIR, LOGS_DIR, RUNTIME_DIR):
        os.makedirs(d, exist_ok=True)
