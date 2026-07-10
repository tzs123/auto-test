import os
import re
import allure
from playwright.sync_api import Page


# 默认 Base URL（被测系统地址），可被环境变量 BASE_URL 覆盖
DEFAULT_BASE_URL = "http://172.16.0.88:9527"


def _normalize_base_url(url: str) -> str:
    """归一化 Base URL，只保留 scheme://host[:port]，去除路径和查询参数。
    防止用户误把完整 URL（带 /home?xxx）配置为 Base URL 导致拼接错误。
    """
    if not url:
        return ""
    url = url.strip()
    # 匹配 scheme://host[:port]，去除后面的路径和查询
    m = re.match(r'^(https?://[^/]+)', url)
    if m:
        return m.group(1)
    # 兜底：如果没有 scheme，原样返回
    return url


class BasePage:
    """页面对象基类，提供通用的虚拟键盘/选择器交互方法。"""

    def __init__(self, page: Page):
        self.page = page
        # 从环境变量读取 Base URL，执行时由 executor 设置
        # 归一化：只保留 origin（scheme://host[:port]），去除路径和查询参数
        raw_url = os.environ.get("BASE_URL", DEFAULT_BASE_URL)
        self.base_url = _normalize_base_url(raw_url)

    # ── 虚拟键盘相关 ──────────────────────────────────────────

    @allure.step("等待虚拟键盘弹框出现")
    def wait_for_keyboard_popup(self, timeout: int = 5000):
        """等待 .van-popup 或包含 keyboard/key 的容器出现。"""
        popup_selectors = [
            ".van-popup:visible",
            '[class*="keyboard"]:visible',
            '[class*="key-board"]:visible',
        ]
        for sel in popup_selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=timeout):
                    return True
            except Exception:
                pass
        return False

    @allure.step("点击虚拟键盘按键: {char}")
    def click_virtual_key(self, char: str, timeout: int = 3000) -> bool:
        """
        在虚拟键盘容器内精确定位并点击指定按键。
        优先使用 Playwright locator，找不到再用 JS evaluate 兜底。
        """
        # 策略1: 在 .van-popup 内查找文本精确匹配的叶子元素
        try:
            popup = self.page.locator(".van-popup:visible").first
            if popup.is_visible(timeout=timeout):
                key_el = popup.locator(
                    f'//span[normalize-space(text())="{char}"] | '
                    f'//div[normalize-space(text())="{char}"] | '
                    f'//li[normalize-space(text())="{char}"] | '
                    f'//p[normalize-space(text())="{char}"]'
                )
                if key_el.count() > 0:
                    key_el.first.click(timeout=timeout)
                    return True
        except Exception:
            pass

        # 策略2: 在包含 keyboard/key 的容器内查找
        try:
            for container_sel in ['[class*="keyboard"]:visible', '[class*="key-board"]:visible']:
                container = self.page.locator(container_sel).first
                if container.is_visible(timeout=1000):
                    key_el = container.locator(
                        f'//span[normalize-space(text())="{char}"] | '
                        f'//div[normalize-space(text())="{char}"] | '
                        f'//li[normalize-space(text())="{char}"] | '
                        f'//p[normalize-space(text())="{char}"]'
                    )
                    if key_el.count() > 0:
                        key_el.first.click(timeout=timeout)
                        return True
        except Exception:
            pass

        # 策略3: 在任意可见的 popup 内查找文本匹配
        try:
            key_el = self.page.locator(
                f'.van-popup:visible :text-is("{char}")'
            )
            if key_el.count() > 0:
                key_el.first.click(timeout=timeout)
                return True
        except Exception:
            pass

        # 策略4: JS evaluate 兜底
        return self._click_key_by_js(char)

    def _click_key_by_js(self, char: str) -> bool:
        """JS evaluate 兜底：在虚拟键盘弹框内查找并点击指定按键。"""
        try:
            return self.page.evaluate(f"""() => {{
                const candidates = document.querySelectorAll(
                    '[class*="key"], [class*="keyboard"], .van-popup, .van-overlay + div'
                );
                for (const container of candidates) {{
                    if (container.offsetParent === null) continue;
                    const els = container.querySelectorAll('span, div, li, p');
                    for (const el of els) {{
                        if (el.children.length === 0 &&
                            el.textContent.trim() === '{char}' &&
                            el.offsetParent !== null) {{
                            el.click();
                            return true;
                        }}
                    }}
                }}
                return false;
            }}""")
        except Exception:
            return False

    # ── Picker 选择器相关 ──────────────────────────────────────

    @allure.step("等待 Picker 弹框出现")
    def wait_for_picker_popup(self, timeout: int = 5000) -> bool:
        """等待 van-picker / van-action-sheet 弹层出现。"""
        selectors = [
            ".van-picker:visible",
            ".van-action-sheet:visible",
            ".van-popup .van-picker:visible",
        ]
        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=timeout):
                    return True
            except Exception:
                pass
        return False

    @allure.step("选择 Picker 选项: {option_text}")
    def select_picker_option(self, option_text: str, timeout: int = 5000) -> bool:
        """
        在 van-picker / van-action-sheet 弹层内选择指定选项。
        移动端H5需要用touch事件。
        """
        # 优先用 Playwright locator + force click
        selectors = [
            f'.van-picker-column__item:has-text("{option_text}")',
            f'.van-action-sheet__item:has-text("{option_text}")',
            f'.van-popup .van-cell:has-text("{option_text}")',
        ]
        for sel in selectors:
            try:
                el = self.page.locator(sel)
                if el.count() > 0 and el.first.is_visible(timeout=timeout):
                    el.first.click(force=True)
                    return True
            except Exception:
                pass

        # JS evaluate + touch 事件兜底
        return self._select_picker_option_by_js(option_text)

    def _select_picker_option_by_js(self, option_text: str) -> bool:
        """JS evaluate 兜底：在可见弹层内查找并点击选项。"""
        try:
            return self.page.evaluate(f"""() => {{
                const popups = document.querySelectorAll(
                    '.van-popup, .van-action-sheet, [class*="popup"], [class*="sheet"]'
                );
                for (const popup of popups) {{
                    if (popup.offsetParent === null) continue;
                    const walker = document.createTreeWalker(
                        popup, NodeFilter.SHOW_TEXT, null);
                    let node;
                    while (node = walker.nextNode()) {{
                        if (node.textContent.trim() === '{option_text}' &&
                            node.parentElement.offsetParent !== null) {{
                            node.parentElement.click();
                            return true;
                        }}
                    }}
                }}
                return false;
            }}""")
        except Exception:
            return False

    @allure.step("确认 Picker 选择")
    def confirm_picker(self, timeout: int = 2000):
        """点击 van-picker 的确认按钮（移动端H5需要用touch事件）。"""
        # 先尝试 Playwright locator
        for sel in ['.van-picker__confirm', 'button:has-text("确认")']:
            try:
                btn = self.page.locator(sel)
                if btn.is_visible(timeout=timeout):
                    btn.click(force=True)
                    self.page.wait_for_timeout(300)
                    # 检查弹窗是否关闭
                    popup = self.page.locator('.van-popup .van-picker:visible')
                    if popup.count() == 0:
                        return
            except Exception:
                pass
        # 如果弹窗还在，用 touch 事件
        self.page.evaluate("""() => {
            const btn = document.querySelector('.van-picker__confirm');
            if (btn) {
                btn.dispatchEvent(new TouchEvent('touchstart', {bubbles: true}));
                btn.dispatchEvent(new TouchEvent('touchend', {bubbles: true}));
            }
            // 备选：查找确认按钮
            const confirmBtn = document.querySelector('button');
            document.querySelectorAll('button').forEach(b => {
                if (b.textContent.trim() === '确认') {
                    b.dispatchEvent(new TouchEvent('touchstart', {bubbles: true}));
                    b.dispatchEvent(new TouchEvent('touchend', {bubbles: true}));
                }
            });
        }""")
        self.page.wait_for_timeout(500)
        # 确保弹窗关闭
        self.page.evaluate("""() => {
            document.querySelectorAll('.van-popup').forEach(p => {
                if (p.querySelector('.van-picker')) p.style.display = 'none';
            });
            document.querySelectorAll('.van-overlay').forEach(o => o.style.display = 'none');
        }""")
