import pytest
import allure
from pages.jdy_submit_page import JdySubmitPage
from tests.ui.jdy_kb_flow import load_kb_cases, flow_home, flow_result, flow_fill

YAML = "cases/ui/test_jdy_kb_submit.yaml"


@allure.feature("今东车融-网申签约-知识库")
@pytest.mark.ui
@pytest.mark.parametrize("case", load_kb_cases(YAML))
def test_jdy_kb_submit(case, page):
    with allure.step(f"[{case['tc_id']}] {case['scenario']}"):
        allure.attach(case.get("kb_summary", ""), name="知识库摘要")
        flow_home(page, case)
        flow_result(page, case)
        flow_fill(page, case)

        submit = JdySubmitPage(page)
        assert "/submit" in submit.get_current_url(), "应在网申签约页"
        allure.attach(submit.screenshot(), name="网申签约页", attachment_type=allure.attachment_type.PNG)

        if case.get("expect_apply_info"):
            assert submit.has_text("申请信息")

        if case.get("expect_borrower_name"):
            assert submit.verify_apply_info(case["expect_borrower_name"])

        if case.get("expect_steps"):
            actual = submit.get_step_status()
            for step, expected_status in case["expect_steps"].items():
                assert actual.get(step) == expected_status, \
                    f"步骤'{step}'期望'{expected_status}'，实际'{actual.get(step)}'"

        if case.get("expect_sign_btn"):
            assert submit.has_text("去签署")
