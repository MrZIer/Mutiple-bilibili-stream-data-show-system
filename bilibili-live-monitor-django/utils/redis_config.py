import redis
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def get_redis_client():
    """获取Redis客户端，带连接重试"""
    
    # 从Django settings获取配置
    redis_config = getattr(settings, 'REDIS_CONFIG', {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'decode_responses': True,
        'socket_timeout': 5,
        'socket_connect_timeout': 5,
        'retry_on_timeout': True,
        'health_check_interval': 30,
    })
    
    # 尝试多个连接配置
    connection_attempts = [
        {**redis_config, 'host': 'localhost'},
        {**redis_config, 'host': '127.0.0.1'},
        {**redis_config, 'host': 'localhost', 'port': 6380},
    ]
    
    for i, config in enumerate(connection_attempts):
        try:
            logger.info(f"尝试Redis连接配置 {i+1}: {config['host']}:{config['port']}")
            
            client = redis.Redis(**config)
            
            # 测试连接
            client.ping()
            logger.info(f"✅ Redis连接成功: {config['host']}:{config['port']}")
            
            return client
            
        except redis.ConnectionError as e:
            logger.warning(f"❌ Redis连接失败 {config['host']}:{config['port']}: {e}")
        except redis.TimeoutError as e:
            logger.warning(f"❌ Redis连接超时 {config['host']}:{config['port']}: {e}")
        except Exception as e:
            logger.error(f"❌ Redis连接异常 {config['host']}:{config['port']}: {e}")
    
    # 所有连接尝试都失败
    logger.error("❌ 所有Redis连接尝试都失败！")
    raise redis.ConnectionError("无法连接到Redis服务器")

def test_redis_connection():
    """测试Redis连接"""
    try:
        client = get_redis_client()
        
        # 基本读写测试
        test_key = 'django_redis_test'
        test_value = 'connection_ok'
        
        client.set(test_key, test_value, ex=60)
        result = client.get(test_key)
        client.delete(test_key)
        
        if result == test_value:
            logger.info("✅ Redis读写测试通过")
            return True
        else:
            logger.error("❌ Redis读写测试失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ Redis连接测试失败: {e}")
        return False

# 全局Redis客户端
_redis_client = None

def get_redis_client_cached():
    """获取缓存的Redis客户端"""
    global _redis_client
    
    if _redis_client is None:
        try:
            _redis_client = get_redis_client()
        except Exception as e:
            logger.error(f"获取Redis客户端失败: {e}")
            return None
    
    # 测试连接是否仍然有效
    try:
        _redis_client.ping()
        return _redis_client
    except:
        logger.warning("Redis连接已断开，重新连接...")
        try:
            _redis_client = get_redis_client()
            return _redis_client
        except Exception as e:
            logger.error(f"重新连接Redis失败: {e}")
            _redis_client = None
            return None