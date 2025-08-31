#!/usr/bin/env python
import os
import sys
import django
import traceback

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

def debug_redis_status():
    """调试Redis状态显示问题"""
    print("🔍 调试Redis状态显示问题...")
    
    # 1. 测试DanmakuService初始化
    print("\n1️⃣ 测试DanmakuService初始化:")
    try:
        from live_data.danmaku_services import DanmakuService
        service = DanmakuService()
        print(f"✅ DanmakuService创建成功")
        print(f"   连接状态: {service.connection_status}")
        print(f"   Redis客户端: {service.redis_client}")
    except Exception as e:
        print(f"❌ DanmakuService创建失败: {e}")
        traceback.print_exc()
        return
    
    # 2. 测试连接状态获取
    print("\n2️⃣ 测试连接状态获取:")
    try:
        status_info = service.get_connection_status()
        print(f"✅ 连接状态信息: {status_info}")
    except Exception as e:
        print(f"❌ 获取连接状态失败: {e}")
        traceback.print_exc()
    
    # 3. 测试系统统计获取
    print("\n3️⃣ 测试系统统计获取:")
    try:
        stats = service.get_system_stats()
        print(f"✅ 系统统计: {stats}")
    except Exception as e:
        print(f"❌ 获取系统统计失败: {e}")
        traceback.print_exc()
    
    # 4. 测试Redis直接连接
    print("\n4️⃣ 测试Redis直接连接:")
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        result = client.ping()
        print(f"✅ Redis直接连接成功: {result}")
        
        # 检查键数量
        keys = client.keys('*')
        print(f"✅ Redis键数量: {len(keys)}")
        
        # 检查房间键
        room_keys = client.keys('room:*')
        print(f"✅ 房间键数量: {len(room_keys)}")
        
    except Exception as e:
        print(f"❌ Redis直接连接失败: {e}")
        traceback.print_exc()
    
    # 5. 测试视图函数
    print("\n5️⃣ 测试Dashboard视图:")
    try:
        from django.test import Client
        client = Client()
        response = client.get('/live/')
        print(f"✅ Dashboard响应状态: {response.status_code}")
        
        # 检查响应内容
        content = response.content.decode('utf-8')
        if 'Redis连接正常' in content:
            print("✅ 页面显示Redis连接正常")
        elif 'Redis连接失败' in content:
            print("⚠️ 页面显示Redis连接失败")
        elif '未知' in content:
            print("❌ 页面显示未知状态")
        else:
            print("⚠️ 页面Redis状态不明确")
            
    except Exception as e:
        print(f"❌ 测试Dashboard视图失败: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    debug_redis_status()