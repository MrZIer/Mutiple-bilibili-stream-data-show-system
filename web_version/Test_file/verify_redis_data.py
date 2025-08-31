from web_version.simple_redis_saver import get_redis_saver
import json

def verify_redis_data():
    """验证Redis中的数据"""
    try:
        redis_saver = get_redis_saver()
        
        print("🔍 检查Redis数据...")
        
        # 获取所有活跃房间
        active_rooms = redis_saver.get_all_active_rooms()
        print(f"📋 活跃房间: {active_rooms}")
        
        for room_id in active_rooms:
            print(f"\n=== 房间 {room_id} ===")
            room_data = redis_saver.get_room_data(room_id)
            
            # 房间信息
            room_info = room_data.get('room_info', {})
            print(f"房间名: {room_info.get('uname', 'Unknown')}")
            print(f"标题: {room_info.get('title', 'Unknown')}")
            print(f"直播状态: {room_info.get('live_status', 'Unknown')}")
            
            # 统计数据
            print(f"总弹幕: {room_data.get('total_danmaku', 0)}")
            print(f"总礼物: {room_data.get('total_gifts', 0)}")
            
            # 最新弹幕
            recent_danmaku = room_data.get('recent_danmaku', [])
            print(f"最新弹幕 ({len(recent_danmaku)} 条):")
            for i, danmaku in enumerate(recent_danmaku[:5]):
                print(f"  {i+1}. {danmaku.get('username', 'Unknown')}: {danmaku.get('message', '')}")
        
        if not active_rooms:
            print("❌ 没有找到活跃房间数据")
            print("💡 请先运行数据收集器: python fixed_data_collector.py test")
    
    except Exception as e:
        print(f"❌ 验证失败: {e}")

if __name__ == "__main__":
    verify_redis_data()