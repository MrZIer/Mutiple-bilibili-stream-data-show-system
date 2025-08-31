import redis
import json
import logging
import time
import sys
import os
from django.conf import settings

# 修复相对导入问题
try:
    from .data_cache import LiveDataCache, get_live_cache
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.data_cache import LiveDataCache, get_live_cache

logger = logging.getLogger(__name__)

def get_redis_client():
    """获取Redis客户端"""
    try:
        redis_config = getattr(settings, 'REDIS_CONFIG', {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'decode_responses': True
        })
        
        client = redis.Redis(**redis_config)
        client.ping()  # 测试连接
        return client
        
    except Exception as e:
        logger.error(f"Redis连接失败: {e}")
        raise

def init_live_cache():
    """初始化直播数据缓存"""
    return get_live_cache()

def save_to_redis(key: str, data: dict, expire_time: int = None):
    """保存数据到Redis"""
    try:
        client = get_redis_client()
        
        # 将数据转换为JSON字符串
        json_data = json.dumps(data, ensure_ascii=False)
        
        # 保存到Redis
        client.set(key, json_data)
        
        # 设置过期时间
        if expire_time:
            client.expire(key, expire_time)
        
        logger.debug(f"数据已保存到Redis: {key}")
        return True
        
    except Exception as e:
        logger.error(f"保存数据到Redis失败: {e}")
        return False

def get_from_redis(key: str) -> dict:
    """从Redis获取数据"""
    try:
        client = get_redis_client()
        data = client.get(key)
        
        if data:
            return json.loads(data)
        return {}
        
    except Exception as e:
        logger.error(f"从Redis获取数据失败: {e}")
        return {}

def delete_from_redis(key: str) -> bool:
    """从Redis删除数据"""
    try:
        client = get_redis_client()
        result = client.delete(key)
        logger.debug(f"从Redis删除数据: {key}")
        return result > 0
        
    except Exception as e:
        logger.error(f"从Redis删除数据失败: {e}")
        return False

def save_room_data_to_redis(room_id: int, data_type: str, data: dict):
    """保存房间数据到Redis"""
    try:
        cache = init_live_cache()
        
        if data_type == 'room_info':
            cache.save_room_info(room_id, data)
        elif data_type == 'danmaku':
            cache.save_real_time_data(room_id, 'danmaku', 1, data)
        elif data_type == 'gift':
            cache.save_real_time_data(room_id, 'gift', data.get('count', 1), data)
        elif data_type == 'popularity':
            cache.save_real_time_data(room_id, 'popularity', data.get('value', 0))
        else:
            # 通用保存
            key = f"room:{room_id}:{data_type}"
            save_to_redis(key, data, expire_time=3600)  # 1小时过期
        
        return True
        
    except Exception as e:
        logger.error(f"保存房间数据到Redis失败: {e}")
        return False

def get_room_data_from_redis(room_id: int, data_type: str = None) -> dict:
    """从Redis获取房间数据"""
    try:
        cache = init_live_cache()
        
        if data_type == 'dashboard':
            return cache.get_room_dashboard_data(room_id)
        elif data_type == 'current':
            return cache.get_room_current_data(room_id)
        elif data_type == 'info':
            return cache.get_room_info(room_id)
        elif data_type == 'danmaku':
            return {'danmaku': cache.get_recent_danmaku(room_id)}
        elif data_type == 'gifts':
            return {'gifts': cache.get_recent_gifts(room_id)}
        else:
            # 获取完整仪表板数据
            return cache.get_room_dashboard_data(room_id)
        
    except Exception as e:
        logger.error(f"从Redis获取房间数据失败: {e}")
        return {}

class RoomDataManager:
    """房间数据管理器"""
    
    def __init__(self):
        self.cache = init_live_cache()
    
    def save_room_data(self, room_id: int, data_type: str, value, extra_data=None):
        """保存房间数据"""
        return self.cache.save_real_time_data(room_id, data_type, value, extra_data)
    
    def save_room_info(self, room_id: int, room_info: dict):
        """保存房间信息"""
        return self.cache.save_room_info(room_id, room_info)
    
    def get_room_dashboard_data(self, room_id: int):
        """获取房间仪表板数据"""
        return self.cache.get_room_dashboard_data(room_id)
    
    def get_room_current_data(self, room_id: int):
        """获取房间当前数据"""
        return self.cache.get_room_current_data(room_id)
    
    def get_rooms_overview(self):
        """获取所有房间概览"""
        active_rooms = self.cache.get_active_rooms()
        rooms_data = []
        
        for room_id in active_rooms:
            try:
                room_info = self.cache.get_room_info(room_id)
                current_data = self.cache.get_room_current_data(room_id)
                
                if room_info or current_data:
                    rooms_data.append({
                        'room_id': room_id,
                        'uname': room_info.get('uname', f'主播{room_id}'),
                        'title': room_info.get('title', f'直播间{room_id}'),
                        'popularity': current_data.get('popularity', 0),
                        'total_danmaku': current_data.get('total_danmaku', 0),
                        'total_gifts': current_data.get('total_gifts', 0),
                        'last_update': current_data.get('last_update', ''),
                        'live_status': room_info.get('live_status', 0)
                    })
            except Exception as e:
                logger.error(f"获取房间 {room_id} 概览数据失败: {e}")
        
        return rooms_data
    
    def get_system_stats(self):
        """获取系统统计"""
        try:
            stats = self.cache.get_monitor_stats()
            active_rooms = self.cache.get_active_rooms()
            
            return {
                'active_rooms_count': len(active_rooms),
                'total_danmaku': stats.get('total_danmaku', 0),
                'total_gifts': stats.get('total_gifts', 0),
                'total_popularity': stats.get('total_popularity', 0),
                'last_update': stats.get('last_update', ''),
                'active_rooms': active_rooms
            }
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {}

    def clear_room_data(self, room_id: int):
        """清理房间数据"""
        return self.cache.clear_room_data(room_id)

# 全局管理器实例
_room_manager = None

def get_room_manager() -> RoomDataManager:
    """获取全局房间数据管理器"""
    global _room_manager
    if _room_manager is None:
        _room_manager = RoomDataManager()
    return _room_manager

# 便捷函数，向后兼容
def save_live_data(room_id: int, data_type: str, data: dict):
    """保存直播数据 - 便捷函数"""
    return save_room_data_to_redis(room_id, data_type, data)

def get_live_data(room_id: int, data_type: str = None):
    """获取直播数据 - 便捷函数"""
    return get_room_data_from_redis(room_id, data_type)

def test_redis_connection():
    """测试Redis连接"""
    try:
        # 创建一个简单的Redis客户端进行测试
        redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'decode_responses': True
        }
        
        client = redis.Redis(**redis_config)
        
        # 测试基本操作
        test_key = 'test_connection'
        test_data = {'test': 'success', 'timestamp': str(int(time.time()))}
        
        # 保存测试数据
        client.set(test_key, json.dumps(test_data), ex=10)
        
        # 读取测试数据
        retrieved_data_str = client.get(test_key)
        if retrieved_data_str:
            retrieved_data = json.loads(retrieved_data_str)
            if retrieved_data.get('test') == 'success':
                # 删除测试数据
                client.delete(test_key)
                logger.info("Redis连接测试成功")
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Redis连接测试失败: {e}")
        return False

def initialize_django_settings():
    """初始化Django设置（用于独立运行）"""
    import os
    import django
    from django.conf import settings
    
    if not settings.configured:
        # 设置Django的基本配置
        settings.configure(
            DEBUG=True,
            REDIS_CONFIG={
                'host': 'localhost',
                'port': 6379,
                'db': 0,
                'decode_responses': True
            },
            USE_TZ=True,
            SECRET_KEY='test-key-for-redis-handler'
        )
        django.setup()

if __name__ == "__main__":
    # 如果直接运行此文件，先初始化Django设置
    try:
        initialize_django_settings()
    except Exception as e:
        print(f"Django初始化失败: {e}")
        print("将使用基本Redis测试...")
    
    # 测试Redis连接
    print("测试Redis连接...")
    if test_redis_connection():
        print("✅ Redis连接正常")
    else:
        print("❌ Redis连接失败")
        print("请确保Redis服务已启动！")
    
    # 测试数据管理器（需要Django环境）
    print("\n测试数据管理器...")
    try:
        manager = get_room_manager()
        print("✅ 数据管理器初始化成功")
        
        # 测试保存数据
        test_room_id = 12345
        test_room_info = {
            'uname': '测试主播',
            'title': '测试直播间',
            'popularity': 1000
        }
        
        manager.save_room_info(test_room_id, test_room_info)
        print("✅ 房间信息保存成功")
        
        # 测试获取数据
        retrieved_info = manager.get_room_current_data(test_room_id)
        print(f"✅ 获取房间数据: {retrieved_info}")
        
        # 清理测试数据
        manager.clear_room_data(test_room_id)
        print("✅ 测试数据清理完成")
        
    except Exception as e:
        print(f"❌ 数据管理器测试失败: {e}")
        print("提示：数据管理器需要完整的Django环境")