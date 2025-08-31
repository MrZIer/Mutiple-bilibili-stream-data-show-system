# Bilibili Live Stream Real-time Monitoring System

A real-time monitoring system for Bilibili live streams based on Django and Redis, supporting multi-room monitoring, real-time danmaku collection, gift statistics, and data visualization.

## 🌟 Features

- 🎯 **Multi-room Monitoring** - Monitor multiple live rooms simultaneously
- 💬 **Real-time Danmaku Collection** - Real-time acquisition and display of danmaku messages
- 🎁 **Gift Statistics Analysis** - Statistics on gift quantity, value, and trends
- 📊 **Data Visualization** - Django web interface for real-time data display
- 💾 **High-performance Storage** - Redis caching for fast data access
- ⚡ **Real-time Updates** - Auto-refresh and WebSocket real-time push
- 🔄 **Auto Restart** - Automatic recovery when services fail
- 🛠️ **Debug Tools** - Complete debugging and monitoring tools

## 📋 System Requirements

- **Python**: 3.8 or higher
- **Redis**: 6.0 or higher
- **Operating System**: Windows/Linux/macOS
- **Memory**: 4GB+ recommended
- **Network**: Stable internet connection

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/bilibili-live-monitor.git
cd bilibili-live-monitor
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Or use conda
conda install --file requirements.txt
```

### 3. Start Redis Service

```bash
# Windows (using chocolatey)
choco install redis-64
redis-server

# Linux (Ubuntu/Debian)
sudo apt-get install redis-server
sudo systemctl start redis

# macOS (using homebrew)
brew install redis
brew services start redis
```

### 4. Configure Django

```bash
cd bilibili-live-monitor-django

# Database migration
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic
```

### 5. Start the System

#### Method 1: One-click Start (Recommended)

```bash
# Return to project root directory
cd ..

# Start all services with one command
python setup.py
```

#### Method 2: Start Separately

```bash
# Terminal 1: Start data collector
cd web_version
python multi_room_collector.py

# Terminal 2: Start Django server
cd bilibili-live-monitor-django
python manage.py runserver 0.0.0.0:8000
```

### 6. Access the System

Open your browser and visit:

- 🏠 **Homepage**: http://localhost:8000/live/
- 📊 **Data Dashboard**: http://localhost:8000/live/dashboard/
- 💬 **Danmaku Browser**: http://localhost:8000/live/danmaku/
- 🔧 **Debug Page**: http://localhost:8000/live/debug/

## 📁 Project Structure

```
bilibili-live-monitor/
├── bilibili-live-monitor-django/     # Django Web Application
│   ├── bilibili_monitor/             # Django project configuration
│   ├── live_data/                    # Main application module
│   │   ├── templates/                # HTML templates
│   │   ├── static/                   # Static files
│   │   ├── management/               # Django management commands
│   │   └── ...
│   ├── utils/                        # Utility libraries
│   ├── static/                       # Global static files
│   ├── logs/                         # Log files
│   └── manage.py                     # Django management script
├── web_version/                      # Data collector
│   ├── multi_room_collector.py       # Multi-room collector
│   ├── simple_redis_saver.py         # Redis data saver
│   └── ...
├── live_data/                        # Historical data and tools
├── spider_live_data/                 # Data analysis tools
├── setup.py                         # One-click startup script
├── requirements.txt                  # Python dependencies
└── README.md                         # Project documentation
```

## ⚙️ Configuration

### Monitor Room Configuration

Edit the room ID list in `web_version/multi_room_collector.py`:

```python
# Default monitored room IDs
DEFAULT_ROOMS = [
    1962481108,  # Room 1
    1982728080,  # Room 2
    1959064353,  # Room 3
    # Add more room IDs...
]
```

### Redis Configuration

Edit `utils/redis_config.py`:

```python
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True,
    'max_connections': 50
}
```

### Django Configuration

Edit `bilibili_monitor/settings.py`:

```python
# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Redis configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
    }
}
```

## 🔧 Advanced Usage

### Custom Monitor Rooms

```bash
# Monitor specific rooms
python setup.py --rooms 1962481108,1982728080,1959064353

# Use configuration file
python setup.py --config custom_config.json
```

### Start Specific Services Only

```bash
# Django only
python setup.py --django-only

# Collector only
python setup.py --collector-only
```

### Using API

The system provides RESTful API endpoints:

```bash
# Get room danmaku data
curl http://localhost:8000/live/api/room/1962481108/danmaku/

# Get room gift data
curl http://localhost:8000/live/api/room/1962481108/gifts/

# Get room statistics
curl http://localhost:8000/live/api/room/1962481108/stats/
```

### Debug Mode

```bash
# Enable verbose debug information
python setup.py --no-background --status-display

# Check Redis data
python manage.py shell
>>> from utils.redis_handler import get_redis_client
>>> client = get_redis_client()
>>> client.keys('room:*')
```

## 🐛 Troubleshooting

### Common Issues

**Q: Collector process stops frequently**
```bash
# Check Redis connection
redis-cli ping

# View error logs
tail -f logs/collector.log

# Use debug mode
python setup.py --no-background
```

**Q: Encoding errors (UnicodeEncodeError)**
```bash
# Set environment variable on Windows
set PYTHONIOENCODING=utf-8

# Or set in code
os.environ['PYTHONIOENCODING'] = 'utf-8'
```

**Q: Cannot access Django**
```bash
# Check if port is occupied
netstat -an | grep 8000

# Use different port
python manage.py runserver 0.0.0.0:8080
```

**Q: Redis connection failed**
```bash
# Check Redis service status
redis-cli ping

# Start Redis on Windows
redis-server

# Start Redis on Linux
sudo systemctl start redis
```

### Log Files

- **Django logs**: `logs/django.log`
- **Collector logs**: `logs/collector.log`
- **Startup logs**: `startup.log`

## 🤝 Contributing

Issues and Pull Requests are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details


⭐ If this project helps you, please give it a star!