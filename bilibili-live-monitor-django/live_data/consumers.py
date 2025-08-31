import json
import asyncio
import redis
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .danmaku_services import DanmakuService
import logging

logger = logging.getLogger(__name__)

class LiveDataConsumer(AsyncWebsocketConsumer):
    """实时直播数据WebSocket消费者"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.room_id = None
        self.room_group_name = None
        self.redis_client = None
        self.is_monitoring = False
        self.monitor_task = None
    
    async def connect(self):
        """WebSocket连接"""
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'room_{self.room_id}'
        
        # 加入房间组
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # 初始化Redis连接
        try:
            self.redis_client = redis.Redis(
                host='localhost', port=6379, db=0, decode_responses=True
            )
            self.redis_client.ping()
            logger.info(f"WebSocket连接成功，房间: {self.room_id}")
            
            # 发送初始数据
            await self.send_initial_data()
            
            # 开始监控
            await self.start_monitoring()
            
        except Exception as e:
            logger.error(f"WebSocket初始化失败: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'连接失败: {e}'
            }))
    
    async def disconnect(self, close_code):
        """WebSocket断开连接"""
        logger.info(f"WebSocket断开连接，房间: {self.room_id}")
        
        # 停止监控
        await self.stop_monitoring()
        
        # 离开房间组
        if self.room_group_name:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """接收WebSocket消息"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'get_recent_data':
                await self.send_recent_data()
            elif message_type == 'search_danmaku':
                keyword = data.get('keyword', '')
                await self.search_and_send_danmaku(keyword)
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': '消息格式错误'
            }))
        except Exception as e:
            logger.error(f"处理WebSocket消息失败: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def send_initial_data(self):
        """发送初始数据"""
        try:
            danmaku_service = DanmakuService()
            
            # 获取房间统计
            room_stats = danmaku_service.get_room_stats(self.room_id)
            
            # 获取最近弹幕
            recent_danmaku = danmaku_service.get_recent_danmaku(self.room_id, 20)
            
            # 获取最近礼物
            recent_gifts = danmaku_service.get_recent_gifts(self.room_id, 10)
            
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'data': {
                    'room_stats': room_stats,
                    'recent_danmaku': recent_danmaku,
                    'recent_gifts': recent_gifts
                }
            }))
            
        except Exception as e:
            logger.error(f"发送初始数据失败: {e}")
    
    async def send_recent_data(self):
        """发送最近数据"""
        try:
            danmaku_service = DanmakuService()
            
            # 获取最新弹幕
            recent_danmaku = danmaku_service.get_recent_danmaku(self.room_id, 20)
            
            # 获取最新礼物
            recent_gifts = danmaku_service.get_recent_gifts(self.room_id, 10)
            
            await self.send(text_data=json.dumps({
                'type': 'recent_data',
                'data': {
                    'recent_danmaku': recent_danmaku,
                    'recent_gifts': recent_gifts,
                    'timestamp': asyncio.get_event_loop().time()
                }
            }))
            
        except Exception as e:
            logger.error(f"发送最近数据失败: {e}")
    
    async def search_and_send_danmaku(self, keyword):
        """搜索并发送弹幕"""
        try:
            danmaku_service = DanmakuService()
            
            search_results = danmaku_service.search_danmaku(
                self.room_id, keyword=keyword, limit=50
            )
            
            await self.send(text_data=json.dumps({
                'type': 'search_results',
                'data': {
                    'keyword': keyword,
                    'results': search_results,
                    'count': len(search_results)
                }
            }))
            
        except Exception as e:
            logger.error(f"搜索弹幕失败: {e}")
    
    async def start_monitoring(self):
        """开始实时监控"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_task = asyncio.create_task(self.monitor_redis_data())
    
    async def stop_monitoring(self):
        """停止实时监控"""
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
    
    async def monitor_redis_data(self):
        """监控Redis数据变化"""
        last_danmaku_count = 0
        last_gift_count = 0
        
        while self.is_monitoring:
            try:
                # 检查弹幕数量变化
                danmaku_key = f"room:{self.room_id}:danmaku"
                current_danmaku_count = self.redis_client.llen(danmaku_key)
                
                # 检查礼物数量变化
                gift_key = f"room:{self.room_id}:gifts"
                current_gift_count = self.redis_client.llen(gift_key)
                
                # 如果有新数据，发送更新
                if (current_danmaku_count > last_danmaku_count or 
                    current_gift_count > last_gift_count):
                    
                    await self.send_live_update(
                        new_danmaku=current_danmaku_count > last_danmaku_count,
                        new_gifts=current_gift_count > last_gift_count
                    )
                    
                    last_danmaku_count = current_danmaku_count
                    last_gift_count = current_gift_count
                
                # 每2秒检查一次
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"监控Redis数据失败: {e}")
                await asyncio.sleep(5)
    
    async def send_live_update(self, new_danmaku=False, new_gifts=False):
        """发送实时更新"""
        try:
            danmaku_service = DanmakuService()
            update_data = {}
            
            if new_danmaku:
                # 获取最新弹幕
                latest_danmaku = danmaku_service.get_recent_danmaku(self.room_id, 5)
                update_data['new_danmaku'] = latest_danmaku
            
            if new_gifts:
                # 获取最新礼物
                latest_gifts = danmaku_service.get_recent_gifts(self.room_id, 3)
                update_data['new_gifts'] = latest_gifts
            
            # 总是更新统计数据
            room_stats = danmaku_service.get_room_stats(self.room_id)
            update_data['room_stats'] = room_stats
            
            await self.send(text_data=json.dumps({
                'type': 'live_update',
                'data': update_data,
                'timestamp': asyncio.get_event_loop().time()
            }))
            
        except Exception as e:
            logger.error(f"发送实时更新失败: {e}")
    
    # 群组消息处理
    async def room_message(self, event):
        """处理房间群组消息"""
        await self.send(text_data=json.dumps({
            'type': 'room_message',
            'data': event['data']
        }))