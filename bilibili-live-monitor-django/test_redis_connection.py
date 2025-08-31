"""
测试Redis连接和数据的脚本
"""
import os
import sys
import django

# 设置Django环境
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')
django.setup()

def test_redis_connection():
    """测试Redis连接和数据"""
    try:
        from utils.redis_handler import get_redis_client
        redis_client = get_redis_client()
        
        # 测试Redis连接
        redis_client.ping()
        print('✅ Redis连接正常')
        
        # 查看Redis中的房间数据
        keys = redis_client.keys('room:*')
        print(f'Redis中有 {len(keys)} 个房间相关的键')
        
        # 显示前几个键
        for i, key in enumerate(keys[:5]):
            # 修复：统一处理字符串和字节类型的键
            if isinstance(key, bytes):
                key_str = key.decode('utf-8')
            else:
                key_str = str(key)
            print(f'  {i+1}. {key_str}')
        
        # 查看弹幕和礼物数据
        danmaku_keys = redis_client.keys('room:*:danmaku')
        gift_keys = redis_client.keys('room:*:gifts')
        
        print(f'\n📝 弹幕数据键: {len(danmaku_keys)} 个')
        print(f'🎁 礼物数据键: {len(gift_keys)} 个')
        
        if danmaku_keys:
            # 查看第一个房间的弹幕数量
            first_key = danmaku_keys[0]
            if isinstance(first_key, bytes):
                first_key_str = first_key.decode('utf-8')
            else:
                first_key_str = str(first_key)
                
            count = redis_client.llen(first_key)
            print(f'\n房间 {first_key_str} 有 {count} 条弹幕')
            
            # 查看最新的一条弹幕
            if count > 0:
                latest = redis_client.lindex(first_key, 0)
                if isinstance(latest, bytes):
                    latest_str = latest.decode('utf-8')
                else:
                    latest_str = str(latest)
                print(f'最新弹幕: {latest_str[:100]}...')
        
        return True
        
    except Exception as e:
        print(f'❌ Redis测试失败: {e}')
        return False

if __name__ == '__main__':
    test_redis_connection()