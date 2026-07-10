"""飞书机器人通知：富文本交互卡片 + 可选签名校验。"""
import time
import hmac
import hashlib
import base64
import requests
from . import settings, db


def _sign(secret: str, timestamp: int) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def _webhook() -> str:
    return settings.FEISHU.get("webhook", "")


def _secret() -> str:
    return settings.FEISHU.get("secret", "")


def _color(status: str) -> str:
    if status == "success":
        return "green"
    if status == "failed":
        return "red"
    return "grey"


def _status_text(status: str) -> str:
    return {"success": "✅ 全部通过", "failed": "❌ 存在失败",
            "running": "🏃 执行中", "pending": "⏳ 等待中"}.get(status, status)


def send_card(task: dict):
    """发送带报告详情的飞书交互卡片。task 至少含:
    id, project_id, module, status, passed, failed, total, duration,
    triggered_by, report_url, started_at, finished_at
    """
    webhook = _webhook()
    if not webhook:
        return {"skipped": True, "reason": "feishu.webhook 未配置"}

    project_id = task.get("project_id", "")
    project_name = task.get("project_name", "")
    if not project_name and project_id:
        rows = db.execute("SELECT name FROM projects WHERE id=?", (project_id,), fetch=True)
        project_name = rows[0][0] if rows else project_id

    status = task.get("status", "pending")
    template = _color(status)
    pass_n = int(task.get("passed", 0) or 0)
    fail_n = int(task.get("failed", 0) or 0)
    total = int(task.get("total", 0) or 0)
    rate = f"{pass_n / total * 100:.1f}%" if total else "0%"

    MODULE_MAP = {"api": "接口测试", "ui": "UI测试", "all": "全部测试"}
    module_name = MODULE_MAP.get(task.get("module", ""), task.get("module", ""))

    elements = [
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**项目：** {project_name or project_id}　**模块：** {module_name}"}},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**状态：** {_status_text(status)}　**通过率：** {rate}"}},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**总计：** {total}　**通过：** {pass_n}　**失败：** {fail_n}"}},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**耗时：** {task.get('duration', 0)}s　**触发：** {task.get('triggered_by','manual')}"}},
        {"tag": "div", "text": {"tag": "lark_md",
         "content": f"**开始：** {task.get('started_at','-')}　**结束：** {task.get('finished_at','-')}"}},
    ]
    report_url = task.get("report_url")
    download_url = task.get("report_download_url")
    actions = []
    if download_url:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "📄 下载静态报告(pytest-html)"},
            "url": download_url, "type": "primary",
        })
    if report_url:
        actions.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": "📊 Allure报告(在线)"},
            "url": report_url, "type": "default",
        })
    if actions:
        elements.append({"tag": "action", "actions": actions})
        if download_url:
            elements.append({"tag": "div", "text": {"tag": "lark_md",
             "content": "💡 静态报告下载后双击用浏览器打开即可，无需服务；Allure报告需服务在线"}})

    body = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text",
                          "content": f"🚀 测试执行报告 - {task.get('id','')[:8]}"},
                "template": template,
            },
            "elements": elements,
        },
    }

    secret = _secret()
    if secret:
        ts = int(time.time())
        body["timestamp"] = str(ts)
        body["sign"] = _sign(secret, ts)

    try:
        resp = requests.post(webhook, json=body, timeout=10)
        return resp.json() if resp.text else {"status": resp.status_code}
    except Exception as e:
        return {"error": str(e)}


# 兼容旧调用（纯文本）
def send_message(text: str):
    webhook = _webhook()
    if not webhook:
        return {"skipped": True}
    body = {"msg_type": "text", "content": {"text": text}}
    secret = _secret()
    if secret:
        ts = int(time.time())
        body["timestamp"] = str(ts)
        body["sign"] = _sign(secret, ts)
    try:
        return requests.post(webhook, json=body, timeout=10).json()
    except Exception as e:
        return {"error": str(e)}
