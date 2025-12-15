# Agentic AI Delivery OS

多智能体 AI 工程交付系统

## 项目结构

```
agentic_delivery_os/
├── frontend/          # 用户交互层（React + TypeScript）
├── backend/           # API + 调度入口（FastAPI）
├── runtime/           # 多智能体执行与状态系统
├── artifacts/         # 交付产物
├── configs/           # 系统配置
└── docs/              # 文档
```

## 快速开始

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

## 系统架构

系统由以下模块组成：

- **Frontend**: Wizard 流程、Review 页面、任务状态展示
- **Backend**: API 接口、Orchestration 调度
- **Runtime**: 6 个职责型 Agent、执行图、状态管理、工具层

## 开发说明

本项目为最小系统骨架，不包含具体业务逻辑实现。


