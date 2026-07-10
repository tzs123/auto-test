import pytest
import allure
import requests
import json
import os
from utils.yaml_loader import load_cases, load_config
from utils.signer import make_headers
from utils.api_assert import assert_api_response

config = load_config()
BASE_URL = config["base_url"]
ACCESS_KEY = config["access_key"]
SECRET_KEY = config.get("secret_key", "")


@allure.feature("今东车融-文件上传接口")
@pytest.mark.api
@pytest.mark.parametrize("case", load_cases("cases/api/test_jdy_upload.yaml"))
def test_jdy_upload(case):
    with allure.step(case["name"]):
        headers = make_headers(ACCESS_KEY, SECRET_KEY,
                              method=case.get("method", "POST"),
                              query_params=case.get("params"))
        headers.pop("Content-Type", None)
        url = BASE_URL + case["path"]

        allure.attach(f"{case['method']} {url}", name="请求地址")
        if case.get("params"):
            allure.attach(json.dumps(case["params"], ensure_ascii=False), name="请求参数")

        if case["method"] == "GET":
            resp = requests.get(url, params=case.get("params"), headers=headers,
                                verify=False, timeout=30)
        else:
            files = {}
            if case.get("files"):
                for key, filepath in case["files"].items():
                    if os.path.exists(filepath):
                        filename = os.path.basename(filepath)
                        ext = os.path.splitext(filename)[1].lower()
                        content_type = {
                            ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg",
                            ".png": "image/png",
                        }.get(ext, "application/octet-stream")
                        files[key] = (filename, open(filepath, "rb"), content_type)
                    else:
                        allure.attach(f"文件不存在: {filepath}", name="上传文件警告")

            resp = requests.post(url, params=case.get("params"), files=files,
                                 headers=headers, verify=False, timeout=30)

            for v in files.values():
                v[1].close()  # tuple: (filename, fileobj, content_type)

        allure.attach(str(resp.status_code), name="HTTP状态码")
        allure.attach(resp.text[:2000], name="响应体")
        assert_api_response(resp, case, attach_fn=allure.attach)
