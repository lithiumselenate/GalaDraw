# GalaBee

轻量级应用，用于年会抽奖，基于flask和sqlite

- 管理员工列表
- 使用CSV导入员工
- 奖品等级设置
- 服务端抽取
- 导出中奖名单
- 基于SQLite
- 可用于Docker容器
- 三层用户权限
- 签到和用户管理功能
## 本地环境
#### 需求：
均为在项目根目录运行
- Python 3.10+
- pip
- git

安装依赖，配置虚拟环境和运行

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
pip install -r requirements.txt
python -m venv .venv
python app.py
```

获取代码仓库的更新
```powershell
git pull
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


- 在app.py可以通过修改常量 AUTH_ENABLED 来开关用户控制和签到功能
- 开启时需要注册/登录，建议在有部署需求的环境使用
- 关闭时不需要登录 建议在本地使用
- 注意在正式活动前确认所有员工的可抽奖属性
