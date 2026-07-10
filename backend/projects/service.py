"""项目 CRUD。每个项目对应独立 case_dir，base_url 决定接口测试目标。"""
import os
import re
import json
import shutil
import time
import yaml
from .. import db, settings


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _normalize_base_url(url: str) -> str:
    """归一化 Base URL，只保留 scheme://host[:port]，去除路径和查询参数。
    防止用户误把完整 URL（带 /home?xxx）配置为 Base URL 导致拼接错误。
    """
    if not url:
        return ""
    url = url.strip()
    m = re.match(r'^(https?://[^/]+)', url)
    if m:
        return m.group(1)
    return url


def _normalize_project(proj: dict) -> dict:
    """规范化项目数据：如果 envs 为空，从 base_url 自动构造默认环境配置。"""
    if not proj:
        return proj
    envs_raw = proj.get("envs") or ""
    if envs_raw:
        try:
            envs = json.loads(envs_raw)
            if not isinstance(envs, dict):
                envs = {}
        except (json.JSONDecodeError, TypeError):
            envs = {}
    else:
        envs = {}
    # 如果 envs 为空，从 base_url 自动构造
    if not envs:
        base_url = proj.get("base_url") or ""
        if base_url:
            envs = {"test": base_url}
        else:
            envs = {}
    # 归一化所有环境的 base_url（只保留 origin）
    envs = {k: _normalize_base_url(v) for k, v in envs.items()}
    proj["envs"] = envs
    # 兼容字段：base_url 归一化后取 test 环境的值
    if envs.get("test"):
        proj["base_url"] = envs["test"]
    elif proj.get("base_url"):
        proj["base_url"] = _normalize_base_url(proj["base_url"])
    return proj


def list_projects() -> list:
    rows = db.execute("SELECT * FROM projects ORDER BY created_at DESC", fetch=True)
    return [_normalize_project(p) for p in db.to_dicts(rows)]


def get_project(project_id: str) -> dict:
    rows = db.execute("SELECT * FROM projects WHERE id=?", (project_id,), fetch=True)
    return _normalize_project(db.to_dict(rows[0])) if rows else {}


def create_project(name: str, description: str = "", base_url: str = "",
                   case_dir: str = None, defect_xlsx_path: str = "",
                   envs: dict = None) -> dict:
    import uuid
    pid = uuid.uuid4().hex[:8]
    case_dir = case_dir or f"cases/{pid}"
    pages_dir = f"pages/{pid}"
    # 构造 envs JSON：如果传入 envs 用 envs，否则用 base_url 构造默认
    if envs:
        envs_json = json.dumps(envs, ensure_ascii=False)
    elif base_url:
        envs_json = json.dumps({"test": base_url}, ensure_ascii=False)
    else:
        envs_json = "{}"
    db.execute(
        "INSERT INTO projects(id,name,description,base_url,case_dir,pages_dir,defect_xlsx_path,envs,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (pid, name, description, base_url, case_dir, pages_dir, defect_xlsx_path, envs_json, _now()),
    )
    # 建立用例目录骨架: cases/{pid}/api, cases/{pid}/ui
    root = os.path.join(settings.ROOT, case_dir)
    os.makedirs(os.path.join(root, "api"), exist_ok=True)
    os.makedirs(os.path.join(root, "ui"), exist_ok=True)

    # 建立测试脚本目录骨架: tests/{pid}/api, tests/{pid}/ui，并创建 __init__.py
    test_root = os.path.join(settings.ROOT, "tests", pid)
    for sub in ("", "api", "ui"):
        d = os.path.join(test_root, sub)
        os.makedirs(d, exist_ok=True)
        _touch_init(d)

    # 建立项目级 pages 目录: pages/{pid}/，复制 base_page.py
    pages_root = os.path.join(settings.ROOT, "pages", pid)
    os.makedirs(pages_root, exist_ok=True)
    _touch_init(pages_root)
    _copy_base_page(pages_root)

    # 建立项目级环境配置: config/{pid}/，复制默认配置并替换 base_url
    _init_project_config(pid, base_url)

    return get_project(pid)


def update_project(project_id: str, **fields):
    allowed = {"name", "description", "base_url", "case_dir", "defect_xlsx_path", "envs"}
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    # envs 字典转为 JSON 字符串存储
    if "envs" in sets and isinstance(sets["envs"], dict):
        sets["envs"] = json.dumps(sets["envs"], ensure_ascii=False)
    if not sets:
        return get_project(project_id)
    cols = ", ".join(f"{k}=?" for k in sets)
    db.execute(f"UPDATE projects SET {cols} WHERE id=?",
               tuple(sets.values()) + (project_id,))
    return get_project(project_id)


def delete_project(project_id: str):
    proj = get_project(project_id)
    # 获取该项目下所有任务ID（用于清理报告、截图、日志）
    task_rows = db.execute("SELECT id FROM tasks WHERE project_id=?", (project_id,), fetch=True)
    task_ids = [db.to_dict(r)["id"] for r in task_rows] if task_rows else []

    db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    db.execute("DELETE FROM tasks WHERE project_id=?", (project_id,))
    db.execute("DELETE FROM jobs WHERE project_id=?", (project_id,))
    db.execute("DELETE FROM defects WHERE project_id=?", (project_id,))

    # 删除项目级用例目录（仅项目专属目录，不动默认 cases/）
    if proj and proj.get("case_dir", "").startswith("cases/") and proj["case_dir"] != "cases":
        d = os.path.join(settings.ROOT, proj["case_dir"])
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

    # 删除项目级测试脚本目录 tests/{pid}/
    test_dir = os.path.join(settings.ROOT, "tests", project_id)
    if os.path.isdir(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)

    # 删除项目级环境配置 config/{pid}/
    config_dir = os.path.join(settings.ROOT, "config", project_id)
    if os.path.isdir(config_dir):
        shutil.rmtree(config_dir, ignore_errors=True)

    # 删除项目级 pages 目录 pages/{pid}/
    pages_dir = os.path.join(settings.ROOT, "pages", project_id)
    if os.path.isdir(pages_dir):
        shutil.rmtree(pages_dir, ignore_errors=True)

    # 删除项目配置的缺陷库 xlsx 文件
    if proj:
        defect_xlsx = proj.get("defect_xlsx_path", "")
        if defect_xlsx:
            defect_xlsx = os.path.expanduser(defect_xlsx)
            if os.path.isfile(defect_xlsx):
                try:
                    os.remove(defect_xlsx)
                except Exception:
                    pass

    # 删除项目下所有任务的报告、截图、日志
    from backend import log_store
    for tid in task_ids:
        # 删除任务报告目录
        report_dir = os.path.join(settings.REPORT_DIR, "tasks", tid)
        if os.path.isdir(report_dir):
            shutil.rmtree(report_dir, ignore_errors=True)
        # 删除任务截图目录
        screenshot_dir = os.path.join(settings.SCREENSHOTS_DIR, tid)
        if os.path.isdir(screenshot_dir):
            shutil.rmtree(screenshot_dir, ignore_errors=True)
        # 删除任务日志文件
        log_store.delete(tid)


def seed_default_project():
    """首次启动注册默认项目（指向现有 cases/，含今东车融用例）。"""
    if not list_projects():
        db.execute(
            "INSERT INTO projects(id,name,description,base_url,case_dir,created_at) "
            "VALUES(?,?,?,?,?,?)",
            ("default", "默认项目", "内置 cases/api 与 cases/ui 用例",
             "http://172.16.0.88:9527", "cases", _now()),
        )


def _init_project_config(project_id: str, base_url: str = ""):
    """为项目初始化环境配置文件：复制全局默认配置到 config/{pid}/，并替换 base_url。"""
    config_dir = os.path.join(settings.ROOT, "config", project_id)
    os.makedirs(config_dir, exist_ok=True)

    for env_name in ("test", "staging", "prod"):
        src = os.path.join(settings.ROOT, "config", f"{env_name}.yaml")
        if not os.path.exists(src):
            continue
        with open(src, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        if base_url:
            cfg["base_url"] = base_url
        dst = os.path.join(config_dir, f"{env_name}.yaml")
        with open(dst, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


def _touch_init(directory: str):
    """在指定目录创建空的 __init__.py（如不存在）。"""
    init_path = os.path.join(directory, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w", encoding="utf-8") as f:
            pass


def _copy_base_page(pages_root: str):
    """将全局 pages/base_page.py 复制到项目级 pages 目录（如不存在）。"""
    src = os.path.join(settings.ROOT, "pages", "base_page.py")
    dst = os.path.join(pages_root, "base_page.py")
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy2(src, dst)


def get_pages_dir(project_id: str) -> str:
    """获取项目的 pages 目录路径"""
    proj = get_project(project_id)
    if not proj:
        return os.path.join(settings.ROOT, "pages")
    pages_dir = proj.get("pages_dir") or "pages"
    if project_id == "default":
        return os.path.join(settings.ROOT, pages_dir)
    return os.path.join(settings.ROOT, "pages", project_id)


def get_test_dir(project_id: str) -> str:
    """获取项目的测试脚本目录路径"""
    if project_id == "default":
        return os.path.join(settings.ROOT, "tests")
    return os.path.join(settings.ROOT, "tests", project_id)
