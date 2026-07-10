#!/bin/bash


export ENV="test"


BASE_DIR=$(pwd)


RESULT_DIR="$BASE_DIR/reports"

RESULTS="$RESULT_DIR/allure-results"

REPORT="$RESULT_DIR/allure-report"



echo "当前目录:"
pwd


echo "====== 今东车融 自动化回归 $(date '+%Y-%m-%d %H:%M:%S') ======"


mkdir -p "$RESULTS"


rm -rf "$RESULTS"/*



echo "--- [1/3] 接口回归 ---"


python3 -m pytest \
tests/api/test_jdy_query.py \
tests/api/test_jdy_business.py \
-v \
--tb=short \
-W ignore::Warning \
--alluredir="$RESULTS" \
|| true




echo "--- [2/3] UI 回归 ---"


python3 -m pytest \
tests/ui/test_jdy_flow.py \
-v \
--tb=short \
-k "submit_page or result_page or fill_page or regression" \
--alluredir="$RESULTS" \
|| true




echo "--- [3/3] 首页冒烟 ---"


python3 -m pytest \
tests/ui/test_jdy_home.py \
-v \
--tb=short \
--alluredir="$RESULTS" \
|| true




echo "--- 生成 Allure ---"


mkdir -p "$REPORT"


allure generate \
"$RESULTS" \
-o "$REPORT" \
--clean



echo "检查报告"

ls -la "$REPORT"



echo "====== 完成 ======"
