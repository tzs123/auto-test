"""用例 CRUD：以 YAML 文件存储，按 项目/模块(api|ui) 组织。

目录约定:
  项目 case_dir=cases            -> cases/api/*.yaml, cases/ui/*.yaml
  项目 case_dir=cases/<pid>      -> cases/<pid>/api/*.yaml, cases/<pid>/ui/*.yaml
对应 pytest 文件:
  默认项目: tests/<module>/<stem>.py
  新项目:   tests/<pid>/<module>/<stem>.py（用例与测试脚本同名映射）
"""
import os
from .. import settings
from ..projects import service as project_service


def _module_dir(project_id: str, module: str) -> str:
    proj = project_service.get_project(project_id)
    if not proj:
        raise ValueError(f"项目不存在: {project_id}")
    case_dir = proj.get("case_dir") or "cases"
    d = os.path.join(settings.ROOT, case_dir, module)
    os.makedirs(d, exist_ok=True)
    return d


def _abs(project_id: str, module: str, filename: str) -> str:
    if not filename.endswith((".yaml", ".yml")):
        filename += ".yaml"
    return os.path.join(_module_dir(project_id, module), filename)


def list_cases(project_id: str, module: str = "api") -> list:
    d = _module_dir(project_id, module)
    files = sorted(f for f in os.listdir(d) if f.endswith((".yaml", ".yml")))
    result = []
    for fn in files:
        path = os.path.join(d, fn)
        result.append({
            "name": fn,
            "module": module,
            "project_id": project_id,
            "size": os.path.getsize(path),
            "mtime": int(os.path.getmtime(path)),
            "relative": f"{project_service.get_project(project_id).get('case_dir','cases')}/{module}/{fn}",
        })
    return result


def get_case(project_id: str, module: str, filename: str) -> str:
    with open(_abs(project_id, module, filename), "r", encoding="utf-8") as f:
        return f.read()


def save_case(project_id: str, module: str, filename: str, content: str) -> str:
    """新增/更新用例 YAML，并自动创建对应 tests/<module>/<stem>.py 骨架（缺失时）。"""
    path = _abs(project_id, module, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    _ensure_test_stub(project_id, module, filename)
    return path


def delete_case(project_id: str, module: str, filename: str) -> bool:
    path = _abs(project_id, module, filename)
    if os.path.exists(path):
        os.remove(path)
    # 同步删除对应的 pytest 脚本，避免执行"全部"时跑到已删除用例的旧 .py
    stem = filename.rsplit(".", 1)[0]
    if project_id == "default":
        test_path = os.path.join(settings.ROOT, "tests", module, f"{stem}.py")
    else:
        test_path = os.path.join(settings.ROOT, "tests", project_id, module, f"{stem}.py")
    if os.path.exists(test_path):
        os.remove(test_path)
    return os.path.exists(path) is False


def _ensure_test_stub(project_id: str, module: str, filename: str):
    """为新增 YAML 用例生成对应 pytest 文件（数据驱动），避免执行时找不到。
    默认项目：tests/api/test_x.py
    新项目：  tests/{pid}/api/test_x.py（import 使用 pages.{pid}.xxx）
    """
    stem = filename.rsplit(".", 1)[0]
    # 默认项目 -> tests/module/；新项目 -> tests/{pid}/module/
    if project_id == "default":
        test_dir = os.path.join(settings.ROOT, "tests", module)
    else:
        test_dir = os.path.join(settings.ROOT, "tests", project_id, module)
    os.makedirs(test_dir, exist_ok=True)
    test_path = os.path.join(test_dir, f"{stem}.py")
    if os.path.exists(test_path):
        return
    rel = f"cases/{module}/{filename}" if project_id == "default" \
        else f"{project_service.get_project(project_id).get('case_dir','cases')}/{module}/{filename}"
    template = f'''import pytest
import allure
from utils.yaml_loader import load_cases


@allure.feature("{stem}")
@pytest.mark.{module}
@pytest.mark.parametrize("case", load_cases("{rel}"))
def test_{stem}(case{("" if module == "api" else ", page")}):
    with allure.step(case.get("name", case.get("scenario", "{stem}"))):
        # TODO: 按 YAML 字段补充断言逻辑
        assert True
'''
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(template)
