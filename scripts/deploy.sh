#!/bin/bash
# 一键启动脚本

set -e

ENVIRONMENT=${1:-prod}

echo "=========================================="
echo "Multi-Agent AI Delivery OS - Deployment"
echo "Environment: $ENVIRONMENT"
echo "=========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

# 检查 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

# 创建必要目录
mkdir -p artifacts/{phase8_sample_tenant,phase8_sample_billing,phase8_sample_incident}
mkdir -p configs

# 生成配置快照
echo "Generating config snapshot..."
python scripts/generate_config_snapshot.py --environment $ENVIRONMENT

# 启动前一致性校验
echo "Running pre-deployment checks..."
python scripts/pre_deployment_check.py --environment $ENVIRONMENT

# 启动服务
echo "Starting services..."
ENVIRONMENT=$ENVIRONMENT docker-compose up -d

echo "=========================================="
echo "Deployment completed"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "=========================================="


