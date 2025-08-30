import asyncio
from bilibili_api import live
from datetime import datetime
import threading
import os
from live_data_visualizer import init_visualizer, get_visualizer
from data_storage import init_storage, get_storage

# 存储多个直播间的数据
room_data = {}

class RoomMonitor:
    def __init__(self, room_id):
        self.room_id = room_id
        self.popularity = 0
        self.watched = 0
        self.likes = 0
        self.last_update = ""
        
    def get_timestamp(self):
        return datetime.now().strftime("%H:%M:%S")
    
    def print_status(self):
        print(f"📊 [{self.last_update}] [房间{self.room_id}状态] 人气: {self.popularity} | 观看: {self.watched} | 点赞: {self.likes}")

async def monitor_room(room_id):
    """监听单个直播间"""
    monitor = RoomMonitor(room_id)
    room_data[room_id] = monitor
    
    try:
        room = live.LiveDanmaku(room_id)
        storage = get_storage()
        
        # 添加连接状态检查
        print(f"🔍 正在连接房间 {room_id}...")
        
        @room.on('DANMU_MSG')
        async def on_danmaku(event):
            try:
                info = event["data"]["info"]
                username = info[2][1]
                message = info[1]
                timestamp = monitor.get_timestamp()
                print(f"💬 [{timestamp}] [房间{room_id}弹幕] {username}: {message}")
                
                # 添加到可视化器和存储
                vis = get_visualizer()
                if vis:
                    vis.add_data(room_id, 'danmaku', 1, {
                        'username': username,
                        'message': message
                    })
                    
            except (KeyError, IndexError) as e:
                print(f"❌ [房间{room_id}] 解析弹幕数据时出错: {e}")
        
        @room.on('SEND_GIFT')
        async def on_gift(event):
            try:
                data = event["data"]["data"]
                username = data["uname"]
                gift_name = data["giftName"]
                num = data["num"]
                timestamp = monitor.get_timestamp()
                print(f"🎁 [{timestamp}] [房间{room_id}礼物] {username} 送出 {gift_name} x{num}")
                
                # 添加到可视化器和存储
                vis = get_visualizer()
                if vis:
                    vis.add_data(room_id, 'gift', num, {
                        'username': username,
                        'gift_name': gift_name
                    })
                    
            except KeyError as e:
                print(f"❌ [房间{room_id}] 解析礼物数据时出错: {e}")
        
        @room.on('LIKE_INFO_V3_UPDATE')
        async def on_like_update(event):
            try:
                data = event["data"]["data"]
                click_count = data.get("click_count", 0)
                monitor.likes = click_count
                monitor.last_update = monitor.get_timestamp()
                print(f"👍 [{monitor.last_update}] [房间{room_id}点赞] 当前点赞数: {click_count}")
                
                # 添加到可视化器和存储
                vis = get_visualizer()
                if vis:
                    vis.add_data(room_id, 'likes', click_count)
                    
            except KeyError as e:
                print(f"❌ [房间{room_id}] 解析点赞数据时出错: {e}")
        
        @room.on('ONLINE_RANK_COUNT')
        async def on_popularity(event):
            try:
                monitor.popularity = event["data"]["data"]["count"]
                monitor.last_update = monitor.get_timestamp()
                monitor.print_status()
                
                # 添加到可视化器和存储
                vis = get_visualizer()
                if vis:
                    vis.add_data(room_id, 'popularity', monitor.popularity)
                    
            except KeyError as e:
                print(f"❌ [房间{room_id}] 解析人气数据时出错: {e}")
        
        @room.on('WATCHED_CHANGE')
        async def on_watched_change(event):
            try:
                monitor.watched = event["data"]["data"]["num"]
                monitor.last_update = monitor.get_timestamp()
                monitor.print_status()
                
                # 添加到可视化器和存储
                vis = get_visualizer()
                if vis:
                    vis.add_data(room_id, 'watched', monitor.watched)
                    
            except KeyError as e:
                print(f"❌ [房间{room_id}] 解析观看数据时出错: {e}")
        
        monitor.last_update = monitor.get_timestamp()
        print(f"🎯 开始监听直播间 {room_id} 的数据...")
        
        await room.connect()
        print(f"✅ 房间 {room_id} 连接成功！")
        
    except Exception as e:
        print(f"❌ [房间{room_id}] 连接失败: {e}")
        # 避免无限递归，限制重试次数
        await asyncio.sleep(5)
        print(f"🔄 5秒后将停止重试房间 {room_id}")

def run_async_monitor(room_ids):
    """在后台线程中运行异步监听"""
    async def monitor_all():
        print(f"🎯 准备监控 {len(room_ids)} 个直播间: {room_ids}")
        
        tasks = []
        for room_id in room_ids:
            task = asyncio.create_task(monitor_room(room_id))
            tasks.append(task)
            print(f"📝 为房间 {room_id} 创建监控任务")
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"❌ 监控任务执行出错: {e}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(monitor_all())

async def check_room_status(room_id):
    """检查直播间状态"""
    try:
        room = live.LiveRoom(room_display_id=room_id)
        info = await room.get_room_info()
        
        live_status = info.get('room_info', {}).get('live_status', 0)
        title = info.get('room_info', {}).get('title', '未知')
        uname = info.get('anchor_info', {}).get('base_info', {}).get('uname', '未知')
        
        status_text = {
            0: "未开播",
            1: "直播中", 
            2: "轮播中"
        }.get(live_status, "未知状态")
        
        print(f"🏠 房间{room_id} ({uname}): {title}")
        print(f"📺 状态: {status_text}")
        print(f"🔴 是否可监控: {'是' if live_status in [1, 2] else '否'}")
        
        return live_status in [1, 2]
        
    except Exception as e:
        print(f"❌ 检查房间 {room_id} 状态失败: {e}")
        return False

async def check_all_rooms(room_ids):
    """检查所有房间状态"""
    print("🔍 正在检查所有直播间状态...")
    print("=" * 50)
    
    available_rooms = []
    for room_id in room_ids:
        if await check_room_status(room_id):
            available_rooms.append(room_id)
        print("-" * 30)
    
    print(f"✅ 可监控的房间: {available_rooms}")
    return available_rooms

async def main_async():
    #room_ids = [6, 22427859, 7720242]  # 添加更多房间测试
    room_ids = [10542806, 1746, 30563631]
    print("🚀 初始化B站直播数据监控系统...")
    
    # 检查房间状态 - 直接调用当前文件中的函数
    available_rooms = await check_all_rooms(room_ids)
    
    if not available_rooms:
        print("❌ 没有可监控的直播间")
        return
    
    # 使用可用的房间
    room_ids = available_rooms
    
    # 初始化数据存储
    print("📁 初始化数据存储系统...")
    storage = init_storage(room_ids, data_dir="live_data")
    
    # 显示创建的JSON文件
    print("\n📋 已创建/加载的数据文件:")
    for room_id, filepath in storage.get_all_room_files().items():
        room_info = storage.get_room_info(room_id)
        print(f"  房间{room_id} ({room_info.get('uname', '未知')}): {os.path.basename(filepath)}")
    
    # 在主线程中初始化可视化器
    print("\n📊 初始化可视化系统...")
    visualizer = init_visualizer(room_ids)
    
    # 在后台线程中启动数据监听
    monitor_thread = threading.Thread(target=run_async_monitor, args=(room_ids,), daemon=True)
    monitor_thread.start()
    
    print("🎯 启动可视化界面...")
    print("💡 提示：关闭图表窗口将结束程序")
    print("=" * 60)
    
    # 在主线程中启动可视化（这必须在主线程中执行）
    visualizer.start()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()