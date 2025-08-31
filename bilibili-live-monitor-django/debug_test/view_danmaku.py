import redis
import json
import time
from datetime import datetime

class DanmakuViewer:
    """弹幕数据查看器"""
    
    def __init__(self, room_id):
        self.room_id = room_id
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
    
    def view_stored_danmaku(self, count=20):
        """查看已存储的弹幕"""
        try:
            danmaku_key = f"room:{self.room_id}:danmaku"
            
            if not self.redis_client.exists(danmaku_key):
                print(f"❌ 房间 {self.room_id} 没有弹幕数据")
                return
            
            total_count = self.redis_client.llen(danmaku_key)
            print(f"📺 房间 {self.room_id} 弹幕数据 (共 {total_count} 条)")
            print("=" * 60)
            
            # 获取最新的弹幕
            danmaku_list = self.redis_client.lrange(danmaku_key, 0, count - 1)
            
            for i, danmaku_json in enumerate(danmaku_list):
                try:
                    danmaku = json.loads(danmaku_json)
                    timestamp = danmaku.get('timestamp', 0)
                    
                    # 转换时间戳
                    if timestamp:
                        if len(str(int(timestamp))) > 10:  # 毫秒时间戳
                            dt = datetime.fromtimestamp(timestamp / 1000)
                        else:  # 秒时间戳
                            dt = datetime.fromtimestamp(timestamp)
                        time_str = dt.strftime('%H:%M:%S')
                    else:
                        time_str = danmaku.get('time', 'Unknown')[:8]
                    
                    user = danmaku.get('user', 'Unknown')
                    content = danmaku.get('content', '')
                    
                    print(f"[{time_str}] {user}: {content}")
                    
                except json.JSONDecodeError:
                    print(f"[ERROR] 无法解析弹幕数据: {danmaku_json}")
                except Exception as e:
                    print(f"[ERROR] 处理弹幕数据失败: {e}")
            
        except Exception as e:
            print(f"❌ 查看弹幕数据失败: {e}")
    
    def monitor_real_time_danmaku(self):
        """实时监控弹幕"""
        try:
            print(f"🔴 开始实时监控房间 {self.room_id} 的弹幕...")
            print("按 Ctrl+C 停止监控")
            print("=" * 60)
            
            # 订阅Redis频道
            pubsub = self.redis_client.pubsub()
            channel = f'live_updates:room:{self.room_id}'
            pubsub.subscribe(channel)
            
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        
                        if data.get('type') == 'danmaku':
                            user = data.get('user', 'Unknown')
                            content = data.get('content', '')
                            timestamp = data.get('timestamp', time.time() * 1000)
                            
                            # 转换时间
                            dt = datetime.fromtimestamp(timestamp / 1000)
                            time_str = dt.strftime('%H:%M:%S')
                            
                            print(f"[{time_str}] {user}: {content}")
                    
                    except Exception as e:
                        print(f"[ERROR] 处理实时弹幕失败: {e}")
        
        except KeyboardInterrupt:
            print("\n🛑 停止实时监控")
        except Exception as e:
            print(f"❌ 实时监控失败: {e}")
    
    def view_room_stats(self):
        """查看房间统计"""
        try:
            current_key = f"room:{self.room_id}:current"
            counters_key = f"room:{self.room_id}:counters"
            
            current_data = self.redis_client.hgetall(current_key)
            counters_data = self.redis_client.hgetall(counters_key)
            
            print(f"📊 房间 {self.room_id} 统计信息")
            print("=" * 40)
            
            if current_data:
                print("当前数据:")
                for key, value in current_data.items():
                    print(f"  {key}: {value}")
            
            if counters_data:
                print("\n计数器:")
                for key, value in counters_data.items():
                    print(f"  {key}: {value}")
            
            if not current_data and not counters_data:
                print("❌ 没有统计数据")
        
        except Exception as e:
            print(f"❌ 查看统计失败: {e}")

def main():
    """主函数"""
    print("🎬 B站直播弹幕查看器")
    print("=" * 40)
    
    # 默认房间ID
    room_id = input("请输入房间ID (默认: 1923353057): ").strip()
    if not room_id:
        room_id = 1923353057
    else:
        room_id = int(room_id)
    
    viewer = DanmakuViewer(room_id)
    
    while True:
        print(f"\n请选择操作:")
        print("1. 查看已存储的弹幕")
        print("2. 实时监控弹幕")
        print("3. 查看房间统计")
        print("4. 退出")
        
        choice = input("请输入选择 (1-4): ").strip()
        
        if choice == '1':
            count = input("显示弹幕数量 (默认: 20): ").strip()
            count = int(count) if count.isdigit() else 20
            viewer.view_stored_danmaku(count)
            
        elif choice == '2':
            viewer.monitor_real_time_danmaku()
            
        elif choice == '3':
            viewer.view_room_stats()
            
        elif choice == '4':
            print("👋 再见!")
            break
            
        else:
            print("❌ 无效选择，请重新输入")

if __name__ == "__main__":
    main()