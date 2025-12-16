# 启动指南

## 后端启动

### Windows (PowerShell)

```powershell
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

或使用批处理文件：
```powershell
.\start_backend.bat
```

### Linux/Mac

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

或使用脚本：
```bash
chmod +x start_backend.sh
./start_backend.sh
```

## 验证启动

1. 访问健康检查：http://localhost:8000/api/health
2. 访问 API 文档：http://localhost:8000/docs
3. 验证 OpenAPI schema 正常生成

## 测试 API

运行测试脚本：
```bash
python test_api.py
```

测试脚本会：
- 连续执行 2 次完整任务
- 验证 task_id 不冲突
- 验证 artifacts 不覆盖
- 验证 trace 可清晰区分

## 系统要求

- Python 3.8+
- 已安装依赖：`pip install -r backend/requirements.txt`




