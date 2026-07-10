import json
import os


path="reports/allure-results"


total=0
passed=0
failed=0
broken=0


for f in os.listdir(path):

    if f.endswith("-result.json"):

        total+=1

        data=json.load(
            open(
                os.path.join(path,f)
            )
        )

        status=data.get("status")


        if status=="passed":
            passed+=1

        elif status=="failed":
            failed+=1

        elif status=="broken":
            broken+=1



print("====================")
print("测试统计")
print("====================")

print(f"总数:{total}")
print(f"通过:{passed}")
print(f"失败:{failed}")
print(f"异常:{broken}")
