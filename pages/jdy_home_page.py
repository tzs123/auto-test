import allure
from playwright.sync_api import Page
from pages.base_page import BasePage


class JdyHomePage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)

    @allure.step("打开首页")
    def goto(self, channel_id="JDYFWH", product_id="JDYPRD01"):
        self.page.goto(
            f"{self.base_url}/home?channelId={channel_id}&productId={product_id}",
            timeout=30000
        )
        self.page.wait_for_load_state("networkidle")
        self.page.evaluate("localStorage.clear()")
        self.page.wait_for_timeout(1000)

    @allure.step("输入手机号")
    def input_phone(self, phone: str):
        self.page.locator('input[name="phone"]').fill(phone)

    @allure.step("点击发送验证码")
    def click_send_captcha(self):
        self.page.locator('button.form-container-send-btn').click()
        self.page.wait_for_timeout(1000)

    @allure.step("输入验证码")
    def input_captcha(self, captcha: str):
        self.page.locator('input[name="password"]').fill(captcha)

    @allure.step("输入车牌号: {plate}")
    def input_car_number(self, plate: str):
        """通过虚拟键盘输入车牌号：移动端H5需要用touchstart/touchend事件模拟点击"""
        chars = list(plate)
        if not chars:
            return

        # 点击第1个格子触发虚拟键盘弹出
        self.page.locator('.car-input-item').first.click(force=True)
        self.page.wait_for_timeout(1000)

        # 确认虚拟键盘已弹出
        keyboard = self.page.locator('.car-keyboard')
        if keyboard.count() == 0:
            allure.attach("虚拟键盘未弹出", name="车牌号输入失败")
            return

        # 第1个字符是省份简称，在中文模式下直接输入
        self._tap_car_key(chars[0])
        self.page.wait_for_timeout(300)

        # 切换到英文/数字模式
        self._switch_car_keyboard_to_en()
        self.page.wait_for_timeout(500)

        # 输入剩余字符
        for char in chars[1:]:
            self._tap_car_key(char)
            self.page.wait_for_timeout(300)

        # 点击确认按钮（用touch事件）
        self._tap_element('.car-tooltips-submit')
        self.page.wait_for_timeout(500)

        # 确保遮罩层已关闭
        self.page.evaluate("""() => {
            document.querySelectorAll('.van-popup').forEach(p => {
                if (p.querySelector('.car-keyboard')) p.style.display = 'none';
            });
            document.querySelectorAll('.van-overlay').forEach(o => o.style.display = 'none');
        }""")
        self.page.wait_for_timeout(300)

    def _tap_car_key(self, char: str):
        """用touchstart/touchend事件模拟点击虚拟键盘按键（移动端H5绑定的是touch事件）"""
        self.page.evaluate(f"""() => {{
            const btns = document.querySelectorAll('.car-keyboard-grids-btn');
            for (const btn of btns) {{
                if (btn.textContent.trim() === '{char}' && btn.offsetParent !== null) {{
                    btn.dispatchEvent(new TouchEvent('touchstart', {{bubbles: true}}));
                    btn.dispatchEvent(new TouchEvent('touchend', {{bubbles: true}}));
                    return true;
                }}
            }}
            return false;
        }}""")

    def _tap_element(self, selector: str):
        """用touchstart/touchend事件模拟点击指定元素"""
        self.page.evaluate(f"""() => {{
            const el = document.querySelector('{selector}');
            if (el) {{
                el.dispatchEvent(new TouchEvent('touchstart', {{bubbles: true}}));
                el.dispatchEvent(new TouchEvent('touchend', {{bubbles: true}}));
                return true;
            }}
            return false;
        }}""")

    def _switch_car_keyboard_to_en(self):
        """切换虚拟键盘到英文/数字模式"""
        self.page.evaluate("""() => {
            const changeBtn = document.querySelector('.car-keyboard-change');
            if (changeBtn) {
                const zhSpan = changeBtn.querySelector('.zh');
                if (zhSpan && zhSpan.classList.contains('active')) {
                    changeBtn.dispatchEvent(new TouchEvent('touchstart', {bubbles: true}));
                    changeBtn.dispatchEvent(new TouchEvent('touchend', {bubbles: true}));
                }
            }
        }""")
        self.page.wait_for_timeout(500)

    @allure.step("勾选同意协议")
    def check_agree(self):
        checkbox = self.page.locator('.van-checkbox.read-agree-box')
        if checkbox.get_attribute('aria-checked') == 'false':
            checkbox.click()

    @allure.step("点击同意并申请")
    def click_submit(self):
        # 首页提交按钮使用 Playwright click（该页面绑定的是 click 事件）
        self.page.locator('button:has-text("同意并申请")').click(force=True)
        self.page.wait_for_timeout(2000)

    def get_page_title_text(self) -> str:
        try:
            return self.page.locator('.form-box-title text').first.inner_text(timeout=5000)
        except Exception:
            return self.page.locator('.form-box-title').inner_text(timeout=5000)

    def get_send_btn_text(self) -> str:
        return self.page.locator('button.form-container-send-btn').inner_text(timeout=5000)

    def is_apply_btn_visible(self) -> bool:
        return self.page.locator('button:has-text("同意并申请")').is_visible()

    def get_apply_id_from_storage(self) -> str:
        return self.page.evaluate("localStorage.getItem('applyId') || ''")

    @allure.step("检查页面是否包含指定文本")
    def has_text(self, text: str) -> bool:
        try:
            return text in self.page.inner_text('body', timeout=5000)
        except Exception:
            return False

    @allure.step("获取手机号输入框的值")
    def get_phone_value(self) -> str:
        return self.page.locator('input[name="phone"]').input_value()

    @allure.step("获取车牌号显示文本")
    def get_car_number_text(self) -> str:
        try:
            result = self.page.evaluate("""
                () => {
                    const texts = [];
                    const items = document.querySelectorAll('.car-input-item');
                    items.forEach(item => {
                        const span = item.querySelector('span');
                        const text = item.querySelector('text');
                        const val = item.querySelector('.van-cell__value, .van-field__control');
                        const content = (span || text || val);
                        if (content) {
                            const t = content.textContent || content.value || '';
                            if (t.trim() && t.trim() !== '新能源' && t.trim() !== '_') {
                                texts.push(t.trim());
                            }
                        }
                    });
                    if (texts.length === 0) {
                        const container = document.querySelector('[class*="car-input"], [class*="car-input"]');
                        if (container) {
                            const allSpans = container.querySelectorAll('span');
                            allSpans.forEach(s => {
                                const t = s.textContent.trim();
                                if (t && t !== '新能源') texts.push(t);
                            });
                        }
                    }
                    return texts.join('');
                }
            """)
            return result
        except Exception:
            return ""

    @allure.step("检查是否仍在首页")
    def is_still_on_home_page(self) -> bool:
        return "/home" in self.page.url or self.page.url.rstrip('/').endswith(':9527')

    def screenshot(self) -> bytes:
        return self.page.screenshot()
