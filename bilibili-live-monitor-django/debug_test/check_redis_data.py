import redis
import json
from datetime import datetime
import sys

def check_redis_data(test_mode=False):
    """检查Redis中的数据"""
    try:
        # 连接Redis
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        
        # 测试连接
        redis_client.ping()
        print("✅ Redis连接成功")
        
        # 查看所有键
        all_keys = redis_client.keys("*")
        print(f"\n📋 Redis中共有 {len(all_keys)} 个键:")
        
        if not all_keys:
            print("❌ Redis中没有数据！")
            return False
        
        # 分类显示键
        room_keys = [k for k in all_keys if k.startswith('room:')]
        monitor_keys = [k for k in all_keys if k.startswith('monitor:')]
        
        print(f"\n🏠 房间相关键 ({len(room_keys)} 个):")
        for key in room_keys[:10]:  # 只显示前10个
            key_type = redis_client.type(key)
            print(f"  - {key} ({key_type})")
        
        print(f"\n📊 监控相关键 ({len(monitor_keys)} 个):")
        for key in monitor_keys:
            key_type = redis_client.type(key)
            print(f"  - {key} ({key_type})")
        
        # 检查具体房间数据
        test_room_id = 24486091
        print(f"\n🔍 检查房间 {test_room_id} 的数据:")
        
        # 房间基本信息
        info_key = f"room:{test_room_id}:info"
        if redis_client.exists(info_key):
            info_data = redis_client.hgetall(info_key)
            print(f"  房间信息: {info_data}")
        else:
            print("  ❌ 没有房间信息")
        
        # 当前数据
        current_key = f"room:{test_room_id}:current"
        if redis_client.exists(current_key):
            current_data = redis_client.hgetall(current_key)
            print(f"  当前数据: {current_data}")
        else:
            print("  ❌ 没有当前数据")
        
        # 弹幕数据
        danmaku_key = f"room:{test_room_id}:danmaku"
        if redis_client.exists(danmaku_key):
            danmaku_count = redis_client.llen(danmaku_key)
            print(f"  弹幕数据: 共 {danmaku_count} 条")
            
            # 显示最新几条弹幕
            if danmaku_count > 0:
                recent_danmaku = redis_client.lrange(danmaku_key, 0, 4)
                print("  最新弹幕:")
                for i, danmaku_json in enumerate(recent_danmaku):
                    try:
                        danmaku = json.loads(danmaku_json)
                        print(f"    {i+1}. {danmaku.get('user', 'Unknown')}: {danmaku.get('content', '')}")
                    except:
                        print(f"    {i+1}. [解析失败] {danmaku_json}")
        else:
            print("  ❌ 没有弹幕数据")
        
        # 礼物数据
        gift_key = f"room:{test_room_id}:gifts"
        if redis_client.exists(gift_key):
            gift_count = redis_client.llen(gift_key)
            print(f"  礼物数据: 共 {gift_count} 条")
        else:
            print("  ❌ 没有礼物数据")
        
        # 时序数据流
        stream_key = f"room:{test_room_id}:stream"
        if redis_client.exists(stream_key):
            stream_info = redis_client.xinfo_stream(stream_key)
            print(f"  时序数据流: 共 {stream_info['length']} 条记录")
        else:
            print("  ❌ 没有时序数据流")
        
        # 测试模式下，检查特定房间ID
        if test_mode:
            test_room_ids = [17961, 12345, 67890]  # 示例房间ID
            for room_id in test_room_ids:
                print(f"\n🔍 测试模式 - 检查房间 {room_id} 的数据:")
                # 房间基本信息
                info_key = f"room:{room_id}:info"
                if redis_client.exists(info_key):
                    info_data = redis_client.hgetall(info_key)
                    print(f"  房间信息: {info_data}")
                else:
                    print("  ❌ 没有房间信息")
                
                # 当前数据
                current_key = f"room:{room_id}:current"
                if redis_client.exists(current_key):
                    current_data = redis_client.hgetall(current_key)
                    print(f"  当前数据: {current_data}")
                else:
                    print("  ❌ 没有当前数据")
                
                # 弹幕数据
                danmaku_key = f"room:{room_id}:danmaku"
                if redis_client.exists(danmaku_key):
                    danmaku_count = redis_client.llen(danmaku_key)
                    print(f"  弹幕数据: 共 {danmaku_count} 条")
                    
                    # 显示最新几条弹幕
                    if danmaku_count > 0:
                        recent_danmaku = redis_client.lrange(danmaku_key, 0, 4)
                        print("  最新弹幕:")
                        for i, danmaku_json in enumerate(recent_danmaku):
                            try:
                                danmaku = json.loads(danmaku_json)
                                print(f"    {i+1}. {danmaku.get('user', 'Unknown')}: {danmaku.get('content', '')}")
                            except:
                                print(f"    {i+1}. [解析失败] {danmaku_json}")
                else:
                    print("  ❌ 没有弹幕数据")
                
                # 礼物数据
                gift_key = f"room:{room_id}:gifts"
                if redis_client.exists(gift_key):
                    gift_count = redis_client.llen(gift_key)
                    print(f"  礼物数据: 共 {gift_count} 条")
                else:
                    print("  ❌ 没有礼物数据")
                
                # 时序数据流
                stream_key = f"room:{room_id}:stream"
                if redis_client.exists(stream_key):
                    stream_info = redis_client.xinfo_stream(stream_key)
                    print(f"  时序数据流: 共 {stream_info['length']} 条记录")
                else:
                    print("  ❌ 没有时序数据流")
        
        return True
        
    except redis.ConnectionError:
        print("❌ Redis连接失败！请确保Redis服务已启动")
        return False
    except Exception as e:
        print(f"❌ 检查Redis数据失败: {e}")
        return False

if __name__ == "__main__":
    # 检查是否为测试模式
    test_mode = len(sys.argv) > 1 and sys.argv[1] == "test"
    check_redis_data(test_mode)