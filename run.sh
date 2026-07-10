#!/bin/bash

export ENV="test"

BASE_DIR=$(pwd)

RESULTS="$BASE_DIR/reports/allure-results"


echo "====== 今东车融 自动化回归 $(date '+%Y-%m-%d %H:%M:%S') ======"

rm -rf "$RESULTS"

mkdir -p "$RESULTS"


echo "--- [1/3] 接口回归 ---"

python3 -m pytest \
tests/api/test_jdy_query.py \
tests/api/test_jdy_business.py \
-v \
--tb=short \
-W ignore::Warning \
--alluredir="$RESULTS" || true


echo "--- [2/3] UI 回归 ---"

python3 -m pytest \
tests/ui/test_jdy_flow.py \
-v \
--tb=short \
-k "submit_page or result_page or fill_page or regression" \
--alluredir="$RESULTS" || true


echo "--- [3/3] 首页冒烟 ---"

python3 -m pytest \
tests/ui/test_jdy_home.py \
-v \
--tb=short \
--alluredir="$RESULTS" || true


echo "--- 生成报告 ---"

mkdir -p "$BASE_DIR/reports/allure-report"

allure generate \
"$RESULTS" \
-o "$BASE_DIR/reports/allure-report" \
--clean


echo "检查报告目录"

ls -la "$BASE_DIR/reports/allure-report"

echo "====== 完成 ======"
exit 0
