import pytest
import allure
from utils.yaml_loader import load_cases

@allure.feature("GET接口测试")
@pytest.mark.api
@pytest.mark.parametrize("case", load_cases("cases/api/test_get.yaml"))
def test_get(case, client):
    with allure.step(case["name"]):
        resp = client.get(case["path"], params=case.get("params"))
        assert resp.status_code == case["expect_code"]
        if "expect_field" in case:
            data = resp.json()
            # 兼容列表和对象两种返回
            if isinstance(data, list):
                assert case["expect_field"] in data[0]
            else:
                assert case["expect_field"] in data
