#!/bin/bash


export ENV="test"


BASE_DIR="/Users/tanzsongsen/auto_test"

RESULT_DIR="$BASE_DIR/reports"

RESULTS="$RESULT_DIR/allure-results"

REPORT="$RESULT_DIR/allure-report"

STAT="$RESULT_DIR/test-stat.json"



echo "====== 今东车融 自动化回归 $(date '+%Y-%m-%d %H:%M:%S') ======"



# 创建目录

mkdir -p "$RESULTS"



# 清理历史结果

rm -rf "$RESULTS"/*



echo ""
echo "--- [1/3] 接口回归 ---"


python3 -m pytest \
tests/api/test_jdy_query.py \
tests/api/test_jdy_business.py \
-v \
--tb=short \
-W ignore::Warning \
--alluredir="$RESULTS" \
--json-report \
--json-report-file="$STAT" \
|| true





echo ""
echo "--- [2/3] UI 回归（各页面）---"


python3 -m pytest \
tests/ui/test_jdy_flow.py \
-v \
--tb=short \
-W ignore::Warning \
-k "submit_page or result_page or fill_page or regression" \
--alluredir="$RESULTS" \
--json-report \
--json-report-file="$STAT" \
|| true





echo ""
echo "--- [3/3] 首页冒烟 ---"


python3 -m pytest \
tests/ui/test_jdy_home.py \
-v \
--tb=short \
-W ignore::Warning \
--alluredir="$RESULTS" \
--json-report \
--json-report-file="$STAT" \
|| true






#################################
# 测试统计
#################################


echo ""
echo "--- 测试统计 ---"


python3 <<EOF


import json


file="$STAT"


try:

    with open(file,encoding="utf-8") as f:

        data=json.load(f)


    summary=data["summary"]


    print("===================")

    print("总数量:",summary.get("total"))

    print("通过:",summary.get("passed"))

    print("失败:",summary.get("failed"))

    print("跳过:",summary.get("skipped"))

    print("耗时:",
          round(summary.get("duration",0),2),
          "秒")


    print("===================")


except Exception as e:

    print("统计失败:",e)


EOF






#################################
# 生成Allure
#################################


echo ""
echo "--- 生成报告 ---"



mkdir -p "$REPORT"



allure generate \
"$RESULTS" \
-o "$REPORT" \
--clean \
|| true





echo ""

echo "====== 完成！======"

echo "Allure:"
echo "$REPORT"


echo "统计:"
echo "$STAT"


exit 0
