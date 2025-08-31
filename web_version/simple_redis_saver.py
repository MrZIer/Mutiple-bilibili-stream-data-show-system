import redis
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

class SimpleRedisSaver:
    """简化的Redis数据保存器 - 增强版"""
    
    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.logger = logging.getLogger('RedisSaver')
        
        try:
            self.redis_client = redis.Redis(
                host=host, 
                port=port, 
                db=db, 
                password=password,
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # 测试连接
            self.redis_client.ping()
            self.logger.info(f"✅ Redis连接成功: {host}:{port}")
            
        except Exception as e:
            self.logger.error(f"❌ Redis连接失败: {e}")
            self.redis_client = None
    
    def is_connected(self) -> bool:
        """检查Redis连接状态"""
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def save_room_info(self, room_id: int, room_info: Dict[str, Any]) -> bool:
        """保存房间信息 - 增强版"""
        if not self.is_connected():
            return False
        
        try:
            key = f'room:{room_id}:info'
            
            # 添加保存时间戳
            room_info_copy = room_info.copy()
            room_info_copy['saved_at'] = datetime.now().isoformat()
            room_info_copy['last_updated'] = datetime.now().isoformat()
            
            # 使用Redis Hash存储
            success = self.redis_client.hset(key, mapping=room_info_copy)
            
            # 设置过期时间（24小时）
            self.redis_client.expire(key, 86400)
            
            # 同时保存到房间索引
            self.redis_client.sadd('rooms:active', str(room_id))
            
            # 保存UP主索引（如果有UID）
            if room_info.get('uid'):
                self.redis_client.hset('rooms:uid_mapping', room_info['uid'], str(room_id))
            
            # 保存房间分区索引
            if room_info.get('area_name'):
                self.redis_client.sadd(f'rooms:area:{room_info["area_name"]}', str(room_id))
            
            self.logger.debug(f"✅ 房间信息已保存: {room_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 保存房间信息失败 {room_id}: {e}")
            return False
    
    def get_room_info(self, room_id: int) -> Optional[Dict[str, Any]]:
        """获取房间信息"""
        if not self.is_connected():
            return None
        
        try:
            key = f'room:{room_id}:info'
            room_info = self.redis_client.hgetall(key)
            
            if room_info:
                # 转换数字字段
                numeric_fields = ['room_id', 'uid', 'live_status', 'online', 'attention', 'gender']
                for field in numeric_fields:
                    if field in room_info and room_info[field].isdigit():
                        room_info[field] = int(room_info[field])
                
                return room_info
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ 获取房间信息失败 {room_id}: {e}")
            return None
    
    def get_all_active_rooms(self) -> List[int]:
        """获取所有活跃房间ID"""
        if not self.is_connected():
            return []
        
        try:
            room_ids = self.redis_client.smembers('rooms:active')
            return [int(room_id) for room_id in room_ids if room_id.isdigit()]
        except Exception as e:
            self.logger.error(f"❌ 获取活跃房间列表失败: {e}")
            return []
    
    def get_rooms_by_area(self, area_name: str) -> List[int]:
        """根据分区获取房间列表"""
        if not self.is_connected():
            return []
        
        try:
            room_ids = self.redis_client.smembers(f'rooms:area:{area_name}')
            return [int(room_id) for room_id in room_ids if room_id.isdigit()]
        except Exception as e:
            self.logger.error(f"❌ 获取分区房间列表失败 {area_name}: {e}")
            return []
    
    def save_danmaku(self, room_id: int, danmaku_data: Dict[str, Any]) -> bool:
        """保存弹幕数据 - 增强版"""
        if not self.is_connected():
            return False
        
        try:
            key = f'room:{room_id}:danmaku'
            
            # 添加额外字段
            danmaku_data_copy = danmaku_data.copy()
            danmaku_data_copy['saved_at'] = datetime.now().isoformat()
            danmaku_data_copy['id'] = f"{room_id}_{danmaku_data_copy.get('send_time_ms', int(datetime.now().timestamp() * 1000))}"
            
            # 序列化并保存到列表
            serialized_data = json.dumps(danmaku_data_copy, ensure_ascii=False)
            self.redis_client.lpush(key, serialized_data)
            
            # 限制列表长度（保留最近500条）
            self.redis_client.ltrim(key, 0, 499)
            
            # 设置过期时间（1小时）
            self.redis_client.expire(key, 3600)
            
            # 更新房间活跃状态
            self.redis_client.hset(f'room:{room_id}:stats', 'last_danmaku_time', datetime.now().isoformat())
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 保存弹幕失败 {room_id}: {e}")
            return False
    
    def save_gift(self, room_id: int, gift_data: Dict[str, Any]) -> bool:
        """保存礼物数据 - 增强版"""
        if not self.is_connected():
            return False
        
        try:
            key = f'room:{room_id}:gifts'
            
            # 添加额外字段
            gift_data_copy = gift_data.copy()
            gift_data_copy['saved_at'] = datetime.now().isoformat()
            gift_data_copy['id'] = f"{room_id}_{gift_data_copy.get('gift_timestamp', int(datetime.now().timestamp()))}"
            
            # 序列化并保存到列表
            serialized_data = json.dumps(gift_data_copy, ensure_ascii=False)
            self.redis_client.lpush(key, serialized_data)
            
            # 限制列表长度（保留最近200个）
            self.redis_client.ltrim(key, 0, 199)
            
            # 设置过期时间（1小时）
            self.redis_client.expire(key, 3600)
            
            # 更新房间活跃状态
            self.redis_client.hset(f'room:{room_id}:stats', 'last_gift_time', datetime.now().isoformat())
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 保存礼物失败 {room_id}: {e}")
            return False
    
    def save_popularity(self, room_id: int, popularity: int) -> bool:
        """保存人气数据 - 增强版"""
        if not self.is_connected():
            return False
        
        try:
            # 更新房间信息中的人气值
            self.redis_client.hset(f'room:{room_id}:info', 'online', str(popularity))
            self.redis_client.hset(f'room:{room_id}:info', 'popularity_updated_at', datetime.now().isoformat())
            
            # 保存人气历史记录
            popularity_key = f'room:{room_id}:popularity_history'
            popularity_data = {
                'popularity': popularity,
                'timestamp': datetime.now().isoformat(),
                'unix_timestamp': int(datetime.now().timestamp())
            }
            
            self.redis_client.lpush(popularity_key, json.dumps(popularity_data))
            
            # 限制历史记录长度（保留最近100次）
            self.redis_client.ltrim(popularity_key, 0, 99)
            
            # 设置过期时间（6小时）
            self.redis_client.expire(popularity_key, 21600)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 保存人气失败 {room_id}: {e}")
            return False
    
    def get_room_stats(self, room_id: int) -> Dict[str, Any]:
        """获取房间统计信息"""
        if not self.is_connected():
            return {}
        
        try:
            stats = {}
            
            # 获取弹幕数量
            danmaku_count = self.redis_client.llen(f'room:{room_id}:danmaku')
            stats['danmaku_count'] = danmaku_count
            
            # 获取礼物数量
            gift_count = self.redis_client.llen(f'room:{room_id}:gifts')
            stats['gift_count'] = gift_count
            
            # 获取房间基本信息
            room_info = self.get_room_info(room_id)
            if room_info:
                stats['current_popularity'] = room_info.get('online', 0)
                stats['uname'] = room_info.get('uname', f'主播{room_id}')
                stats['title'] = room_info.get('title', '')
                stats['area_name'] = room_info.get('area_name', '')
                stats['live_status'] = room_info.get('live_status', 0)
                stats['face'] = room_info.get('face', '')  # UP主头像
                stats['uid'] = room_info.get('uid', 0)
                stats['is_verified'] = room_info.get('is_verified', False)
                stats['verify_desc'] = room_info.get('verify_desc', '')
            
            # 获取最后活跃时间
            room_stats_data = self.redis_client.hgetall(f'room:{room_id}:stats')
            stats.update(room_stats_data)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ 获取房间统计失败 {room_id}: {e}")
            return {}
    
    def cleanup_old_data(self, hours: int = 24) -> bool:
        """清理旧数据"""
        if not self.is_connected():
            return False
        
        try:
            # 这里可以添加清理逻辑
            # 由于我们已经设置了过期时间，Redis会自动清理
            self.logger.info(f"🧹 数据清理完成（Redis自动过期机制）")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 数据清理失败: {e}")
            return False


# 单例模式获取Redis保存器
_redis_saver = None

def get_redis_saver() -> SimpleRedisSaver:
    """获取Redis保存器实例"""
    global _redis_saver
    if _redis_saver is None:
        _redis_saver = SimpleRedisSaver()
    return _redis_saver

def reset_redis_saver():
    """重置Redis保存器实例"""
    global _redis_saver
    _redis_saver = None