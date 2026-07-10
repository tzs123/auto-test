import pytest
import allure
from utils.yaml_loader import load_cases


@allure.feature("demo_smoke")
@pytest.mark.api
@pytest.mark.parametrize("case", load_cases("cases/api/demo_smoke.yaml"))
def test_demo_smoke(case):
    with allure.step(case.get("name", case.get("scenario", "demo_smoke"))):
        # TODO: 按 YAML 字段补充断言逻辑
        assert True
