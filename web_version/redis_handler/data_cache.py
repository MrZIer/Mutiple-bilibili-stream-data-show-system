import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from config.redis_config import get_redis_client
import logging

class LiveDataCache:
    """直播数据Redis缓存管理器"""
    
    def __init__(self):
        self.redis_client = get_redis_client()
        self.logger = logging.getLogger(__name__)
        
        # Redis键名模板
        self.KEYS = {
            'room_current': 'room:{room_id}:current',           # 当前状态
            'room_stream': 'room:{room_id}:stream',             # 时序数据流
            'room_danmaku': 'room:{room_id}:danmaku',           # 弹幕列表
            'room_gifts': 'room:{room_id}:gifts',               # 礼物列表
            'active_rooms': 'monitor:active_rooms',             # 活跃房间
            'room_info': 'room:{room_id}:info',                 # 房间信息
            'stats': 'monitor:stats',                           # 监控统计
        }
    
    def save_room_info(self, room_id: int, room_info: Dict):
        """保存房间基本信息"""
        try:
            key = self.KEYS['room_info'].format(room_id=room_id)
            self.redis_client.hset(key, mapping=room_info)
            
            # 添加到活跃房间集合
            self.redis_client.sadd(self.KEYS['active_rooms'], room_id)
            
            self.logger.info(f"房间 {room_id} 信息已保存到Redis")
        except Exception as e:
            self.logger.error(f"保存房间信息失败: {e}")
    
    def save_real_time_data(self, room_id: int, data_type: str, value: Any, extra_data: Dict = None):
        """保存实时数据到Redis"""
        try:
            timestamp = int(time.time() * 1000)  # 毫秒时间戳
            current_time = datetime.now().isoformat()
            
            # 1. 更新当前状态
            current_key = self.KEYS['room_current'].format(room_id=room_id)
            
            if data_type == 'popularity':
                # 更新人气数据
                self.redis_client.hset(current_key, mapping={
                    'popularity': value,
                    'last_update': current_time,
                    'timestamp': timestamp
                })
                
                # 获取当前累计数据
                current_data = self.redis_client.hgetall(current_key)
                danmaku_count = int(current_data.get('total_danmaku', 0))
                gift_count = int(current_data.get('total_gifts', 0))
                
                # 添加到时序数据流
                stream_data = {
                    'type': 'metrics',
                    'popularity': value,
                    'danmaku_count': danmaku_count,
                    'gift_count': gift_count,
                    'timestamp': timestamp
                }
                
            elif data_type == 'watched':
                self.redis_client.hset(current_key, 'watched', value)
                stream_data = {
                    'type': 'watched',
                    'value': value,
                    'timestamp': timestamp
                }
                
            elif data_type == 'likes':
                self.redis_client.hset(current_key, 'likes', value)
                stream_data = {
                    'type': 'likes', 
                    'value': value,
                    'timestamp': timestamp
                }
                
            elif data_type == 'danmaku':
                # 更新累计弹幕数
                total_danmaku = self.redis_client.hincrby(current_key, 'total_danmaku', 1)
                
                # 保存弹幕详情
                if extra_data:
                    danmaku_data = {
                        'username': extra_data.get('username', ''),
                        'message': extra_data.get('message', ''),
                        'timestamp': current_time
                    }
                    
                    # 添加到弹幕列表（保持最新100条）
                    danmaku_key = self.KEYS['room_danmaku'].format(room_id=room_id)
                    self.redis_client.lpush(danmaku_key, json.dumps(danmaku_data, ensure_ascii=False))
                    self.redis_client.ltrim(danmaku_key, 0, 99)  # 只保留最新100条
                
                stream_data = {
                    'type': 'danmaku',
                    'total_count': total_danmaku,
                    'username': extra_data.get('username', '') if extra_data else '',
                    'message': extra_data.get('message', '') if extra_data else '',
                    'timestamp': timestamp
                }
                
            elif data_type == 'gift':
                # 更新累计礼物数
                total_gifts = self.redis_client.hincrby(current_key, 'total_gifts', value)
                
                # 保存礼物详情
                if extra_data:
                    gift_data = {
                        'username': extra_data.get('username', ''),
                        'gift_name': extra_data.get('gift_name', ''),
                        'num': value,
                        'timestamp': current_time
                    }
                    
                    # 添加到礼物列表（保持最新50条）
                    gift_key = self.KEYS['room_gifts'].format(room_id=room_id)
                    self.redis_client.lpush(gift_key, json.dumps(gift_data, ensure_ascii=False))
                    self.redis_client.ltrim(gift_key, 0, 49)  # 只保留最新50条
                
                stream_data = {
                    'type': 'gift',
                    'total_count': total_gifts,
                    'gift_name': extra_data.get('gift_name', '') if extra_data else '',
                    'num': value,
                    'timestamp': timestamp
                }
            
            # 2. 添加到时序数据流
            stream_key = self.KEYS['room_stream'].format(room_id=room_id)
            self.redis_client.xadd(stream_key, stream_data, maxlen=1000)  # 最多保存1000条
            
            # 3. 发布实时更新通知
            self._publish_update(room_id, stream_data)
            
            # 4. 更新监控统计
            self._update_stats(room_id, data_type)
            
            self.logger.debug(f"房间 {room_id} {data_type} 数据已保存: {value}")
            
        except Exception as e:
            self.logger.error(f"保存实时数据失败: {e}")
    
    def _publish_update(self, room_id: int, data: Dict):
        """发布实时更新通知"""
        try:
            channel = f'live_updates:room:{room_id}'
            self.redis_client.publish(channel, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            self.logger.error(f"发布更新失败: {e}")
    
    def _update_stats(self, room_id: int, data_type: str):
        """更新监控统计"""
        try:
            stats_key = self.KEYS['stats']
            self.redis_client.hincrby(stats_key, f'total_{data_type}', 1)
            self.redis_client.hset(stats_key, 'last_update', datetime.now().isoformat())
        except Exception as e:
            self.logger.error(f"更新统计失败: {e}")
    
    def get_room_current_data(self, room_id: int) -> Dict:
        """获取房间当前数据"""
        try:
            current_key = self.KEYS['room_current'].format(room_id=room_id)
            data = self.redis_client.hgetall(current_key)
            
            # 转换数据类型
            if data:
                for key in ['popularity', 'watched', 'likes', 'total_danmaku', 'total_gifts', 'timestamp']:
                    if key in data and data[key]:
                        try:
                            data[key] = int(data[key])
                        except ValueError:
                            pass
            
            return data
        except Exception as e:
            self.logger.error(f"获取房间当前数据失败: {e}")
            return {}
    
    def get_room_stream_data(self, room_id: int, count: int = 30) -> List[Dict]:
        """获取房间时序数据"""
        try:
            stream_key = self.KEYS['room_stream'].format(room_id=room_id)
            # 获取最新的count条数据
            stream_data = self.redis_client.xrevrange(stream_key, count=count)
            
            result = []
            for stream_id, fields in stream_data:
                # 转换数据类型
                processed_fields = {}
                for key, value in fields.items():
                    if key in ['popularity', 'danmaku_count', 'gift_count', 'value', 'total_count', 'num', 'timestamp']:
                        try:
                            processed_fields[key] = int(value)
                        except ValueError:
                            processed_fields[key] = value
                    else:
                        processed_fields[key] = value
                
                processed_fields['stream_id'] = stream_id
                result.append(processed_fields)
            
            return list(reversed(result))  # 按时间正序返回
        except Exception as e:
            self.logger.error(f"获取时序数据失败: {e}")
            return []
    
    def get_recent_danmaku(self, room_id: int, count: int = 10) -> List[Dict]:
        """获取最近弹幕"""
        try:
            danmaku_key = self.KEYS['room_danmaku'].format(room_id=room_id)
            danmaku_list = self.redis_client.lrange(danmaku_key, 0, count - 1)
            
            result = []
            for danmaku_json in danmaku_list:
                try:
                    danmaku_data = json.loads(danmaku_json)
                    result.append(danmaku_data)
                except json.JSONDecodeError:
                    continue
            
            return result
        except Exception as e:
            self.logger.error(f"获取弹幕数据失败: {e}")
            return []
    
    def get_recent_gifts(self, room_id: int, count: int = 10) -> List[Dict]:
        """获取最近礼物"""
        try:
            gift_key = self.KEYS['room_gifts'].format(room_id=room_id)
            gift_list = self.redis_client.lrange(gift_key, 0, count - 1)
            
            result = []
            for gift_json in gift_list:
                try:
                    gift_data = json.loads(gift_json)
                    result.append(gift_data)
                except json.JSONDecodeError:
                    continue
            
            return result
        except Exception as e:
            self.logger.error(f"获取礼物数据失败: {e}")
            return []
    
    def get_active_rooms(self) -> List[int]:
        """获取活跃房间列表"""
        try:
            rooms = self.redis_client.smembers(self.KEYS['active_rooms'])
            return [int(room_id) for room_id in rooms]
        except Exception as e:
            self.logger.error(f"获取活跃房间失败: {e}")
            return []
    
    def clear_room_data(self, room_id: int):
        """清理房间数据"""
        try:
            keys_to_delete = [
                self.KEYS['room_current'].format(room_id=room_id),
                self.KEYS['room_stream'].format(room_id=room_id),
                self.KEYS['room_danmaku'].format(room_id=room_id),
                self.KEYS['room_gifts'].format(room_id=room_id),
                self.KEYS['room_info'].format(room_id=room_id),
            ]
            
            self.redis_client.delete(*keys_to_delete)
            self.redis_client.srem(self.KEYS['active_rooms'], room_id)
            
            self.logger.info(f"房间 {room_id} 数据已清理")
        except Exception as e:
            self.logger.error(f"清理房间数据失败: {e}")

# 全局缓存实例
_live_cache = None

def get_live_cache() -> LiveDataCache:
    """获取全局缓存实例"""
    global _live_cache
    if _live_cache is None:
        _live_cache = LiveDataCache()
    return _live_cache