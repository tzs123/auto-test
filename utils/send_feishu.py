import json
import os
import requests


SUMMARY = "reports/summary.json"


def main():

    with open(
        SUMMARY,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)


    webhook = os.environ.get(
        "FEISHU_WEBHOOK"
    )


    if not webhook:
        raise Exception(
            "FEISHU_WEBHOOK 未配置"
        )


    status = str(
        data.get("status", "")
    )


    if (
        "success" in status.lower()
        or "passed" in status.lower()
        or "通过" in status
    ):

        template = "green"
        title = "✅ 自动化测试通过"

    else:

        template = "red"
        title = "❌ 自动化测试失败"



    card = {

        "msg_type": "interactive",

        "card": {


            "config": {
                "wide_screen_mode": True
            },


            "header": {

                "template": template,

                "title": {

                    "tag": "plain_text",

                    "content": title

                }

            },


            "elements": [


                # ======================
                # 第一排：核心指标
                # ======================

                {

                    "tag": "div",

                    "fields": [

                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                    f"**📋 总用例**\n{data['total']}"

                            }

                        },


                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                    f"**✅ 通过**\n{data['passed']}"

                            }

                        },


                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                    f"**❌ 失败**\n{data['failed']}"

                            }

                        },


                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                    f"**📈 通过率**\n{data['rate']}"

                            }

                        }

                    ]

                },


                {
                    "tag": "hr"
                },


                # ======================
                # 第二部分：执行信息
                # ======================


                {

                    "tag": "div",

                    "text": {

                        "tag": "lark_md",

                        "content": f"""
**项目**
{data['project']}


**状态**
{data['status']}


**跳过**
{data['skipped']}


**执行耗时**
{data['duration']}


**开始时间**
{data['start_time']}


**结束时间**
{data['end_time']}
"""

                    }

                },


                {
                    "tag": "hr"
                },


                {

                    "tag": "div",

                    "text": {

                        "tag": "lark_md",

                        "content":
                            "🤖 GitHub Actions 自动生成测试报告"

                    }

                }


            ]

        }

    }



    response = requests.post(

        webhook,

        json=card,

        timeout=10

    )


    print(
        response.text
    )



if __name__ == "__main__":

    main()
