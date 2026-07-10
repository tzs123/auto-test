"""调试首页提交按钮：检查点击后为什么没有跳转到 /result"""
from playwright.sync_api import sync_playwright
import time

def debug():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 375, "height": 812},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()
        
        # 打开首页
        page.goto("http://172.16.0.88:9527/home?channelId=JDYFWH&productId=JDYPRD01", timeout=30000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        print(f"[1] 首页URL: {page.url}")
        
        # 输入手机号
        page.locator('input[name="phone"]').fill("19514012290")
        print(f"[2] 手机号已输入")
        
        # 点击发送验证码
        page.locator('button.form-container-send-btn').click()
        page.wait_for_timeout(1000)
        print(f"[3] 验证码已发送")
        
        # 输入验证码
        page.locator('input[name="password"]').fill("111111")
        print(f"[4] 验证码已输入")
        
        # 输入车牌号 (touch 事件)
        page.locator('.car-input-item').first.click(force=True)
        page.wait_for_timeout(1000)
        
        # 输入"浙"
        page.evaluate("""() => {
            const btns = document.querySelectorAll('.car-keyboard-grids-btn');
            for (const btn of btns) {
                if (btn.textContent.trim() === '浙' && btn.offsetParent !== null) {
                    btn.dispatchEvent(new TouchEvent('touchstart', {bubbles: true}));
                    btn.dispatchEvent(new TouchEvent('touchend', {bubbles: true}));
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(300)
        
        # 切换到英文模式
        page.evaluate("""() => {
            const changeBtn = document.querySelector('.car-keyboard-change');
            if (changeBtn) {
                const zhSpan = changeBtn.querySelector('.zh');
                if (zhSpan && zhSpan.classList.contains('active')) {
                    changeBtn.dispatchEvent(new TouchEvent('touchstart', {bubbles: true}));
                    changeBtn.dispatchEvent(new TouchEvent('touchend', {bubbles: true}));
                }
            }
        }""")
        page.wait_for_timeout(500)
        
        # 输入 A24D3M
        for ch in ['A', '2', '4', 'D', '3', 'M']:
            page.evaluate(f"""() => {{
                const btns = document.querySelectorAll('.car-keyboard-grids-btn');
                for (const btn of btns) {{
                    if (btn.textContent.trim() === '{ch}' && btn.offsetParent !== null) {{
                        btn.dispatchEvent(new TouchEvent('touchstart', {{bubbles: true}}));
                        btn.dispatchEvent(new TouchEvent('touchend', {{bubbles: true}}));
                        return true;
                    }}
                }}
                return false;
            }}""")
            page.wait_for_timeout(300)
        
        # 点击确认
        page.evaluate("""() => {
            const el = document.querySelector('.car-tooltips-submit');
            if (el) {
                el.dispatchEvent(new TouchEvent('touchstart', {bubbles: true}));
                el.dispatchEvent(new TouchEvent('touchend', {bubbles: true}));
            }
        }""")
        page.wait_for_timeout(500)
        
        # 关闭弹窗
        page.evaluate("""() => {
            document.querySelectorAll('.van-popup').forEach(p => {
                if (p.querySelector('.car-keyboard')) p.style.display = 'none';
            });
            document.querySelectorAll('.van-overlay').forEach(o => o.style.display = 'none');
        }""")
        page.wait_for_timeout(500)
        
        # 获取车牌号
        car_text = page.evaluate("""() => {
            const items = document.querySelectorAll('.car-input-item');
            const texts = [];
            items.forEach(item => {
                const span = item.querySelector('span');
                if (span) {
                    const t = span.textContent.trim();
                    if (t && t !== '新能源' && t !== '_') texts.push(t);
                }
            });
            return texts.join('');
        }""")
        print(f"[5] 车牌号: '{car_text}'")
        
        # 勾选同意
        checkbox = page.locator('.van-checkbox.read-agree-box')
        if checkbox.get_attribute('aria-checked') == 'false':
            checkbox.click()
        print(f"[6] 已勾选同意")
        
        # 检查提交按钮
        submit_btn = page.locator('button:has-text("同意并申请")')
        print(f"[7] 提交按钮可见: {submit_btn.is_visible()}")
        print(f"[7] 提交按钮可用: {submit_btn.is_enabled()}")
        
        # 监听网络请求
        api_calls = []
        def on_request(request):
            if 'api' in request.url or 'apply' in request.url or 'loan' in request.url:
                api_calls.append(f"{request.method} {request.url}")
        page.on("request", on_request)
        
        api_responses = []
        def on_response(response):
            if 'api' in response.url or 'apply' in response.url or 'loan' in response.url:
                try:
                    body = response.text()
                    api_responses.append(f"{response.status} {response.url} -> {body[:200]}")
                except:
                    api_responses.append(f"{response.status} {response.url}")
        page.on("response", on_response)
        
        # 点击提交 - 方式1: Playwright click
        print(f"\n[8] 尝试 Playwright click(force=True)...")
        submit_btn.click(force=True)
        page.wait_for_timeout(3000)
        
        print(f"[9] 提交后URL: {page.url}")
        print(f"[9] API请求: {api_calls}")
        print(f"[9] API响应: {api_responses}")
        
        # 检查错误提示
        error_info = page.evaluate("""() => {
            const toast = document.querySelector('.van-toast');
            const notify = document.querySelector('.van-notify');
            const errors = document.querySelectorAll('.van-field__error-message');
            const result = {toast: '', notify: '', errors: []};
            if (toast) result.toast = toast.textContent.trim();
            if (notify) result.notify = notify.textContent.trim();
            errors.forEach(e => {
                const style = window.getComputedStyle(e);
                if (style.display !== 'none' && style.visibility !== 'hidden' && e.textContent.trim()) {
                    result.errors.push(e.textContent.trim());
                }
            });
            return result;
        }""")
        print(f"[9] 错误信息: {error_info}")
        
        # 检查页面内容
        page_text = page.inner_text('body', timeout=5000)
        print(f"[9] 页面文本(前200字): {page_text[:200]}")
        
        # 如果还在首页，尝试 touch 事件点击
        if "/result" not in page.url:
            print(f"\n[10] Playwright click无效，尝试 touch 事件...")
            api_calls.clear()
            api_responses.clear()
            
            page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.includes('同意并申请')) {
                        btn.dispatchEvent(new TouchEvent('touchstart', {bubbles: true}));
                        btn.dispatchEvent(new TouchEvent('touchend', {bubbles: true}));
                        return;
                    }
                }
            }""")
            page.wait_for_timeout(3000)
            
            print(f"[11] touch后URL: {page.url}")
            print(f"[11] API请求: {api_calls}")
            print(f"[11] API响应: {api_responses}")
            
            error_info2 = page.evaluate("""() => {
                const toast = document.querySelector('.van-toast');
                const notify = document.querySelector('.van-notify');
                const errors = document.querySelectorAll('.van-field__error-message');
                const result = {toast: '', notify: '', errors: []};
                if (toast) result.toast = toast.textContent.trim();
                if (notify) result.notify = notify.textContent.trim();
                errors.forEach(e => {
                    const style = window.getComputedStyle(e);
                    if (style.display !== 'none' && style.visibility !== 'hidden' && e.textContent.trim()) {
                        result.errors.push(e.textContent.trim());
                    }
                });
                return result;
            }""")
            print(f"[11] 错误信息: {error_info2}")
        
        # 如果还是没跳转，检查按钮的事件监听器
        if "/result" not in page.url:
            print(f"\n[12] 两种方式都无效，检查按钮事件绑定...")
            btn_info = page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.textContent.includes('同意并申请')) {
                        return {
                            tagName: btn.tagName,
                            className: btn.className,
                            type: btn.type,
                            disabled: btn.disabled,
                            outerHTML: btn.outerHTML.substring(0, 300),
                            parentHTML: btn.parentElement ? btn.parentElement.outerHTML.substring(0, 300) : '',
                            // 检查 Vue 组件信息
                            hasVueApp: !!btn.__vue_app__,
                            hasVnode: !!btn._vnode,
                            // 检查父元素 Vue 信息
                            parentVueApp: btn.parentElement ? !!btn.parentElement.__vue_app__ : false,
                        };
                    }
                }
                return null;
            }""")
            print(f"[12] 按钮信息: {btn_info}")
        
        # 等待观察
        print(f"\n等待5秒观察...")
        page.wait_for_timeout(5000)
        print(f"最终URL: {page.url}")
        
        browser.close()

if __name__ == "__main__":
    debug()
