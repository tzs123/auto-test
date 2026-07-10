import pytest
import allure
from tests.ui.jdy_kb_flow import load_kb_cases, flow_home

YAML = "cases/ui/test_jdy_kb_home.yaml"


@allure.feature("今东车融-首页-知识库")
@pytest.mark.ui
@pytest.mark.parametrize("case", load_kb_cases(YAML))
def test_jdy_kb_home(case, page):
    with allure.step(f"[{case['tc_id']}] {case['scenario']}"):
        allure.attach(case.get("kb_summary", ""), name="知识库摘要")
        flow_home(page, case)
