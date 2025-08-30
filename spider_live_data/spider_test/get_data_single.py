import asyncio
from bilibili_api import live
from datetime import datetime

# 全局变量存储最新的人气和观看数据
current_popularity = 0
current_watched = 0
last_update_time = ""

async def main():
    global current_popularity, current_watched, last_update_time
    
    # 创建直播弹幕监听器
    room = live.LiveDanmaku(6)#4190942
    
    def get_timestamp():
        """获取当前时间戳"""
        return datetime.now().strftime("%H:%M:%S")
    
    def print_status():
        """打印当前状态（人气和观看数据在一行，带时间戳）"""
        print(f"\r[{last_update_time}] [状态] 人气: {current_popularity} | 观看: {current_watched}", end="", flush=True)
    
    @room.on('DANMU_MSG')
    async def on_danmaku(event):
        try:
            # 解析弹幕数据
            info = event["data"]["info"]
            username = info[2][1]  # 弹幕发出者
            message = info[1]      # 弹幕内容
            timestamp = get_timestamp()
            print(f"\n[{timestamp}] [弹幕] {username}: {message}")
            print_status()  # 重新显示状态行
        except (KeyError, IndexError) as e:
            print(f"\n解析弹幕数据时出错: {e}")
            print_status()
    
    @room.on('SEND_GIFT')
    async def on_gift(event):
        try:
            # 解析礼物数据
            data = event["data"]["data"]
            username = data["uname"]      # 礼物送出者
            gift_name = data["giftName"]  # 礼物名称
            num = data["num"]             # 礼物数量
            timestamp = get_timestamp()
            print(f"\n[{timestamp}] [礼物] {username} 送出 {gift_name} x{num}")
            print_status()  # 重新显示状态行
        except KeyError as e:
            print(f"\n解析礼物数据时出错: {e}")
            print_status()
    
    @room.on('ONLINE_RANK_COUNT')
    async def on_popularity(event):
        global current_popularity, last_update_time
        try:
            # 解析人气值数据
            current_popularity = event["data"]["data"]["count"]
            last_update_time = get_timestamp()
            print_status()
        except KeyError as e:
            print(f"\n解析人气数据时出错: {e}")
            print_status()
    
    @room.on('WATCHED_CHANGE')
    async def on_watched_change(event):
        global current_watched, last_update_time
        try:
            # 观看人数变化
            current_watched = event["data"]["data"]["num"]
            last_update_time = get_timestamp()
            print_status()
        except KeyError as e:
            print(f"\n解析观看数据时出错: {e}")
            print_status()
    
    # 初始化时间戳
    last_update_time = get_timestamp()
    print(f"开始监听直播间 {4190942} 的数据...")
    print_status()  # 初始显示状态行
    
    try:
        await room.connect()
    except Exception as e:
        print(f"\n连接直播间时出错: {e}")

if __name__ == "__main__":
    asyncio.run(main())