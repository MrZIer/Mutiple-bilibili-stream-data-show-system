import json
import logging
import redis
from datetime import datetime
from typing import Dict, List, Any, Optional
from django.utils import timezone

from .models import LiveRoom, DanmakuData, GiftData
from utils.redis_handler import get_redis_client

logger = logging.getLogger(__name__)

class LiveDataCollector:
    """直播数据收集器"""
    
    def __init__(self, room_id: int):
        self.room_id = room_id
        self.redis_client = get_redis_client()
        self.room = None
        self._initialize_room()
    
    def _initialize_room(self):
        """初始化房间对象"""
        try:
            self.room, created = LiveRoom.objects.get_or_create(
                room_id=self.room_id,
                defaults={
                    'title': f'房间 {self.room_id}',
                    'uname': '未知主播',
                    'status': 0
                }
            )
            if created:
                logger.info(f"创建新房间记录: {self.room_id}")
        except Exception as e:
            logger.error(f"初始化房间失败 {self.room_id}: {e}")
    
    def collect_danmaku(self, danmaku_data: Dict[str, Any]) -> bool:
        """收集弹幕数据"""
        try:
            # 添加时间戳
            if 'timestamp' not in danmaku_data:
                danmaku_data['timestamp'] = datetime.now().timestamp()
            
            # 存储到Redis
            danmaku_key = f"room:{self.room_id}:danmaku"
            danmaku_json = json.dumps(danmaku_data, ensure_ascii=False)
            
            # 使用lpush添加到列表开头，ltrim保持列表长度
            pipe = self.redis_client.pipeline()
            pipe.lpush(danmaku_key, danmaku_json)
            pipe.ltrim(danmaku_key, 0, 999)  # 只保留最新1000条
            pipe.execute()
            
            # 更新统计
            self._update_stats('danmaku')
            
            logger.debug(f"收集弹幕: {self.room_id} - {danmaku_data.get('username', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"收集弹幕失败 {self.room_id}: {e}")
            return False
    
    def collect_gift(self, gift_data: Dict[str, Any]) -> bool:
        """收集礼物数据"""
        try:
            # 添加时间戳
            if 'timestamp' not in gift_data:
                gift_data['timestamp'] = datetime.now().timestamp()
            
            # 计算总价值
            if 'total_price' not in gift_data:
                gift_data['total_price'] = gift_data.get('price', 0) * gift_data.get('num', 1)
            
            # 存储到Redis
            gift_key = f"room:{self.room_id}:gifts"
            gift_json = json.dumps(gift_data, ensure_ascii=False)
            
            # 使用lpush添加到列表开头，ltrim保持列表长度
            pipe = self.redis_client.pipeline()
            pipe.lpush(gift_key, gift_json)
            pipe.ltrim(gift_key, 0, 499)  # 只保留最新500条
            pipe.execute()
            
            # 更新统计
            self._update_stats('gift', gift_data.get('total_price', 0))
            
            logger.debug(f"收集礼物: {self.room_id} - {gift_data.get('gift_name', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"收集礼物失败 {self.room_id}: {e}")
            return False
    
    def update_room_info(self, room_info: Dict[str, Any]) -> bool:
        """更新房间信息"""
        try:
            # 存储到Redis
            room_key = f"room:{self.room_id}:info"
            self.redis_client.hset(room_key, mapping=room_info)
            
            # 更新数据库中的房间信息
            if self.room:
                self.room.title = room_info.get('title', self.room.title)
                self.room.uname = room_info.get('uname', self.room.uname)
                self.room.face = room_info.get('face', self.room.face)
                self.room.online = room_info.get('online', self.room.online)
                self.room.status = room_info.get('status', self.room.status)
                self.room.save()
            
            logger.debug(f"更新房间信息: {self.room_id}")
            return True
            
        except Exception as e:
            logger.error(f"更新房间信息失败 {self.room_id}: {e}")
            return False
    
    def _update_stats(self, data_type: str, value: float = 1):
        """更新统计信息"""
        try:
            stats_key = f"room:{self.room_id}:stats"
            current_time = datetime.now()
            
            # 更新计数
            if data_type == 'danmaku':
                self.redis_client.hincrby(stats_key, 'danmaku_count', 1)
                self.redis_client.hset(stats_key, 'last_danmaku_time', current_time.isoformat())
            elif data_type == 'gift':
                self.redis_client.hincrby(stats_key, 'gift_count', 1)
                self.redis_client.hincrbyfloat(stats_key, 'gift_value', value)
                self.redis_client.hset(stats_key, 'last_gift_time', current_time.isoformat())
            
            # 设置过期时间（24小时）
            self.redis_client.expire(stats_key, 86400)
            
        except Exception as e:
            logger.error(f"更新统计失败 {self.room_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            stats_key = f"room:{self.room_id}:stats"
            stats = self.redis_client.hgetall(stats_key)
            
            return {
                'danmaku_count': int(stats.get('danmaku_count', 0)),
                'gift_count': int(stats.get('gift_count', 0)),
                'gift_value': float(stats.get('gift_value', 0)),
                'last_danmaku_time': stats.get('last_danmaku_time'),
                'last_gift_time': stats.get('last_gift_time')
            }
            
        except Exception as e:
            logger.error(f"获取统计失败 {self.room_id}: {e}")
            return {}
    
    def get_recent_danmaku(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近的弹幕"""
        try:
            danmaku_key = f"room:{self.room_id}:danmaku"
            danmaku_list = self.redis_client.lrange(danmaku_key, 0, limit - 1)
            
            result = []
            for danmaku_json in danmaku_list:
                try:
                    danmaku_data = json.loads(danmaku_json)
                    result.append(danmaku_data)
                except json.JSONDecodeError:
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"获取弹幕失败 {self.room_id}: {e}")
            return []
    
    def get_recent_gifts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近的礼物"""
        try:
            gift_key = f"room:{self.room_id}:gifts"
            gift_list = self.redis_client.lrange(gift_key, 0, limit - 1)
            
            result = []
            for gift_json in gift_list:
                try:
                    gift_data = json.loads(gift_json)
                    result.append(gift_data)
                except json.JSONDecodeError:
                    continue
            
            return result
            
        except Exception as e:
            logger.error(f"获取礼物失败 {self.room_id}: {e}")
            return []
    
    def clear_data(self):
        """清理数据"""
        try:
            keys_to_delete = [
                f"room:{self.room_id}:danmaku",
                f"room:{self.room_id}:gifts",
                f"room:{self.room_id}:stats",
                f"room:{self.room_id}:info"
            ]
            
            if keys_to_delete:
                self.redis_client.delete(*keys_to_delete)
            
            logger.info(f"清理房间数据: {self.room_id}")
            
        except Exception as e:
            logger.error(f"清理数据失败 {self.room_id}: {e}")

class LiveDataCollectorManager:
    """数据收集器管理器"""
    
    def __init__(self):
        self._collectors: Dict[int, LiveDataCollector] = {}
    
    def get_collector(self, room_id: int) -> LiveDataCollector:
        """获取或创建数据收集器"""
        if room_id not in self._collectors:
            self._collectors[room_id] = LiveDataCollector(room_id)
        return self._collectors[room_id]
    
    def remove_collector(self, room_id: int):
        """移除数据收集器"""
        if room_id in self._collectors:
            self._collectors[room_id].clear_data()
            del self._collectors[room_id]
    
    def get_all_collectors(self) -> Dict[int, LiveDataCollector]:
        """获取所有收集器"""
        return self._collectors.copy()
    
    def clear_all(self):
        """清理所有收集器"""
        for collector in self._collectors.values():
            collector.clear_data()
        self._collectors.clear()

# 全局收集器管理器实例
collector_manager = LiveDataCollectorManager()

def get_data_collector(room_id: int) -> LiveDataCollector:
    """获取数据收集器的便捷函数"""
    return collector_manager.get_collector(room_id)