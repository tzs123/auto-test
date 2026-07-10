import os
import sys
import time
import pytest
import allure
from playwright.sync_api import sync_playwright
from utils.http_client import HttpClient
from utils.yaml_loader import load_config

# ===== monkey-patch allure.attach：同时收集文本附件到 pytest-html extras =====
# pytest-html 默认只有用例名/状态/耗时，不显示 allure.attach 的内容。
# 通过 hook 把 allure 文本附件收集到 item，再用 pytest_html.extras 注入 report，
# 静态报告(pytest-html)即可展开查看 请求地址/参数/响应体/诊断信息。
_original_allure_attach = allure.attach
_current_item = None


def _is_image(attachment_type):
    if attachment_type is None:
        return False
    s = str(attachment_type).lower()
    return "png" in s or "image" in s


def _attach_with_collect(body, name=None, attachment_type=None, **kwargs):
    _original_allure_attach(body, name=name, attachment_type=attachment_type, **kwargs)
    # 收集文本类附件，供 pytest-html 静态报告显示
    if not _is_image(attachment_type) and isinstance(body, (str, bytes)):
        text = body if isinstance(body, str) else body.decode("utf-8", errors="replace")
        if _current_item is not None:
            if not hasattr(_current_item, "_pytest_html_attachments"):
                _current_item._pytest_html_attachments = []
            _current_item._pytest_html_attachments.append((name or "附件", text[:3000]))


allure.attach = _attach_with_collect
# ===== monkey-patch end =====


# ===== 项目级 pages 目录支持 =====
_project_id = os.getenv("PROJECT_ID", "")
if _project_id and _project_id != "default":
    _project_pages = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages", _project_id)
    if os.path.isdir(_project_pages) and _project_pages not in sys.path:
        sys.path.insert(0, _project_pages)


# ===== 接口测试 fixture =====
@pytest.fixture(scope="session")
def config():
    return load_config(os.getenv("ENV", "test"))


@pytest.fixture(scope="session")
def client(config):
    return HttpClient(
        base_url=config["base_url"],
        timeout=config.get("timeout", 30),
        headers=config.get("headers", {}),
    )


# ===== UI 测试 fixture =====
@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        yield browser
        browser.close()


@pytest.fixture(scope="function")
def page(browser):
    context = browser.new_context(
        viewport={"width": 375, "height": 812},
        locale="zh-CN",
        has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
            "Mobile/15E148 Safari/604.1"
        ),
    )
    page = context.new_page()
    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    yield page
    context.clear_cookies()
    context.close()


def _task_screenshot_dir() -> str:
    """当前执行任务截图目录（由执行器设置 TASK_ID 环境变量）。"""
    task_id = os.getenv("TASK_ID", "")
    if not task_id:
        return ""
    d = os.path.join("screenshots", task_id)
    os.makedirs(d, exist_ok=True)
    return d


# ===== 设置/清除当前 item，供 allure.attach 收集器使用 =====
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    global _current_item
    _current_item = item
    item._pytest_html_attachments = []
    yield
    _current_item = None


# ===== 失败自动截图（allure + 任务目录） + 注入 pytest-html extras =====
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        # 把收集到的 allure 文本附件注入 pytest-html extras（静态报告可展开查看）
        attachments = getattr(item, "_pytest_html_attachments", [])
        if attachments:
            try:
                from pytest_html import extras
                from pytest_html.fixtures import extras_stash_key
                extra_list = [extras.text(text, name=name) for name, text in attachments]
                # 方式1: 直接设置 report.extras（兼容旧版）
                existing = getattr(report, "extras", None) or []
                report.extras = existing + extra_list
                # 方式2: 写入 config.stash（pytest-html 4.x plugin 会从此读取并合并）
                stash_list = item.config.stash.get(extras_stash_key, None)
                if stash_list is None:
                    stash_list = []
                    item.config.stash[extras_stash_key] = stash_list
                stash_list.extend(extra_list)
            except Exception:
                pass
        # 失败自动截图
        if report.failed:
            page = item.funcargs.get("page")
            if page:
                try:
                    img = page.screenshot()
                    allure.attach(
                        img, name="失败截图", attachment_type=allure.attachment_type.PNG
                    )
                    shot_dir = _task_screenshot_dir()
                    if shot_dir:
                        fname = f"{int(time.time())}_{item.name}.png"
                        with open(os.path.join(shot_dir, fname), "wb") as f:
                            f.write(img)
                except Exception:
                    pass


# ===== 跑完汇总 =====
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    error = len(terminalreporter.stats.get("error", []))
    skipped = len(terminalreporter.stats.get("skipped", []))
    total = passed + failed + error + skipped

    print(f"\n{'=' * 20} 测试汇总 {'=' * 20}")
    print(f"总计: {total} | 通过: {passed} | 失败: {failed + error} | 跳过: {skipped}")
