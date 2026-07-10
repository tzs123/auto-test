"""定时任务调度（APScheduler），支持从 DB 增删查 + 启停。"""
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import db, executor

_scheduler: BackgroundScheduler = None


def _run_job(job_id: str):
    """定时任务触发：创建并派发任务。"""
    rows = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,), fetch=True)
    if not rows:
        return
    job = db.to_dict(rows[0])
    if not job.get("enabled"):
        return
    case_files = json.loads(job.get("case_files") or "[]")
    task_id = executor.create_task(
        project_id=job["project_id"], module=job.get("module") or "all",
        case_files=case_files, triggered_by=f"cron:{job_id}",
    )
    executor.dispatch(task_id)
    db.execute("UPDATE jobs SET last_run=? WHERE id=?",
               (_now(), job_id))


def _now():
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _auto_log_cleanup():
    """每日自动清理旧日志（由 scheduler 每日凌晨 3:00 调用）。

    读取 runtime/log_cleanup_config.json 配置：
    - enabled=False 时跳过
    - enabled=True 时按 retention_days 清理
    """
    try:
        from . import log_cleanup
        result = log_cleanup.auto_cleanup_if_needed()
        print(f"[scheduler] 日志自动清理: {result}", flush=True)
    except Exception as e:
        print(f"[scheduler] 日志自动清理异常: {e}", flush=True)


def _sync_jobs():
    """根据 DB 重建所有启用的 job。"""
    if _scheduler is None:
        return
    # 移除已存在的本调度 job
    for job in list(_scheduler.get_jobs()):
        if job.id.startswith("job-"):
            job.remove()
    rows = db.execute("SELECT * FROM jobs", fetch=True) or []
    for r in rows:
        job = db.to_dict(r)
        if not job.get("enabled"):
            continue
        try:
            trigger = CronTrigger.from_crontab(job["cron"])
            _scheduler.add_job(_run_job, trigger, id=f"job-{job['id']}",
                               args=[job["id"]], replace_existing=True)
        except Exception:
            pass


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.start()
    _sync_jobs()
    # 注册每日日志自动清理 job（凌晨 3:00 执行）
    _scheduler.add_job(
        _auto_log_cleanup,
        CronTrigger(hour=3, minute=0),
        id="auto-log-cleanup",
        replace_existing=True,
    )
    return _scheduler


def reload_jobs():
    _sync_jobs()
