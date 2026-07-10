import pytest
import allure
import requests
import json
from utils.yaml_loader import load_cases, load_config
from utils.signer import make_headers
from utils.api_assert import assert_api_response

config = load_config()
BASE_URL = config["base_url"]
ACCESS_KEY = config["access_key"]
SECRET_KEY = config.get("secret_key", "")


@allure.feature("今东车融-贷款信息接口")
@pytest.mark.api
@pytest.mark.parametrize("case", load_cases("cases/api/test_jdy_loan.yaml"))
def test_jdy_loan(case):
    with allure.step(case["name"]):
        headers = make_headers(ACCESS_KEY, SECRET_KEY,
                              method=case.get("method", "GET"),
                              query_params=case.get("params"))
        url = BASE_URL + case["path"]

        allure.attach(f"{case['method']} {url}", name="请求地址")
        if case.get("params"):
            allure.attach(json.dumps(case["params"], ensure_ascii=False), name="请求参数")
        if case.get("body"):
            allure.attach(json.dumps(case["body"], ensure_ascii=False, default=str), name="请求体")

        if case["method"] == "GET":
            resp = requests.get(url, params=case.get("params"), headers=headers,
                                verify=False, timeout=30)
        else:
            resp = requests.post(url, json=case.get("body"), headers=headers,
                                 verify=False, timeout=30)

        allure.attach(str(resp.status_code), name="HTTP状态码")
        allure.attach(resp.text[:2000], name="响应体")
        assert_api_response(resp, case, attach_fn=allure.attach)
