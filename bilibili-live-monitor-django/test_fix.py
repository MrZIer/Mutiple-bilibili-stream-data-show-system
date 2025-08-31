#!/usr/bin/env python
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')

def test_imports():
    """测试导入问题"""
    print("🔍 测试导入...")
    
    try:
        django.setup()
        print("✅ Django设置成功")
    except Exception as e:
        print(f"❌ Django设置失败: {e}")
        return False
    
    try:
        from live_data import views
        print("✅ views导入成功")
    except Exception as e:
        print(f"❌ views导入失败: {e}")
        return False
    
    try:
        from live_data.danmaku_services import DanmakuService
        print("✅ DanmakuService导入成功")
    except Exception as e:
        print(f"❌ DanmakuService导入失败: {e}")
        return False
    
    try:
        from django.urls import reverse
        dashboard_url = reverse('live_data:dashboard')
        print(f"✅ URL解析成功: {dashboard_url}")
    except Exception as e:
        print(f"❌ URL解析失败: {e}")
        return False
    
    return True

def test_redis_connection():
    """测试Redis连接"""
    print("\n🔗 测试Redis连接...")
    
    try:
        from live_data.danmaku_services import DanmakuService
        service = DanmakuService()
        rooms = service.get_available_rooms()
        print(f"✅ Redis连接成功，找到 {len(rooms)} 个房间")
        return True
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        return False

def test_api_views():
    """测试API视图"""
    print("\n🌐 测试API视图...")
    
    try:
        from django.test import Client
        client = Client()
        
        # 测试系统统计API
        response = client.get('/live/api/system/stats/')
        print(f"✅ 系统统计API: HTTP {response.status_code}")
        
        # 测试房间列表API
        response = client.get('/live/api/rooms/')
        print(f"✅ 房间列表API: HTTP {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ API测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🛠️ 开始全面测试...")
    
    success = True
    success &= test_imports()
    success &= test_redis_connection()
    success &= test_api_views()
    
    print(f"\n{'🎉 所有测试通过!' if success else '❌ 测试失败，请检查错误信息'}")