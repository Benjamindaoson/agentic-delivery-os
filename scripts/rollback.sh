#!/bin/bash
# 一键回滚脚本

set -e

VERSION=${1:-latest}

echo "=========================================="
echo "Multi-Agent AI Delivery OS - Rollback"
echo "Target Version: $VERSION"
echo "=========================================="

# 检查配置快照是否存在
CONFIG_SNAPSHOT="configs/config_snapshot_${VERSION}.json"
if [ ! -f "$CONFIG_SNAPSHOT" ]; then
    echo "Error: Config snapshot not found: $CONFIG_SNAPSHOT"
    exit 1
fi

# 停止当前服务
echo "Stopping current services..."
docker-compose down

# 恢复配置
echo "Restoring config snapshot..."
cp "$CONFIG_SNAPSHOT" configs/config_snapshot.json

# 恢复代码版本（如果使用 git）
if [ -d ".git" ]; then
    echo "Restoring code version..."
    git checkout $VERSION
fi

# 重新构建并启动
echo "Rebuilding and starting services..."
docker-compose build
docker-compose up -d

echo "=========================================="
echo "Rollback completed"
echo "Version: $VERSION"
echo "=========================================="


