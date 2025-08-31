#!/usr/bin/env python
import os
import sys
import django
import redis

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

def test_csrf_fix():
    """测试CSRF修复"""
    print("🔍 测试CSRF修复...")
    
    # 1. 测试Django设置
    print("\n1️⃣ 检查Django CSRF设置:")
    try:
        from django.conf import settings
        print(f"✅ DEBUG: {settings.DEBUG}")
        print(f"✅ ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
        print(f"✅ CSRF_COOKIE_SECURE: {getattr(settings, 'CSRF_COOKIE_SECURE', '未设置')}")
        print(f"✅ CSRF_TRUSTED_ORIGINS: {getattr(settings, 'CSRF_TRUSTED_ORIGINS', '未设置')}")
    except Exception as e:
        print(f"❌ 设置检查失败: {e}")
    
    # 2. 测试简单GET请求
    print("\n2️⃣ 测试简单GET请求:")
    try:
        from django.test import Client
        client = Client()
        
        # 测试根路径重定向
        response = client.get('/')
        print(f"✅ GET / : HTTP {response.status_code}")
        
        # 测试live路径
        response = client.get('/live/')
        print(f"✅ GET /live/ : HTTP {response.status_code}")
        
        if response.status_code == 200:
            print("🎉 CSRF问题已修复！")
            content = response.content.decode('utf-8')
            if 'csrf' in content.lower():
                print("✅ 页面包含CSRF token")
        elif response.status_code == 400:
            print("❌ 仍然有HTTP 400错误")
        else:
            print(f"⚠️ 意外状态码: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试请求失败: {e}")
    
    # 3. 测试API接口
    print("\n3️⃣ 测试API接口:")
    try:
        from django.test import Client
        client = Client()
        
        api_endpoints = [
            '/live/api/redis/status/',
            '/live/api/system/stats/',
            '/live/api/rooms/',
        ]
        
        for endpoint in api_endpoints:
            try:
                response = client.get(endpoint)
                print(f"✅ GET {endpoint} : HTTP {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"   📄 响应: {data.get('success', 'unknown')}")
            except Exception as e:
                print(f"❌ GET {endpoint} : 失败 - {e}")
                
    except Exception as e:
        print(f"❌ API测试失败: {e}")
    
    # 4. 测试模板渲染
    print("\n4️⃣ 测试模板渲染:")
    try:
        from django.template.loader import render_to_string
        from django.template import Context, RequestContext
        from django.test import RequestFactory
        
        factory = RequestFactory()
        request = factory.get('/live/')
        
        # 测试简单模板渲染
        html = render_to_string('live_data/dashboard.html', {
            'system_stats': {
                'redis_status': 'connected',
                'redis_message': '测试消息',
                'total_rooms': 1,
                'active_rooms': 1,
                'total_danmaku': 100,
                'total_gifts': 10,
            },
            'active_rooms': [],
            'debug_info': {'test': 'success'}
        }, request=request)
        
        print(f"✅ 模板渲染成功，长度: {len(html)}")
        
        if 'csrf' in html.lower():
            print("✅ 模板包含CSRF处理")
        
    except Exception as e:
        print(f"❌ 模板渲染失败: {e}")

def check_redis_service():
    """检查Redis服务状态"""
    print("🔍 检查Redis连接状态...")
    
    # 测试不同的连接配置
    redis_configs = [
        {'host': 'localhost', 'port': 6379, 'db': 0},
        {'host': '127.0.0.1', 'port': 6379, 'db': 0},
        {'host': 'localhost', 'port': 6380, 'db': 0},  # 备用端口
    ]
    
    for i, config in enumerate(redis_configs, 1):
        print(f"\n{i}️⃣ 测试配置: {config}")
        try:
            client = redis.Redis(**config, decode_responses=True, socket_timeout=5)
            client.ping()
            print(f"✅ Redis连接成功！")
            
            # 测试基本操作
            client.set('test_key', 'test_value')
            value = client.get('test_key')
            client.delete('test_key')
            
            print(f"✅ Redis读写操作正常")
            print(f"📊 Redis信息: {client.info('server')['redis_version']}")
            return config
            
        except redis.ConnectionError as e:
            print(f"❌ 连接失败: {e}")
        except redis.TimeoutError as e:
            print(f"❌ 连接超时: {e}")
        except Exception as e:
            print(f"❌ 其他错误: {e}")
    
    return None

def check_redis_installation():
    """检查Redis是否已安装"""
    print("\n🔍 检查Redis安装状态...")
    
    try:
        import subprocess
        result = subprocess.run(['redis-server', '--version'], 
                              capture_output=True, text=True, timeout=5)
        print(f"✅ Redis已安装: {result.stdout.strip()}")
        return True
    except subprocess.TimeoutExpired:
        print("❌ Redis命令响应超时")
    except FileNotFoundError:
        print("❌ Redis未安装或不在PATH中")
        print("💡 请安装Redis:")
        print("   Windows: https://github.com/tporadowski/redis/releases")
        print("   或使用Docker: docker run -d -p 6379:6379 redis:latest")
    except Exception as e:
        print(f"❌ 检查Redis安装失败: {e}")
    
    return False

def start_redis_service():
    """尝试启动Redis服务"""
    print("\n🚀 尝试启动Redis服务...")
    
    try:
        import subprocess
        
        # Windows系统尝试启动服务
        if sys.platform == "win32":
            commands = [
                ['net', 'start', 'Redis'],  # Windows服务
                ['redis-server'],  # 直接启动
            ]
        else:
            commands = [
                ['sudo', 'systemctl', 'start', 'redis'],  # Linux systemd
                ['sudo', 'service', 'redis-server', 'start'],  # Linux service
                ['redis-server'],  # 直接启动
            ]
        
        for cmd in commands:
            try:
                print(f"尝试命令: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"✅ Redis启动成功")
                    return True
                else:
                    print(f"❌ 命令失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                print("❌ 命令超时")
            except FileNotFoundError:
                print("❌ 命令不存在")
            except Exception as e:
                print(f"❌ 执行失败: {e}")
    
    except Exception as e:
        print(f"❌ 启动Redis失败: {e}")
    
    return False

if __name__ == "__main__":
    test_csrf_fix()
    
    print("\n🚀 修复完成建议:")
    print("1. 重启Django服务器: python manage.py runserver")
    print("2. 访问 http://localhost:8000/live/")
    print("3. 检查浏览器开发者工具的Console和Network标签")
    print("4. 如果仍有问题，查看Django服务器日志")
    
    print("\n🔧 Redis连接诊断工具")
    print("=" * 50)
    
    # 1. 检查Redis安装
    if not check_redis_installation():
        print("\n💡 请先安装Redis后再重试")
        sys.exit(1)
    
    # 2. 检查连接
    working_config = check_redis_service()
    
    if working_config:
        print(f"\n🎉 Redis连接正常！使用配置: {working_config}")
        print("\n📋 建议在Django settings.py中使用此配置:")
        print(f"REDIS_CONFIG = {working_config}")
    else:
        print("\n❌ Redis连接失败，尝试启动Redis服务...")
        if start_redis_service():
            print("🔄 Redis启动后，重新检查连接...")
            working_config = check_redis_service()
            if working_config:
                print(f"🎉 现在Redis连接正常了！")
        
        if not working_config:
            print("\n💡 解决建议:")
            print("1. 确保Redis服务已启动")
            print("2. 检查防火墙设置")
            print("3. 确认Redis配置文件正确")
            print("4. 使用Docker运行Redis: docker run -d -p 6379:6379 redis:latest")