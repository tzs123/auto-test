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
        data=json.load(f)


    webhook=os.environ.get(
        "FEISHU_WEBHOOK"
    )


    card={
        "msg_type":"interactive",
        "card":{
            "config":{
                "wide_screen_mode":True
            },

            "header":{
                "template":"red",
                "title":{
                    "tag":"plain_text",
                    "content":"🚀 自动化测试完成"
                }
            },


            "elements":[

                {
                    "tag":"div",
                    "text":{
                        "tag":"lark_md",
                        "content":f"""
**项目：** {data['project']}

**状态：** {data['status']}

**通过率：** {data['rate']}

**总计：** {data['total']}

**通过：** {data['passed']}

**失败：** {data['failed']}

**跳过：** {data['skipped']}

**耗时：** {data['duration']}

**开始时间：** {data['start_time']}

**结束时间：** {data['end_time']}

**Allure报告：**
https://tzs123.github.io/auto-test/
"""
                    }
                },


                {
                    "tag":"action",

                    "actions":[

                        {
                            "tag":"button",

                            "type":"primary",

                            "text":{
                                "tag":"plain_text",
                                "content":"📊 查看 Allure 报告"
                            },

                            "url":
                            "https://tzs123.github.io/auto-test/"
                        }

                    ]
                }
            ]
        }
    }



    requests.post(
        webhook,
        json=card
    )


if __name__=="__main__":
    main()
