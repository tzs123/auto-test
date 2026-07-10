import pytest
import allure
from utils.yaml_loader import load_cases

@allure.feature("POST接口测试")
@pytest.mark.api
@pytest.mark.parametrize("case", load_cases("cases/api/test_post.yaml"))
def test_post(case, client):
    with allure.step(case["name"]):
        resp = client.post(case["path"], json=case.get("body"))
        assert resp.status_code == case["expect_code"]
        if "expect_field" in case:
            assert case["expect_field"] in resp.json()
