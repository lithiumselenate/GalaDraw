# GalaBee

轻量级应用，用于年会抽奖，基于flask和sqlite

- 管理员工列表
- 使用CSV导入员工
- 奖品等级设置
- 服务端抽取
- 导出中奖名单
- 基于SQLite
- 可用于Docker容器

## 本地环境
#### 需求：

- Python 3.10+
- pip

启动虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
pip install -r requirements.txt
```

运行

```powershell
python app.py
```

打开网页

```text
http://localhost:8000
```

## CSV 导入格式

UTF-8 CSV，表头如下:

```csv
employee_no,name,department
001,Alice,Engineering
002,Bob,Sales
```

## Docker

建立和运行：

```powershell
docker compose up --build
```

打开：

```text
http://localhost:8000
```

## 备注


生产环境应该使用强密钥，定期备份`instance/gala_draw.db`.
