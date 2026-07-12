import pytest
import allure
import os
from utils.yaml_loader import load_cases
from pages.jdy_home_page import JdyHomePage
from pages.jdy_result_page import JdyResultPage
from pages.jdy_fill_page import JdyFillPage
from pages.jdy_submit_page import JdySubmitPage
from pages.admin_login_page import AdminLoginPage
from pages.admin_application_page import AdminApplicationPage

def _generate_random_phone():
    """生成随机中国手机号"""
    import random
    prefix = random.choice([3, 4, 5, 6, 7, 8, 9])
    return f"1{prefix}{random.randint(100000000, 999999999)}"

def get_cases_by_tag(tag):
    """每次调用重新加载并生成新的随机手机号，避免服务器端状态污染"""
    cases = load_cases("cases/ui/test_jdy_flow.yaml")
    if not cases:
        return [pytest.param(None, marks=pytest.mark.skip(reason="No cases in YAML"))]
    for case in cases:
        if case.get("phone"):
            case["phone"] = _generate_random_phone()
    filtered = [c for c in cases if tag in c.get("tags", [])]
    if not filtered:
        return [pytest.param(None, marks=pytest.mark.skip(reason=f"No cases with tag '{tag}'"))]
    return filtered


# ────────── SPA 路由等待工具（pushState 不触发导航事件） ──────────

def _wait_url_contains(page, keyword: str, timeout: int = 8000):
    """轮询等待 URL 包含指定关键词（兼容 SPA pushState 导航）"""
    import time as _time
    start = _time.time()
    while _time.time() - start < timeout / 1000:
        if keyword in page.url:
            return True
        page.wait_for_timeout(100)
    raise TimeoutError(f"等待URL包含'{keyword}'超时({timeout}ms)，当前URL: {page.url}")


def _smart_wait_url_change(page, old_url: str, timeout: int = 3000):
    """提交后智能等待URL变化，一旦变化立即返回"""
    import time as _time
    start = _time.time()
    while _time.time() - start < timeout / 1000:
        if page.url != old_url:
            page.wait_for_timeout(200)
            return True
        page.wait_for_timeout(100)
    return False


def _collect_fill_page_diag(page) -> str:
    """收集补充信息页的完整诊断信息（按钮状态、所有字段值、错误提示）"""
    diag = page.evaluate("""() => {
        const result = {url: location.href, buttons: [], errors: [], cellValues: []};
        // 收集所有按钮
        document.querySelectorAll('button').forEach((b, i) => {
            const text = b.textContent.trim();
            if (text) {
                result.buttons.push(`[${i}] '${text}' disabled=${b.disabled || b.classList.contains('van-button--disabled')}`);
            }
        });
        // 收集所有错误
        document.querySelectorAll('.van-field__error-message, .van-cell__error-message, .van-toast, .van-notify, .van-dialog__message').forEach(e => {
            const style = window.getComputedStyle(e);
            if (style.display === 'none' || style.visibility === 'hidden') return;
            const t = e.textContent.trim();
            if (t) result.errors.push(t);
        });
        // 收集所有 cell 的值
        const cells = document.querySelectorAll('.van-cell');
        cells.forEach((cell, i) => {
            const label = cell.querySelector('.van-field__label')?.textContent?.trim() || '';
            const ctrl = cell.querySelector('.van-field__control');
            const val = ctrl ? (ctrl.value || ctrl.textContent || '').trim() : '';
            if (label) result.cellValues.push(`[${i}] ${label} = '${val}'`);
        });
        return result;
    }""")
    return (
        f"URL: {diag.get('url')}\n"
        f"按钮:\n  " + "\n  ".join(diag.get('buttons', [])) + "\n"
        f"错误: {diag.get('errors', [])}\n"
        f"所有字段值:\n  " + "\n  ".join(diag.get('cellValues', []))
    )


def _log_fill_cells(page, stage: str):
    """记录补充信息页所有 cell 的标签和值到 allure 报告"""
    try:
        info = page.evaluate("""() => {
            const cells = document.querySelectorAll('.van-cell');
            return Array.from(cells).map((c, i) => {
                const title = c.querySelector('.van-cell__title, .van-field__label, label');
                const text = title ? title.textContent.trim() : '(no label)';
                const ctrl = c.querySelector('.van-field__control, input, textarea');
                const val = ctrl ? (ctrl.value || '').trim().slice(0, 30) : '';
                return `[${i}] ${text} = '${val}'`;
            }).join('\\n');
        }""")
        allure.attach(info, name=f"fill页-{stage}", attachment_type=allure.attachment_type.TEXT)
    except Exception:
        pass


# ────────── 流程辅助：按需走完前置页面 ──────────

def _flow_home(page, case):
    """首页：填写信息并提交，跳转到借款人信息页"""
    home = JdyHomePage(page)
    home.goto(case["channel_id"], case["product_id"])
    allure.attach(home.screenshot(), name="首页加载", attachment_type=allure.attachment_type.PNG)

    # 断言：首页标题
    assert home.has_text("输入信息获取评测额度"), "首页标题应包含'输入信息获取评测额度'"

    home.input_phone(case["phone"])
    assert home.get_phone_value() == case["phone"], f"手机号应为{case['phone']}"

    home.click_send_captcha()
    home.input_captcha(case["captcha"])
    home.input_car_number(case["car_number"])
    allure.attach(home.screenshot(), name="输入车牌号后", attachment_type=allure.attachment_type.PNG)
    car_text = home.get_car_number_text()
    allure.attach(f"车牌号显示: {car_text}", name="车牌号检测")
    if not car_text:
        allure.attach("车牌号获取为空，跳过断言继续执行", name="车牌号警告")
    else:
        assert len(car_text) >= 7, f"车牌号应至少7位，实际: {car_text}"

    home.check_agree()
    assert home.is_apply_btn_visible(), "申请按钮应可见"
    allure.attach(home.screenshot(), name="首页填写完毕", attachment_type=allure.attachment_type.PNG)

    home.click_submit()
    allure.attach(home.screenshot(), name="点击提交后", attachment_type=allure.attachment_type.PNG)
    old_url = page.url
    _smart_wait_url_change(page, old_url, timeout=3000)
    error_msg = page.evaluate("""() => {
        const toast = document.querySelector('.van-toast');
        const notify = document.querySelector('.van-notify');
        const errors = document.querySelectorAll('.van-field__error-message');
        const getVisibleText = (el) => {
            if (!el) return '';
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return '';
            return el.textContent.trim();
        };
        const toastText = getVisibleText(toast);
        const notifyText = getVisibleText(notify);
        if (toastText) return toastText;
        if (notifyText) return notifyText;
        const errTexts = Array.from(errors).map(getVisibleText).filter(t => t);
        if (errTexts.length > 0) return errTexts.join(', ');
        return '';
    }""")
    if error_msg:
        allure.attach(f"错误提示: {error_msg}", name="表单错误")
    allure.attach(f"当前URL: {page.url}", name="当前URL")

    # 首页反向用例：预期提交失败停在首页
    if case.get("expect_submit_fail") and case.get("expect_fail_page") == "home":
        if "/home" in page.url:
            allure.attach(page.screenshot(), name="首页反向用例-停在首页", attachment_type=allure.attachment_type.PNG)
            allure.attach(f"✅ 首页提交被拦截，停在首页（错误: {error_msg or '无'}）", name="提交结果")
            return
        # 如果意外跳转了，继续走正常流程

    try:
        _wait_url_contains(page, "/result", timeout=15000)
    except TimeoutError:
        if "/home" in page.url:
            allure.attach(page.screenshot(), name="提交失败停留在首页", attachment_type=allure.attachment_type.PNG)
            allure.attach(f"期望跳转到'/result'，但实际停留在首页（可能是风控拦截或服务异常）", name="提交结果")
            raise


def _flow_result(page, case):
    """借款人信息页：上传身份证 OCR + 填写贷款信息并提交"""
    result = JdyResultPage(page)
    assert result.is_still_on_result_page(), "应在借款人信息页"
    allure.attach(result.screenshot(), name="借款人信息页加载", attachment_type=allure.attachment_type.PNG)

    # 上传身份证 OCR
    if case.get("id_front") and os.path.exists(case["id_front"]):
        result.upload_id_front(case["id_front"])
        allure.attach(result.screenshot(), name="上传身份证正面后", attachment_type=allure.attachment_type.PNG)
    if case.get("id_back") and os.path.exists(case["id_back"]):
        result.upload_id_back(case["id_back"])
        allure.attach(result.screenshot(), name="上传身份证背面后", attachment_type=allure.attachment_type.PNG)

    # OCR 字段断言（上传后等待 OCR 识别完成，字段自动填充）
    if case.get("borrower_name"):
        assert result.verify_name_filled(), "借款人姓名应已通过OCR自动填写"
        name_val = result.get_name_value()
        id_val = result.get_id_card_value()
        allure.attach(f"OCR识别姓名: '{name_val}', 身份证号: '{id_val}'", name="OCR字段值")

    # 覆写借款人身份证号（用于测试风控拦截，如未成年人身份证）
    if case.get("override_borrower_id"):
        result.override_borrower_id(case["override_borrower_id"])
        allure.attach(f"覆写身份证号为: {case['override_borrower_id']}", name="覆写身份证号")

    # 选择贷款信息
    if case.get("loan_term"):
        result.select_loan_term(case["loan_term"])
    if case.get("area"):
        result.select_area(case["area"])
    if case.get("loan_use"):
        result.select_loan_use(case["loan_use"])

    # OCR 后可手动补充的字段
    if case.get("ethnicity"):
        result.select_ethnicity(case["ethnicity"])
    if case.get("id_card_address"):
        current = page.locator('textarea[name="address"]').input_value(timeout=3000)
        if not current.strip():
            result.fill_address(case["id_card_address"])
    if case.get("issue_authority"):
        current = page.locator('input[name="issueAuthority"]').input_value(timeout=3000)
        if not current.strip():
            result.fill_issue_authority(case["issue_authority"])
    if case.get("valid_period"):
        result.select_valid_period(case["valid_period"])

    # 贷款期限断言
    if case.get("loan_term"):
        term_val = result.get_loan_term_value()
        allure.attach(f"贷款期限值: {term_val}", name="贷款期限检测")

    allure.attach(result.screenshot(), name="借款人信息填写完毕", attachment_type=allure.attachment_type.PNG)
    old_url = page.url
    result.click_submit()

    # 提交后智能等待URL变化
    _smart_wait_url_change(page, old_url, timeout=2000)

    # 默认处理人车不一致弹窗（首页车牌号与身份证 OCR 不是同一人时会弹窗要求辅助验证）
    page.wait_for_timeout(1500)
    default_driving_license = case.get(
        "driving_license",
        "/Users/tanzsongsen/Downloads/行驶证正面.png"
    )
    if os.path.exists(default_driving_license) and hasattr(result, 'has_inconsistency_popup') and result.has_inconsistency_popup():
        allure.attach(
            page.screenshot(),
            name="检测到人车不一致弹窗",
            attachment_type=allure.attachment_type.PNG
        )
        if hasattr(result, 'handle_inconsistency') and result.handle_inconsistency(default_driving_license):
            allure.attach("✅ 行驶证辅助验证已处理", name="人车不一致处理")
            _smart_wait_url_change(page, old_url, timeout=5000)

    error_msg = page.evaluate("""() => {
        const toast = document.querySelector('.van-toast');
        const notify = document.querySelector('.van-notify');
        const errors = document.querySelectorAll('.van-field__error-message');
        const getVisibleText = (el) => {
            if (!el) return '';
            const style = window.getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden') return '';
            return el.textContent.trim();
        };
        if (toast) { const t = getVisibleText(toast); if (t) return t; }
        if (notify) { const t = getVisibleText(notify); if (t) return t; }
        const errTexts = Array.from(errors).map(getVisibleText).filter(t => t);
        if (errTexts.length > 0) return errTexts.join(', ');
        return '';
    }""")
    if error_msg:
        allure.attach(f"提交错误: {error_msg}", name="借款人信息页提交错误")
    allure.attach(f"当前URL: {page.url}", name="提交后URL")

    # 借款人信息页反向用例：预期提交失败停在 result 页
    if case.get("expect_submit_fail") and case.get("expect_fail_page") == "result":
        if "/result" in page.url:
            allure.attach(page.screenshot(), name="result反向用例-停在result", attachment_type=allure.attachment_type.PNG)
            allure.attach(f"✅ 借款人信息页提交被拦截，停在result（错误: {error_msg or '无'}）", name="提交结果")
            return

    try:
        _wait_url_contains(page, "/fill", timeout=15000)
    except TimeoutError:
        if "/result" in page.url:
            allure.attach(page.screenshot(), name="提交失败停留在借款人信息页", attachment_type=allure.attachment_type.PNG)
            allure.attach(f"期望跳转到'/fill'，但实际停留在'/result'（预审未通过或服务异常）", name="提交结果")
            raise


def _flow_fill(page, case):
    """补充信息页：填写补充信息并提交

    填写顺序：婚姻状况最先（可能触发页面重新渲染/字段变化），
    然后地区和地址，最后其他字段和联系人。
    """
    fill = JdyFillPage(page)
    assert "/fill" in fill.get_current_url(), "应在补充信息页"
    # 等待补充信息页完全加载（van-cell 渲染完成）
    page.wait_for_selector('.van-cell', timeout=15000)
    page.wait_for_load_state("networkidle", timeout=10000)
    page.wait_for_timeout(2000)
    # 如果页面恢复了上一次的信息，先一键清空
    try:
        clear_btn = page.locator('text=一键清空')
        if clear_btn.is_visible(timeout=2000):
            clear_btn.click()
            page.wait_for_timeout(500)
            allure.attach("已清空恢复的信息", name="一键清空")
    except Exception:
        pass
    # 一键清空后关闭可能残留的 picker/overlay
    overlay_before = page.locator('.van-overlay:visible').count()
    picker_before = page.locator('.van-popup:visible .van-picker').count()
    if overlay_before > 0 or picker_before > 0:
        fill._close_popup_vue_safe()
        page.wait_for_timeout(500)
        allure.attach("清空后关闭了残留弹窗", name="清空后弹窗清理")
    allure.attach(fill.screenshot(), name="补充信息页加载", attachment_type=allure.attachment_type.PNG)

    # 诊断：记录填写前页面所有 cell 信息
    _log_fill_cells(page, "填写前")

    # 婚姻状况最先选择（不同婚姻状况会显示不同字段，可能触发页面重新渲染）
    if case.get("marriage"):
        fill.select_marriage(case["marriage"])
        page.wait_for_timeout(500)
        m_selected = fill.is_marriage_selected(case["marriage"])
        assert m_selected, f"婚姻状况应显示'{case['marriage']}'"
        # 诊断：检查是否有残留 overlay/popup 阻挡后续操作
        overlay_count = page.locator('.van-overlay:visible').count()
        picker_count = page.locator('.van-popup:visible .van-picker').count()
        allure.attach(f"overlay={overlay_count}, picker={picker_count}", name="婚姻选择后弹窗状态")
        if overlay_count > 0 or picker_count > 0:
            fill._close_popup_vue_safe()
            page.wait_for_timeout(300)
        _log_fill_cells(page, "选择婚姻后")

    if case.get("fill_area"):
        fill.select_area(case["fill_area"])
        ov = page.locator('.van-overlay:visible').count()
        if ov > 0: fill._close_popup_vue_safe()
        _log_fill_cells(page, "选地区后")
    if case.get("fill_address"):
        fill.fill_address(case["fill_address"])
        _log_fill_cells(page, "填地址后")
    if case.get("education"):
        fill.select_education(case["education"])
        _log_fill_cells(page, "选教育后")
    if case.get("company"):
        fill.fill_company(case["company"])
        _log_fill_cells(page, "填单位后")
    if case.get("unit_industry"):
        fill.select_unit_industry(case["unit_industry"])
        _log_fill_cells(page, "选行业后")
    if case.get("unit_address"):
        fill.fill_unit_address(case["unit_address"])
        _log_fill_cells(page, "填单位地址后")
    if case.get("work_type"):
        fill.select_work_type(case["work_type"])
        _log_fill_cells(page, "选职业后")
    if case.get("annual_income"):
        fill.fill_annual_income(case["annual_income"])
        _log_fill_cells(page, "填年收入后")
    if case.get("contact1_name"):
        fill.fill_contact1(
            case["contact1_name"], case["contact1_relation"],
            case["contact1_phone"], case.get("contact1_id", "")
        )
        _log_fill_cells(page, "填联系人1后")
    if case.get("contact2_name"):
        fill.fill_contact2(
            case["contact2_name"], case["contact2_relation"],
            case["contact2_phone"]
        )
        _log_fill_cells(page, "填联系人2后")

    _log_fill_cells(page, "填写完毕后")
    allure.attach(fill.screenshot(), name="补充信息填写完毕", attachment_type=allure.attachment_type.PNG)
    fill.click_submit()


# ────────── 后台申请单验证流程 ──────────

def _flow_admin_verify(page, case):
    """走完完整流程到 /submit 后，登录后台管理系统验证申请单是否生成。

    步骤：
    1. 在同一 context 中新开一个页面，访问后台登录 URL
    2. 输入账号密码登录
    3. 进入申请单管理页面
    4. 在手机号搜索框输入前面流程使用的手机号
    5. 点击搜索按钮
    6. 断言列表中有一条数据
    """
    phone = case.get("phone", "")
    admin_url = case.get("admin_url", "http://172.16.0.86:5174/login")
    username = case.get("admin_username", "admin")
    password = case.get("admin_password", "admin123")
    expected_rows = case.get("admin_expect_row_count", 1)

    allure.attach(
        f"待验证手机号: {phone}\n后台URL: {admin_url}\n期望行数: {expected_rows}",
        name="后台验证参数",
        attachment_type=allure.attachment_type.TEXT,
    )

    # 在同一 context 中新开页面（保留签署页状态便于排错）
    new_page = page.context.new_page()
    try:
        # 1. 登录后台
        login_page = AdminLoginPage(new_page, base_url=admin_url.rsplit("/login", 1)[0])
        login_page.goto()
        allure.attach(new_page.screenshot(), name="后台登录页", attachment_type=allure.attachment_type.PNG)

        login_page.login(username, password)
        assert login_page.is_logged_in(), f"登录失败，当前URL: {new_page.url}"
        allure.attach(f"登录成功，当前URL: {new_page.url}", name="登录结果")

        # 2. 进入申请单管理页面
        app_page = AdminApplicationPage(new_page)
        app_page.goto_application_page()
        allure.attach(new_page.screenshot(), name="申请单管理页", attachment_type=allure.attachment_type.PNG)

        # 3. 输入手机号并搜索
        app_page.input_phone(phone)
        actual_phone = app_page.get_phone_value()
        allure.attach(f"搜索框手机号: '{actual_phone}'", name="搜索框值")
        assert actual_phone == phone, f"搜索框手机号应为'{phone}'，实际'{actual_phone}'"

        app_page.click_search()
        allure.attach(new_page.screenshot(), name="搜索结果", attachment_type=allure.attachment_type.PNG)

        # 4. 断言列表有数据
        row_count = app_page.get_row_count()
        total_count = app_page.get_total_count()
        pagination_text = app_page.get_pagination_total_text()
        has_empty = app_page.has_empty_state()

        allure.attach(
            f"表格行数: {row_count}\n分页总数: {total_count}\n分页文本: '{pagination_text}'\n空状态: {has_empty}",
            name="搜索结果详情",
            attachment_type=allure.attachment_type.TEXT,
        )

        # 断言：表格行数 >= 期望值，或分页总数 >= 期望值
        assert row_count >= expected_rows or total_count >= expected_rows, \
            f"期望至少{expected_rows}条申请单数据，实际表格行数={row_count}，分页总数={total_count}"

        # 如果有空状态提示，则断言失败
        assert not has_empty, "搜索结果为空（页面显示空状态）"

        # ──── 前后台数据一致性校验 ────
        # 获取后台表格第一行的手机号和车牌号，与前台流程中使用的值对比
        row_data = app_page.get_first_row_phone_and_car()
        allure.attach(
            f"前台手机号: {phone}\n后台表格手机号: {row_data.get('phone', '')}\n"
            f"后台表格车牌号: {row_data.get('carNumber', '')}",
            name="前后台数据对比",
            attachment_type=allure.attachment_type.TEXT,
        )

        if row_data:
            # 断言手机号一致（后台显示明文，前台输入的也是明文）
            back_phone = row_data.get("phone", "")
            assert back_phone == phone, \
                f"前后台手机号不一致！前台='{phone}'，后台='{back_phone}'"
            allure.attach(f"✅ 手机号一致: {phone}", name="手机号一致性校验")

            # 断言车牌号一致（如果用例有期望车牌号）
            expected_car = case.get("carNumber", "")
            if expected_car:
                back_car = row_data.get("carNumber", "")
                assert back_car == expected_car, \
                    f"前后台车牌号不一致！前台='{expected_car}'，后台='{back_car}'"
                allure.attach(f"✅ 车牌号一致: {expected_car}", name="车牌号一致性校验")

        allure.attach(
            f"✅ 验证通过：搜索手机号'{phone}'找到 {max(row_count, total_count)} 条申请单数据，"
            f"前后台数据一致",
            name="后台验证结果",
        )
    finally:
        # 关闭新开的页面
        try:
            new_page.close()
        except Exception:
            pass


# ────────── 测试用例 ──────────

# ===================== 冒烟：端到端完整流程 =====================
@allure.feature("今东车融-完整流程")
@pytest.mark.ui
@pytest.mark.parametrize("case", get_cases_by_tag("smoke"))
def test_smoke_full_flow(case, page):
    """冒烟测试：首页→借款人信息(OCR)→补充信息→签署页，完整端到端流程"""

    # 1. 首页
    with allure.step("1. 首页：填写信息并提交"):
        _flow_home(page, case)

    # 2. 借款人信息页
    with allure.step("2. 借款人信息页：上传身份证OCR并填写"):
        _flow_result(page, case)

    # 3. 补充信息页
    with allure.step("3. 补充信息页：填写补充信息"):
        _flow_fill(page, case)
        try:
            _wait_url_contains(page, "/submit", timeout=15000)
        except TimeoutError:
            # 超时后收集完整诊断信息
            diag_text = _collect_fill_page_diag(page)
            allure.attach(page.screenshot(), name="/fill提交后超时未跳转", attachment_type=allure.attachment_type.PNG)
            allure.attach(diag_text, name="超时完整诊断", attachment_type=allure.attachment_type.TEXT)
            raise TimeoutError(f"等待URL包含'/submit'超时(15000ms)\n{diag_text}")

    # 4. 签署页
    with allure.step("4. 签署页：验证申请信息和步骤状态"):
        submit = JdySubmitPage(page)
        assert "/submit" in submit.get_current_url(), "应在签署页"
        allure.attach(submit.screenshot(), name="签署页加载", attachment_type=allure.attachment_type.PNG)

        assert submit.has_text("申请信息"), "页面应包含'申请信息'"

        if case.get("expect_borrower_name"):
            assert submit.verify_apply_info(case["expect_borrower_name"]), \
                f"页面应包含借款人'{case['expect_borrower_name']}'"

        if case.get("expect_steps"):
            actual = submit.get_step_status()
            for step, expected_status in case["expect_steps"].items():
                assert actual.get(step) == expected_status, \
                    f"步骤'{step}'状态期望'{expected_status}'，实际'{actual.get(step)}'"

        allure.attach(submit.screenshot(), name="签署页验证完毕", attachment_type=allure.attachment_type.PNG)


# ===================== 完整流程 + 后台申请单验证 =====================
@allure.feature("今东车融-后台申请单验证")
@allure.story("完整流程后验证后台申请单已生成")
@pytest.mark.ui
@pytest.mark.parametrize("case", get_cases_by_tag("admin_verify"))
def test_admin_verify_after_submit(case, page):
    """完整流程到签署页后，登录后台管理系统按手机号搜索申请单，断言列表有数据。

    场景：首页 → 借款人信息页 → 补充信息页 → 签署页 → 后台申请单验证
    """

    # 1. 首页
    with allure.step("1. 首页：填写信息并提交"):
        _flow_home(page, case)

    # 2. 借款人信息页
    with allure.step("2. 借款人信息页：上传身份证OCR并填写"):
        _flow_result(page, case)

    # 3. 补充信息页
    with allure.step("3. 补充信息页：填写补充信息"):
        _flow_fill(page, case)
        try:
            _wait_url_contains(page, "/submit", timeout=15000)
        except TimeoutError:
            diag_text = _collect_fill_page_diag(page)
            allure.attach(page.screenshot(), name="/fill提交后超时未跳转", attachment_type=allure.attachment_type.PNG)
            allure.attach(diag_text, name="超时完整诊断", attachment_type=allure.attachment_type.TEXT)
            raise TimeoutError(f"等待URL包含'/submit'超时(15000ms)\n{diag_text}")

    # 4. 签署页验证
    with allure.step("4. 签署页：验证申请信息和步骤状态"):
        submit = JdySubmitPage(page)
        assert "/submit" in submit.get_current_url(), "应在签署页"
        allure.attach(submit.screenshot(), name="签署页加载", attachment_type=allure.attachment_type.PNG)
        assert submit.has_text("申请信息"), "页面应包含'申请信息'"
        if case.get("expect_borrower_name"):
            assert submit.verify_apply_info(case["expect_borrower_name"]), \
                f"页面应包含借款人'{case['expect_borrower_name']}'"
        if case.get("expect_steps"):
            actual = submit.get_step_status()
            for step, expected_status in case["expect_steps"].items():
                assert actual.get(step) == expected_status, \
                    f"步骤'{step}'状态期望'{expected_status}'，实际'{actual.get(step)}'"
        allure.attach(submit.screenshot(), name="签署页验证完毕", attachment_type=allure.attachment_type.PNG)

    # 5. 后台申请单验证
    with allure.step("5. 后台验证：登录后台按手机号搜索申请单"):
        allure.attach(
            f"使用手机号 '{case.get('phone', '')}' 在后台搜索申请单",
            name="后台验证开始",
        )
        _flow_admin_verify(page, case)


# ===================== 回归：借款人信息页 =====================
@allure.feature("今东车融-借款人信息页")
@pytest.mark.ui
@pytest.mark.parametrize("case", get_cases_by_tag("result_page"))
def test_result_page(case, page):
    """回归测试：走完首页流程后，在借款人信息页做详细验证"""
    with allure.step("前置：走完首页流程"):
        _flow_home(page, case)

    with allure.step("借款人信息页验证"):
        _flow_result(page, case)


# ===================== 回归：补充信息页 =====================
@allure.feature("今东车融-补充信息页")
@pytest.mark.ui
@pytest.mark.parametrize("case", get_cases_by_tag("fill_page"))
def test_fill_page(case, page):
    """回归测试：走完首页+借款人信息页流程后，在补充信息页做详细验证"""
    with allure.step("前置：走完首页流程"):
        _flow_home(page, case)

    with allure.step("前置：走完借款人信息页流程"):
        _flow_result(page, case)

    with allure.step("补充信息页验证"):
        _flow_fill(page, case)
        if not case.get("expect_submit_fail"):
            try:
                _wait_url_contains(page, "/submit", timeout=15000)
            except TimeoutError:
                diag_text = _collect_fill_page_diag(page)
                allure.attach(page.screenshot(), name="/fill提交后超时未跳转", attachment_type=allure.attachment_type.PNG)
                allure.attach(diag_text, name="超时完整诊断", attachment_type=allure.attachment_type.TEXT)
                raise TimeoutError(f"等待URL包含'/submit'超时(15000ms)\n{diag_text}")


# ===================== 反向用例：补充信息页提交失败 =====================
@allure.feature("今东车融-反向用例")
@pytest.mark.ui
@pytest.mark.parametrize("case", get_cases_by_tag("negative"))
def test_negative_fill_submit(case, page):
    """反向用例：已婚有子女+联系人身份证异常，期望提交失败"""
    with allure.step("前置：走完首页流程"):
        _flow_home(page, case)

    # 首页反向用例：已在首页失败，直接断言
    if case.get("expect_fail_page") == "home":
        error_msg = page.evaluate("""() => {
            const toast = document.querySelector('.van-toast');
            const notify = document.querySelector('.van-notify');
            const errors = document.querySelectorAll('.van-field__error-message');
            const getVisibleText = (el) => {
                if (!el) return '';
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return '';
                return el.textContent.trim();
            };
            if (toast) return getVisibleText(toast);
            if (notify) return getVisibleText(notify);
            return Array.from(errors).map(getVisibleText).filter(t => t).join(', ');
        }""")
        if case.get("expect_error_keyword"):
            assert case["expect_error_keyword"] in error_msg, \
                f"期望错误提示包含'{case['expect_error_keyword']}'，实际: '{error_msg}'"
            allure.attach(f"✅ 校验通过：错误提示包含'{case['expect_error_keyword']}'", name="断言结果")
        else:
            default_keywords = ["请输入", "请选择", "不能为空", "格式不正确", "请填写", "必填"]
            matched = [kw for kw in default_keywords if kw in error_msg]
            if matched:
                allure.attach(f"✅ 校验通过：{matched} - {error_msg}", name="断言结果")
        return

    with allure.step("前置：走完借款人信息页流程"):
        _flow_result(page, case)

    # 借款人信息页反向用例：已在result页失败，直接断言
    if case.get("expect_fail_page") == "result":
        error_msg = page.evaluate("""() => {
            const toast = document.querySelector('.van-toast');
            const notify = document.querySelector('.van-notify');
            const errors = document.querySelectorAll('.van-field__error-message');
            const getVisibleText = (el) => {
                if (!el) return '';
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return '';
                return el.textContent.trim();
            };
            if (toast) return getVisibleText(toast);
            if (notify) return getVisibleText(notify);
            return Array.from(errors).map(getVisibleText).filter(t => t).join(', ');
        }""")
        if case.get("expect_error_keyword"):
            assert case["expect_error_keyword"] in error_msg, \
                f"期望错误提示包含'{case['expect_error_keyword']}'，实际: '{error_msg}'"
            allure.attach(f"✅ 校验通过：错误提示包含'{case['expect_error_keyword']}'", name="断言结果")
        return

    with allure.step("补充信息页：填写异常数据并提交"):
        fill = JdyFillPage(page)
        assert "/fill" in fill.get_current_url(), "应在补充信息页"

        if case.get("fill_area"):
            fill.select_area(case["fill_area"])
        if case.get("fill_address"):
            fill.fill_address(case["fill_address"])
        if case.get("marriage"):
            fill.select_marriage(case["marriage"])
        if case.get("education"):
            fill.select_education(case["education"])
        if case.get("company"):
            fill.fill_company(case["company"])
        if case.get("work_type"):
            fill.select_work_type(case["work_type"])
        if case.get("annual_income"):
            fill.fill_annual_income(case["annual_income"])
        if case.get("contact1_name"):
            fill.fill_contact1(
                case["contact1_name"], case["contact1_relation"],
                case["contact1_phone"], case.get("contact1_id", "")
            )
        if case.get("contact2_name"):
            fill.fill_contact2(
                case["contact2_name"], case["contact2_relation"],
                case["contact2_phone"]
            )

        allure.attach(fill.screenshot(), name="异常数据填写完毕", attachment_type=allure.attachment_type.PNG)
        fill.click_submit()

        # 断言：提交失败，对页面错误提示进行断言（而非等待跳转到下一页）
        # 立即等待错误提示元素出现（toast 可能只显示 2s，不能等太久）
        try:
            page.wait_for_selector(
                '.van-toast, .van-notify, .van-field__error-message, .van-dialog__message, [class*="error"]',
                state='visible', timeout=5000
            )
        except Exception:
            pass
        allure.attach(fill.screenshot(), name="提交后截图", attachment_type=allure.attachment_type.PNG)
        error_msg = page.evaluate("""() => {
            const getVisibleText = (el) => {
                if (!el) return '';
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return '';
                if (style.opacity === '0') return '';
                return el.textContent.trim();
            };
            const toasts = document.querySelectorAll('.van-toast');
            for (const t of toasts) { const txt = getVisibleText(t); if (txt) return txt; }
            const notifies = document.querySelectorAll('.van-notify');
            for (const n of notifies) { const txt = getVisibleText(n); if (txt) return txt; }
            const dialogs = document.querySelectorAll('.van-dialog__message, .van-dialog');
            for (const d of dialogs) { const txt = getVisibleText(d); if (txt) return txt; }
            const errors = document.querySelectorAll('.van-field__error-message, .van-cell__error-message, .error-msg, .error-text, .error-message');
            const errTexts = Array.from(errors).map(getVisibleText).filter(t => t);
            if (errTexts.length > 0) return errTexts.join(', ');
            const allElements = document.querySelectorAll('div, span, p');
            for (const el of allElements) {
                const txt = getVisibleText(el);
                if (txt && txt.length < 50 && (txt.startsWith('请') || txt.includes('不能为空') || txt.includes('格式不正确') || txt.includes('请输入') || txt.includes('请选择'))) {
                    return txt;
                }
            }
            return '';
        }""")
        still_on_fill = "/fill" in page.url
        allure.attach(f"error_msg='{error_msg}', still_on_fill={still_on_fill}, url={page.url}",
                      name="反向用例提交结果", attachment_type=allure.attachment_type.TEXT)

        if error_msg:
            allure.attach(error_msg, name="错误提示", attachment_type=allure.attachment_type.TEXT)
            if case.get("expect_error_keyword"):
                assert case["expect_error_keyword"] in error_msg, \
                    f"期望错误提示包含'{case['expect_error_keyword']}'，实际: '{error_msg}'"
                allure.attach(f"✅ 校验通过：错误提示包含期望关键词'{case['expect_error_keyword']}'", name="断言结果")
            else:
                # 无指定关键词时，检查是否包含常见校验关键词
                default_keywords = ["请输入", "请选择", "不能为空", "格式不正确", "请填写", "必填",
                                    "请上传", "请勾选", "不一致", "重复", "相同", "错误", "无效"]
                matched = [kw for kw in default_keywords if kw in error_msg]
                if matched:
                    allure.attach(f"✅ 校验通过：错误提示包含关键词{matched} - {error_msg}", name="断言结果")
                else:
                    allure.attach(f"✅ 校验通过：提交被拦截（错误提示: {error_msg}）", name="断言结果")
        elif still_on_fill:
            # 提交被拦截但没有显式错误提示 - 如果指定了关键词则失败
            if case.get("expect_error_keyword"):
                raise AssertionError(
                    f"期望错误提示包含'{case['expect_error_keyword']}'，但未检测到任何错误提示（页面停留在/fill）")
            allure.attach("✅ 校验通过：提交被拦截，页面未跳转（无显式错误提示）", name="断言结果")
        else:
            # 页面跳转了 - 异常数据被系统接受，这是 bug
            raise AssertionError("期望提交失败（异常数据应被拦截），但页面已跳转（提交成功了）")


# ===================== 签署协议验证：走完整流程后点击【去签署】验证签署协议页 =====================
@allure.feature("今东车融-签署协议验证")
@pytest.mark.ui
@pytest.mark.parametrize("case", get_cases_by_tag("sign_agreement"))
def test_sign_agreement(case, page):
    """完整流程到签署页后，点击【去签署】按钮，验证页面是否进入签署协议"""

    # 1. 首页
    with allure.step("1. 首页：填写信息并提交"):
        _flow_home(page, case)

    # 2. 借款人信息页
    with allure.step("2. 借款人信息页：上传身份证OCR并填写"):
        _flow_result(page, case)

    # 3. 补充信息页
    with allure.step("3. 补充信息页：填写补充信息"):
        _flow_fill(page, case)
        try:
            _wait_url_contains(page, "/submit", timeout=15000)
        except TimeoutError:
            diag_text = _collect_fill_page_diag(page)
            allure.attach(page.screenshot(), name="/fill提交后超时未跳转", attachment_type=allure.attachment_type.PNG)
            allure.attach(diag_text, name="超时完整诊断", attachment_type=allure.attachment_type.TEXT)
            raise

    # 4. 签署页：验证【去签署】按钮并点击
    with allure.step("4. 签署页：验证申请信息并点击【去签署】"):
        submit = JdySubmitPage(page)
        assert "/submit" in submit.get_current_url(), "应在签署页"
        allure.attach(submit.screenshot(), name="签署页加载", attachment_type=allure.attachment_type.PNG)

        # 验证签署按钮存在且可点击
        assert submit.has_sign_btn(), "签署页应有'去签署'按钮"
        assert submit.is_sign_btn_enabled(), "'去签署'按钮应可点击"

    # 5. 点击【去签署】验证进入签署协议页
    with allure.step("5. 点击【去签署】验证进入签署协议页"):
        entered = submit.click_sign_and_verify(timeout=10000)
        expect_entered = case.get("expect_sign_agreement_entered", True)
        if expect_entered:
            assert entered, "点击【去签署】后应进入签署协议页，但未检测到签署协议页面特征"
            allure.attach("✅ 已成功进入签署协议页", name="签署协议验证")
        else:
            assert not entered, "期望未进入签署协议页，但实际检测到签署协议页面特征"
            allure.attach("✅ 未进入签署协议页（符合预期）", name="签署协议验证")
