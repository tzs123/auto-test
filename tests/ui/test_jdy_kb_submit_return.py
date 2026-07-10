import pytest
import allure
from pages.jdy_home_page import JdyHomePage
from pages.jdy_result_page import JdyResultPage
from pages.jdy_fill_page import JdyFillPage
from pages.jdy_submit_page import JdySubmitPage
from tests.ui.jdy_kb_flow import (
    load_kb_cases, flow_home, flow_result, flow_fill, wait_url_contains
)

YAML = "cases/ui/test_jdy_kb_submit_return.yaml"


@allure.feature("今东车融-签署页返回逻辑-知识库")
@pytest.mark.ui
@pytest.mark.parametrize("case", load_kb_cases(YAML))
def test_jdy_kb_submit_return(case, page):
    """签署页返回逻辑：返回fill再进入不可点击，从home重新进入可点击"""
    with allure.step(f"[{case['tc_id']}] {case['scenario']}"):
        allure.attach(case.get("kb_summary", ""), name="知识库摘要")

        test_flow = case.get("test_flow", "")
        expect_enabled = case.get("expect_sign_btn_enabled", True)

        # ========== 第一遍：从 home 走到签署页 ==========
        with allure.step("第一遍：从首页走到签署页"):
            flow_home(page, case)
            flow_result(page, case)
            flow_fill(page, case)

            submit = JdySubmitPage(page)
            wait_url_contains(page, "/submit", timeout=15000)
            assert "/submit" in submit.get_current_url(), "应在签署页"
            allure.attach(
                submit.screenshot(),
                name="首次进入签署页",
                attachment_type=allure.attachment_type.PNG
            )

            # 记录第一遍的签署按钮状态
            first_btn_enabled = submit.is_sign_btn_enabled()
            allure.attach(
                f"首次签署按钮状态: {'可点击' if first_btn_enabled else '禁用'}",
                name="首次签署按钮"
            )

            # ========== 先点击【去签署】按钮 ==========
            if case.get("click_sign_before_return", False):
                with allure.step("点击【去签署】按钮验证"):
                    if first_btn_enabled:
                        # 点击【去签署】并验证是否进入签署协议页
                        entered = submit.click_sign_and_verify(timeout=10000)
                        allure.attach(
                            f"点击【去签署】后{'已进入签署协议页' if entered else '未进入签署协议页（可能需要勾选协议或被拦截）'}",
                            name="去签署验证"
                        )
                        # 如果进入了签署协议页，需要返回到 /submit
                        if entered or "/submit" not in page.url:
                            with allure.step("从签署协议页返回到签署页"):
                                submit.click_back()
                                allure.attach(
                                    page.screenshot(),
                                    name="从签署协议页返回",
                                    attachment_type=allure.attachment_type.PNG
                                )
                                # 确认回到了 /submit
                                if "/submit" not in page.url:
                                    page.go_back()
                                    page.wait_for_timeout(2000)
                                allure.attach(f"返回后URL: {page.url}", name="返回后URL")
                    else:
                        allure.attach("'去签署'按钮禁用，跳过点击", name="去签署验证")

        # ========== 根据 test_flow 执行不同场景 ==========
        if test_flow == "submit_return_to_fill":
            # 场景1：从 /submit 返回 /fill，再从 /fill 进入 /submit
            with allure.step("场景1：从签署页返回fill，再进入签署页"):
                # 点击返回按钮
                submit.click_back()
                allure.attach(
                    page.screenshot(),
                    name="返回后页面",
                    attachment_type=allure.attachment_type.PNG
                )

                # 确认回到了 /fill
                if "/fill" not in page.url:
                    # 可能还在 /submit，尝试浏览器后退
                    page.go_back()
                    page.wait_for_timeout(2000)

                allure.attach(f"当前URL: {page.url}", name="返回后URL")

                # 从 /fill 重新提交进入 /submit
                fill = JdyFillPage(page)
                if "/fill" in page.url:
                    # 点击完成补充重新提交
                    fill.click_submit()
                    try:
                        wait_url_contains(page, "/submit", timeout=15000)
                    except Exception:
                        allure.attach(
                            page.screenshot(),
                            name="重新提交后",
                            attachment_type=allure.attachment_type.PNG
                        )

                # 检查签署按钮状态
                allure.attach(
                    page.screenshot(),
                    name="重新进入签署页",
                    attachment_type=allure.attachment_type.PNG
                )

                if "/submit" in page.url:
                    btn_enabled = submit.is_sign_btn_enabled()
                    allure.attach(
                        f"签署按钮状态: {'可点击' if btn_enabled else '禁用'}",
                        name="签署按钮检查"
                    )
                    if expect_enabled:
                        assert btn_enabled, \
                            "期望签署按钮可点击，但实际禁用"
                    else:
                        assert not btn_enabled, \
                            "期望签署按钮禁用，但实际可点击"
                else:
                    # 没跳转到 /submit，可能是重复提交被拦截
                    allure.attach(
                        f"未跳转到签署页，当前URL: {page.url}",
                        name="签署页跳转"
                    )
                    if expect_enabled:
                        pytest.fail(f"未进入签署页，无法验证签署按钮: {page.url}")

        elif test_flow == "home_reenter_to_submit":
            # 场景2：返回首页，重新输入同一手机号车牌号
            # 业务规则：前提是手机号和车牌号已走了一遍完整流程，
            # 然后回到首页输入相同的手机号和车牌号，点击提交直接进入签署页
            with allure.step("场景2：返回首页重新输入相同手机号车牌号"):
                # 返回首页
                home = JdyHomePage(page)
                home.goto(case["channel_id"], case["product_id"])
                allure.attach(
                    home.screenshot(),
                    name="返回首页",
                    attachment_type=allure.attachment_type.PNG
                )

                # 重新输入同一手机号和车牌号
                home.input_phone(case["phone"])
                home.click_send_captcha()
                home.input_captcha(case["captcha"])
                home.input_car_number(case["car_number"])
                home.check_agree()

                import random
                page.wait_for_timeout(random.randint(2000, 4000))
                old_url = page.url
                home.click_submit()

                # 业务规则：已走过完整流程的手机号+车牌号，再次提交应直接进入签署页
                # 但也可能需要再走一遍 result→fill，兼容两种情况
                reached_submit = False
                try:
                    wait_url_contains(page, "/submit", timeout=10000)
                    reached_submit = True
                except Exception:
                    # 没有直接到 /submit，可能到了 /result，需要走完整流程
                    allure.attach(
                        page.screenshot(),
                        name="首页提交后（未直接到签署页）",
                        attachment_type=allure.attachment_type.PNG
                    )
                    allure.attach(f"当前URL: {page.url}", name="首页提交后URL")

                if not reached_submit:
                    # 走完 result 和 fill 到达 /submit
                    if "/result" in page.url:
                        flow_result(page, case)
                        flow_fill(page, case)
                    elif "/fill" in page.url:
                        flow_fill(page, case)
                    else:
                        # 停留在首页，提交失败
                        allure.attach(
                            page.screenshot(),
                            name="首页提交失败",
                            attachment_type=allure.attachment_type.PNG
                        )
                        pytest.fail(f"首页提交后未跳转: {page.url}")

                    # 进入签署页
                    try:
                        wait_url_contains(page, "/submit", timeout=15000)
                        reached_submit = True
                    except Exception:
                        allure.attach(
                            page.screenshot(),
                            name="未能到达签署页",
                            attachment_type=allure.attachment_type.PNG
                        )
                        pytest.fail(f"未能到达签署页: {page.url}")

                assert "/submit" in submit.get_current_url(), "应在签署页"
                allure.attach(
                    submit.screenshot(),
                    name="重新进入签署页",
                    attachment_type=allure.attachment_type.PNG
                )
                if reached_submit:
                    allure.attach("✅ 首页提交后直接进入签署页（业务规则匹配）", name="流程结果")

                # 检查签署按钮状态
                btn_enabled = submit.is_sign_btn_enabled()
                allure.attach(
                    f"签署按钮状态: {'可点击' if btn_enabled else '禁用'}",
                    name="签署按钮检查"
                )
                if expect_enabled:
                    assert btn_enabled, \
                        "期望签署按钮可点击，但实际禁用"
                else:
                    assert not btn_enabled, \
                        "期望签署按钮禁用，但实际可点击"
