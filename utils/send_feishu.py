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


    failed = int(
        data.get("failed", 0)
    )


    # 测试状态颜色
    if failed == 0:

        template = "green"

        title = "🚀 自动化测试完成"

    else:

        template = "red"

        title = "🚨 自动化测试完成"



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
                # 项目 + 状态
                # ======================

                {

                    "tag": "div",

                    "text": {

                        "tag": "lark_md",

                        "content": f"""
**项目：** {data['project']}

**状态：** {data['status']}
"""

                    }

                },


                # ======================
                # 核心数据横排
                # ======================

                {

                    "tag": "div",

                    "fields": [


                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                f"**总计**\n{data['total']}"

                            }

                        },


                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                f"**通过**\n{data['passed']}"

                            }

                        },


                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                f"**失败**\n{data['failed']}"

                            }

                        },


                        {

                            "is_short": True,

                            "text": {

                                "tag": "lark_md",

                                "content":
                                f"**通过率**\n{data['rate']}"

                            }

                        }


                    ]

                },


                {

                    "tag": "hr"

                },


                # ======================
                # 执行信息
                # ======================

                {

                    "tag": "div",

                    "text": {

                        "tag": "lark_md",

                        "content": f"""
⏱ **耗时：** {data['duration']}


🕒 **执行时间：**

{data['start_time']} ~ {data['end_time']}
"""

                    }

                },


                # ======================
                # Allure按钮
                # ======================

                {

                    "tag": "action",

                    "actions": [

                        {

                            "tag": "button",

                            "text": {

                                "tag": "plain_text",

                                "content":
                                "📊 查看 Allure 报告"

                            },

                            "type":
                            "primary",

                            "url":
                            "https://tzs123.github.io/auto-test/"

                        }

                    ]

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
