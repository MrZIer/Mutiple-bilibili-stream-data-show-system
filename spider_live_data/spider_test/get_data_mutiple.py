import asyncio
from bilibili_api import live
from datetime import datetime

# 存储多个直播间的数据
room_data = {}

class RoomMonitor:
    def __init__(self, room_id):
        self.room_id = room_id
        self.popularity = 0
        self.watched = 0
        self.last_update = ""
        
    def get_timestamp(self):
        """获取当前时间戳"""
        return datetime.now().strftime("%H:%M:%S")
    
    def print_status(self):
        """打印当前房间状态"""
        print(f"\r[{self.last_update}] [房间{self.room_id}状态] 人气: {self.popularity} | 观看: {self.watched}")

async def monitor_room(room_id):
    """监听单个直播间"""
    monitor = RoomMonitor(room_id)
    room_data[room_id] = monitor
    
    # 创建直播弹幕监听器
    room = live.LiveDanmaku(room_id)
    
    @room.on('DANMU_MSG')
    async def on_danmaku(event):
        try:
            # 解析弹幕数据
            info = event["data"]["info"]
            username = info[2][1]  # 弹幕发出者
            message = info[1]      # 弹幕内容
            timestamp = monitor.get_timestamp()
            print(f"[{timestamp}] [房间{room_id}弹幕] {username}: {message}")
        except (KeyError, IndexError) as e:
            print(f"[房间{room_id}] 解析弹幕数据时出错: {e}")
    
    @room.on('SEND_GIFT')
    async def on_gift(event):
        try:
            # 解析礼物数据
            data = event["data"]["data"]
            username = data["uname"]      # 礼物送出者
            gift_name = data["giftName"]  # 礼物名称
            num = data["num"]             # 礼物数量
            timestamp = monitor.get_timestamp()
            print(f"[{timestamp}] [房间{room_id}礼物] {username} 送出 {gift_name} x{num}")
        except KeyError as e:
            print(f"[房间{room_id}] 解析礼物数据时出错: {e}")
    
    @room.on('ONLINE_RANK_COUNT')
    async def on_popularity(event):
        try:
            # 解析人气值数据
            monitor.popularity = event["data"]["data"]["count"]
            monitor.last_update = monitor.get_timestamp()
            monitor.print_status()
        except KeyError as e:
            print(f"[房间{room_id}] 解析人气数据时出错: {e}")
    
    @room.on('WATCHED_CHANGE')
    async def on_watched_change(event):
        try:
            # 观看人数变化
            monitor.watched = event["data"]["data"]["num"]
            monitor.last_update = monitor.get_timestamp()
            monitor.print_status()
        except KeyError as e:
            print(f"[房间{room_id}] 解析观看数据时出错: {e}")
    
    # 初始化
    monitor.last_update = monitor.get_timestamp()
    print(f"=" * 50)
    print(f"开始监听直播间 {room_id} 的数据...")
    print(f"=" * 50)
    
    try:
        await room.connect()
    except Exception as e:
        print(f"[房间{room_id}] 连接直播间时出错: {e}")

async def print_all_status():
    """定期打印所有房间状态汇总"""
    while True:
        await asyncio.sleep(30)  # 每30秒打印一次汇总
        print("\n" + "=" * 60)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 所有直播间状态汇总:")
        print("=" * 60)
        for room_id, monitor in room_data.items():
            print(f"房间{room_id}: 人气{monitor.popularity} | 观看{monitor.watched} | 更新时间{monitor.last_update}")
        print("=" * 60)

async def main():
    # 要监听的直播间ID列表
    room_ids = [6, 4190942, 22427859]  # 你可以修改这里的房间号
    
    # 创建监听任务
    tasks = []
    
    # 为每个房间创建监听任务
    for room_id in room_ids:
        task = asyncio.create_task(monitor_room(room_id))
        tasks.append(task)
    
    # 创建状态汇总任务
    status_task = asyncio.create_task(print_all_status())
    tasks.append(status_task)
    
    # 并发执行所有任务
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"程序执行出错: {e}")

if __name__ == "__main__":
    asyncio.run(main())