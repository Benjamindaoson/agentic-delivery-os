# Phase 8 Deployment Specification

> 本文档定义 Phase 8 部署与环境硬化规格

## 1. 部署方式

### 1.1 Docker Compose（推荐）

使用 `docker-compose.yml` 一键部署：

```bash
./scripts/deploy.sh [dev|staging|prod]
```

### 1.2 环境分层

- **dev**: 开发环境
- **staging**: 预发布环境
- **prod**: 生产环境

环境通过 `ENVIRONMENT` 环境变量指定。

---

## 2. 配置快照机制

### 2.1 配置快照生成

运行以下命令生成配置快照：

```bash
python scripts/generate_config_snapshot.py --environment [dev|staging|prod]
```

配置快照包含：
- version
- environment
- timestamp
- runtime_version
- dependencies
- system_config
- deployment_config
- config_hash

### 2.2 配置快照版本化

配置快照文件命名格式：
- `config_snapshot_{environment}_{timestamp}.json`（历史版本）
- `config_snapshot.json`（当前版本）

### 2.3 配置回滚

使用以下命令回滚到指定版本：

```bash
./scripts/rollback.sh [version]
```

---

## 3. 启动前一致性校验

### 3.1 校验项

运行 `scripts/pre_deployment_check.py` 进行校验：

1. **Config Hash**: 验证配置快照 hash
2. **Runtime Version**: 验证 Python 版本（3.11）
3. **Dependency Lock**: 验证依赖锁定文件

### 3.2 校验失败处理

如果任何校验失败，部署将中止。

---

## 4. 一键启动脚本

### 4.1 启动

```bash
./scripts/deploy.sh [environment]
```

脚本执行：
1. 检查 Docker 和 Docker Compose
2. 创建必要目录
3. 生成配置快照
4. 运行启动前一致性校验
5. 启动服务

### 4.2 服务端口

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Redis: `localhost:6379`

---

## 5. 一键回滚脚本

### 5.1 回滚

```bash
./scripts/rollback.sh [version]
```

脚本执行：
1. 检查配置快照是否存在
2. 停止当前服务
3. 恢复配置
4. 恢复代码版本（如果使用 git）
5. 重新构建并启动

---

## 6. 部署文档

### 6.1 新客户独立部署

新客户可按照以下步骤独立部署：

1. 克隆代码仓库
2. 安装 Docker 和 Docker Compose
3. 运行 `./scripts/deploy.sh prod`
4. 访问 `http://localhost:8000` 验证部署

### 6.2 依赖要求

- Docker >= 20.10
- Docker Compose >= 2.0
- Python >= 3.11（用于脚本）

---

**状态**: ✅ **Phase 8 Deployment Specification 已定义**


