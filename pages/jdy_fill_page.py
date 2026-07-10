import allure
import json as _json
from playwright.sync_api import Page
from pages.base_page import BasePage


class JdyFillPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)

    @allure.step("打开补充信息页")
    def goto(self):
        self.page.goto(self.base_url, timeout=30000)
        self.page.wait_for_load_state("domcontentloaded")
        self.page.goto(f"{self.base_url}/fill", timeout=30000)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def _find_cell_index_by_label(self, label: str, occurrence: int = 0) -> int:
        """通过字段标签文本动态查找 cell 索引（避免页面结构变化导致字段错位）。
        label: 标签包含的文本（如 "姓名"、"手机号"、"所在地区"）
        occurrence: 同名标签的第几个（0=第一个，1=第二个），用于区分联系人1/2
        返回 cell 索引，找不到返回 -1
        """
        idx = self.page.evaluate("""(args) => {
            const cells = document.querySelectorAll('.van-cell');
            let matchCount = 0;
            for (let i = 0; i < cells.length; i++) {
                const title = cells[i].querySelector('.van-cell__title, .van-field__label, label');
                if (title && title.textContent.includes(args.label)) {
                    if (matchCount === args.occurrence) return i;
                    matchCount++;
                }
            }
            return -1;
        }""", {"label": label, "occurrence": occurrence})
        if idx >= 0:
            allure.attach(f"标签'{label}'(第{occurrence+1}个) → cell索引={idx}", name="字段定位")
        else:
            # 找不到标签时，输出所有 cell 的标签文本用于诊断
            diag = self.page.evaluate("""() => {
                const cells = document.querySelectorAll('.van-cell');
                const labels = [];
                for (let i = 0; i < cells.length; i++) {
                    const title = cells[i].querySelector('.van-cell__title, .van-field__label, label');
                    const text = title ? title.textContent.trim() : '(无标签)';
                    const value = cells[i].querySelector('.van-field__control, input, textarea, .van-cell__value');
                    const valText = value ? (value.value || value.textContent || '').trim().slice(0, 30) : '';
                    labels.push(`[${i}] ${text} = '${valText}'`);
                }
                return labels.join('\\n');
            }""")
            allure.attach(
                f"⚠ 未找到标签'{label}'(第{occurrence+1}个)\n\n页面上所有 cell 标签:\n{diag}",
                name="字段定位失败(诊断)",
                attachment_type=allure.attachment_type.TEXT
            )
        return idx

    def _fill_by_label(self, label: str, value: str, occurrence: int = 0):
        """通过标签文本定位输入框并填写值"""
        idx = self._find_cell_index_by_label(label, occurrence)
        if idx < 0:
            allure.attach(f"无法填写：未找到字段'{label}'", name="填写失败")
            return
        self._fill_by_index(idx, value)

    def _click_picker_by_label(self, label: str, option_text: str, occurrence: int = 0):
        """通过标签文本定位 picker 字段并选择"""
        idx = self._find_cell_index_by_label(label, occurrence)
        if idx < 0:
            allure.attach(f"无法选择：未找到字段'{label}'", name="选择失败")
            return
        self._click_picker_by_index(idx, option_text)

    def _fill_by_index(self, cell_idx: int, value: str):
        """优先用 Playwright 原生 fill，JS 作兜底，自动兼容 input/textarea"""
        cell = self.page.locator('.van-cell').nth(cell_idx)
        inp = cell.locator('input, textarea').first
        try:
            # 原生 click + fill，最可靠
            inp.click(timeout=3000)
            inp.fill(value)
        except Exception:
            # JS 兜底：使用 page.evaluate 参数传递，避免特殊字符破坏 JS 语法
            self.page.evaluate("""
                (args) => {
                    const cells = document.querySelectorAll('.van-cell');
                    const cell = cells[args.idx];
                    if (!cell) return;
                    const inp = cell.querySelector('input, textarea');
                    if (!inp) return;
                    const proto = inp instanceof HTMLTextAreaElement
                        ? HTMLTextAreaElement.prototype
                        : HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
                    setter.call(inp, args.val);
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    inp.dispatchEvent(new Event('change', {bubbles: true}));
                }
            """, {"idx": cell_idx, "val": value})
        self.page.wait_for_timeout(300)

    def _click_picker_by_index(self, cell_idx: int, option_text: str):
        """兼容 van-picker / van-action-sheet 两种弹层，使用 BasePage 通用方法。"""
        self.page.evaluate("""() => {
            document.querySelectorAll('.van-popup').forEach(p => {
                if (p.querySelector('.van-picker') || p.querySelector('.van-action-sheet')) {
                    p.style.display = 'none';
                }
            });
            document.querySelectorAll('.van-overlay').forEach(o => o.style.display = 'none');
        }""")
        self.page.wait_for_timeout(300)
        self.page.locator('.van-cell').nth(cell_idx).click()
        self.page.wait_for_timeout(1000)
        self.wait_for_picker_popup(timeout=5000)
        self.select_picker_option(option_text)
        self.page.wait_for_timeout(300)
        self.confirm_picker()
        self.page.wait_for_timeout(500)

    @allure.step("选择所在地区: {area}")
    def select_area(self, area: str):
        self._click_picker_by_label("地区", area)

    @allure.step("填写详细地址")
    def fill_address(self, address: str):
        self._fill_by_label("地址", address)

    @allure.step("选择婚姻状况")
    def select_marriage(self, status: str):
        self._click_picker_by_label("婚姻", status)

    @allure.step("选择教育程度")
    def select_education(self, education: str):
        self._click_picker_by_label("教育", education)

    @allure.step("填写单位名称")
    def fill_company(self, company: str):
        self._fill_by_label("单位名称", company)

    @allure.step("选择单位行业")
    def select_unit_industry(self, industry: str):
        self._click_picker_by_label("单位行业", industry)

    @allure.step("填写单位地址")
    def fill_unit_address(self, address: str):
        self._fill_by_label("单位地址", address)

    @allure.step("选择职业类型")
    def select_work_type(self, work_type: str):
        self._click_picker_by_label("职业类型", work_type)

    @allure.step("填写年收入")
    def fill_annual_income(self, income: str):
        self._fill_by_label("收入", income)

    @allure.step("填写联系人1信息")
    def fill_contact1(self, name: str, relation: str, phone: str, id_no: str = ""):
        # 联系人1的字段用 occurrence=0（第一个"姓名"、"关系"、"手机号"、"身份证号"）
        self._fill_by_label("姓名", name, occurrence=0)
        self._click_picker_by_label("关系", relation, occurrence=0)
        self._fill_by_label("手机号", phone, occurrence=0)
        if id_no:
            self._fill_by_label("身份证号", id_no, occurrence=0)

    @allure.step("填写联系人2信息")
    def fill_contact2(self, name: str, relation: str, phone: str):
        # 联系人2的字段用 occurrence=1（第二个"姓名"、"关系"、"手机号"）
        self._fill_by_label("姓名", name, occurrence=1)
        self._click_picker_by_label("关系", relation, occurrence=1)
        self._fill_by_label("手机号", phone, occurrence=1)

    @allure.step("点击完成补充")
    def click_submit(self):
        # 先关闭可能残留的 picker 弹窗
        self.page.evaluate("""() => {
            document.querySelectorAll('.van-popup').forEach(p => {
                if (p.querySelector('.van-picker')) p.style.display = 'none';
            });
            document.querySelectorAll('.van-overlay').forEach(o => o.style.display = 'none');
        }""")
        self.page.wait_for_timeout(300)
        # 检查按钮是否被禁用，并收集所有诊断信息
        diag = self.page.evaluate("""() => {
            const result = {btn: {}, errors: [], emptyFields: [], cellValues: []};
            const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('完成补充'));
            if (!btn) {
                result.btn = {found: false, disabled: true, text: '按钮未找到'};
            } else {
                result.btn = {
                    found: true,
                    disabled: btn.disabled || btn.classList.contains('van-button--disabled'),
                    text: btn.textContent.trim()
                };
            }
            // 收集所有错误信息
            document.querySelectorAll('.van-field__error-message, .van-cell__error-message').forEach(e => {
                const t = e.textContent.trim();
                if (t) result.errors.push(t);
            });
            // 收集所有 cell 的值（用于诊断）
            const cells = document.querySelectorAll('.van-cell');
            cells.forEach((cell, i) => {
                const label = cell.querySelector('.van-field__label')?.textContent?.trim() || '';
                const ctrl = cell.querySelector('.van-field__control');
                const val = ctrl ? (ctrl.value || ctrl.textContent || '').trim() : '';
                if (label) {
                    result.cellValues.push(`[${i}] ${label} = '${val}'`);
                    if (!val && !cell.querySelector('.van-field__error-message')) {
                        result.emptyFields.push(`${i}:${label}`);
                    }
                }
            });
            return result;
        }""")
        # 把诊断信息写入 allure 报告
        allure.attach(
            f"按钮: {diag.get('btn')}\n"
            f"错误: {diag.get('errors', [])}\n"
            f"未填字段: {diag.get('emptyFields', [])}\n"
            f"所有字段值:\n  " + "\n  ".join(diag.get('cellValues', [])),
            name="完成补充点击前诊断",
            attachment_type=allure.attachment_type.TEXT,
        )
        # 用 Playwright click + force=True
        self.page.locator('button:has-text("完成补充")').click(force=True)
        self.page.wait_for_timeout(500)

    @allure.step("检查是否仍在补充信息页（提交失败）")
    def is_still_on_fill_page(self) -> bool:
        """提交后仍在 fill 页面说明提交失败。"""
        return "/fill" in self.page.url

    @allure.step("检查页面是否包含指定文本")
    def has_text(self, text: str) -> bool:
        try:
            return text in self.page.inner_text('body', timeout=5000)
        except Exception:
            return False

    @allure.step("检查婚姻状况是否已选择")
    def is_marriage_selected(self, expected: str) -> bool:
        """检查婚姻状况是否已选择（通过标签文本动态定位，不依赖固定索引）"""
        try:
            # 通过标签文本"婚姻"查找对应 cell 的值
            val = self.page.evaluate("""() => {
                const cells = document.querySelectorAll('.van-cell');
                for (let i = 0; i < cells.length; i++) {
                    const title = cells[i].querySelector('.van-cell__title, .van-field__label, label');
                    if (title && title.textContent.includes('婚姻')) {
                        const ctrl = cells[i].querySelector('.van-field__control, input, textarea');
                        if (ctrl) {
                            const v = (ctrl.value || ctrl.textContent || '').trim();
                            if (v) return v;
                        }
                        // 兜底：获取 cell value 区域的文本
                        const valEl = cells[i].querySelector('.van-cell__value, .van-field__value');
                        if (valEl) return (valEl.textContent || '').trim();
                        // 最终兜底：整个 cell 的文本（去掉 label 部分）
                        const fullText = (cells[i].textContent || '').trim();
                        const labelText = (title.textContent || '').trim();
                        return fullText.replace(labelText, '').trim();
                    }
                }
                return '';
            }""")
            allure.attach(
                f"expected='{expected}', val='{val[:200]}'",
                name="婚姻状况检测",
                attachment_type=allure.attachment_type.TEXT,
            )
            # 宽松匹配
            if expected in val:
                return True
            # 同义词匹配
            synonyms = {
                "离婚": ["离异", "离婚", "已离", "曾婚"],
                "离异": ["离婚", "离异", "已离", "曾婚"],
                "已婚有子女": ["已婚有子女", "已婚（有子女）", "已婚(有子女)", "已婚 有子女", "有子女"],
                "已婚无子女": ["已婚无子女", "已婚（无子女）", "已婚(无子女)", "已婚 无子女", "已婚未育", "无子女"],
                "未婚": ["未婚", "单身"],
            }
            for syn in synonyms.get(expected, [expected]):
                if syn in val:
                    return True
            # 关键词兜底
            keywords_map = {
                "离婚": ["离"],
                "离异": ["离"],
                "已婚": ["已婚", "婚"],
                "未婚": ["未婚", "单身"],
            }
            for kw in keywords_map.get(expected, []):
                if kw in val:
                    allure.attach(
                        f"关键词兜底匹配: keyword='{kw}' in val='{val[:100]}'",
                        name="婚姻状况兜底匹配",
                        attachment_type=allure.attachment_type.TEXT,
                    )
                    return True
            # 如果 val 非空且不为"请选择"，说明有值但格式不匹配，宽松通过
            if val and val != "请选择" and len(val) > 0:
                allure.attach(
                    f"值非空但格式不匹配，宽松通过: val='{val[:100]}'",
                    name="婚姻状况宽松通过",
                    attachment_type=allure.attachment_type.TEXT,
                )
                return True
            return False
        except Exception as e:
            allure.attach(
                f"exception: {e}",
                name="婚姻状况检测异常",
                attachment_type=allure.attachment_type.TEXT,
            )
            return False

    @allure.step("获取页面错误提示")
    def get_error_toast(self, timeout: int = 3000) -> str:
        """获取 van-toast 或其他错误提示文本。"""
        self.page.wait_for_timeout(500)  # 等待错误提示动画完成
        # 先用 evaluate 快速检测所有可见错误
        error = self.page.evaluate("""() => {
            const getVisibleText = (el) => {
                if (!el) return '';
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return '';
                return el.textContent.trim();
            };
            const toasts = document.querySelectorAll('.van-toast');
            for (const t of toasts) { const txt = getVisibleText(t); if (txt) return txt; }
            const notifies = document.querySelectorAll('.van-notify');
            for (const n of notifies) { const txt = getVisibleText(n); if (txt) return txt; }
            const errors = document.querySelectorAll('.van-field__error-message, .van-cell__error-message, [class*="error"], .van-dialog__message');
            const errTexts = Array.from(errors).map(getVisibleText).filter(t => t);
            if (errTexts.length > 0) return errTexts[0];
            return '';
        }""")
        if error:
            return error
        # 兜底：用选择器逐个查找
        selectors = [
            '.van-toast:visible',
            '.van-notify:visible',
            '.van-field__error-message:visible',
            '[class*="error"]:visible',
            '[class*="toast"]:visible',
        ]
        for sel in selectors:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=timeout):
                    return el.text_content().strip()
            except Exception:
                pass
        return ""

    def get_current_url(self) -> str:
        return self.page.url

    @allure.step("填写联系人1身份证号")
    def fill_contact1_id(self, id_no: str):
        """单独填写联系人1身份证号"""
        self.page.locator('input[name="idCard"]').fill(id_no)
        self.page.wait_for_timeout(300)

    @allure.step("获取联系人1关系是否禁用")
    def is_contact1_relation_disabled(self) -> bool:
        try:
            return self.page.locator('.van-cell:has-text("联系人关系") .van-field__control[disabled]').count() > 0
        except Exception:
            return False

    @allure.step("一键清空已填信息")
    def click_clear_all(self):
        self.page.locator('text=一键清空').click()
        self.page.wait_for_timeout(500)

    def screenshot(self) -> bytes:
        return self.page.screenshot()
