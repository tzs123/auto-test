import os
import json
import glob
import time
from datetime import datetime


RESULT_PATH = "reports/allure-results"

OUTPUT = "reports/summary.json"


def parse_allure_result():

    total = 0
    passed = 0
    failed = 0
    broken = 0
    skipped = 0

    start_time = None
    end_time = None


    files = glob.glob(
        f"{RESULT_PATH}/*-result.json"
    )


    for file in files:

        try:

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                data=json.load(f)


            status=data.get(
                "status"
            )


            total += 1


            if status=="passed":
                passed += 1

            elif status=="failed":
                failed += 1

            elif status=="broken":
                broken += 1

            elif status=="skipped":
                skipped += 1


            # 时间统计
            start=data.get(
                "start"
            )

            stop=data.get(
                "stop"
            )


            if start:

                if start_time is None or start < start_time:
                    start_time=start


            if stop:

                if end_time is None or stop > end_time:
                    end_time=stop



        except Exception as e:

            print(
                "解析失败:",
                file,
                e
            )



    real_failed = failed + broken


    if total:

        rate = round(
            passed / total * 100,
            2
        )

    else:

        rate = 0



    if start_time and end_time:

        duration = round(
            (end_time-start_time)/1000,
            2
        )

    else:

        duration=0



    result={

        "project":
            "国信小米",


        "status":
            "❌ 存在失败"
            if real_failed >0
            else "✅ 全部通过",


        "total":
            total,


        "passed":
            passed,


        "failed":
            real_failed,


        "skipped":
            skipped,


        "rate":
            f"{rate}%",


        "duration":
            f"{duration}s",


        "start_time":
            datetime.fromtimestamp(
                start_time/1000
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if start_time else "",


        "end_time":
            datetime.fromtimestamp(
                end_time/1000
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if end_time else "",


        "allure_url":
            "https://tzs123.github.io/auto-test/"

    }



    os.makedirs(
        "reports",
        exist_ok=True
    )


    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=4
        )


    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=4
        )
    )



if __name__=="__main__":

    parse_allure_result()
