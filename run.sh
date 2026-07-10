#!/bin/bash

export MS_URL="http://localhost:8081"
export MS_ACCESS_KEY="BAJqNGDU1U87qQBD"
export MS_SECRET_KEY="6ooIgWL5Acr8FLCw"
export MS_PROJECT_ID="1531249729009098752"
export ENV="test"

BASE_DIR="/Users/tanzsongsen/auto_test"
RESULTS="$BASE_DIR/reports/allure-results"

echo "====== 今东车融 自动化回归 $(date '+%Y-%m-%d %H:%M:%S') ======"
rm -rf "$RESULTS"

echo "--- [1/3] 接口回归 ---"
python3 -m pytest tests/api/test_jdy_query.py tests/api/test_jdy_business.py \
    -v --tb=short -W ignore::Warning \
    --alluredir="$RESULTS" || true

echo "--- [2/3] UI 回归（各页面）---"
python3 -m pytest tests/ui/test_jdy_flow.py \
    -v --tb=short -W ignore::Warning \
    -k "submit_page or result_page or fill_page or regression" \
    --alluredir="$RESULTS" || true

echo "--- [3/3] 首页冒烟 ---"
python3 -m pytest tests/ui/test_jdy_home.py \
    -v --tb=short -W ignore::Warning \
    --alluredir="$RESULTS" || true

echo "--- 同步到 MeterSphere ---"
python3 "$BASE_DIR/utils/ms_sync.py"

echo "--- 生成报告 ---"
allure generate "$RESULTS" -o "$BASE_DIR/reports/allure-report" --clean 2>/dev/null || true

echo "====== 完成！查看报告: allure serve $RESULTS ======"
python3 run_main.py
