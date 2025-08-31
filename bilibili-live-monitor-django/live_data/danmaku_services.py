import redis
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from django.conf import settings
from django.utils import timezone
import time

logger = logging.getLogger(__name__)

class DanmakuService:
    """弹幕数据服务层"""
    
    def __init__(self):
        self.redis_client = None
        self.connection_status = {'status': 'unknown', 'message': '未初始化'}
        self._init_redis_connection()
    
    def _init_redis_connection(self):
        """初始化Redis连接，带重试机制"""
        redis_configs = [
            {'host': 'localhost', 'port': 6379, 'db': 0},
            {'host': '127.0.0.1', 'port': 6379, 'db': 0},
            {'host': 'redis', 'port': 6379, 'db': 0},  # Docker环境
        ]
        
        for config in redis_configs:
            try:
                logger.info(f"尝试连接Redis: {config}")
                
                self.redis_client = redis.Redis(
                    **config,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    max_connections=20,
                    health_check_interval=30
                )
                
                # 测试连接
                result = self.redis_client.ping()
                logger.info(f"Redis ping结果: {result}")
                
                if result:
                    # 获取Redis信息
                    info = self.redis_client.info()
                    self.connection_status = {
                        'status': 'connected',
                        'message': f"Redis连接成功 ({config['host']}:{config['port']}, 版本: {info.get('redis_version', 'unknown')})",
                        'config': config,
                        'redis_version': info.get('redis_version'),
                        'used_memory_human': info.get('used_memory_human')
                    }
                    
                    # 测试基本操作
                    test_key = f"test:django:{int(time.time())}"
                    self.redis_client.set(test_key, "test_value", ex=10)
                    test_result = self.redis_client.get(test_key)
                    self.redis_client.delete(test_key)
                    
                    if test_result == "test_value":
                        logger.info(f"✅ Redis连接成功并通过读写测试: {config}")
                        return
                    else:
                        logger.warning(f"Redis读写测试失败: {config}")
                        continue
                        
            except redis.ConnectionError as e:
                logger.warning(f"❌ Redis连接失败 {config}: ConnectionError - {e}")
                continue
            except redis.TimeoutError as e:
                logger.warning(f"❌ Redis连接超时 {config}: TimeoutError - {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Redis连接异常 {config}: {type(e).__name__} - {e}")
                continue
        
        # 所有连接都失败
        self.redis_client = None
        self.connection_status = {
            'status': 'error',
            'message': 'Redis连接失败，请检查Redis服务是否启动'
        }
        logger.error("❌ 所有Redis连接尝试都失败")
    
    def get_connection_status(self) -> Dict:
        """获取Redis连接状态"""
        try:
            if self.redis_client is None:
                return self.connection_status
            
            # 实时测试连接
            start_time = time.time()
            response = self.redis_client.ping()
            ping_time = round((time.time() - start_time) * 1000, 2)
            
            if response:
                info = self.redis_client.info()
                total_keys = len(self.redis_client.keys('*'))
                room_keys = len(self.redis_client.keys('room:*'))
                
                return {
                    'status': 'connected',
                    'message': f"Redis服务正常运行 (ping: {ping_time}ms)",
                    'redis_version': info.get('redis_version'),
                    'used_memory_human': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients', 0),
                    'total_keys': total_keys,
                    'room_keys': room_keys,
                    'ping_time': ping_time,
                    'last_check': datetime.now().strftime('%H:%M:%S')
                }
            else:
                return {
                    'status': 'error',
                    'message': 'Redis ping失败'
                }
                
        except redis.ConnectionError:
            logger.error("Redis连接断开，尝试重连...")
            self._init_redis_connection()
            return self.connection_status
        except Exception as e:
            logger.error(f"检查Redis状态失败: {e}")
            return {
                'status': 'error',
                'message': f'连接检查失败: {str(e)}'
            }
    
    def get_system_stats(self) -> Dict:
        """获取系统统计"""
        try:
            if self.redis_client is None:
                return {
                    'total_rooms': 0,
                    'active_rooms': 0,
                    'total_danmaku': 0,
                    'total_gifts': 0,
                    'redis_status': 'error',
                    'redis_message': 'Redis未连接'
                }
            
            # 获取Redis状态
            connection_status = self.get_connection_status()
            
            # 获取所有房间
            room_keys = self.redis_client.keys("room:*:info")
            total_rooms = len(room_keys)
            
            # 统计活跃房间和数据
            active_rooms = 0
            total_danmaku = 0
            total_gifts = 0
            
            for room_key in room_keys:
                try:
                    room_id = room_key.split(':')[1]
                    
                    # 检查是否有当前数据（判断为活跃）
                    current_key = f"room:{room_id}:current"
                    if self.redis_client.exists(current_key):
                        active_rooms += 1
                    
                    # 统计弹幕数量
                    danmaku_key = f"room:{room_id}:danmaku"
                    if self.redis_client.exists(danmaku_key):
                        count = self.redis_client.llen(danmaku_key)
                        total_danmaku += count
                    
                    # 统计礼物数量
                    gifts_key = f"room:{room_id}:gifts"
                    if self.redis_client.exists(gifts_key):
                        count = self.redis_client.llen(gifts_key)
                        total_gifts += count
                        
                except Exception as e:
                    logger.warning(f"处理房间 {room_key} 统计失败: {e}")
                    continue
            
            return {
                'total_rooms': total_rooms,
                'active_rooms': active_rooms,
                'total_danmaku': total_danmaku,
                'total_gifts': total_gifts,
                'redis_status': connection_status.get('status'),
                'redis_message': connection_status.get('message'),
                'last_check': datetime.now().strftime('%H:%M:%S'),
                'ping_time': connection_status.get('ping_time', 0)
            }
            
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {
                'total_rooms': 0,
                'active_rooms': 0,
                'total_danmaku': 0,
                'total_gifts': 0,
                'redis_status': 'error',
                'redis_message': f'统计失败: {str(e)}'
            }
    
    def get_available_rooms(self) -> List[Dict]:
        """获取所有有数据的房间"""
        try:
            if self.redis_client is None:
                logger.warning("Redis客户端未连接，返回空房间列表")
                return []
            
            room_keys = self.redis_client.keys("room:*:info")
            logger.info(f"找到 {len(room_keys)} 个房间键")
            
            rooms = []
            
            for room_key in room_keys:
                try:
                    room_id = int(room_key.split(':')[1])
                    room_info = self.redis_client.hgetall(room_key)
                    
                    if not room_info:
                        logger.warning(f"房间 {room_id} 信息为空")
                        continue
                    
                    # 获取弹幕数量
                    danmaku_key = f"room:{room_id}:danmaku"
                    danmaku_count = self.redis_client.llen(danmaku_key) if self.redis_client.exists(danmaku_key) else 0
                    
                    # 获取礼物数量
                    gifts_key = f"room:{room_id}:gifts"
                    gift_count = self.redis_client.llen(gifts_key) if self.redis_client.exists(gifts_key) else 0
                    
                    # 获取当前数据
                    current_key = f"room:{room_id}:current"
                    current_data = self.redis_client.hgetall(current_key) if self.redis_client.exists(current_key) else {}
                    
                    room_data = {
                        'room_id': room_id,
                        'uname': room_info.get('uname', f'主播{room_id}'),
                        'title': room_info.get('title', f'直播间{room_id}'),
                        'live_status': int(room_info.get('live_status', 0)),
                        'popularity': int(current_data.get('popularity', room_info.get('popularity', 0))),
                        'danmaku_count': danmaku_count,
                        'total_gifts': gift_count,
                        'last_update': current_data.get('last_update', ''),
                        'area_name': room_info.get('area_name', '未知分区'),
                        'online': int(current_data.get('online', room_info.get('online', 0))),
                    }
                    
                    # 只添加有数据的房间
                    if danmaku_count > 0 or gift_count > 0:
                        rooms.append(room_data)
                        logger.debug(f"添加房间 {room_id}: 弹幕{danmaku_count}, 礼物{gift_count}")
                    
                except (ValueError, KeyError) as e:
                    logger.warning(f"处理房间数据失败: {room_key}, 错误: {e}")
                    continue
            
            # 按弹幕数量排序
            rooms.sort(key=lambda x: x['danmaku_count'], reverse=True)
            logger.info(f"返回 {len(rooms)} 个有数据的房间")
            return rooms
            
        except Exception as e:
            logger.error(f"获取房间列表失败: {e}")
            return []
    
    def get_room_info(self, room_id: int) -> Optional[Dict]:
        """获取房间基本信息"""
        try:
            if self.redis_client is None:
                return None
            
            room_key = f"room:{room_id}:info"
            room_info = self.redis_client.hgetall(room_key)
            
            if room_info:
                # 获取当前数据
                current_key = f"room:{room_id}:current"
                current_data = self.redis_client.hgetall(current_key)
                
                return {
                    'room_id': room_id,
                    'uname': room_info.get('uname', '未知主播'),
                    'title': room_info.get('title', f'直播间{room_id}'),
                    'popularity': int(current_data.get('popularity', room_info.get('popularity', 0))),
                    'live_status': int(room_info.get('live_status', 0)),
                    'area_name': room_info.get('area_name', '未知分区'),
                    'cover': room_info.get('cover', ''),
                    'online': int(current_data.get('online', room_info.get('online', 0))),
                    'last_update': current_data.get('last_update', ''),
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"获取房间信息失败: {e}")
            return None
    
    def get_room_danmaku_stats(self, room_id: int) -> Dict:
        """获取房间弹幕统计"""
        try:
            if self.redis_client is None:
                return {'danmaku_count': 0, 'gift_count': 0}
            
            danmaku_key = f"room:{room_id}:danmaku"
            gift_key = f"room:{room_id}:gifts"
            
            danmaku_count = self.redis_client.llen(danmaku_key) if self.redis_client.exists(danmaku_key) else 0
            gift_count = self.redis_client.llen(gift_key) if self.redis_client.exists(gift_key) else 0
            
            # 获取当前数据
            current_key = f"room:{room_id}:current"
            current_data = self.redis_client.hgetall(current_key)
            
            return {
                'danmaku_count': danmaku_count,
                'gift_count': gift_count,
                'popularity': int(current_data.get('popularity', 0)),
                'online': int(current_data.get('online', 0)),
                'last_update': current_data.get('last_update', '')
            }
            
        except Exception as e:
            logger.error(f"获取房间统计失败: {e}")
            return {'danmaku_count': 0, 'gift_count': 0}
    
    def get_recent_danmaku(self, room_id: int, limit: int = 20) -> List[Dict]:
        """获取最近弹幕"""
        try:
            if self.redis_client is None:
                return []
            
            danmaku_key = f"room:{room_id}:danmaku"
            
            if not self.redis_client.exists(danmaku_key):
                logger.warning(f"弹幕键不存在: {danmaku_key}")
                return []
            
            # 获取最新的弹幕
            danmaku_list = self.redis_client.lrange(danmaku_key, 0, limit - 1)
            logger.debug(f"获取到 {len(danmaku_list)} 条弹幕数据")
            
            results = []
            for danmaku_json in danmaku_list:
                try:
                    danmaku_data = json.loads(danmaku_json)
                    
                    # 标准化数据格式
                    formatted_danmaku = {
                        'username': danmaku_data.get('username', danmaku_data.get('user', '未知用户')),
                        'message': danmaku_data.get('message', danmaku_data.get('content', '')),
                        'timestamp': danmaku_data.get('timestamp', danmaku_data.get('send_time', '')),
                        'user_level': danmaku_data.get('user_level', 0),
                        'send_time_formatted': danmaku_data.get('send_time_formatted', ''),
                        'room_id': room_id,
                    }
                    
                    results.append(formatted_danmaku)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"弹幕JSON解析失败: {danmaku_json[:100]}...")
                    continue
            
            logger.debug(f"成功解析 {len(results)} 条弹幕")
            return results
            
        except Exception as e:
            logger.error(f"获取弹幕失败: {e}")
            return []
    
    def get_recent_gifts(self, room_id: int, limit: int = 20) -> List[Dict]:
        """获取最近礼物"""
        try:
            if self.redis_client is None:
                return []
            
            gifts_key = f"room:{room_id}:gifts"
            
            if not self.redis_client.exists(gifts_key):
                return []
            
            # 获取最新的礼物
            gifts_list = self.redis_client.lrange(gifts_key, 0, limit - 1)
            
            results = []
            for gift_json in gifts_list:
                try:
                    gift_data = json.loads(gift_json)
                    
                    # 标准化数据格式
                    formatted_gift = {
                        'username': gift_data.get('username', '未知用户'),
                        'gift_name': gift_data.get('gift_name', '未知礼物'),
                        'num': gift_data.get('num', 1),
                        'price': gift_data.get('price', 0),
                        'coin_type': gift_data.get('coin_type', 'silver'),
                        'timestamp': gift_data.get('timestamp', ''),
                        'gift_time_formatted': gift_data.get('gift_time_formatted', ''),
                        'room_id': room_id,
                    }
                    
                    results.append(formatted_gift)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"礼物JSON解析失败: {gift_json[:100]}...")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"获取礼物失败: {e}")
            return []
    
    def search_danmaku(self, room_id: int, keyword: str = None, username: str = None, limit: int = 50) -> List[Dict]:
        """搜索弹幕"""
        try:
            if self.redis_client is None:
                return []
            
            danmaku_key = f"room:{room_id}:danmaku"
            
            if not self.redis_client.exists(danmaku_key):
                return []
            
            # 获取所有弹幕进行搜索
            all_danmaku = self.redis_client.lrange(danmaku_key, 0, -1)
            
            results = []
            for danmaku_json in all_danmaku:
                try:
                    danmaku_data = json.loads(danmaku_json)
                    
                    # 检查是否匹配搜索条件
                    match = False
                    
                    if keyword:
                        message = danmaku_data.get('message', danmaku_data.get('content', ''))
                        if keyword.lower() in message.lower():
                            match = True
                    
                    if username:
                        user = danmaku_data.get('username', danmaku_data.get('user', ''))
                        if username.lower() in user.lower():
                            match = True
                    
                    if match:
                        # 标准化数据格式
                        formatted_danmaku = {
                            'username': danmaku_data.get('username', danmaku_data.get('user', '未知用户')),
                            'message': danmaku_data.get('message', danmaku_data.get('content', '')),
                            'timestamp': danmaku_data.get('timestamp', danmaku_data.get('send_time', '')),
                            'send_time_formatted': danmaku_data.get('send_time_formatted', ''),
                            'room_id': room_id,
                        }
                        
                        results.append(formatted_danmaku)
                    
                    # 限制结果数量
                    if len(results) >= limit:
                        break
                        
                except json.JSONDecodeError:
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"搜索弹幕失败: {e}")
            return []
    
    def is_connected(self) -> bool:
        """检查Redis是否连接"""
        try:
            if self.redis_client is None:
                return False
            return self.redis_client.ping()
        except:
            return False
    
    def get_room_detailed_info(self, room_id: int) -> dict:
        """获取房间详细信息，包括UP主信息 - 增强版"""
        try:
            if not self.redis_client:
                self._init_redis_connection()
            
            room_info_key = f'room:{room_id}:info'
            room_info = self.redis_client.hgetall(room_info_key)
            
            if not room_info:
                return {}
            
            # 解码数据
            decoded_info = {}
            for k, v in room_info.items():
                key_name = k.decode('utf-8') if isinstance(k, bytes) else str(k)
                value = v.decode('utf-8') if isinstance(v, bytes) else str(v)
                decoded_info[key_name] = value
            
            # 转换数字字段
            numeric_fields = ['room_id', 'uid', 'live_status', 'online', 'attention', 'gender']
            for field in numeric_fields:
                if field in decoded_info and decoded_info[field].isdigit():
                    decoded_info[field] = int(decoded_info[field])
            
            # 转换布尔字段
            boolean_fields = ['is_verified']
            for field in boolean_fields:
                if field in decoded_info:
                    decoded_info[field] = decoded_info[field].lower() in ['true', '1', 'yes']
            
            # 添加实时统计
            stats = self.get_room_danmaku_stats(room_id)
            decoded_info.update(stats)
            
            # 添加额外的计算字段
            decoded_info['is_live'] = decoded_info.get('live_status', 0) == 1
            decoded_info['is_offline'] = decoded_info.get('live_status', 0) == 0
            decoded_info['is_round'] = decoded_info.get('live_status', 0) == 2
            
            # 人气等级
            popularity = decoded_info.get('online', 0)
            if popularity >= 10000:
                decoded_info['popularity_level'] = 'high'
            elif popularity >= 1000:
                decoded_info['popularity_level'] = 'medium'
            elif popularity >= 100:
                decoded_info['popularity_level'] = 'low'
            else:
                decoded_info['popularity_level'] = 'very_low'
            
            # 性别文本转换
            gender_map = {0: '未知', 1: '男', 2: '女', 3: '保密'}
            decoded_info['gender_text'] = gender_map.get(decoded_info.get('gender', 0), '未知')
            
            return decoded_info
            
        except Exception as e:
            logger.error(f"获取房间 {room_id} 详细信息失败: {e}")
            return {}

    def get_all_rooms_with_uploader_info(self) -> list:
        """获取所有房间及UP主信息"""
        try:
            if not self.redis_client:
                self._init_redis_connection()
            
            # 获取所有活跃房间
            active_rooms = self.redis_client.smembers('rooms:active')
            
            if not active_rooms:
                # 备用方案：从房间信息键中提取
                room_keys = self.redis_client.keys('room:*:info')
                room_ids = []
                for key in room_keys:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
                    try:
                        room_id = key_str.split(':')[1]
                        if room_id.isdigit():
                            room_ids.append(room_id)
                    except IndexError:
                        continue
                active_rooms = room_ids
            
            rooms = []
            processed_count = 0
            max_rooms = 200  # 限制最大房间数量，避免性能问题
            
            for room_id in active_rooms:
                if processed_count >= max_rooms:
                    break
                    
                try:
                    room_id = room_id.decode('utf-8') if isinstance(room_id, bytes) else str(room_id)
                    if not room_id.isdigit():
                        continue
                    
                    room_id = int(room_id)
                    room_data = self.get_room_detailed_info(room_id)
                    
                    if room_data:
                        # 确保包含所需字段
                        enhanced_room = {
                            'room_id': room_id,
                            'uname': room_data.get('uname', f'主播{room_id}'),
                            'title': room_data.get('title', ''),
                            'face': room_data.get('face', ''),  # UP主头像
                            'uid': room_data.get('uid', 0),
                            'gender': room_data.get('gender', 0),
                            'gender_text': room_data.get('gender_text', '未知'),
                            'is_verified': room_data.get('is_verified', False),
                            'verify_desc': room_data.get('verify_desc', ''),
                            'area_name': room_data.get('area_name', ''),
                            'parent_area_name': room_data.get('parent_area_name', ''),
                            'live_status': room_data.get('live_status', 0),
                            'live_status_text': self._get_live_status_text(room_data.get('live_status', 0)),
                            'online': room_data.get('online', 0),
                            'attention': room_data.get('attention', 0),
                            'cover': room_data.get('cover', ''),
                            'keyframe': room_data.get('keyframe', ''),
                            'danmaku_count': room_data.get('danmaku_count', 0),
                            'gift_count': room_data.get('gift_count', 0),
                            'last_danmaku_time': room_data.get('last_danmaku_time'),
                            'last_gift_time': room_data.get('last_gift_time'),
                            'updated_at': room_data.get('updated_at', timezone.now().isoformat()),
                            'popularity_level': room_data.get('popularity_level', 'very_low'),
                            'is_live': room_data.get('is_live', False),
                            'is_offline': room_data.get('is_offline', True),
                            'is_round': room_data.get('is_round', False),
                            'live_time': self._calculate_live_time(room_data.get('live_time')),
                        }
                        
                        rooms.append(enhanced_room)
                        processed_count += 1
                        
                except Exception as e:
                    logger.warning(f"处理房间 {room_id} 信息时出错: {e}")
                    continue
            
            # 按在线人数和弹幕活跃度排序
            rooms.sort(key=lambda x: (
                x.get('online', 0) * 1000 + x.get('danmaku_count', 0)
            ), reverse=True)
            
            logger.info(f"成功处理 {len(rooms)} 个房间信息")
            return rooms
            
        except Exception as e:
            logger.error(f"获取所有房间UP主信息失败: {e}")
            return []

    def _get_live_status_text(self, status: int) -> str:
        """获取直播状态文本"""
        status_map = {
            0: '未开播',
            1: '直播中',
            2: '轮播中'
        }
        return status_map.get(status, '未知')

    def _calculate_live_time(self, live_time_data) -> str:
        """计算直播时长"""
        try:
            if not live_time_data:
                return '--:--'
            
            # 如果已经是格式化的时间字符串，直接返回
            if isinstance(live_time_data, str) and ':' in live_time_data:
                return live_time_data
            
            # 如果是时间戳，计算时长
            if isinstance(live_time_data, (int, float)):
                hours = int(live_time_data // 3600)
                minutes = int((live_time_data % 3600) // 60)
                return f"{hours:02d}:{minutes:02d}"
            
            return '--:--'
        except:
            return '--:--'

    def get_room_danmaku_stats(self, room_id: int) -> dict:
        """获取房间弹幕统计"""
        try:
            if not self.redis_client:
                self._init_redis_connection()
            
            stats = {}
            
            # 获取弹幕数量
            danmaku_count = self.redis_client.llen(f'room:{room_id}:danmaku')
            stats['danmaku_count'] = danmaku_count
            
            # 获取礼物数量
            gift_count = self.redis_client.llen(f'room:{room_id}:gifts')
            stats['gift_count'] = gift_count
            
            # 获取房间统计信息
            room_stats_data = self.redis_client.hgetall(f'room:{room_id}:stats')
            for k, v in room_stats_data.items():
                key_name = k.decode('utf-8') if isinstance(k, bytes) else str(k)
                value = v.decode('utf-8') if isinstance(v, bytes) else str(v)
                stats[key_name] = value
            
            # 获取最后活动时间
            last_danmaku = self.redis_client.lrange(f'room:{room_id}:danmaku', 0, 0)
            if last_danmaku:
                try:
                    danmaku_data = json.loads(last_danmaku[0].decode('utf-8'))
                    stats['last_danmaku_time'] = danmaku_data.get('timestamp')
                except:
                    pass
            
            last_gift = self.redis_client.lrange(f'room:{room_id}:gifts', 0, 0)
            if last_gift:
                try:
                    gift_data = json.loads(last_gift[0].decode('utf-8'))
                    stats['last_gift_time'] = gift_data.get('timestamp')
                except:
                    pass
            
            return stats
            
        except Exception as e:
            logger.error(f"获取房间 {room_id} 弹幕统计失败: {e}")
            return {}

    def get_system_stats(self) -> dict:
        """获取系统统计信息"""
        try:
            connection_status = self.get_connection_status()
            
            if connection_status.get('status') != 'connected':
                return {
                    'redis_status': 'error',
                    'redis_message': connection_status.get('message', 'Redis连接失败'),
                    'total_rooms': 0,
                    'active_rooms': 0,
                    'total_danmaku': 0,
                    'total_gifts': 0,
                    'verified_users': 0,
                    'total_online': 0
                }
            
            # 获取所有房间数据
            rooms = self.get_all_rooms_with_uploader_info()
            
            # 计算统计
            total_rooms = len(rooms)
            active_rooms = len([r for r in rooms if r.get('live_status') == 1])
            verified_users = len([r for r in rooms if r.get('is_verified')])
            total_danmaku = sum(r.get('danmaku_count', 0) for r in rooms)
            total_gifts = sum(r.get('gift_count', 0) for r in rooms)
            total_online = sum(r.get('online', 0) for r in rooms)
            
            return {
                'redis_status': 'connected',
                'redis_message': '连接正常',
                'total_rooms': total_rooms,
                'active_rooms': active_rooms,
                'offline_rooms': total_rooms - active_rooms,
                'verified_users': verified_users,
                'total_danmaku': total_danmaku,
                'total_gifts': total_gifts,
                'total_online': total_online,
                'avg_popularity': round(total_online / max(total_rooms, 1), 2),
                'last_update': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {
                'redis_status': 'error',
                'redis_message': f'获取统计失败: {str(e)}',
                'total_rooms': 0,
                'active_rooms': 0,
                'total_danmaku': 0,
                'total_gifts': 0,
                'verified_users': 0,
                'total_online': 0
            }

    def get_available_rooms(self) -> list:
        """获取可用房间列表"""
        try:
            rooms_with_info = self.get_all_rooms_with_uploader_info()
            
            # 转换为简化格式以保持兼容性
            simple_rooms = []
            for room in rooms_with_info:
                simple_room = {
                    'room_id': room['room_id'],
                    'title': room.get('title', ''),
                    'uname': room.get('uname', f'主播{room["room_id"]}'),
                    'online': room.get('online', 0),
                    'live_status': room.get('live_status', 0),
                    'area_name': room.get('area_name', ''),
                    'danmaku_count': room.get('danmaku_count', 0),
                    'gift_count': room.get('gift_count', 0)
                }
                simple_rooms.append(simple_room)
            
            return simple_rooms
            
        except Exception as e:
            logger.error(f"获取可用房间列表失败: {e}")
            return []

    def get_room_info(self, room_id: int) -> dict:
        """获取房间基本信息"""
        try:
            detailed_info = self.get_room_detailed_info(room_id)
            
            if not detailed_info:
                return {}
            
            # 返回基本信息字段
            return {
                'room_id': detailed_info.get('room_id', room_id),
                'title': detailed_info.get('title', ''),
                'uname': detailed_info.get('uname', ''),
                'uid': detailed_info.get('uid', 0),
                'live_status': detailed_info.get('live_status', 0),
                'online': detailed_info.get('online', 0),
                'area_name': detailed_info.get('area_name', ''),
                'parent_area_name': detailed_info.get('parent_area_name', ''),
                'face': detailed_info.get('face', ''),
                'cover': detailed_info.get('cover', ''),
                'attention': detailed_info.get('attention', 0),
                'is_verified': detailed_info.get('is_verified', False),
                'gender_text': detailed_info.get('gender_text', '未知')
            }
            
        except Exception as e:
            logger.error(f"获取房间 {room_id} 信息失败: {e}")
            return {}



