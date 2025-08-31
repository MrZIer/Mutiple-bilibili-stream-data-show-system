#!/usr/bin/env python
import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

from django.urls import reverse, resolve
from django.test import Client
from django.conf import settings

def test_url_patterns():
    """测试URL模式"""
    print("🔍 测试URL路由配置...")
    
    # 测试页面URL
    try:
        dashboard_url = reverse('live_data:dashboard')
        print(f"✅ Dashboard URL: {dashboard_url}")
    except Exception as e:
        print(f"❌ Dashboard URL错误: {e}")
    
    try:
        danmaku_url = reverse('live_data:danmaku_browser')
        print(f"✅ 弹幕浏览器URL: {danmaku_url}")
    except Exception as e:
        print(f"❌ 弹幕浏览器URL错误: {e}")
    
    # 测试API URL
    api_urls = [
        '/api/rooms/',
        '/api/room/24486091/stats/',
        '/api/room/24486091/danmaku/',
        '/api/room/24486091/gifts/',
        '/api/system/stats/',
        '/api/redis/status/',
    ]
    
    client = Client()
    
    for url in api_urls:
        try:
            # 只测试URL解析，不实际请求
            resolved = resolve(url)
            print(f"✅ API URL解析成功: {url} -> {resolved.func.__name__}")
        except Exception as e:
            print(f"❌ API URL解析失败: {url} -> {e}")

def test_api_requests():
    """测试API请求"""
    print("\n🌐 测试API请求...")
    
    client = Client()
    
    # 测试API请求
    test_urls = [
        '/api/rooms/',
        '/api/system/stats/',
        '/api/redis/status/',
    ]
    
    for url in test_urls:
        try:
            response = client.get(url)
            print(f"✅ {url}: HTTP {response.status_code}")
            if response.status_code == 200:
                # 尝试解析JSON
                try:
                    data = response.json()
                    print(f"   📄 响应: {data.get('success', 'unknown')}")
                except:
                    print("   📄 响应: 非JSON格式")
        except Exception as e:
            print(f"❌ {url}: 请求失败 - {e}")

if __name__ == "__main__":
    test_url_patterns()
    test_api_requests()