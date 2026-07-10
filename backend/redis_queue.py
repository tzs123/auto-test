"""Redis 任务队列（负载均衡：多 worker 从同一队列消费）。"""
import json
import redis
from . import settings


def _client() -> redis.Redis:
    cfg = settings.REDIS_CFG
    return redis.Redis(
        host=cfg.get("host", "localhost"),
        port=int(cfg.get("port", 6379)),
        db=int(cfg.get("db", 0)),
        decode_responses=True,
    )


def _queue() -> str:
    return settings.REDIS_CFG.get("queue", "test_tasks")


def push_task(task: dict):
    _client().lpush(_queue(), json.dumps(task))


def pop_task(timeout: int = 5) -> dict:
    """阻塞式弹出任务，便于 worker 长轮询。"""
    data = _client().brpop(_queue(), timeout=timeout)
    if data:
        return json.loads(data[1])
    return None


def queue_len() -> int:
    return _client().llen(_queue())


def available() -> bool:
    try:
        _client().ping()
        return True
    except Exception:
        return False
