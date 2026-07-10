"""API 接口测试共享断言工具。

提供统一的断言方法，断言失败时输出详细诊断信息（含接口返回的完整 body、
code、msg 等），方便定位根因并在平台缺陷库和 xlsx 日志中展示。
"""

import json


def _parse_json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _build_detail(resp, resp_json):
    """构造详细的错误信息，包含请求和响应的关键信息。"""
    lines = []
    lines.append(f"【HTTP状态码】实际={resp.status_code}")
    lines.append(f"【响应体】{resp.text[:2000]}")
    if resp_json is not None:
        lines.append(f"【业务码 code】={resp_json.get('code', '(无)')}")
        lines.append(f"【业务成功 success】={resp_json.get('success', '(无)')}")
        lines.append(f"【业务消息 msg】={resp_json.get('msg', '(无)')}")
        data = resp_json.get("data")
        if data is not None:
            data_str = str(data)[:500]
            lines.append(f"【业务数据 data】={data_str}")
    return "\n".join(lines)


def assert_api_response(resp, case, *, attach_fn=None):
    """统一 API 断言入口，失败时输出详细诊断信息并写入 allure 附件。

    Args:
        resp: requests.Response 对象
        case: YAML 用例字典（含 expect_code / expect_success / expect_code_body 等）
        attach_fn: allure.attach 函数引用（用于附加详细信息到报告）

    Raises:
        AssertionError: 任一断言不满足时抛出，附带详细诊断信息
    """
    resp_json = _parse_json(resp.text)
    detail = _build_detail(resp, resp_json)

    # 将详细诊断信息写入 allure 报告（平台可读取）
    if attach_fn:
        attach_fn(detail, name="详细诊断", attachment_type="text/plain")

    # ---- HTTP 状态码断言 ----
    expect_http = case.get("expect_code")
    if expect_http is not None:
        actual_http = resp.status_code
        if actual_http != expect_http:
            raise AssertionError(
                f"HTTP状态码不一致\n"
                f"  期望HTTP={expect_http}, 实际HTTP={actual_http}\n"
                f"\n--- 详细诊断 ---\n{detail}"
            )

    # ---- 业务字段断言 ----
    if resp_json is not None:

        # success 断言
        expect_success = case.get("expect_success")
        if expect_success is not None:
            actual_success = resp_json.get("success")
            if actual_success != expect_success:
                raise AssertionError(
                    f"业务success不一致\n"
                    f"  期望success={expect_success}, 实际success={actual_success}\n"
                    f"  接口返回msg={resp_json.get('msg', '(无)')}\n"
                    f"  接口返回code={resp_json.get('code', '(无)')}\n"
                    f"\n--- 详细诊断 ---\n{detail}"
                )

        # 业务码 code 断言
        expect_code_body = case.get("expect_code_body")
        if expect_code_body is not None:
            actual_code = resp_json.get("code")
            if str(actual_code) != str(expect_code_body):
                raise AssertionError(
                    f"业务码不一致\n"
                    f"  期望code={expect_code_body}, 实际code={actual_code}\n"
                    f"  接口返回msg={resp_json.get('msg', '(无)')}\n"
                    f"\n--- 详细诊断 ---\n{detail}"
                )

        # msg 包含断言
        expect_msg = case.get("expect_msg")
        if expect_msg:
            actual_msg = resp_json.get("msg", "")
            if expect_msg not in actual_msg:
                raise AssertionError(
                    f"消息内容不匹配\n"
                    f"  msg应包含'{expect_msg}', 实际msg='{actual_msg}'\n"
                    f"\n--- 详细诊断 ---\n{detail}"
                )

        # data 非空断言
        if case.get("expect_data_not_null"):
            actual_data = resp_json.get("data")
            if actual_data is None:
                raise AssertionError(
                    f"data为空\n"
                    f"  期望data不为空, 实际data=None\n"
                    f"  接口返回msg={resp_json.get('msg', '(无)')}\n"
                    f"  接口返回code={resp_json.get('code', '(无)')}\n"
                    f"\n--- 详细诊断 ---\n{detail}"
                )

    # ---- 响应体包含断言 ----
    expect_contains = case.get("expect_body_contains")
    if expect_contains and expect_contains not in resp.text:
        raise AssertionError(
            f"响应体未包含期望文本\n"
            f"  应包含'{expect_contains}'\n"
            f"\n--- 详细诊断 ---\n{detail}"
        )
