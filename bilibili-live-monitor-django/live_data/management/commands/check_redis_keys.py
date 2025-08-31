from django.core.management.base import BaseCommand
from utils.redis_handler import get_redis_client
import json

class Command(BaseCommand):
    help = '检查Redis中键的类型和内容'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--pattern',
            type=str,
            default='*',
            help='要检查的键模式'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='最多检查多少个键'
        )
    
    def handle(self, *args, **options):
        try:
            redis_client = get_redis_client()
            pattern = options['pattern']
            limit = options['limit']
            
            # 获取匹配的键
            keys = redis_client.keys(pattern)
            self.stdout.write(f"🔍 找到 {len(keys)} 个匹配 '{pattern}' 的键")
            
            if len(keys) == 0:
                self.stdout.write("⚠️ 没有找到任何键，可能Redis中没有数据")
                self.stdout.write("💡 建议先运行数据收集器: python multi_room_collector.py")
                return
            
            # 检查每个键
            for i, key in enumerate(keys[:limit]):
                if isinstance(key, bytes):
                    key_str = key.decode('utf-8')
                else:
                    key_str = str(key)
                
                self.stdout.write(f"\n📋 键 {i+1}: {key_str}")
                
                # 检查键类型
                key_type = redis_client.type(key)
                if isinstance(key_type, bytes):
                    key_type = key_type.decode('utf-8')
                
                self.stdout.write(f"   类型: {key_type}")
                
                # 根据类型显示内容
                try:
                    if key_type == 'string':
                        value = redis_client.get(key)
                        if isinstance(value, bytes):
                            value = value.decode('utf-8')
                        self.stdout.write(f"   长度: {len(value)} 字符")
                        
                        # 尝试解析为JSON
                        try:
                            json_data = json.loads(value)
                            if isinstance(json_data, dict):
                                self.stdout.write(f"   JSON字段: {list(json_data.keys())}")
                            else:
                                self.stdout.write(f"   JSON类型: {type(json_data).__name__}")
                        except:
                            self.stdout.write("   格式: 非JSON字符串")
                    
                    elif key_type == 'list':
                        length = redis_client.llen(key)
                        self.stdout.write(f"   列表长度: {length}")
                        if length > 0:
                            first_item = redis_client.lindex(key, 0)
                            if isinstance(first_item, bytes):
                                first_item = first_item.decode('utf-8')
                            self.stdout.write(f"   首项预览: {first_item[:50]}...")
                    
                    elif key_type == 'hash':
                        field_count = redis_client.hlen(key)
                        self.stdout.write(f"   哈希字段数: {field_count}")
                        if field_count > 0:
                            fields = redis_client.hkeys(key)[:3]
                            field_names = []
                            for field in fields:
                                if isinstance(field, bytes):
                                    field_names.append(field.decode('utf-8'))
                                else:
                                    field_names.append(str(field))
                            self.stdout.write(f"   字段示例: {', '.join(field_names)}")
                    
                    elif key_type == 'set':
                        size = redis_client.scard(key)
                        self.stdout.write(f"   集合大小: {size}")
                    
                    elif key_type == 'zset':
                        size = redis_client.zcard(key)
                        self.stdout.write(f"   有序集合大小: {size}")
                    
                    else:
                        self.stdout.write(f"   未知类型: {key_type}")
                
                except Exception as e:
                    self.stdout.write(f"   ❌ 读取失败: {e}")
            
            # 统计信息
            self.stdout.write(f"\n📊 统计信息:")
            patterns_to_check = [
                ("房间弹幕", "room:*:danmaku"),
                ("房间礼物", "room:*:gifts"),
                ("房间信息", "room:*:info"),
                ("监控任务", "task:*")
            ]
            
            for pattern_name, pattern_str in patterns_to_check:
                count = len(redis_client.keys(pattern_str))
                self.stdout.write(f"   {pattern_name}: {count} 个键")
            
        except Exception as e:
            self.stdout.write(f"❌ 检查失败: {e}")
            import traceback
            traceback.print_exc()