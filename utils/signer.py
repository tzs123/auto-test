import hashlib
import os
import json
from urllib.parse import quote


def _generate_nonce(length: int = 32) -> str:
    """生成安全的随机 nonce（十六进制字符串）"""
    return os.urandom(length).hex()[:length * 2]


def _normalize_params(params: dict) -> dict:
    """过滤空值，按键名排序，对象转 JSON 字符串"""
    filtered = {k: v for k, v in params.items() if v is not None and v != ""}
    sorted_keys = sorted(filtered.keys())
    result = {}
    for k in sorted_keys:
        v = filtered[k]
        if isinstance(v, (dict, list)):
            result[k] = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        else:
            result[k] = str(v)
    return result


def _build_sign_string(params: dict) -> str:
    """构建签名字符串：key1=value1&key2=value2（URL 编码）"""
    return "&".join(
        f"{k}={quote(v, safe='')}"
        for k, v in params.items()
    )


def _sha256_double_salt(text: str, salt: str) -> str:
    """双重 SHA256 加盐签名：sha256(sha256(text) + sha256(salt))"""
    hash_text = hashlib.sha256(text.encode()).hexdigest()
    hash_salt = hashlib.sha256(salt.encode()).hexdigest()
    return hashlib.sha256((hash_text + hash_salt).encode()).hexdigest()


def make_headers(access_key: str, secret_key: str = "",
                 method: str = "GET", query_params: dict = None,
                 extra: dict = None) -> dict:
    """生成每次请求需要的签名 headers

    签名算法（与前端一致）：
    1. 构建参数：{nonce, timestamp, accessKey, version, action=method, ...queryParams}
    2. 过滤空值，按键名排序
    3. 构建签名字符串：key1=value1&key2=value2（URL编码）
    4. 拼接 key：signString + "&key=" + secretKey
    5. 双重 SHA256：sha256(sha256(signString+key) + sha256(secretKey))
    """
    timestamp = str(int(os.getenv("MOCK_TIMESTAMP", "") ) if os.getenv("MOCK_TIMESTAMP") else __import__("time").time() * 1000)
    timestamp = str(int(float(timestamp)))
    nonce = _generate_nonce()

    # 构建签名参数
    sign_params = {
        "nonce": nonce,
        "timestamp": timestamp,
        "accessKey": access_key,
        "version": "v1",
        "action": method.lower(),
    }
    # 合并 query 参数
    if query_params:
        sign_params.update(query_params)

    # 规范化并排序
    normalized = _normalize_params(sign_params)
    # 构建签名字符串
    sign_string = _build_sign_string(normalized)
    # 拼接 key
    raw = sign_string + "&key=" + secret_key
    # 双重 SHA256 加盐
    signature = _sha256_double_salt(raw, secret_key)

    headers = {
        "X-API-AccessKey": access_key,
        "X-API-Nonce": nonce,
        "X-API-Signature": signature,
        "X-API-Timestamp": timestamp,
        "X-API-Version": "v1",
        "x-user": "1",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers
