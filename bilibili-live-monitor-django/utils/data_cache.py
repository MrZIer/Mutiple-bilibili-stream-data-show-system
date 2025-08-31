import redis
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .redis_config import get_redis_client

logger = logging.getLogger(__name__)

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
            'room_comments': 'room:{room_id}:comments',         # 评论列表
            'active_rooms': 'monitor:active_rooms',             # 活跃房间
            'room_info': 'room:{room_id}:info',                 # 房间信息
            'stats': 'monitor:stats',                           # 监控统计
            'room_counters': 'room:{room_id}:counters',         # 房间计数器
        }
    
    def save_room_info(self, room_id: int, room_info: Dict):
        """保存房间基本信息"""
        try:
            key = self.KEYS['room_info'].format(room_id=room_id)
            
            # 准备房间信息数据
            info_data = {
                'room_id': str(room_id),
                'real_room_id': str(room_info.get('real_room_id', room_id)),
                'uname': room_info.get('uname', f'主播{room_id}'),
                'title': room_info.get('title', f'直播间{room_id}'),
                'area_name': room_info.get('area_name', ''),
                'parent_area_name': room_info.get('parent_area_name', ''),
                'uid': str(room_info.get('uid', 0)),
                'cover': room_info.get('cover', ''),
                'keyframe': room_info.get('keyframe', ''),
                'live_status': str(room_info.get('live_status', 0)),
                'last_update': datetime.now().isoformat()
            }
            
            self.redis_client.hset(key, mapping=info_data)
            
            # 添加到活跃房间集合
            self.redis_client.sadd(self.KEYS['active_rooms'], room_id)
            
            # 设置过期时间（24小时）
            self.redis_client.expire(key, 86400)
            
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
            
            # 构建流数据
            stream_data = {
                'timestamp': timestamp,
                'time': current_time,
                'type': data_type,
                'value': str(value),
                'room_id': str(room_id)
            }
            
            if data_type == 'popularity':
                self.redis_client.hset(current_key, 'popularity', value)
                self.redis_client.hset(current_key, 'last_popularity_update', current_time)
                
            elif data_type == 'watched':
                self.redis_client.hset(current_key, 'watched', value)
                self.redis_client.hset(current_key, 'last_watched_update', current_time)
                
            elif data_type == 'likes':
                self.redis_client.hset(current_key, 'likes', value)
                self.redis_client.hset(current_key, 'last_likes_update', current_time)
                
            elif data_type == 'danmaku':
                # 累计弹幕数量
                counters_key = self.KEYS['room_counters'].format(room_id=room_id)
                new_count = self.redis_client.hincrby(counters_key, 'total_danmaku', 1)
                self.redis_client.hset(current_key, 'total_danmaku', new_count)
                
                # 保存弹幕详情
                if extra_data:
                    danmaku_data = {
                        'timestamp': timestamp,
                        'time': current_time,
                        'user': extra_data.get('user', '匿名'),
                        'content': extra_data.get('content', ''),
                        'uid': str(extra_data.get('uid', 0))
                    }
                    danmaku_key = self.KEYS['room_danmaku'].format(room_id=room_id)
                    self.redis_client.lpush(danmaku_key, json.dumps(danmaku_data))
                    self.redis_client.ltrim(danmaku_key, 0, 999)  # 保持最新1000条
                    
                stream_data.update(extra_data or {})
                
            elif data_type == 'gift':
                # 累计礼物数量
                counters_key = self.KEYS['room_counters'].format(room_id=room_id)
                gift_count = extra_data.get('count', 1) if extra_data else 1
                new_count = self.redis_client.hincrby(counters_key, 'total_gifts', gift_count)
                self.redis_client.hset(current_key, 'total_gifts', new_count)
                
                # 保存礼物详情
                if extra_data:
                    gift_data = {
                        'timestamp': timestamp,
                        'time': current_time,
                        'user': extra_data.get('user', '匿名'),
                        'gift_name': extra_data.get('gift_name', '礼物'),
                        'count': extra_data.get('count', 1),
                        'price': extra_data.get('price', 0),
                        'uid': str(extra_data.get('uid', 0))
                    }
                    gift_key = self.KEYS['room_gifts'].format(room_id=room_id)
                    self.redis_client.lpush(gift_key, json.dumps(gift_data))
                    self.redis_client.ltrim(gift_key, 0, 999)  # 保持最新1000条
                    
                stream_data.update(extra_data or {})
            
            elif data_type == 'comment':
                # 保存评论
                if extra_data:
                    comment_data = {
                        'timestamp': timestamp,
                        'time': current_time,
                        'user': extra_data.get('user', '匿名'),
                        'content': extra_data.get('content', ''),
                        'uid': str(extra_data.get('uid', 0))
                    }
                    comment_key = self.KEYS['room_comments'].format(room_id=room_id)
                    self.redis_client.lpush(comment_key, json.dumps(comment_data))
                    self.redis_client.ltrim(comment_key, 0, 999)  # 保持最新1000条
                    
                stream_data.update(extra_data or {})
            
            # 2. 添加到时序数据流
            stream_key = self.KEYS['room_stream'].format(room_id=room_id)
            self.redis_client.xadd(stream_key, stream_data, maxlen=1000)  # 最多保存1000条
            
            # 3. 更新通用信息
            self.redis_client.hset(current_key, 'last_update', current_time)
            self.redis_client.expire(current_key, 86400)  # 24小时过期
            
            # 4. 发布实时更新通知
            self._publish_update(room_id, stream_data)
            
            # 5. 更新监控统计
            self._update_stats(room_id, data_type)
            
            self.logger.debug(f"房间 {room_id} {data_type} 数据已保存: {value}")
            
        except Exception as e:
            self.logger.error(f"保存实时数据失败: {e}")
    
    def _publish_update(self, room_id: int, data: Dict):
        """发布实时更新通知"""
        try:
            channel = f'live_updates:room:{room_id}'
            message = json.dumps(data, ensure_ascii=False)
            self.redis_client.publish(channel, message)
            
            # 全局更新通知
            global_channel = 'live_updates:all'
            global_data = {'room_id': room_id, **data}
            self.redis_client.publish(global_channel, json.dumps(global_data, ensure_ascii=False))
            
        except Exception as e:
            self.logger.error(f"发布更新通知失败: {e}")
    
    def _update_stats(self, room_id: int, data_type: str):
        """更新监控统计"""
        try:
            stats_key = self.KEYS['stats']
            current_time = datetime.now().isoformat()
            
            # 更新统计信息
            self.redis_client.hincrby(stats_key, f'total_{data_type}', 1)
            self.redis_client.hset(stats_key, f'last_{data_type}_time', current_time)
            self.redis_client.hset(stats_key, 'last_update', current_time)
            
            # 每日统计
            today = datetime.now().strftime('%Y-%m-%d')
            daily_stats_key = f'stats:daily:{today}'
            self.redis_client.hincrby(daily_stats_key, f'total_{data_type}', 1)
            self.redis_client.expire(daily_stats_key, 86400 * 7)  # 保存7天
            
        except Exception as e:
            self.logger.error(f"更新统计失败: {e}")
    
    def get_room_current_data(self, room_id: int) -> Dict:
        """获取房间当前数据"""
        try:
            current_key = self.KEYS['room_current'].format(room_id=room_id)
            data = self.redis_client.hgetall(current_key)
            
            if not data:
                return {}
            
            # 转换数据类型
            result = {}
            for key, value in data.items():
                if key in ['popularity', 'watched', 'likes', 'total_danmaku', 'total_gifts']:
                    result[key] = int(value) if value.isdigit() else 0
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取房间当前数据失败: {e}")
            return {}
    
    def get_room_stream_data(self, room_id: int, count: int = 30) -> List[Dict]:
        """获取房间时序数据"""
        try:
            stream_key = self.KEYS['room_stream'].format(room_id=room_id)
            
            # 获取最新的数据
            streams = self.redis_client.xrevrange(stream_key, count=count)
            
            result = []
            for stream_id, fields in streams:
                data = {
                    'stream_id': stream_id,
                    'timestamp': int(fields.get('timestamp', 0)),
                    'time': fields.get('time', ''),
                    'type': fields.get('type', ''),
                    'value': fields.get('value', ''),
                    'room_id': int(fields.get('room_id', room_id))
                }
                
                # 添加额外字段
                for key, value in fields.items():
                    if key not in data:
                        data[key] = value
                
                result.append(data)
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取房间时序数据失败: {e}")
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
            self.logger.error(f"获取最近弹幕失败: {e}")
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
            self.logger.error(f"获取最近礼物失败: {e}")
            return []
    
    def get_recent_comments(self, room_id: int, count: int = 10) -> List[Dict]:
        """获取最近评论"""
        try:
            comment_key = self.KEYS['room_comments'].format(room_id=room_id)
            comment_list = self.redis_client.lrange(comment_key, 0, count - 1)
            
            result = []
            for comment_json in comment_list:
                try:
                    comment_data = json.loads(comment_json)
                    result.append(comment_data)
                except json.JSONDecodeError:
                    continue
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取最近评论失败: {e}")
            return []
    
    def get_active_rooms(self) -> List[int]:
        """获取活跃房间列表"""
        try:
            room_ids = self.redis_client.smembers(self.KEYS['active_rooms'])
            return [int(room_id) for room_id in room_ids]
        except Exception as e:
            self.logger.error(f"获取活跃房间失败: {e}")
            return []
    
    def get_room_info(self, room_id: int) -> Dict:
        """获取房间信息"""
        try:
            info_key = self.KEYS['room_info'].format(room_id=room_id)
            data = self.redis_client.hgetall(info_key)
            
            if not data:
                return {}
            
            # 转换数据类型
            result = {}
            for key, value in data.items():
                if key in ['room_id', 'real_room_id', 'uid', 'live_status']:
                    result[key] = int(value) if value.isdigit() else 0
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取房间信息失败: {e}")
            return {}
    
    def get_monitor_stats(self) -> Dict:
        """获取监控统计"""
        try:
            stats_key = self.KEYS['stats']
            data = self.redis_client.hgetall(stats_key)
            
            if not data:
                return {}
            
            # 转换数据类型
            result = {}
            for key, value in data.items():
                if key.startswith('total_'):
                    result[key] = int(value) if value.isdigit() else 0
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取监控统计失败: {e}")
            return {}
    
    def clear_room_data(self, room_id: int):
        """清理房间数据"""
        try:
            keys_to_delete = []
            for key_template in self.KEYS.values():
                if '{room_id}' in key_template:
                    key = key_template.format(room_id=room_id)
                    keys_to_delete.append(key)
            
            if keys_to_delete:
                self.redis_client.delete(*keys_to_delete)
            
            # 从活跃房间集合中移除
            self.redis_client.srem(self.KEYS['active_rooms'], room_id)
            
            self.logger.info(f"房间 {room_id} 数据已清理")
            
        except Exception as e:
            self.logger.error(f"清理房间数据失败: {e}")
    
    def get_room_dashboard_data(self, room_id: int) -> Dict:
        """获取房间仪表板完整数据"""
        try:
            return {
                'room_info': self.get_room_info(room_id),
                'current_data': self.get_room_current_data(room_id),
                'stream_data': self.get_room_stream_data(room_id, count=50),
                'recent_danmaku': self.get_recent_danmaku(room_id, count=20),
                'recent_gifts': self.get_recent_gifts(room_id, count=20),
                'recent_comments': self.get_recent_comments(room_id, count=20)
            }
        except Exception as e:
            self.logger.error(f"获取房间仪表板数据失败: {e}")
            return {}

# 全局缓存实例
_live_cache = None

def get_live_cache() -> LiveDataCache:
    """获取全局缓存实例"""
    global _live_cache
    if _live_cache is None:
        _live_cache = LiveDataCache()
    return _live_cache

def init_live_cache() -> LiveDataCache:
    """初始化直播数据缓存"""
    return get_live_cache()