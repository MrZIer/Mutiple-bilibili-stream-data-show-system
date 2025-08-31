#!/usr/bin/env python
import os
import sys
import django
import traceback

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

def diagnose_400_error():
    """诊断HTTP 400错误"""
    print("🔍 诊断HTTP 400错误...")
    
    # 1. 检查Django设置
    print("\n1️⃣ 检查Django设置:")
    try:
        from django.conf import settings
        print(f"✅ DEBUG: {settings.DEBUG}")
        print(f"✅ ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
        print(f"✅ SECRET_KEY存在: {'SECRET_KEY' in dir(settings)}")
        print(f"✅ DATABASES: {settings.DATABASES}")
    except Exception as e:
        print(f"❌ Django设置检查失败: {e}")
        traceback.print_exc()
    
    # 2. 检查URL配置
    print("\n2️⃣ 检查URL配置:")
    try:
        from django.urls import reverse, resolve
        
        # 测试reverse
        try:
            dashboard_url = reverse('live_data:dashboard')
            print(f"✅ Dashboard URL reverse: {dashboard_url}")
        except Exception as e:
            print(f"❌ Dashboard URL reverse失败: {e}")
        
        # 测试resolve
        try:
            resolved = resolve('/live/')
            print(f"✅ /live/ resolve成功: {resolved.func.__name__}")
        except Exception as e:
            print(f"❌ /live/ resolve失败: {e}")
            
    except Exception as e:
        print(f"❌ URL配置检查失败: {e}")
        traceback.print_exc()
    
    # 3. 测试模板
    print("\n3️⃣ 检查模板:")
    try:
        from django.template.loader import get_template
        template = get_template('live_data/dashboard.html')
        print(f"✅ Dashboard模板加载成功: {template}")
    except Exception as e:
        print(f"❌ Dashboard模板加载失败: {e}")
        traceback.print_exc()
    
    # 4. 测试DanmakuService
    print("\n4️⃣ 测试DanmakuService:")
    try:
        from live_data.danmaku_services import DanmakuService
        service = DanmakuService()
        print(f"✅ DanmakuService初始化成功")
        
        # 测试get_system_stats
        stats = service.get_system_stats()
        print(f"✅ 系统统计: {stats}")
        
        # 测试get_available_rooms
        rooms = service.get_available_rooms()
        print(f"✅ 房间数量: {len(rooms)}")
        
    except Exception as e:
        print(f"❌ DanmakuService测试失败: {e}")
        traceback.print_exc()
    
    # 5. 直接测试视图函数
    print("\n5️⃣ 直接测试视图函数:")
    try:
        from live_data.views import dashboard
        from django.http import HttpRequest
        
        # 创建假请求
        request = HttpRequest()
        request.method = 'GET'
        request.META['HTTP_HOST'] = 'localhost:8000'
        
        # 调用视图函数
        response = dashboard(request)
        print(f"✅ 视图函数调用成功: HTTP {response.status_code}")
        
        if hasattr(response, 'content'):
            content = response.content.decode('utf-8')
            print(f"✅ 响应内容长度: {len(content)}")
            
            # 检查关键内容
            if 'Redis连接正常' in content:
                print("✅ 响应包含: Redis连接正常")
            elif 'Redis连接失败' in content:
                print("⚠️ 响应包含: Redis连接失败")
            elif 'redis_status' in content:
                print("✅ 响应包含: redis_status变量")
            else:
                print("❌ 响应不包含Redis状态信息")
                
        if hasattr(response, 'context_data'):
            print(f"✅ 上下文数据: {response.context_data}")
            
    except Exception as e:
        print(f"❌ 直接测试视图函数失败: {e}")
        traceback.print_exc()
    
    # 6. 使用Django测试客户端
    print("\n6️⃣ 使用Django测试客户端 (详细模式):")
    try:
        from django.test import Client
        from django.test.utils import override_settings
        
        # 确保DEBUG=True以获得详细错误信息
        with override_settings(DEBUG=True):
            client = Client()
            response = client.get('/live/', follow=True)
            
            print(f"✅ 测试客户端响应状态: {response.status_code}")
            print(f"✅ 响应头: {dict(response.items())}")
            
            if response.status_code == 400:
                print("❌ HTTP 400 Bad Request")
                content = response.content.decode('utf-8')
                
                # 查找错误信息
                if 'CSRF' in content:
                    print("   可能原因: CSRF token问题")
                elif 'Bad Request' in content:
                    print("   可能原因: 请求格式问题")
                elif 'template' in content.lower():
                    print("   可能原因: 模板问题")
                else:
                    print("   详细错误内容:")
                    print(content[:1000])  # 显示前1000个字符
            
            elif response.status_code == 200:
                print("✅ HTTP 200 OK")
                content = response.content.decode('utf-8')
                
                # 检查Redis状态
                if 'Redis连接正常' in content:
                    print("✅ 页面显示: Redis连接正常")
                elif 'Redis连接失败' in content:
                    print("⚠️ 页面显示: Redis连接失败")
                elif '未知' in content and 'Redis' in content:
                    print("❌ 页面显示: Redis状态未知")
                else:
                    print("⚠️ 页面Redis状态信息不明确")
                    
                    # 搜索system_stats相关内容
                    if 'system_stats' in content:
                        print("✅ 页面包含system_stats变量")
                    else:
                        print("❌ 页面不包含system_stats变量")
                        
            else:
                print(f"❌ 意外的HTTP状态码: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Django测试客户端失败: {e}")
        traceback.print_exc()

def check_redis_connection():
    """检查Redis连接"""
    print("\n🔗 检查Redis连接:")
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        result = client.ping()
        print(f"✅ Redis Ping: {result}")
        
        # 检查数据
        keys = client.keys('room:*')
        print(f"✅ 房间相关键数量: {len(keys)}")
        
        if keys:
            # 显示一些示例数据
            sample_key = keys[0]
            print(f"✅ 示例键: {sample_key}")
            
            if 'danmaku' in sample_key:
                count = client.llen(sample_key)
                print(f"✅ 该键的数据量: {count}")
                
        return True
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        return False

if __name__ == "__main__":
    redis_ok = check_redis_connection()
    diagnose_400_error()
    
    print("\n💡 修复建议:")
    if not redis_ok:
        print("1. 启动Redis服务器: redis-server 或 docker run -d -p 6379:6379 redis:latest")
        print("2. 启动数据收集器: python real_time_collector.py 24486091")
    
    print("3. 检查Django日志输出，查看详细错误信息")
    print("4. 确保模板文件存在且格式正确")
    print("5. 尝试重启Django服务器")