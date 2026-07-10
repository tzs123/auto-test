"""测试可视化平台后端：FastAPI 完整 REST API。

能力：
- 项目 / 用例（YAML）CRUD
- 单/批量执行（任务隔离 + 流式日志 + Allure 报告 + 截图）
- 任务列表 / 详情 / 日志 / 截图查看
- 定时任务管理（cron）
- 负载均衡（Redis 队列 + 多 worker）
- 飞书报告通知
"""
import os
import json
import time
import shutil
import asyncio
import threading
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import db, settings, log_store, executor, feishu, redis_queue
from backend.projects import service as project_service
from backend.cases import service as case_service
from backend import scheduler as scheduler_module

app = FastAPI(title="自动化测试可视化平台", version="1.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ===== 静态资源挂载 =====
os.makedirs(settings.REPORT_DIR, exist_ok=True)
os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
app.mount("/report", StaticFiles(directory=settings.REPORT_DIR, html=True), name="report")
app.mount("/screenshots", StaticFiles(directory=settings.SCREENSHOTS_DIR), name="screenshots")


# ===== 启动初始化 =====
@app.on_event("startup")
def _startup():
    db.init_db()
    project_service.seed_default_project()
    try:
        scheduler_module.start_scheduler()
    except Exception as e:
        print(f"[scheduler] 启动失败（不影响主服务）: {e}")


# ===== 首页 =====
@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(settings.ROOT, "templates", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ===== Pydantic 模型 =====
class ProjectIn(BaseModel):
    name: str
    description: str = ""
    base_url: str = ""
    case_dir: str = None
    defect_xlsx_path: str = ""
    envs: dict = None            # 多环境 Base URL，如 {"test": "http://...", "staging": "http://..."}


class CaseIn(BaseModel):
    content: str


class RunIn(BaseModel):
    project_id: str
    module: str = "all"          # api / ui / all
    case_files: list = []        # 空=该模块全部
    triggered_by: str = "manual"
    env: str = "test"            # 环境：test/staging/prod
    base_url: str = ""           # 执行时使用的 Base URL（覆盖项目默认配置）


class JobIn(BaseModel):
    project_id: str
    name: str
    module: str = "all"
    case_files: list = []
    cron: str                    # 6 段 cron（含秒）
    enabled: bool = True


class BatchDeleteIn(BaseModel):
    task_ids: list[str]


# ===== 项目 =====
@app.get("/api/projects")
def projects_list():
    return project_service.list_projects()


@app.post("/api/projects")
def projects_create(body: ProjectIn):
    return project_service.create_project(
        body.name, body.description, body.base_url, body.case_dir,
        body.defect_xlsx_path, envs=body.envs)


@app.get("/api/projects/{pid}")
def projects_get(pid: str):
    p = project_service.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p


@app.put("/api/projects/{pid}")
def projects_update(pid: str, body: ProjectIn):
    return project_service.update_project(
        pid, name=body.name, description=body.description,
        base_url=body.base_url, case_dir=body.case_dir,
        defect_xlsx_path=body.defect_xlsx_path, envs=body.envs)


@app.delete("/api/projects/{pid}")
def projects_delete(pid: str):
    if pid == "default":
        raise HTTPException(400, "默认项目不可删除")
    project_service.delete_project(pid)
    return {"ok": True}


# ===== 用例（YAML）=====
@app.get("/api/projects/{pid}/cases")
def cases_list(pid: str, module: str = "api"):
    try:
        return case_service.list_cases(pid, module)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/projects/{pid}/cases/{module}/{filename}")
def cases_get(pid: str, module: str, filename: str):
    try:
        content = case_service.get_case(pid, module, filename)
        return {"filename": filename, "module": module, "content": content}
    except FileNotFoundError:
        raise HTTPException(404, "用例不存在")
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/projects/{pid}/cases/{module}/{filename}")
def cases_save(pid: str, module: str, filename: str, body: CaseIn):
    if module not in ("api", "ui"):
        raise HTTPException(400, "module 必须是 api 或 ui")
    try:
        path = case_service.save_case(pid, module, filename, body.content)
        return {"ok": True, "path": os.path.relpath(path, settings.ROOT)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.delete("/api/projects/{pid}/cases/{module}/{filename}")
def cases_delete(pid: str, module: str, filename: str):
    if case_service.delete_case(pid, module, filename):
        return {"ok": True}
    raise HTTPException(404, "用例不存在")


# ===== 执行 =====
@app.post("/api/run")
def run(body: RunIn):
    proj = project_service.get_project(body.project_id)
    if not proj:
        raise HTTPException(404, "项目不存在")
    # 如果未指定 base_url，使用项目 envs 中对应环境的 URL，再退回 proj.base_url
    base_url = body.base_url
    if not base_url:
        envs = proj.get("envs") or {}
        base_url = envs.get(body.env) or proj.get("base_url") or ""
    task_id = executor.create_task(
        body.project_id, body.module, body.case_files, body.triggered_by,
        body.env, base_url=base_url)
    # 负载均衡：入队由 worker 消费；Redis 不可用时本地同步执行
    threading.Thread(target=executor.dispatch, args=(task_id,), daemon=True).start()
    return {"task_id": task_id, "status": "pending",
            "queue": redis_queue.available(), "base_url": base_url}


@app.get("/api/tasks")
def tasks_list(project_id: str = None, limit: int = 100):
    if project_id:
        rows = db.execute(
            "SELECT t.*, p.name as project_name FROM tasks t "
            "LEFT JOIN projects p ON t.project_id=p.id "
            "WHERE t.project_id=? ORDER BY t.started_at DESC LIMIT ?",
            (project_id, limit), fetch=True)
    else:
        rows = db.execute(
            "SELECT t.*, p.name as project_name FROM tasks t "
            "LEFT JOIN projects p ON t.project_id=p.id "
            "ORDER BY t.started_at DESC LIMIT ?", (limit,), fetch=True)
    return db.to_dicts(rows)


@app.delete("/api/tasks/batch")
def tasks_batch_delete(body: BatchDeleteIn):
    deleted = 0
    errors = []
    for tid in body.task_ids:
        try:
            # a. 删除数据库记录
            db.execute("DELETE FROM tasks WHERE id=?", (tid,))
            # b. 删除报告目录
            report_dir = os.path.join(settings.REPORT_DIR, "tasks", tid)
            if os.path.isdir(report_dir):
                shutil.rmtree(report_dir)
            # c. 删除截图目录
            screenshot_dir = os.path.join(settings.SCREENSHOTS_DIR, tid)
            if os.path.isdir(screenshot_dir):
                shutil.rmtree(screenshot_dir)
            # d. 删除日志文件
            log_store.delete(tid)
            deleted += 1
        except Exception as e:
            errors.append({"task_id": tid, "error": str(e)})
    return {"deleted": deleted, "errors": errors}


@app.get("/api/tasks/{tid}")
def task_detail(tid: str):
    rows = db.execute(
        "SELECT t.*, p.name as project_name FROM tasks t "
        "LEFT JOIN projects p ON t.project_id=p.id WHERE t.id=?", (tid,), fetch=True)
    if not rows:
        raise HTTPException(404, "任务不存在")
    return db.to_dict(rows[0])


@app.post("/api/tasks/{tid}/stop")
def task_stop(tid: str):
    """停止正在运行的任务。"""
    rows = db.execute("SELECT status FROM tasks WHERE id=?", (tid,), fetch=True)
    if not rows:
        raise HTTPException(404, "任务不存在")
    status = db.to_dict(rows[0])["status"]
    if status not in ("running", "pending"):
        raise HTTPException(400, f"任务状态为'{status}'，无法停止")
    result = executor.stop_task(tid)
    if not result["ok"]:
        # 任务可能在 Redis 队列中尚未消费，直接标记为 stopped
        db.execute("UPDATE tasks SET status='stopped', finished_at=? WHERE id=?",
                   (executor._now(), tid))
        return {"ok": True, "msg": "任务已标记为停止"}
    return result


@app.get("/api/tasks/{tid}/log")
def task_log(tid: str):
    return {"task_id": tid, "log": log_store.read(tid)}


@app.get("/api/tasks/{tid}/log/stream")
async def task_log_stream(tid: str):
    """SSE 端点：实时推送日志增量内容。"""
    # 验证任务存在
    rows = db.execute("SELECT status FROM tasks WHERE id=?", (tid,), fetch=True)
    if not rows:
        raise HTTPException(404, "任务不存在")

    async def event_generator():
        offset = 0
        # 先发送当前已有日志
        current_log = log_store.read(tid)
        if current_log:
            offset = len(current_log)
            yield f"data: {json.dumps({'log': current_log}, ensure_ascii=False)}\n\n"

        idle_count = 0
        max_idle = 600  # 500ms * 600 = 300s 超时

        while True:
            await asyncio.sleep(0.5)
            # 检查任务状态，终止态则再推一次后断开
            rows = db.execute("SELECT status FROM tasks WHERE id=?", (tid,), fetch=True)
            status = db.to_dict(rows[0])["status"] if rows else "unknown"
            finished = status in ("success", "failed", "stopped")

            current_log = log_store.read(tid)
            new_content = current_log[offset:]
            if new_content:
                offset = len(current_log)
                idle_count = 0
                yield f"data: {json.dumps({'log': new_content}, ensure_ascii=False)}\n\n"

            if finished:
                yield f"data: {json.dumps({'status': status, 'finished': True}, ensure_ascii=False)}\n\n"
                break

            idle_count += 1
            if idle_count >= max_idle:
                yield f"data: {json.dumps({'timeout': True}, ensure_ascii=False)}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/tasks/{tid}/screenshots")
def task_screenshots(tid: str):
    d = os.path.join(settings.SCREENSHOTS_DIR, tid)
    if not os.path.isdir(d):
        return {"task_id": tid, "screenshots": []}
    files = sorted(f for f in os.listdir(d) if f.endswith(".png"))
    return {"task_id": tid, "screenshots": [f"/screenshots/{tid}/{f}" for f in files]}


# ===== 定时任务 =====
@app.get("/api/jobs")
def jobs_list():
    rows = db.execute("SELECT * FROM jobs ORDER BY id", fetch=True)
    return db.to_dicts(rows)


@app.post("/api/jobs")
def jobs_create(body: JobIn):
    import uuid
    jid = uuid.uuid4().hex[:8]
    db.execute(
        "INSERT INTO jobs(id,project_id,name,module,case_files,cron,enabled,last_run) "
        "VALUES(?,?,?,?,?,?,?,NULL)",
        (jid, body.project_id, body.name, body.module,
         json.dumps(body.case_files, ensure_ascii=False), body.cron, int(body.enabled)),
    )
    scheduler_module.reload_jobs()
    return {"id": jid, "ok": True}


@app.put("/api/jobs/{jid}")
def jobs_update(jid: str, body: JobIn):
    db.execute(
        "UPDATE jobs SET project_id=?,name=?,module=?,case_files=?,cron=?,enabled=? WHERE id=?",
        (body.project_id, body.name, body.module,
         json.dumps(body.case_files, ensure_ascii=False), body.cron,
         int(body.enabled), jid),
    )
    scheduler_module.reload_jobs()
    return {"ok": True}


@app.delete("/api/jobs/{jid}")
def jobs_delete(jid: str):
    db.execute("DELETE FROM jobs WHERE id=?", (jid,))
    scheduler_module.reload_jobs()
    return {"ok": True}


# ===== 系统状态 =====
@app.get("/api/status")
def status():
    redis_ok = redis_queue.available()
    qlen = redis_queue.queue_len() if redis_ok else 0
    task_rows = db.execute(
        "SELECT status, COUNT(*) c FROM tasks GROUP BY status", fetch=True) or []
    stats = {db.to_dict(r)["status"]: db.to_dict(r)["c"] for r in task_rows}
    job_rows = db.execute("SELECT COUNT(*) c FROM jobs", fetch=True)
    job_count = db.to_dict(job_rows[0])["c"] if job_rows else 0
    # 检查 worker 进程是否存活
    worker_alive = _check_worker_alive()
    return {
        "redis": redis_ok,
        "queue_length": qlen,
        "task_stats": stats,
        "job_count": job_count,
        "project_count": len(project_service.list_projects()),
        "allure_cli": settings.ALLURE_CLI,
        "worker_alive": worker_alive,
    }


def _check_worker_alive() -> bool:
    """检查 worker 进程是否存活"""
    try:
        import subprocess as _sp
        result = _sp.run(
            ["pgrep", "-f", "backend.worker"],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def _count_workers() -> int:
    """统计当前存活的 worker 进程数"""
    try:
        import subprocess as _sp
        result = _sp.run(
            ["pgrep", "-f", "backend.worker"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            return len([p for p in result.stdout.split("\n") if p.strip()])
        return 0
    except Exception:
        return 0


def _start_worker_process(count: int = 1) -> dict:
    """在后台启动新的 worker 进程。

    使用 subprocess.Popen 启动 `python -m backend.worker`，
    重定向 stdout/stderr 到日志文件，start_new_session=True 让进程独立于父进程。
    """
    import subprocess as _sp
    import sys as _sys

    started = []
    errors = []
    worker_log_dir = os.path.join(settings.LOGS_DIR, "workers")
    os.makedirs(worker_log_dir, exist_ok=True)

    for i in range(count):
        try:
            log_file = os.path.join(
                worker_log_dir,
                f"worker_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time())}_{i}.log"
            )
            log_fp = open(log_file, "a", encoding="utf-8")
            # start_new_session=True：让 worker 进程脱离父进程会话组，
            # 即使 API 请求结束或 uvicorn 重载，worker 也不会被杀死
            proc = _sp.Popen(
                [_sys.executable, "-m", "backend.worker"],
                cwd=settings.ROOT,
                stdout=log_fp,
                stderr=_sp.STDOUT,
                stdin=_sp.DEVNULL,
                start_new_session=True,
                # 确保 worker 命令行包含 "backend.worker" 字样，
                # 这样 _check_worker_alive 才能检测到
            )
            started.append({"pid": proc.pid, "log": log_file})
        except Exception as e:
            errors.append(str(e))

    # 等待 1.5s 让 worker 进程完成初始化
    time.sleep(1.5)

    return {
        "started": started,
        "errors": errors,
        "alive_count": _count_workers(),
    }


def _start_redis() -> dict:
    """自动启动 Redis 服务。

    按优先级尝试以下启动方式：
    1. `brew services start redis`（推荐，brew 托管进程，开机自启）
    2. `redis-server --daemonize yes`（直接启动守护进程）
    3. 兜底：查找 redis-server 完整路径后启动

    启动后等待最多 5s 确认 Redis 可用。
    """
    import subprocess as _sp
    import shutil as _shutil

    methods_tried = []
    started = False
    method = ""
    detail = ""

    # 方式1：brew services start redis（macOS Homebrew）
    brew_bin = _shutil.which("brew")
    if brew_bin:
        methods_tried.append("brew services")
        try:
            result = _sp.run(
                [brew_bin, "services", "start", "redis"],
                capture_output=True, text=True, timeout=15
            )
            out = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                method = "brew services start redis"
                detail = out
                started = True
            else:
                detail = f"brew services 失败: {out}"
        except Exception as e:
            detail = f"brew services 异常: {e}"

    # 方式2：redis-server --daemonize yes（直接启动）
    if not started:
        redis_bin = _shutil.which("redis-server")
        if redis_bin:
            methods_tried.append("redis-server --daemonize")
            try:
                # 读取配置的端口，确保启动在正确端口
                redis_port = int(settings.REDIS_CFG.get("port", 6379))
                result = _sp.run(
                    [redis_bin, "--daemonize", "yes", "--port", str(redis_port)],
                    capture_output=True, text=True, timeout=10
                )
                out = (result.stdout + result.stderr).strip()
                if result.returncode == 0:
                    method = f"redis-server --daemonize yes --port {redis_port}"
                    detail = out
                    started = True
                else:
                    detail = f"{detail} | redis-server 失败: {out}".strip(" |")
            except Exception as e:
                detail = f"{detail} | redis-server 异常: {e}".strip(" |")

    # 等待 Redis 完全就绪（最多 5s）
    ping_ok = False
    for _ in range(10):
        try:
            import redis as _redis
            client = _redis.Redis(
                host=settings.REDIS_CFG.get("host", "localhost"),
                port=int(settings.REDIS_CFG.get("port", 6379)),
                db=int(settings.REDIS_CFG.get("db", 0)),
            )
            client.ping()
            ping_ok = True
            break
        except Exception:
            time.sleep(0.5)

    return {
        "started": started,
        "ping_ok": ping_ok,
        "method": method,
        "methods_tried": methods_tried,
        "detail": detail,
    }


def _kill_zombie_processes():
    """杀掉僵尸 pytest 和 playwright driver 进程"""
    import subprocess as _sp
    killed = []
    try:
        # 查找 auto_test 项目下的 pytest 进程
        result = _sp.run(
            ["pgrep", "-f", "auto_test.*pytest"],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.split("\n") if p.strip()]
        for pid in pids:
            try:
                _sp.run(["kill", "-9", pid], timeout=3)
                killed.append(f"pytest({pid})")
            except Exception:
                pass
        # 查找 playwright driver 进程
        result = _sp.run(
            ["pgrep", "-f", "auto_test.*playwright.*driver"],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.split("\n") if p.strip()]
        for pid in pids:
            try:
                _sp.run(["kill", "-9", pid], timeout=3)
                killed.append(f"playwright({pid})")
            except Exception:
                pass
    except Exception:
        pass
    return killed


@app.post("/api/worker/restart")
def worker_restart(worker_count: int = 1, auto_start: bool = True):
    """重启 Worker：检查 Redis → 杀僵尸进程 → 清队列 → 重派 pending 任务 → 自动启动新 worker。

    参数：
    - worker_count: 启动的 worker 进程数（默认 1，UI 测试建议 1 个）
    - auto_start: 是否自动启动新 worker 进程（默认 True）

    若 Redis 不可用，会先尝试自动启动 Redis（brew services / redis-server --daemonize）。
    """
    import subprocess as _sp

    # 0. 检查 Redis 是否可用，不可用则自动启动
    redis_result = None
    if not redis_queue.available():
        redis_result = _start_redis()
    redis_ok = redis_queue.available()

    # 1. 杀掉僵尸 pytest 和 playwright 进程
    killed = _kill_zombie_processes()

    # 2. 杀掉旧的 worker 进程（确保完全重启，避免旧配置残留）
    old_worker_count = 0
    try:
        result = _sp.run(
            ["pgrep", "-f", "backend.worker"],
            capture_output=True, text=True, timeout=3
        )
        old_pids = [p.strip() for p in result.stdout.split("\n") if p.strip()]
        old_worker_count = len(old_pids)
        for pid in old_pids:
            try:
                _sp.run(["kill", "-9", pid], timeout=3)
                killed.append(f"worker({pid})")
            except Exception:
                pass
    except Exception:
        pass

    # 等待旧进程完全退出
    time.sleep(1)

    # 3. 清空 Redis 队列残留（使用 settings 中配置的队列名）
    queue_name = settings.REDIS_CFG.get("queue", "test_tasks")
    queue_cleared = 0
    if redis_ok:
        try:
            import redis as _redis
            client = _redis.Redis(
                host=settings.REDIS_CFG.get("host", "localhost"),
                port=int(settings.REDIS_CFG.get("port", 6379)),
                db=int(settings.REDIS_CFG.get("db", 0)),
            )
            queue_cleared = client.llen(queue_name) or 0
            client.delete(queue_name)
        except Exception:
            pass

    # 4. 把所有 pending 状态的任务重新入队
    pending_tasks = db.execute(
        "SELECT id FROM tasks WHERE status='pending' ORDER BY started_at",
        fetch=True
    ) or []
    redispatched = []
    if redis_ok:
        for row in pending_tasks:
            tid = db.to_dict(row)["id"]
            try:
                redis_queue.push_task({"task_id": tid})
                redispatched.append(tid)
            except Exception:
                pass

    # 5. 自动启动新 worker 进程
    start_result = None
    if auto_start and redis_ok:
        start_result = _start_worker_process(count=worker_count)
    elif auto_start and not redis_ok:
        start_result = {"started": [], "errors": ["Redis 不可用，跳过 worker 启动"], "alive_count": 0}

    # 6. 检查 worker 是否存活
    worker_alive = _check_worker_alive()
    alive_count = _count_workers()

    message_parts = []
    if redis_result:
        if redis_result["ping_ok"]:
            message_parts.append(f"✅ Redis 已启动 ({redis_result['method']})")
        else:
            message_parts.append(f"❌ Redis 启动失败 ({redis_result['detail'][:80]})")
    else:
        message_parts.append("Redis 已在线")
    message_parts.append(f"杀掉 {len(killed)} 个进程")
    message_parts.append(f"清理队列 {queue_cleared} 条")
    message_parts.append(f"重派 {len(redispatched)} 个任务")
    if start_result:
        if start_result.get("started"):
            pids = [str(s["pid"]) for s in start_result["started"]]
            message_parts.append(f"启动 {len(start_result['started'])} 个 worker (PID: {', '.join(pids)})")
        if start_result.get("errors"):
            message_parts.append(f"启动失败 {len(start_result['errors'])} 次")
    message_parts.append(f"当前存活 worker: {alive_count} 个")

    return {
        "ok": True,
        "redis_ok": redis_ok,
        "redis_result": redis_result,
        "killed_processes": killed,
        "queue_cleared": queue_cleared,
        "redispatched": redispatched,
        "worker_alive": worker_alive,
        "worker_count": alive_count,
        "start_result": start_result,
        "old_worker_count": old_worker_count,
        "message": " | ".join(message_parts),
    }


@app.post("/api/worker/stop_task/{tid}")
def worker_stop_and_clean(tid: str):
    """停止指定任务：杀掉其 pytest 进程 + 标记为 stopped"""
    # 标记为 stopped
    db.execute("UPDATE tasks SET status='stopped', finished_at=? WHERE id=?",
               (time.strftime("%Y-%m-%d %H:%M:%S"), tid))

    # 杀掉该任务的 pytest 进程
    killed = []
    try:
        import subprocess as _sp
        result = _sp.run(
            ["pgrep", "-f", f"TASK_ID={tid}"],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.split("\n") if p.strip()]
        for pid in pids:
            try:
                _sp.run(["kill", "-9", pid], timeout=3)
                killed.append(pid)
            except Exception:
                pass
    except Exception:
        pass

    return {"ok": True, "task_id": tid, "killed_pids": killed}


# ===================== 日志管理 =====================

@app.get("/api/logs/stats")
def logs_stats():
    """获取所有日志目录的统计信息（大小、文件数、最早/最新时间）。"""
    from backend import log_cleanup
    return log_cleanup.get_stats()


@app.post("/api/logs/cleanup")
def logs_cleanup(retention_days: int = 30, dry_run: bool = False):
    """手动清理超过保留天数的日志文件。

    参数：
    - retention_days: 保留最近多少天的日志（默认 30）
    - dry_run: 试运行模式，只统计不实际删除（默认 false）
    """
    from backend import log_cleanup
    return log_cleanup.cleanup_old_logs(retention_days=retention_days, dry_run=dry_run)


@app.get("/api/logs/config")
def logs_config_get():
    """获取自动清理配置。"""
    from backend import log_cleanup
    return log_cleanup.get_config()


@app.post("/api/logs/config")
def logs_config_set(enabled: bool = None, retention_days: int = None):
    """更新自动清理配置。

    参数（都是可选，只更新传入的字段）：
    - enabled: 是否启用自动清理
    - retention_days: 保留天数
    """
    from backend import log_cleanup
    return log_cleanup.set_config(enabled=enabled, retention_days=retention_days)


@app.post("/api/feishu/test")
def feishu_test():
    host = settings.EXTERNAL_URL or f"http://localhost:{settings.SERVER_CFG.get('port', 8000)}"
    return feishu.send_card({
        "id": "test", "project_id": "测试", "module": "all",
        "status": "success", "passed": 1, "failed": 0, "skipped": 0, "total": 1,
        "duration": 0.1, "triggered_by": "manual",
        "started_at": "-", "finished_at": "-",
        "report_url": f"{host}/",
    })


@app.post("/api/feishu/send/{task_id}")
def feishu_send_task(task_id: str):
    rows = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,), fetch=True)
    if not rows:
        raise HTTPException(404, "任务不存在")
    task_dict = db.to_dict(rows[0])
    # report_url 在数据库中是相对路径，飞书需要绝对路径
    report_url = task_dict.get("report_url", "")
    if report_url and not report_url.startswith("http"):
        host = settings.EXTERNAL_URL or f"http://localhost:{settings.SERVER_CFG.get('port', 8000)}"
        task_dict["report_url"] = host + report_url
    return feishu.send_card(task_dict)


# ===== Pages（页面对象）=====
@app.get("/api/projects/{pid}/pages")
def pages_list(pid: str):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    pages_dir = project_service.get_pages_dir(pid)
    result = []
    if os.path.isdir(pages_dir):
        for fn in sorted(os.listdir(pages_dir)):
            if fn.endswith(".py") and fn != "__init__.py":
                fp = os.path.join(pages_dir, fn)
                result.append({
                    "name": fn,
                    "size": os.path.getsize(fp),
                    "mtime": int(os.path.getmtime(fp)),
                })
    return result


@app.get("/api/projects/{pid}/pages/{filename}")
def pages_get(pid: str, filename: str):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    pages_dir = project_service.get_pages_dir(pid)
    fp = os.path.join(pages_dir, filename)
    if not os.path.isfile(fp):
        raise HTTPException(404, "文件不存在")
    with open(fp, "r", encoding="utf-8") as f:
        return {"filename": filename, "content": f.read()}


class PageIn(BaseModel):
    content: str


@app.post("/api/projects/{pid}/pages/{filename}")
def pages_save(pid: str, filename: str, body: PageIn):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    pages_dir = project_service.get_pages_dir(pid)
    os.makedirs(pages_dir, exist_ok=True)
    fp = os.path.join(pages_dir, filename)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(body.content)
    return {"ok": True}


@app.delete("/api/projects/{pid}/pages/{filename}")
def pages_delete(pid: str, filename: str):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    pages_dir = project_service.get_pages_dir(pid)
    fp = os.path.join(pages_dir, filename)
    if os.path.isfile(fp):
        os.remove(fp)
        return {"ok": True}
    raise HTTPException(404, "文件不存在")


# ===== Scripts（测试脚本）=====
@app.get("/api/projects/{pid}/scripts")
def scripts_list(pid: str):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    scripts_dir = project_service.get_test_dir(pid)
    result = []
    def _scan(d, prefix=""):
        if not os.path.isdir(d):
            return
        for fn in sorted(os.listdir(d)):
            fp = os.path.join(d, fn)
            rel = f"{prefix}/{fn}" if prefix else fn
            if os.path.isdir(fp):
                _scan(fp, rel)
            elif fn.endswith(".py") and fn != "__init__.py":
                result.append({
                    "name": rel,
                    "size": os.path.getsize(fp),
                    "mtime": int(os.path.getmtime(fp)),
                })
    _scan(scripts_dir)
    return result


@app.get("/api/projects/{pid}/scripts/{path:path}")
def scripts_get(pid: str, path: str):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    scripts_dir = project_service.get_test_dir(pid)
    fp = os.path.join(scripts_dir, path)
    if not os.path.isfile(fp):
        raise HTTPException(404, "文件不存在")
    with open(fp, "r", encoding="utf-8") as f:
        return {"filename": path, "content": f.read()}


class ScriptIn(BaseModel):
    content: str


@app.post("/api/projects/{pid}/scripts/{path:path}")
def scripts_save(pid: str, path: str, body: ScriptIn):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    scripts_dir = project_service.get_test_dir(pid)
    fp = os.path.join(scripts_dir, path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(body.content)
    return {"ok": True}


@app.delete("/api/projects/{pid}/scripts/{path:path}")
def scripts_delete(pid: str, path: str):
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    scripts_dir = project_service.get_test_dir(pid)
    fp = os.path.join(scripts_dir, path)
    if os.path.isfile(fp):
        os.remove(fp)
        return {"ok": True}
    raise HTTPException(404, "文件不存在")


@app.get("/api/projects/{pid}/stats")
def project_stats(pid: str):
    """获取项目统计信息：用例数、pages数、脚本数"""
    proj = project_service.get_project(pid)
    if not proj:
        raise HTTPException(404, "项目不存在")
    # 用例数
    case_count = 0
    for mod in ("api", "ui"):
        try:
            case_count += len(case_service.list_cases(pid, mod))
        except Exception:
            pass
    # pages 数
    pages_dir = project_service.get_pages_dir(pid)
    page_count = len([f for f in os.listdir(pages_dir) if f.endswith(".py") and f != "__init__.py"]) if os.path.isdir(pages_dir) else 0
    # 脚本数
    scripts_dir = project_service.get_test_dir(pid)
    script_count = 0
    for root, dirs, files in os.walk(scripts_dir):
        script_count += len([f for f in files if f.endswith(".py") and f != "__init__.py"])
    return {"case_count": case_count, "page_count": page_count, "script_count": script_count}


@app.get("/api/logs")
def legacy_logs():
    """兼容旧前端：返回最新任务日志。"""
    ids = log_store.list_logs()
    return {"log": log_store.read(ids[-1]) if ids else ""}


# ===== 缺陷库 =====
class DefectIn(BaseModel):
    task_id: str = ""
    project_id: str = "default"
    tc_id: str = ""
    scenario: str = ""
    title: str
    severity: str = "中"
    error_type: str = ""
    error_message: str = ""
    page_url: str = ""
    screenshot: str = ""
    source: str = "manual"


class DefectBatchDeleteIn(BaseModel):
    defect_ids: list[str]


@app.get("/api/defects")
def defects_list(project_id: str = None, status: str = None, limit: int = 200):
    """获取缺陷列表，支持按项目和状态过滤。"""
    sql = "SELECT * FROM defects WHERE 1=1"
    params = []
    if project_id:
        sql += " AND project_id=?"
        params.append(project_id)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = db.execute(sql, tuple(params), fetch=True)
    return db.to_dicts(rows)


@app.get("/api/defects/{did}")
def defect_detail(did: str):
    rows = db.execute("SELECT * FROM defects WHERE id=?", (did,), fetch=True)
    if not rows:
        raise HTTPException(404, "缺陷不存在")
    return db.to_dict(rows[0])


@app.post("/api/defects")
def defect_create(body: DefectIn):
    import uuid as _uuid
    import time as _time
    did = _uuid.uuid4().hex[:12]
    now = _time.strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO defects(id,task_id,project_id,tc_id,scenario,title,severity,"
        "error_type,error_message,page_url,screenshot,source,status,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (did, body.task_id, body.project_id, body.tc_id, body.scenario, body.title,
         body.severity, body.error_type, body.error_message, body.page_url,
         body.screenshot, body.source, "open", now, now),
    )
    return {"id": did, "ok": True}


@app.put("/api/defects/{did}")
def defect_update(did: str, body: dict):
    import time as _time
    rows = db.execute("SELECT id FROM defects WHERE id=?", (did,), fetch=True)
    if not rows:
        raise HTTPException(404, "缺陷不存在")
    allowed = {"severity", "status", "title", "error_message", "scenario"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return {"ok": False, "msg": "无可更新字段"}
    updates["updated_at"] = _time.strftime("%Y-%m-%d %H:%M:%S")
    cols = ", ".join(f"{k}=?" for k in updates)
    db.execute(f"UPDATE defects SET {cols} WHERE id=?",
               tuple(updates.values()) + (did,))
    return {"ok": True}


@app.delete("/api/defects/{did}")
def defect_delete(did: str):
    db.execute("DELETE FROM defects WHERE id=?", (did,))
    return {"ok": True}


@app.delete("/api/defects")
def defects_batch_delete(body: DefectBatchDeleteIn):
    deleted = 0
    for did in body.defect_ids:
        db.execute("DELETE FROM defects WHERE id=?", (did,))
        deleted += 1
    return {"deleted": deleted}


@app.post("/api/defects/export_xlsx")
def defects_export_xlsx(project_id: str = ""):
    """将缺陷库导出到项目配置的 xlsx 文件（含截图和日志）"""
    proj = project_service.get_project(project_id) if project_id else {}
    xlsx_path = (proj or {}).get("defect_xlsx_path", "") or "/Users/tanzsongsen/Documents/缺陷库.xlsx"
    try:
        count = executor._sync_defects_to_xlsx(xlsx_path, project_id=project_id)
        return {"ok": True, "count": count, "path": xlsx_path}
    except Exception as e:
        raise HTTPException(500, f"导出失败: {e}")


@app.post("/api/defects/import_xlsx")
def defects_import_xlsx(project_id: str = ""):
    """从项目配置的 xlsx 文件导入缺陷到数据库"""
    proj = project_service.get_project(project_id) if project_id else {}
    xlsx_path = (proj or {}).get("defect_xlsx_path", "")
    if not xlsx_path:
        raise HTTPException(400, "当前项目未配置缺陷库 xlsx 路径")
    if not os.path.exists(xlsx_path):
        raise HTTPException(404, f"xlsx 文件不存在: {xlsx_path}")
    try:
        count = executor._import_defects_from_xlsx(xlsx_path, project_id=project_id)
        return {"ok": True, "imported": count, "path": xlsx_path}
    except Exception as e:
        raise HTTPException(500, f"导入失败: {e}")


# ===== 知识库层 =====
class KnowledgeBaseIn(BaseModel):
    name: str
    code: str
    path: str
    session_id: str = ""
    extensions: str = ""
    subdirs: str = ""
    description: str = ""


def _safe_json_loads(s, default=None):
    """安全解析 JSON 字符串，失败时返回默认值。"""
    if default is None:
        default = []
    if not s:
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


def _validate_json_array(value: str, field_name: str):
    """校验字符串是合法的 JSON 数组，返回标准化的 JSON 字符串。
    支持多种输入格式：
    1. 标准 JSON 数组：[".md", ".txt"]
    2. 带方括号的 CSV：[.md, .txt]
    3. 纯 CSV：.md, .txt
    4. 单个值：.md
    """
    if not value or not value.strip():
        return "[]"
    s = value.strip()
    # 1. 先尝试标准 JSON 解析
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return json.dumps(parsed, ensure_ascii=False)
        # 不是 list（可能是 dict/str/num），报错
        raise HTTPException(400, f"{field_name} 必须是 JSON 数组，如 [\".md\",\".txt\"]")
    except json.JSONDecodeError:
        pass
    # 2. 兼容格式：去掉首尾方括号后按逗号分隔
    stripped = s.strip()
    if stripped.startswith("["):
        stripped = stripped[1:]
    if stripped.endswith("]"):
        stripped = stripped[:-1]
    items = [item.strip().strip('"').strip("'") for item in stripped.split(",")]
    items = [it for it in items if it]  # 去除空字符串
    if not items:
        return "[]"
    return json.dumps(items, ensure_ascii=False)


@app.get("/api/knowledge/bases")
def knowledge_bases():
    """获取知识库层配置（从数据库读取）。"""
    rows = db.execute("SELECT * FROM knowledge_bases ORDER BY id", fetch=True)
    result = []
    for r in db.to_dicts(rows):
        import os as _os
        file_count = 0
        # 安全解析 extensions 和 subdirs，避免脏数据导致 500
        extensions = _safe_json_loads(r.get("extensions"))
        subdirs = _safe_json_loads(r.get("subdirs"))
        base_path = r.get("path") or ""
        # 判断存在性：支持文件路径（如 .xlsx 缺陷库）和目录路径
        path_exists = _os.path.exists(base_path) if base_path else False
        is_file = _os.path.isfile(base_path) if base_path else False
        is_dir = _os.path.isdir(base_path) if base_path else False
        if is_file:
            # 单文件知识库（如缺陷库 xlsx）：直接计为 1 个文件
            file_count = 1
        elif is_dir:
            scan_dirs = [os.path.join(base_path, sd) for sd in subdirs] if subdirs else [base_path]
            for scan_dir in scan_dirs:
                if not _os.path.isdir(scan_dir):
                    continue
                for root, dirs, files in _os.walk(scan_dir):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', '.venv')]
                    if extensions:
                        file_count += len([f for f in files if not f.startswith('.') and os.path.splitext(f)[1].lower() in extensions])
                    else:
                        file_count += len([f for f in files if not f.startswith('.')])
        result.append({
            **r,
            "exists": path_exists,
            "is_file": is_file,
            "file_count": file_count,
        })
    return result


@app.put("/api/knowledge/bases/{kb_id}")
def knowledge_base_update(kb_id: str, body: KnowledgeBaseIn):
    """更新知识库配置（校验 extensions 和 subdirs 必须是合法的 JSON 数组）。"""
    rows = db.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,), fetch=True)
    if not rows:
        raise HTTPException(404, "知识库不存在")
    # 校验并标准化 extensions 和 subdirs
    extensions_json = _validate_json_array(body.extensions, "文件扩展名")
    subdirs_json = _validate_json_array(body.subdirs, "子目录")
    db.execute(
        "UPDATE knowledge_bases SET name=?, code=?, path=?, session_id=?, extensions=?, subdirs=?, description=?, updated_at=? WHERE id=?",
        (body.name, body.code, body.path, body.session_id, extensions_json, subdirs_json, body.description, executor._now(), kb_id),
    )
    return {"ok": True}


@app.post("/api/knowledge/sync")
def knowledge_sync():
    """触发知识库同步到 cognee（异步执行，返回任务状态）。"""
    import threading
    import subprocess
    cognee_python = "/Users/tanzsongsen/cognee/.venv/bin/python"
    cognee_path = "/Users/tanzsongsen/cognee"

    # 从数据库导出配置到 JSON 文件，供 load_knowledge.py 读取
    rows = db.execute("SELECT * FROM knowledge_bases ORDER BY id", fetch=True)
    config_dict = {}
    for r in db.to_dicts(rows):
        config_dict[r["name"]] = {
            "path": r.get("path", ""),
            "session_id": r.get("session_id", ""),
            "extensions": json.loads(r.get("extensions") or "[]"),
            "subdirs": json.loads(r.get("subdirs") or "[]") or None,
        }
    config_file = os.path.join(settings.ROOT, "config", "knowledge_bases.json")
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, ensure_ascii=False, indent=2)

    def _sync():
        try:
            import os as _os
            clean_env = {
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin",
                "HOME": _os.environ.get("HOME", "/Users/tanzsongsen"),
                "LANG": "en_US.UTF-8",
            }
            subprocess.run(
                [cognee_python, "-m", "load_knowledge"],
                cwd=cognee_path, capture_output=True, text=True, timeout=600,
                env=clean_env,
            )
        except Exception as e:
            print(f"[knowledge_sync] 同步失败: {e}")
    threading.Thread(target=_sync, daemon=True).start()
    return {"ok": True, "msg": "知识库同步已启动（后台执行，约需几分钟）"}


# ===== 结果分析层 =====
@app.get("/api/analysis/{task_id}")
def analysis_task(task_id: str):
    """获取任务的结果分析（AI日志分析 + 自动归因）。"""
    from backend import analysis
    result = analysis.analyze_task(task_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/analysis/{task_id}/knowledge")
def analysis_query_knowledge(task_id: str, body: dict = None):
    """查询知识库获取相关经验（基于失败原因）。"""
    from backend import analysis
    question = (body or {}).get("question", "")
    if not question:
        # 自动构造问题
        result = analysis.analyze_task(task_id)
        if "error" in result:
            raise HTTPException(404, result["error"])
        failures = result.get("failures", [])
        if failures:
            top = failures[0]
            question = f"测试用例 {top.get('tc_id', '')} 失败，错误: {top.get('error_message', '')[:200]}，如何解决？"
        else:
            question = "该任务无失败用例"
    return analysis.query_knowledge_base(question)
