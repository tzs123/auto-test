#!/bin/bash
# ===== 自动化测试可视化平台启动脚本 =====
# 用法:
#   ./启动平台.sh           仅启动 Web 平台 (API + 前端)
#   ./启动平台.sh --workers  同时启动 2 个负载均衡 worker（需先启动 Redis）
cd "$(dirname "$0")"

echo "🚀 启动测试平台 API (http://localhost:8001) ..."
uvicorn backend.app:app --host 0.0.0.0 --port 8001 --reload &
API_PID=$!

if [ "$1" = "--workers" ]; then
  echo "⚙ 启动 2 个负载均衡 worker ..."
  python -m backend.worker --name worker-1 &
  python -m backend.worker --name worker-2 &
  wait $!
fi

wait $API_PID
