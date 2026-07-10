#!/bin/bash


export ENV=test


BASE_DIR=$(pwd)

RESULTS="$BASE_DIR/reports/allure-results"


echo "====== 自动化开始 ======"


rm -rf reports

mkdir -p $RESULTS



echo "--- API测试 ---"


pytest \
tests/api/test_jdy_query.py \
tests/api/test_jdy_business.py \
-v \
--tb=short \
-W ignore::Warning \
--alluredir=$RESULTS



echo "--- UI测试 ---"


pytest \
tests/ui/test_jdy_flow.py \
-v \
--tb=short \
-k "submit_page or result_page or fill_page or regression" \
--alluredir=$RESULTS



echo "--- 首页冒烟 ---"


pytest \
tests/ui/test_jdy_home.py \
-v \
--tb=short \
--alluredir=$RESULTS



echo "--- 生成统计 ---"


python3 scripts/statistic.py



echo "====== 执行结束 ======"
