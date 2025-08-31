import redis
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

# Redis配置
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True,
    'socket_keepalive': True,
    'socket_keepalive_options': {},
    'health_check_interval': 30
}

class RedisClient:
    """Redis客户端管理类"""
    
    def __init__(self, config: Dict = None):
        self.config = config or REDIS_CONFIG
        self.client = None
        self.logger = logging.getLogger(__name__)
        self._connect()
    
    def _connect(self):
        """连接到Redis服务器"""
        try:
            self.client = redis.Redis(**self.config)
            # 测试连接
            self.client.ping()
            self.logger.info("Redis连接成功")
        except redis.ConnectionError as e:
            self.logger.error(f"Redis连接失败: {e}")
            raise
    
    def get_client(self):
        """获取Redis客户端实例"""
        if not self.client:
            self._connect()
        return self.client
    
    def is_connected(self) -> bool:
        """检查Redis连接状态"""
        try:
            self.client.ping()
            return True
        except:
            return False

# 全局Redis客户端实例
_redis_client = None

def get_redis_client() -> redis.Redis:
    """获取全局Redis客户端"""
    global _redis_client
    if _redis_client is None:
        redis_manager = RedisClient()
        _redis_client = redis_manager.get_client()
    return _redis_client