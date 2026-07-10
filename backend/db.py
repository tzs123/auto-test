"""SQLite 存储（项目 / 任务 / 定时任务），WAL 模式保证并发安全。"""
import os
import sqlite3
import json
import time
from . import settings


def get_conn() -> sqlite3.Connection:
    settings.ensure_dirs()
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    settings.ensure_dirs()
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            base_url TEXT,
            case_dir TEXT DEFAULT 'cases',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            module TEXT,              -- api / ui / all
            case_files TEXT,          -- JSON list（空=全部）
            env TEXT DEFAULT 'test',  -- 环境：test/staging/prod
            status TEXT,              -- pending/running/success/failed
            passed INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            duration REAL DEFAULT 0,
            triggered_by TEXT,
            started_at TEXT,
            finished_at TEXT,
            report_url TEXT
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            name TEXT,
            module TEXT,
            case_files TEXT,
            cron TEXT,
            enabled INTEGER DEFAULT 1,
            last_run TEXT
        );

        CREATE TABLE IF NOT EXISTS defects (
            id TEXT PRIMARY KEY,
            task_id TEXT,
            project_id TEXT,
            tc_id TEXT,
            scenario TEXT,
            title TEXT,
            severity TEXT DEFAULT '中',
            error_type TEXT,
            error_message TEXT,
            page_url TEXT,
            screenshot TEXT,
            status TEXT DEFAULT 'open',
            source TEXT DEFAULT 'auto',
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            path TEXT,
            session_id TEXT,
            extensions TEXT,
            subdirs TEXT,
            description TEXT,
            updated_at TEXT
        );
        """
    )
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN env TEXT DEFAULT 'test'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN pages_dir TEXT DEFAULT 'pages'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN engine TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN static_report_url TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN defect_xlsx_path TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN envs TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN base_url TEXT")
    except sqlite3.OperationalError:
        pass
    # 初始化默认知识库配置（仅在表为空时）
    count = conn.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]
    if count == 0:
        defaults = [
            ("kb_requirement", "需求模型库", "requirement", "/Users/tanzsongsen/Documents",
             "kb_requirement", '[".md",".txt",".json",".yaml",".yml",".csv",".xlsx"]', "",
             "需求文档、PRD、业务规则"),
            ("kb_risk", "风险规则库", "risk", "/Users/tanzsongsen/Music",
             "kb_risk", '[".md",".txt",".json",".yaml",".yml",".csv"]', "",
             "风险控制规则、合规要求"),
            ("kb_testcase", "用例库", "testcase", "/Users/tanzsongsen/auto_test",
             "kb_testcase", '[".yaml",".yml",".py",".md",".json"]', '["cases","pages","tests","config"]',
             "测试用例、页面对象、测试脚本"),
            ("kb_defect", "缺陷库", "defect", "/Users/tanzsongsen/Pictures",
             "kb_defect", '[".md",".txt",".json",".csv",".xlsx"]', "",
             "历史缺陷记录、缺陷模式"),
        ]
        now = _now()
        for d in defaults:
            conn.execute(
                "INSERT INTO knowledge_bases(id,name,code,path,session_id,extensions,subdirs,description,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)", (*d, now)
            )
    conn.commit()
    conn.close()


# ===== 通用执行 =====
def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def execute(sql: str, params=(), fetch=False):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall() if fetch else None
        conn.commit()
        return rows
    finally:
        conn.close()


def to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row else {}


def to_dicts(rows) -> list:
    return [dict(r) for r in rows] if rows else []
