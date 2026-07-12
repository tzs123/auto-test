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


    failed = int(
        data.get(
            "failed",
            0
        )
    )


    if failed == 0:

        template = "green"

    else:

        template = "red"



    card = {


        "msg_type":

            "interactive",



        "card": {


            "config": {

                "wide_screen_mode": True

            },



            "header": {


                "template":

                    template,


                "title": {

                    "tag":

                        "plain_text",


                    "content":

                        "🚀 自动化测试完成"

                }

            },



            "elements": [



                {

                    "tag":

                        "div",


                    "text": {


                        "tag":

                            "lark_md",



                        "content":

f"""
**项目：** {data['project']}

**环境：** {data.get('env','未配置')}

**状态：** {data['status']}
"""

                    }

                },



                {

                    "tag":

                        "div",



                    "fields": [


                        {

                            "is_short":

                                True,

                            "text": {

                                "tag":

                                    "lark_md",

                                "content":

                                    f"**总计**\n{data['total']}"

                            }

                        },


                        {

                            "is_short":

                                True,

                            "text": {

                                "tag":

                                    "lark_md",

                                "content":

                                    f"**通过**\n{data['passed']}"

                            }

                        },


                        {

                            "is_short":

                                True,

                            "text": {

                                "tag":

                                    "lark_md",

                                "content":

                                    f"**失败**\n{data['failed']}"

                            }

                        },


                        {

                            "is_short":

                                True,

                            "text": {

                                "tag":

                                    "lark_md",

                                "content":

                                    f"**跳过**\n{data['skipped']}"

                            }

                        },


                        {

                            "is_short":

                                True,

                            "text": {

                                "tag":

                                    "lark_md",

                                "content":

                                    f"**通过率**\n{data['rate']}"

                            }

                        }

                    ]

                },



                {

                    "tag":

                        "hr"

                },



                {

                    "tag":

                        "div",


                    "text": {


                        "tag":

                            "lark_md",


                        "content":

f"""
⏱ **耗时：** {data['duration']}

🕒 **执行时间：**

{data['start_time']} ~ {data['end_time']}
"""

                    }

                },



                {

                    "tag":

                        "action",


                    "actions": [


                        {

                            "tag":

                                "button",


                            "text": {

                                "tag":

                                    "plain_text",


                                "content":

                                    "📊 查看 Allure 报告"

                            },


                            "type":

                                "primary",


                            "url":

                                data["allure_url"]

                        }

                    ]

                }

            ]

        }

    }



    requests.post(

        webhook,

        json=card,

        timeout=10

    )



if __name__ == "__main__":

    main()
