# B站直播数据实时监控系统

一个基于Django和Redis的B站直播间数据实时监控系统，支持多房间同时监控、实时弹幕采集、礼物统计和数据可视化。

## 🌟 功能特性

- 🎯 **多房间监控** - 同时监控多个直播间数据
- 💬 **实时弹幕采集** - 实时获取和展示弹幕内容
- 🎁 **礼物统计分析** - 统计礼物数量、价值和趋势
- 📊 **数据可视化** - Django Web界面展示实时数据
- 💾 **高性能存储** - Redis缓存确保数据快速访问
- ⚡ **实时更新** - 自动刷新和WebSocket实时推送
- 🔄 **自动重启** - 服务异常时自动恢复
- 🛠️ **调试工具** - 完整的调试和监控工具

## 📋 系统要求

- **Python**: 3.8 或更高版本
- **Redis**: 6.0 或更高版本
- **操作系统**: Windows/Linux/macOS
- **内存**: 建议 4GB 以上
- **网络**: 稳定的互联网连接

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/YOUR_USERNAME/bilibili-live-monitor.git
cd bilibili-live-monitor
```

### 2. 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 或使用conda
conda install --file requirements.txt
```

### 3. 启动Redis服务

```bash
# Windows (使用chocolatey)
choco install redis-64
redis-server

# Linux (Ubuntu/Debian)
sudo apt-get install redis-server
sudo systemctl start redis

# macOS (使用homebrew)
brew install redis
brew services start redis
```

### 4. 配置Django

```bash
cd bilibili-live-monitor-django

# 数据库迁移
python manage.py migrate

# 创建超级用户（可选）
python manage.py createsuperuser

# 收集静态文件
python manage.py collectstatic
```

### 5. 启动系统

#### 方式一：一键启动（推荐）

```bash
# 返回项目根目录
cd ..

# 一键启动所有服务
python setup.py
```

#### 方式二：分别启动

```bash
# 终端1：启动数据收集器
cd web_version
python multi_room_collector.py

# 终端2：启动Django服务器
cd bilibili-live-monitor-django
python manage.py runserver 0.0.0.0:8000
```

### 6. 访问系统

打开浏览器访问以下地址：

- 🏠 **主页面**: http://localhost:8000/live/
- 📊 **数据仪表板**: http://localhost:8000/live/dashboard/
- 💬 **弹幕浏览器**: http://localhost:8000/live/danmaku/
- 🔧 **调试页面**: http://localhost:8000/live/debug/

## 📁 项目结构

```
bilibili-live-monitor/
├── bilibili-live-monitor-django/     # Django Web应用
│   ├── bilibili_monitor/             # Django项目配置
│   ├── live_data/                    # 主应用模块
│   │   ├── templates/                # HTML模板
│   │   ├── static/                   # 静态文件
│   │   ├── management/               # Django管理命令
│   │   └── ...
│   ├── utils/                        # 工具类库
│   ├── static/                       # 全局静态文件
│   ├── logs/                         # 日志文件
│   └── manage.py                     # Django管理脚本
├── web_version/                      # 数据收集器
│   ├── multi_room_collector.py       # 多房间收集器
│   ├── simple_redis_saver.py         # Redis数据保存器
│   └── ...
├── live_data/                        # 历史数据和工具
├── spider_live_data/                 # 数据分析工具
├── setup.py                         # 一键启动脚本
├── requirements.txt                  # Python依赖
└── README.md                         # 项目说明
```

## ⚙️ 配置说明

### 监控房间配置

编辑 `web_version/multi_room_collector.py` 中的房间ID列表：

```python
# 默认监控的房间ID
DEFAULT_ROOMS = [
    1962481108,  # 房间1
    1982728080,  # 房间2
    1959064353,  # 房间3
    # 添加更多房间ID...
]
```

### Redis配置

编辑 `utils/redis_config.py`：

```python
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True,
    'max_connections': 50
}
```

### Django配置

编辑 `bilibili_monitor/settings.py`：

```python
# 数据库配置
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Redis配置
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
    }
}
```

## 🔧 高级使用

### 自定义监控房间

```bash
# 监控指定房间
python setup.py --rooms 1962481108,1982728080,1959064353

# 使用配置文件
python setup.py --config custom_config.json
```

### 仅启动特定服务

```bash
# 仅启动Django
python setup.py --django-only

# 仅启动数据收集器
python setup.py --collector-only
```

### 使用API

系统提供RESTful API接口：

```bash
# 获取房间弹幕数据
curl http://localhost:8000/live/api/room/1962481108/danmaku/

# 获取房间礼物数据
curl http://localhost:8000/live/api/room/1962481108/gifts/

# 获取房间统计信息
curl http://localhost:8000/live/api/room/1962481108/stats/
```

### 调试模式

```bash
# 启用详细调试信息
python setup.py --no-background --status-display

# 查看Redis数据
python manage.py shell
>>> from utils.redis_handler import get_redis_client
>>> client = get_redis_client()
>>> client.keys('room:*')
```

## 🐛 故障排除

### 常见问题

**Q: 收集器进程经常停止**
```bash
# 检查Redis连接
redis-cli ping

# 查看错误日志
tail -f logs/collector.log

# 使用调试模式
python setup.py --no-background
```

**Q: 编码错误 (UnicodeEncodeError)**
```bash
# Windows系统设置环境变量
set PYTHONIOENCODING=utf-8

# 或在代码中设置
os.environ['PYTHONIOENCODING'] = 'utf-8'
```

**Q: Django无法访问**
```bash
# 检查端口是否被占用
netstat -an | grep 8000

# 使用不同端口
python manage.py runserver 0.0.0.0:8080
```

**Q: Redis连接失败**
```bash
# 检查Redis服务状态
redis-cli ping

# Windows启动Redis
redis-server

# Linux启动Redis
sudo systemctl start redis
```

### 日志文件

- **Django日志**: `logs/django.log`
- **收集器日志**: `logs/collector.log`
- **启动日志**: `startup.log`

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目基于 MIT 许可证开源 - 详见 [LICENSE](LICENSE) 文件

---

⭐ 如果这个项目对您有帮助，请给个Star支持一下！