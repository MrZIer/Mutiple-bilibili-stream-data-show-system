import redis
import json
from datetime import datetime

class InteractiveDanmakuBrowser:
    """交互式弹幕浏览器"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost', port=6379, db=0, decode_responses=True
        )
        self.current_room = None
    
    def run(self):
        """运行交互式界面"""
        print("🎬 Redis弹幕数据浏览器")
        print("=" * 50)
        
        while True:
            try:
                self.show_menu()
                choice = input("\n请选择操作 (1-7): ").strip()
                
                if choice == '1':
                    self.list_rooms()
                elif choice == '2':
                    self.select_room()
                elif choice == '3':
                    self.search_by_keyword()
                elif choice == '4':
                    self.search_by_user()
                elif choice == '5':
                    self.browse_recent()
                elif choice == '6':
                    self.show_stats()
                elif choice == '7':
                    print("👋 再见!")
                    break
                else:
                    print("❌ 无效选择")
                    
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 操作失败: {e}")
    
    def show_menu(self):
        """显示菜单"""
        current_info = f" (当前: {self.current_room})" if self.current_room else ""
        print(f"\n📋 菜单{current_info}:")
        print("1. 列出所有房间")
        print("2. 选择房间")
        print("3. 关键词搜索")
        print("4. 用户搜索")
        print("5. 浏览最近弹幕")
        print("6. 查看统计信息")
        print("7. 退出")
    
    def list_rooms(self):
        """列出所有房间"""
        pattern = "room:*:danmaku"
        keys = self.redis_client.keys(pattern)
        
        if not keys:
            print("❌ 没有找到弹幕数据")
            return
        
        print("\n📋 有弹幕数据的房间:")
        for key in keys:
            room_id = key.split(':')[1]
            count = self.redis_client.llen(key)
            
            # 获取房间信息
            info_key = f"room:{room_id}:info"
            room_info = self.redis_client.hgetall(info_key)
            uname = room_info.get('uname', f'主播{room_id}')
            
            print(f"  🏠 房间 {room_id}: {uname} ({count} 条弹幕)")
    
    def select_room(self):
        """选择房间"""
        room_id = input("请输入房间ID: ").strip()
        
        if not room_id.isdigit():
            print("❌ 房间ID必须是数字")
            return
        
        danmaku_key = f"room:{room_id}:danmaku"
        if not self.redis_client.exists(danmaku_key):
            print(f"❌ 房间 {room_id} 没有弹幕数据")
            return
        
        self.current_room = int(room_id)
        count = self.redis_client.llen(danmaku_key)
        print(f"✅ 已选择房间 {room_id} ({count} 条弹幕)")
    
    def search_by_keyword(self):
        """关键词搜索"""
        if not self.current_room:
            print("❌ 请先选择房间")
            return
        
        keyword = input("请输入搜索关键词: ").strip()
        if not keyword:
            print("❌ 关键词不能为空")
            return
        
        limit = input("结果数量限制 (默认20): ").strip()
        limit = int(limit) if limit.isdigit() else 20
        
        results = self._search_keyword(self.current_room, keyword, limit)
        self._display_results(results, f"关键词 '{keyword}'")
    
    def search_by_user(self):
        """用户搜索"""
        if not self.current_room:
            print("❌ 请先选择房间")
            return
        
        username = input("请输入用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            return
        
        limit = input("结果数量限制 (默认20): ").strip()
        limit = int(limit) if limit.isdigit() else 20
        
        results = self._search_user(self.current_room, username, limit)
        self._display_results(results, f"用户 '{username}'")
    
    def browse_recent(self):
        """浏览最近弹幕"""
        if not self.current_room:
            print("❌ 请先选择房间")
            return
        
        limit = input("显示数量 (默认20): ").strip()
        limit = int(limit) if limit.isdigit() else 20
        
        danmaku_key = f"room:{self.current_room}:danmaku"
        recent_danmaku = self.redis_client.lrange(danmaku_key, 0, limit-1)
        
        results = []
        for danmaku_json in recent_danmaku:
            try:
                results.append(json.loads(danmaku_json))
            except:
                continue
        
        self._display_results(results, "最近弹幕")
    
    def show_stats(self):
        """显示统计信息"""
        if not self.current_room:
            print("❌ 请先选择房间")
            return
        
        # 房间信息
        info_key = f"room:{self.current_room}:info"
        room_info = self.redis_client.hgetall(info_key)
        
        # 计数器
        counter_key = f"room:{self.current_room}:counters"
        counters = self.redis_client.hgetall(counter_key)
        
        # 弹幕总数
        danmaku_key = f"room:{self.current_room}:danmaku"
        danmaku_count = self.redis_client.llen(danmaku_key)
        
        print(f"\n📊 房间 {self.current_room} 统计信息:")
        print("-" * 50)
        print(f"🏠 主播: {room_info.get('uname', 'Unknown')}")
        print(f"📺 标题: {room_info.get('title', 'Unknown')}")
        print(f"🔴 状态: {'直播中' if room_info.get('live_status') == '1' else '未开播'}")
        print(f"💬 弹幕总数: {danmaku_count}")
        print(f"🎁 礼物总数: {counters.get('total_gifts', 0)}")
        print(f"📅 创建时间: {room_info.get('created_at', 'Unknown')}")
    
    def _search_keyword(self, room_id, keyword, limit):
        """搜索关键词"""
        danmaku_key = f"room:{room_id}:danmaku"
        all_danmaku = self.redis_client.lrange(danmaku_key, 0, -1)
        
        results = []
        for danmaku_json in all_danmaku:
            try:
                danmaku = json.loads(danmaku_json)
                if keyword.lower() in danmaku.get('message', '').lower():
                    results.append(danmaku)
                    if len(results) >= limit:
                        break
            except:
                continue
        
        return results
    
    def _search_user(self, room_id, username, limit):
        """搜索用户"""
        danmaku_key = f"room:{room_id}:danmaku"
        all_danmaku = self.redis_client.lrange(danmaku_key, 0, -1)
        
        results = []
        for danmaku_json in all_danmaku:
            try:
                danmaku = json.loads(danmaku_json)
                if username.lower() == danmaku.get('username', '').lower():
                    results.append(danmaku)
                    if len(results) >= limit:
                        break
            except:
                continue
        
        return results
    
    def _display_results(self, results, search_type):
        """显示结果"""
        if not results:
            print(f"❌ 没有找到匹配 {search_type} 的弹幕")
            return
        
        print(f"\n📋 找到 {len(results)} 条匹配 {search_type} 的弹幕:")
        print("-" * 80)
        
        for i, danmaku in enumerate(results, 1):
            time_str = danmaku.get('send_time_formatted', 'Unknown')
            username = danmaku.get('username', 'Unknown')
            message = danmaku.get('message', '')
            
            # 限制显示长度
            username = username[:15] + '...' if len(username) > 15 else username
            message = message[:60] + '...' if len(message) > 60 else message
            
            print(f"{i:3d}. [{time_str}] {username}: {message}")

if __name__ == "__main__":
    browser = InteractiveDanmakuBrowser()
    browser.run()