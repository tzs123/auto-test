import yaml
import os
import random
import re


def _resolve_vars(value):
    """解析 YAML 值中的变量表达式，如 ${random_phone_cn}"""
    if isinstance(value, str):
        def _replace(m):
            var = m.group(1)
            if var == "random_phone_cn":
                # 生成随机中国手机号（1开头 + 3/4/5/6/7/8/9 + 9位）
                prefix = random.choice([3, 4, 5, 6, 7, 8, 9])
                return f"1{prefix}{random.randint(100000000, 999999999)}"
            elif var == "random_apply_id":
                # 生成18位随机申请ID
                return "".join(str(random.randint(0, 9)) for _ in range(18))
            return m.group(0)
        return re.sub(r'\$\{(\w+)\}', _replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_vars(item) for item in value]
    return value


def load_cases(filepath):
    """加载测试用例 YAML 文件，解析其中的变量表达式"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base, filepath)
    if not os.path.exists(full_path):
        return []
    with open(full_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return []
    data = _resolve_vars(data)
    if isinstance(data, list):
        for case in data:
            if isinstance(case, dict):
                case["case_file_path"] = full_path
    return data


def load_config(env=None):
    """加载环境配置，优先使用项目级配置，fallback 到全局配置。
    项目级配置路径：config/{project_id}/{env}.yaml
    全局配置路径：config/{env}.yaml
    """
    env = env or os.getenv("ENV", "test")
    project_id = os.getenv("PROJECT_ID", "")
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 优先项目级配置
    if project_id and project_id != "default":
        project_path = os.path.join(base, "config", project_id, f"{env}.yaml")
        if os.path.exists(project_path):
            with open(project_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
    # fallback 全局配置
    path = os.path.join(base, f"config/{env}.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
