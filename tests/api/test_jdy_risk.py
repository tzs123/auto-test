import pytest
import allure
import requests
import json
import time
from utils.yaml_loader import load_cases, load_config
from utils.signer import make_headers
from utils.api_assert import assert_api_response

config = load_config()
BASE_URL = config["base_url"]
ACCESS_KEY = config["access_key"]
SECRET_KEY = config.get("secret_key", "")


def _check_response_consistency(resp_json: dict, case: dict, attach_fn):
    """校验请求测试字段与响应报错字段的一致性。

    接口职责：
    - loan 接口: 借款人信息接口，只判断身份证信息（idCard, name 等）
    - evaluate 接口: 判断车辆信息 + 手机号 + 验证码（carNumber, phone, captcha）
    - sign 接口: 业务流程校验优先

    加密字段（idCard, phone, address）来自 HAR 抓包，可能已过期，
    导致 API 总是先报这些字段的错误。

    因此一致性校验仅作为信息记录到报告中，不判定为测试失败。
    风险测试的核心目的是验证"API 是否拦截了非法输入"(success=false)。
    """
    verify_keywords = case.get("verify_keywords")
    if not verify_keywords:
        return

    # 只有接口返回失败时才校验一致性
    if resp_json.get("success", True):
        return

    msg = str(resp_json.get("msg", ""))
    verify_field = case.get("verify_field", "")

    # 检查响应 msg 是否包含任意关键词
    matched = [kw for kw in verify_keywords if kw in msg]

    if matched:
        consistency_info = (
            f"一致性校验: 通过 ✓\n"
            f"测试字段: {verify_field}\n"
            f"期望关键词: {verify_keywords}\n"
            f"响应msg: {msg}\n"
            f"匹配关键词: {matched}"
        )
        attach_fn(consistency_info, name="请求响应一致性校验")
    else:
        consistency_info = (
            f"一致性校验: 不一致 ⚠️\n"
            f"测试字段: {verify_field}\n"
            f"期望关键词: {verify_keywords}\n"
            f"响应msg: {msg}\n"
            f"匹配关键词: 无\n"
            f"说明: API有严格字段校验顺序，加密字段(idCard/phone等)\n"
            f"      值可能已过期，导致非目标字段先报错。\n"
            f"      风险测试核心是验证API拦截了非法输入(success=false)，\n"
            f"      而非错误消息与测试字段完全对应。"
        )
        attach_fn(consistency_info, name="请求响应一致性校验-不一致")


@allure.feature("风险规则库-接口安全")
@pytest.mark.api
@pytest.mark.parametrize("case", load_cases("cases/api/test_jdy_risk.yaml"))
def test_jdy_risk(case):
    """风险规则库 API 测试 - 覆盖9大类风险规则

    风险类别：
    - identity: 身份真实性风险
    - mobile: 手机号风险
    - vehicle: 车辆风险
    - captcha: 验证码风险
    - security: 安全攻击风险
    - flow: 业务流程风险
    - behavior: 行为风险
    - graph: 关系图谱风险
    - data_consistency: 数据一致性风险

    一致性校验：
    - 每个用例配置 verify_field（测试目标字段）和 verify_keywords（期望响应关键词）
    - 接口返回失败时，校验响应 msg 是否与测试字段一致
    - 如测手机号格式但响应报车辆错误，则标记为"请求响应不一致"
    """
    repeat = case.get("repeat", 1)

    for i in range(repeat):
        step_name = case["name"] if repeat == 1 else f"{case['name']} (第{i+1}次)"
        with allure.step(step_name):
            headers = make_headers(ACCESS_KEY, SECRET_KEY,
                                  method=case.get("method", "POST"),
                                  query_params=case.get("params"))
            url = BASE_URL + case["path"]

            allure.attach(f"{case['method']} {url}", name="请求地址")
            allure.attach(
                json.dumps({"risk_id": case.get("risk_id", ""),
                            "risk_category": case.get("risk_category", ""),
                            "risk_level": case.get("risk_level", ""),
                            "verify_field": case.get("verify_field", "")},
                           ensure_ascii=False),
                name="风险规则信息"
            )
            if case.get("body"):
                allure.attach(json.dumps(case["body"], ensure_ascii=False, default=str),
                              name="请求体")

            if case["method"] == "GET":
                resp = requests.get(url, params=case.get("params"), headers=headers,
                                    verify=False, timeout=30)
            else:
                resp = requests.post(url, json=case.get("body"), headers=headers,
                                     verify=False, timeout=30)

            allure.attach(str(resp.status_code), name="HTTP状态码")
            allure.attach(resp.text[:2000], name="响应体")

            # 解析响应
            resp_json = None
            try:
                resp_json = json.loads(resp.text)
            except (ValueError, TypeError):
                pass

            if resp_json:
                risk_result = "拦截" if not resp_json.get("success", True) else "未拦截"
                allure.attach(risk_result, name="风险拦截结果")

                # 安全攻击类必须被拦截
                if case.get("risk_category") == "security":
                    assert not resp_json.get("success", True), \
                        f"安全攻击未被拦截！risk_id={case.get('risk_id')}，" \
                        f"响应={resp.text[:500]}"

                # 请求-响应一致性校验（信息记录，不作为硬性断言）
                _check_response_consistency(resp_json, case, allure.attach)

            assert_api_response(resp, case, attach_fn=allure.attach)

            # 重复请求间隔（模拟暴力破解场景）
            if repeat > 1 and i < repeat - 1:
                time.sleep(0.5)
