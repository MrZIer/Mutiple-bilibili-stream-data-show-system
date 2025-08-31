"""
Redis连接处理器 - 修复编码问题版本
"""
import redis
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Redis配置
REDIS_CONFIG = {
    'host': getattr(settings, 'REDIS_HOST', 'localhost'),
    'port': getattr(settings, 'REDIS_PORT', 6379),
    'db': getattr(settings, 'REDIS_DB', 0),
    'decode_responses': False,  # 保持字节格式，手动处理编码
}

def get_redis_client():
    """获取Redis客户端"""
    try:
        client = redis.Redis(**REDIS_CONFIG)
        # 测试连接
        client.ping()
        return client
    except redis.ConnectionError as e:
        logger.error(f"Redis连接失败: {e}")
        raise
    except Exception as e:
        logger.error(f"创建Redis客户端失败: {e}")
        raise

def safe_decode(data, encoding='utf-8', errors='replace'):
    """安全的字符串解码"""
    if data is None:
        return None
    
    if isinstance(data, str):
        return data
    
    if isinstance(data, bytes):
        try:
            # 首先尝试UTF-8解码
            return data.decode(encoding)
        except UnicodeDecodeError:
            try:
                # 尝试其他常见编码
                for enc in ['gbk', 'gb2312', 'iso-8859-1', 'latin1']:
                    try:
                        return data.decode(enc)
                    except UnicodeDecodeError:
                        continue
                
                # 如果所有编码都失败，使用错误处理策略
                return data.decode('utf-8', errors=errors)
            except Exception:
                # 最后的fallback - 返回可打印的表示
                return repr(data)
    
    # 其他类型直接转换为字符串
    return str(data)

def safe_json_loads(data):
    """安全的JSON解析"""
    try:
        if data is None:
            return None
            
        # 安全解码为字符串
        json_str = safe_decode(data)
        if json_str is None:
            return None
            
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"JSON解析失败: {e}")
        return None

def safe_redis_get(client, key):
    """安全的Redis获取操作"""
    try:
        return client.get(key)
    except Exception as e:
        logger.error(f"Redis GET操作失败 {key}: {e}")
        return None

def safe_redis_lrange(client, key, start=0, end=-1):
    """安全的Redis列表范围获取操作"""
    try:
        return client.lrange(key, start, end)
    except Exception as e:
        logger.error(f"Redis LRANGE操作失败 {key}: {e}")
        return []

def safe_redis_keys(client, pattern):
    """安全的Redis键查询操作"""
    try:
        keys = client.keys(pattern)
        # 安全解码键名
        decoded_keys = []
        for key in keys:
            decoded_key = safe_decode(key)
            if decoded_key:
                decoded_keys.append(decoded_key)
        return decoded_keys
    except Exception as e:
        logger.error(f"Redis KEYS操作失败 {pattern}: {e}")
        return []