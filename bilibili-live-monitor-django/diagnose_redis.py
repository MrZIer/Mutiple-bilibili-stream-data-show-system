#!/usr/bin/env python
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

def diagnose_redis_connection():
    """诊断Redis连接问题"""
    print("🔍 Redis连接诊断开始...")
    
    # 1. 检查Redis服务是否运行
    print("\n1️⃣ 检查Redis服务状态:")
    try:
        import subprocess
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and 'PONG' in result.stdout:
            print("✅ Redis服务正在运行")
        else:
            print("❌ Redis服务未响应")
            print(f"   输出: {result.stdout}")
            print(f"   错误: {result.stderr}")
    except FileNotFoundError:
        print("❌ redis-cli 命令未找到，Redis可能未安装")
    except subprocess.TimeoutExpired:
        print("❌ Redis连接超时")
    except Exception as e:
        print(f"❌ 检查Redis服务失败: {e}")
    
    # 2. 检查Python Redis库
    print("\n2️⃣ 检查Python Redis库:")
    try:
        import redis
        print(f"✅ Redis库已安装，版本: {redis.__version__}")
    except ImportError:
        print("❌ Redis库未安装，请运行: pip install redis")
        return
    
    # 3. 测试基本Redis连接
    print("\n3️⃣ 测试基本Redis连接:")
    try:
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        client.ping()
        print("✅ Redis连接成功")
        
        # 检查数据库内容
        keys = client.keys('*')
        print(f"✅ Redis数据库包含 {len(keys)} 个键")
        
        # 检查房间相关的键
        room_keys = client.keys('room:*')
        print(f"✅ 找到 {len(room_keys)} 个房间相关的键")
        
        if room_keys:
            print("   房间键示例:")
            for key in room_keys[:5]:  # 只显示前5个
                print(f"   - {key}")
        
    except redis.ConnectionError:
        print("❌ Redis连接失败 - 连接被拒绝")
        print("   请确保Redis服务正在运行")
    except redis.TimeoutError:
        print("❌ Redis连接超时")
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
    
    # 4. 测试DanmakuService
    print("\n4️⃣ 测试DanmakuService:")
    try:
        from live_data.danmaku_services import DanmakuService
        service = DanmakuService()
        
        if service.redis_client:
            print("✅ DanmakuService Redis客户端已初始化")
            
            # 测试获取房间列表
            rooms = service.get_available_rooms()
            print(f"✅ 找到 {len(rooms)} 个房间")
            
            if rooms:
                print("   房间列表:")
                for room in rooms[:3]:  # 只显示前3个
                    print(f"   - 房间{room['room_id']}: {room['uname']} (弹幕: {room['danmaku_count']})")
            
            # 测试系统统计
            stats = service.get_system_stats()
            print(f"✅ 系统统计: {stats}")
            
        else:
            print("❌ DanmakuService Redis客户端初始化失败")
            
    except Exception as e:
        print(f"❌ DanmakuService测试失败: {e}")
    
    # 5. 检查Django设置
    print("\n5️⃣ 检查Django Redis设置:")
    try:
        from django.conf import settings
        redis_host = getattr(settings, 'REDIS_HOST', 'localhost')
        redis_port = getattr(settings, 'REDIS_PORT', 6379)
        redis_db = getattr(settings, 'REDIS_DB', 0)
        
        print(f"✅ Django Redis配置:")
        print(f"   主机: {redis_host}")
        print(f"   端口: {redis_port}")
        print(f"   数据库: {redis_db}")
        
    except Exception as e:
        print(f"❌ Django设置检查失败: {e}")

def check_redis_data():
    """检查Redis中的具体数据"""
    print("\n6️⃣ 检查Redis数据内容:")
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # 检查是否有房间数据
        room_pattern = "room:*:danmaku"
        danmaku_keys = client.keys(room_pattern)
        
        if danmaku_keys:
            print(f"✅ 找到 {len(danmaku_keys)} 个弹幕数据键")
            
            for key in danmaku_keys[:3]:  # 检查前3个房间
                room_id = key.split(':')[1]
                danmaku_count = client.llen(key)
                
                # 获取房间信息
                info_key = f"room:{room_id}:info"
                room_info = client.hgetall(info_key)
                
                print(f"   房间 {room_id}:")
                print(f"     弹幕数量: {danmaku_count}")
                print(f"     主播: {room_info.get('uname', '未知')}")
                print(f"     标题: {room_info.get('title', '未知')}")
                
                # 获取最新的几条弹幕
                recent_danmaku = client.lrange(key, 0, 2)
                if recent_danmaku:
                    print(f"     最近弹幕:")
                    for dm in recent_danmaku:
                        try:
                            import json
                            dm_data = json.loads(dm)
                            print(f"       {dm_data.get('username', '?')}: {dm_data.get('message', '')[:50]}")
                        except:
                            print(f"       {dm[:100]}")
        else:
            print("❌ 没有找到弹幕数据")
            print("   请确保数据收集器正在运行:")
            print("   cd g:\\Github_Project\\bilibili_data\\web_version\\")
            print("   python real_time_collector.py 24486091")
            
    except Exception as e:
        print(f"❌ 检查Redis数据失败: {e}")

if __name__ == "__main__":
    diagnose_redis_connection()
    check_redis_data()
    
    print("\n💡 如果Redis未运行，请执行以下步骤:")
    print("1. Windows: 下载并启动Redis服务器")
    print("2. Linux/Mac: sudo systemctl start redis 或 brew services start redis")
    print("3. 或者使用Docker: docker run -d -p 6379:6379 redis:latest")
    
    print("\n💡 如果Redis运行但没有数据，请启动数据收集器:")
    print("cd g:\\Github_Project\\bilibili_data\\web_version\\")
    print("python real_time_collector.py 24486091")