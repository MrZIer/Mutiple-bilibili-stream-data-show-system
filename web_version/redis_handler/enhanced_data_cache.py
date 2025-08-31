import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from config.redis_config import get_redis_client
import logging

class EnhancedLiveDataCache:
    """增强版直播数据Redis缓存管理器"""
    
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
            'hourly_stats': 'room:{room_id}:hourly:{hour}',     # 小时统计
            'daily_stats': 'room:{room_id}:daily:{date}',       # 日统计
        }
    
    def save_room_info(self, room_id: int, room_info: Dict):
        """保存房间基本信息"""
        try:
            key = self.KEYS['room_info'].format(room_id=room_id)
            self.redis_client.hset(key, mapping=room_info)
            
            # 添加到活跃房间集合
            self.redis_client.sadd(self.KEYS['active_rooms'], room_id)
            
            # 设置过期时间（24小时）
            self.redis_client.expire(key, 86400)
            
            self.logger.info(f"房间 {room_id} 信息已保存到Redis")
        except Exception as e:
            self.logger.error(f"保存房间信息失败: {e}")
    
    def save_real_time_data(self, room_id: int, data_type: str, value: Any, extra_data: Dict = None):
        """保存实时数据到Redis - 增强版"""
        try:
            timestamp = int(time.time() * 1000)  # 毫秒时间戳
            current_time = datetime.now().isoformat()
            hour_key = datetime.now().strftime('%Y%m%d%H')
            date_key = datetime.now().strftime('%Y%m%d')
            
            # 更新当前状态
            current_key = self.KEYS['room_current'].format(room_id=room_id)
            
            if data_type == 'popularity':
                # 更新人气数据
                self.redis_client.hset(current_key, mapping={
                    'popularity': value,
                    'last_update': current_time,
                    'timestamp': timestamp
                })
                
                # 获取当前累计数据用于时序记录
                current_data = self.redis_client.hgetall(current_key)
                danmaku_count = int(current_data.get('total_danmaku', 0))
                gift_count = int(current_data.get('total_gifts', 0))
                
                stream_data = {
                    'type': 'metrics',
                    'popularity': value,
                    'danmaku_count': danmaku_count,
                    'gift_count': gift_count,
                    'timestamp': timestamp
                }
                
            elif data_type in ['watched', 'likes']:
                self.redis_client.hset(current_key, data_type, value)
                stream_data = {
                    'type': data_type,
                    'value': value,
                    'timestamp': timestamp
                }
                
            elif data_type == 'danmaku':
                # 更新累计弹幕数
                total_danmaku = self.redis_client.hincrby(current_key, 'total_danmaku', 1)
                
                # 更新小时和日统计
                self._update_hourly_stats(room_id, hour_key, 'danmaku', 1)
                self._update_daily_stats(room_id, date_key, 'danmaku', 1)
                
                # 保存弹幕详情
                if extra_data:
                    danmaku_data = {
                        'username': extra_data.get('username', ''),
                        'message': extra_data.get('message', ''),
                        'uid': extra_data.get('uid', 0),
                        'send_time': extra_data.get('send_time', int(time.time())),
                        'timestamp': current_time
                    }
                    
                    # 添加到弹幕列表（保持最新100条）
                    danmaku_key = self.KEYS['room_danmaku'].format(room_id=room_id)
                    self.redis_client.lpush(danmaku_key, json.dumps(danmaku_data, ensure_ascii=False))
                    self.redis_client.ltrim(danmaku_key, 0, 99)
                    self.redis_client.expire(danmaku_key, 3600)  # 1小时过期
                
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
                
                # 更新小时和日统计
                self._update_hourly_stats(room_id, hour_key, 'gifts', value)
                self._update_daily_stats(room_id, date_key, 'gifts', value)
                
                # 保存礼物详情
                if extra_data:
                    gift_data = {
                        'username': extra_data.get('username', ''),
                        'gift_name': extra_data.get('gift_name', ''),
                        'gift_id': extra_data.get('gift_id', 0),
                        'num': value,
                        'price': extra_data.get('price', 0),
                        'coin_type': extra_data.get('coin_type', 'silver'),
                        'timestamp': current_time
                    }
                    
                    # 添加到礼物列表（保持最新50条）
                    gift_key = self.KEYS['room_gifts'].format(room_id=room_id)
                    self.redis_client.lpush(gift_key, json.dumps(gift_data, ensure_ascii=False))
                    self.redis_client.ltrim(gift_key, 0, 49)
                    self.redis_client.expire(gift_key, 3600)  # 1小时过期
                
                stream_data = {
                    'type': 'gift',
                    'total_count': total_gifts,
                    'gift_name': extra_data.get('gift_name', '') if extra_data else '',
                    'num': value,
                    'price': extra_data.get('price', 0) if extra_data else 0,
                    'timestamp': timestamp
                }
            
            # 添加到时序数据流
            stream_key = self.KEYS['room_stream'].format(room_id=room_id)
            self.redis_client.xadd(stream_key, stream_data, maxlen=1000)
            
            # 设置过期时间
            self.redis_client.expire(current_key, 3600)  # 1小时
            self.redis_client.expire(stream_key, 7200)   # 2小时
            
            # 发布实时更新通知
            self._publish_update(room_id, stream_data)
            
            # 更新全局统计
            self._update_global_stats(data_type, value if data_type == 'gift' else 1)
            
        except Exception as e:
            self.logger.error(f"保存实时数据失败: {e}")
    
    def _update_hourly_stats(self, room_id: int, hour_key: str, stat_type: str, value: int):
        """更新小时统计"""
        try:
            stats_key = self.KEYS['hourly_stats'].format(room_id=room_id, hour=hour_key)
            self.redis_client.hincrby(stats_key, stat_type, value)
            self.redis_client.expire(stats_key, 172800)  # 48小时过期
        except Exception as e:
            self.logger.error(f"更新小时统计失败: {e}")
    
    def _update_daily_stats(self, room_id: int, date_key: str, stat_type: str, value: int):
        """更新日统计"""
        try:
            stats_key = self.KEYS['daily_stats'].format(room_id=room_id, date=date_key)
            self.redis_client.hincrby(stats_key, stat_type, value)
            self.redis_client.expire(stats_key, 2592000)  # 30天过期
        except Exception as e:
            self.logger.error(f"更新日统计失败: {e}")
    
    def _update_global_stats(self, data_type: str, value: int):
        """更新全局统计"""
        try:
            stats_key = self.KEYS['stats']
            self.redis_client.hincrby(stats_key, f'total_{data_type}', value)
            self.redis_client.hset(stats_key, 'last_update', datetime.now().isoformat())
        except Exception as e:
            self.logger.error(f"更新全局统计失败: {e}")
    
    def _publish_update(self, room_id: int, data: Dict):
        """发布实时更新通知"""
        try:
            channel = f'live_updates:room:{room_id}'
            self.redis_client.publish(channel, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            self.logger.error(f"发布更新失败: {e}")
    
    def get_room_stats_summary(self, room_id: int) -> Dict:
        """获取房间统计摘要"""
        try:
            current_data = self.get_room_current_data(room_id)
            
            # 获取今日统计
            today = datetime.now().strftime('%Y%m%d')
            daily_key = self.KEYS['daily_stats'].format(room_id=room_id, date=today)
            daily_stats = self.redis_client.hgetall(daily_key)
            
            # 获取当前小时统计
            current_hour = datetime.now().strftime('%Y%m%d%H')
            hourly_key = self.KEYS['hourly_stats'].format(room_id=room_id, hour=current_hour)
            hourly_stats = self.redis_client.hgetall(hourly_key)
            
            return {
                'room_id': room_id,
                'current': current_data,
                'today': {
                    'danmaku': int(daily_stats.get('danmaku', 0)),
                    'gifts': int(daily_stats.get('gifts', 0))
                },
                'this_hour': {
                    'danmaku': int(hourly_stats.get('danmaku', 0)),
                    'gifts': int(hourly_stats.get('gifts', 0))
                }
            }
        except Exception as e:
            self.logger.error(f"获取统计摘要失败: {e}")
            return {}
    
    # 继承原有方法...
    def get_room_current_data(self, room_id: int) -> Dict:
        """获取房间当前数据"""
        try:
            current_key = self.KEYS['room_current'].format(room_id=room_id)
            data = self.redis_client.hgetall(current_key)
            
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
            stream_data = self.redis_client.xrevrange(stream_key, count=count)
            
            result = []
            for stream_id, fields in stream_data:
                processed_fields = {}
                for key, value in fields.items():
                    if key in ['popularity', 'danmaku_count', 'gift_count', 'value', 'total_count', 'num', 'timestamp', 'price']:
                        try:
                            processed_fields[key] = int(value)
                        except ValueError:
                            processed_fields[key] = value
                    else:
                        processed_fields[key] = value
                
                processed_fields['stream_id'] = stream_id
                result.append(processed_fields)
            
            return list(reversed(result))
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

# 全局增强缓存实例
_enhanced_cache = None

def get_enhanced_live_cache() -> EnhancedLiveDataCache:
    """获取全局增强缓存实例"""
    global _enhanced_cache
    if _enhanced_cache is None:
        _enhanced_cache = EnhancedLiveDataCache()
    return _enhanced_cache