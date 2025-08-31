import asyncio
import logging
import time
from typing import Dict, Optional, List
from datetime import datetime

# 使用 bilibili-api-python 库
from bilibili_api import live, user, sync
from bilibili_api.live import LiveDanmaku, LiveRoom
import bilibili_api

logger = logging.getLogger(__name__)

class BilibiliAPIClient:
    """基于 bilibili-api-python 的客户端"""
    
    def __init__(self):
        self.logger = logger
        
    def get_live_room_info(self, room_id: int) -> Dict:
        """获取直播间基本信息"""
        try:
            room = LiveRoom(room_display_id=room_id)
            
            # 同步获取房间信息
            room_info = sync(room.get_room_info())
            
            if room_info:
                room_data = room_info.get('room_info', {})
                anchor_data = room_info.get('anchor_info', {}).get('base_info', {})
                
                return {
                    'room_id': room_data.get('room_id', room_id),
                    'real_room_id': room_data.get('room_id', room_id),
                    'uname': anchor_data.get('uname', f'主播{room_id}'),
                    'title': room_data.get('title', f'直播间{room_id}'),
                    'area_name': room_data.get('area_name', ''),
                    'parent_area_name': room_data.get('parent_area_name', ''),
                    'live_status': room_data.get('live_status', 0),
                    'popularity': room_data.get('online', 0),
                    'watched': room_data.get('attention', 0),
                    'cover': room_data.get('cover', ''),
                    'keyframe': room_data.get('keyframe', ''),
                    'uid': anchor_data.get('uid', 0),
                    'last_update': datetime.now().isoformat()
                }
            return {}
            
        except Exception as e:
            self.logger.error(f"获取房间 {room_id} 信息失败: {e}")
            return {}
    
    def get_live_popularity(self, room_id: int) -> int:
        """获取直播间人气值"""
        try:
            room = LiveRoom(room_display_id=room_id)
            room_info = sync(room.get_room_info())
            return room_info.get('room_info', {}).get('online', 0)
        except Exception as e:
            self.logger.error(f"获取房间 {room_id} 人气失败: {e}")
            return 0
    
    def fetch_live_data(self, room_id: int) -> Dict:
        """获取直播数据 - 统一接口"""
        return self.get_live_room_info(room_id)
    
    def get_multiple_rooms_data(self, room_ids: List[int]) -> Dict[int, Dict]:
        """批量获取多个房间数据"""
        results = {}
        for room_id in room_ids:
            try:
                data = self.fetch_live_data(room_id)
                if data:
                    results[room_id] = data
                    self.logger.info(f"成功获取房间 {room_id} 数据")
                else:
                    self.logger.warning(f"房间 {room_id} 数据为空")
                    
                # 避免请求过快
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"获取房间 {room_id} 数据失败: {e}")
                results[room_id] = {}
        
        return results

class AsyncBilibiliAPIClient:
    """异步 bilibili-api-python 客户端"""
    
    def __init__(self):
        self.logger = logger
    
    async def get_live_room_info(self, room_id: int) -> Dict:
        """异步获取直播间信息"""
        try:
            room = LiveRoom(room_display_id=room_id)
            room_info = await room.get_room_info()
            
            if room_info:
                room_data = room_info.get('room_info', {})
                anchor_data = room_info.get('anchor_info', {}).get('base_info', {})
                
                return {
                    'room_id': room_data.get('room_id', room_id),
                    'real_room_id': room_data.get('room_id', room_id),
                    'uname': anchor_data.get('uname', f'主播{room_id}'),
                    'title': room_data.get('title', f'直播间{room_id}'),
                    'area_name': room_data.get('area_name', ''),
                    'parent_area_name': room_data.get('parent_area_name', ''),
                    'live_status': room_data.get('live_status', 0),
                    'popularity': room_data.get('online', 0),
                    'watched': room_data.get('attention', 0),
                    'cover': room_data.get('cover', ''),
                    'keyframe': room_data.get('keyframe', ''),
                    'uid': anchor_data.get('uid', 0),
                    'last_update': datetime.now().isoformat()
                }
            return {}
            
        except Exception as e:
            self.logger.error(f"异步获取房间 {room_id} 信息失败: {e}")
            return {}
    
    async def fetch_live_data(self, room_id: int) -> Dict:
        """异步获取直播数据"""
        return await self.get_live_room_info(room_id)

class LiveDanmakuCollector:
    """实时弹幕收集器"""
    
    def __init__(self, room_id: int, on_danmaku=None, on_gift=None, redis_cache=None):
        self.room_id = room_id
        self.room = LiveRoom(room_display_id=room_id)
        self.danmaku = LiveDanmaku(self.room_id)
        self.on_danmaku = on_danmaku
        self.on_gift = on_gift
        self.redis_cache = redis_cache
        self.is_running = False
        
        # 注册事件处理器
        @self.danmaku.on('DANMU_MSG')
        async def on_danmaku_msg(event):
            """弹幕消息处理"""
            try:
                info = event['data']['info']
                user_info = info[2]
                danmaku_data = {
                    'user': user_info[1],  # 用户名
                    'content': info[1],    # 弹幕内容
                    'uid': user_info[0],   # 用户ID
                    'timestamp': info[0][4],  # 时间戳
                }
                
                # 保存到Redis
                if self.redis_cache:
                    self.redis_cache.save_real_time_data(
                        self.room_id, 'danmaku', 1, danmaku_data
                    )
                
                # 回调函数
                if self.on_danmaku:
                    await self.on_danmaku(danmaku_data)
                    
                logger.debug(f"房间 {self.room_id} 弹幕: {danmaku_data['user']}: {danmaku_data['content']}")
                
            except Exception as e:
                logger.error(f"处理弹幕消息失败: {e}")
        
        @self.danmaku.on('SEND_GIFT')
        async def on_send_gift(event):
            """礼物消息处理"""
            try:
                data = event['data']['data']
                gift_data = {
                    'user': data['uname'],
                    'gift_name': data['giftName'],
                    'count': data['num'],
                    'price': data['price'],
                    'uid': data['uid'],
                    'timestamp': data['timestamp']
                }
                
                # 保存到Redis
                if self.redis_cache:
                    self.redis_cache.save_real_time_data(
                        self.room_id, 'gift', gift_data['count'], gift_data
                    )
                
                # 回调函数
                if self.on_gift:
                    await self.on_gift(gift_data)
                    
                logger.debug(f"房间 {self.room_id} 礼物: {gift_data['user']} 送出 {gift_data['count']}个 {gift_data['gift_name']}")
                
            except Exception as e:
                logger.error(f"处理礼物消息失败: {e}")
    
    async def start(self):
        """开始监听弹幕"""
        try:
            self.is_running = True
            await self.danmaku.connect()
            logger.info(f"房间 {self.room_id} 弹幕监听已启动")
        except Exception as e:
            logger.error(f"启动房间 {self.room_id} 弹幕监听失败: {e}")
    
    async def stop(self):
        """停止监听弹幕"""
        try:
            self.is_running = False
            await self.danmaku.disconnect()
            logger.info(f"房间 {self.room_id} 弹幕监听已停止")
        except Exception as e:
            logger.error(f"停止房间 {self.room_id} 弹幕监听失败: {e}")

# 全局客户端实例
_sync_client = None
_async_client = None

def get_bilibili_client() -> BilibiliAPIClient:
    """获取同步B站客户端"""
    global _sync_client
    if _sync_client is None:
        _sync_client = BilibiliAPIClient()
    return _sync_client

def get_async_bilibili_client() -> AsyncBilibiliAPIClient:
    """获取异步B站客户端"""
    global _async_client
    if _async_client is None:
        _async_client = AsyncBilibiliAPIClient()
    return _async_client

# 便捷函数
def fetch_live_data(room_id: int) -> Dict:
    """便捷函数：获取直播数据"""
    client = get_bilibili_client()
    return client.fetch_live_data(room_id)

async def async_fetch_live_data(room_id: int) -> Dict:
    """便捷函数：异步获取直播数据"""
    client = get_async_bilibili_client()
    return await client.fetch_live_data(room_id)

def get_multiple_rooms_data(room_ids: List[int]) -> Dict[int, Dict]:
    """便捷函数：批量获取多个房间数据"""
    client = get_bilibili_client()
    return client.get_multiple_rooms_data(room_ids)

def test_api_connection():
    """测试API连接"""
    client = get_bilibili_client()
    test_room_id = 6  # 官方直播间
    
    try:
        data = client.fetch_live_data(test_room_id)
        if data:
            logger.info(f"API连接测试成功，房间 {test_room_id}: {data.get('uname', 'Unknown')}")
            return True
        else:
            logger.error("API连接测试失败：未获取到数据")
            return False
    except Exception as e:
        logger.error(f"API连接测试失败: {e}")
        return False

if __name__ == "__main__":
    # 测试代码
    print("测试B站API客户端...")
    
    # 测试连接
    if test_api_connection():
        print("✅ API连接正常")
    else:
        print("❌ API连接失败")
    
    # 测试获取数据
    test_rooms = [17961]
    client = get_bilibili_client()
    
    for room_id in test_rooms:
        print(f"\n测试房间 {room_id}:")
        data = fetch_live_data(room_id)
        if data:
            print(f"  房间名: {data.get('uname', 'Unknown')}")
            print(f"  标题: {data.get('title', 'Unknown')}")
            print(f"  人气: {data.get('popularity', 0)}")
            print(f"  直播状态: {data.get('live_status', 0)}")
        else:
            print(f"  ❌ 获取数据失败")