from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from live_data.models import LiveRoom, DanmakuData, GiftData, DataMigrationLog
from utils.redis_handler import get_redis_client
import json
import logging
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '将Redis中的数据同步到SQLite数据库'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--room-id',
            type=int,
            help='指定房间ID，不指定则同步所有房间'
        )
        parser.add_argument(
            '--data-type',
            choices=['danmaku', 'gift', 'all'],
            default='all',
            help='指定数据类型'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='批处理大小'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行，不实际写入数据库'
        )
    
    def handle(self, *args, **options):
        self.redis_client = get_redis_client()
        self.batch_size = options['batch_size']
        self.dry_run = options['dry_run']
        
        if self.dry_run:
            self.stdout.write("🔍 试运行模式 - 不会实际写入数据")
        
        # 创建迁移日志
        migration_log = DataMigrationLog.objects.create(
            migration_type=options['data_type'],
            start_time=timezone.now(),
            status='running'
        )
        
        try:
            if options['room_id']:
                rooms = [options['room_id']]
            else:
                rooms = self.get_all_monitored_rooms()
            
            total_synced = 0
            
            for room_id in rooms:
                self.stdout.write(f"📡 同步房间 {room_id} 的数据...")
                
                if options['data_type'] in ['danmaku', 'all']:
                    count = self.sync_danmaku_data(room_id)
                    total_synced += count
                    self.stdout.write(f"  ✅ 弹幕: {count} 条")
                
                if options['data_type'] in ['gift', 'all']:
                    count = self.sync_gift_data(room_id)
                    total_synced += count
                    self.stdout.write(f"  ✅ 礼物: {count} 条")
            
            # 更新迁移日志
            migration_log.end_time = timezone.now()
            migration_log.total_records = total_synced
            migration_log.success_records = total_synced
            migration_log.status = 'completed'
            migration_log.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'🎉 同步完成！总计处理 {total_synced} 条数据')
            )
            
        except Exception as e:
            # 更新迁移日志
            migration_log.end_time = timezone.now()
            migration_log.status = 'failed'
            migration_log.error_message = str(e)
            migration_log.save()
            
            self.stdout.write(
                self.style.ERROR(f'❌ 同步失败: {e}')
            )
            raise
    
    def get_all_monitored_rooms(self):
        """获取所有被监控的房间ID"""
        pattern = "room:*:danmaku"
        keys = self.redis_client.keys(pattern)
        
        room_ids = []
        for key in keys:
            try:
                # 从 "room:123456:danmaku" 中提取房间ID
                room_id = int(key.decode('utf-8').split(':')[1])
                room_ids.append(room_id)
            except (ValueError, IndexError):
                continue
        
        return list(set(room_ids))  # 去重
    
    def sync_danmaku_data(self, room_id):
        """同步弹幕数据"""
        redis_key = f"room:{room_id}:danmaku"
        
        # 获取Redis中的弹幕数据
        danmaku_list = self.redis_client.lrange(redis_key, 0, -1)
        
        if not danmaku_list:
            return 0
        
        # 确保房间存在
        room, created = LiveRoom.objects.get_or_create(
            room_id=room_id,
            defaults={
                'title': f'房间 {room_id}',
                'uname': '未知主播'
            }
        )
        
        synced_count = 0
        batch_data = []
        
        for danmaku_json in danmaku_list:
            try:
                danmaku_data = json.loads(danmaku_json)
                
                # 检查是否已存在（避免重复）
                timestamp = datetime.fromtimestamp(danmaku_data.get('timestamp', 0))
                timestamp = timezone.make_aware(timestamp)
                
                exists = DanmakuData.objects.filter(
                    room=room,
                    uid=danmaku_data.get('uid', 0),
                    message=danmaku_data.get('message', ''),
                    timestamp=timestamp
                ).exists()
                
                if exists:
                    continue
                
                # 准备数据
                danmaku_obj = DanmakuData(
                    room=room,
                    uid=danmaku_data.get('uid', 0),
                    username=danmaku_data.get('username', '匿名用户'),
                    message=danmaku_data.get('message', ''),
                    timestamp=timestamp,
                    medal_name=danmaku_data.get('medal_name', ''),
                    medal_level=danmaku_data.get('medal_level', 0),
                    user_level=danmaku_data.get('user_level', 0),
                    is_admin=danmaku_data.get('is_admin', False),
                    is_vip=danmaku_data.get('is_vip', False)
                )
                
                batch_data.append(danmaku_obj)
                
                # 批量插入
                if len(batch_data) >= self.batch_size:
                    if not self.dry_run:
                        with transaction.atomic():
                            DanmakuData.objects.bulk_create(batch_data, ignore_conflicts=True)
                    synced_count += len(batch_data)
                    batch_data = []
                    
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"解析弹幕数据失败: {e}")
                continue
        
        # 处理剩余数据
        if batch_data:
            if not self.dry_run:
                with transaction.atomic():
                    DanmakuData.objects.bulk_create(batch_data, ignore_conflicts=True)
            synced_count += len(batch_data)
        
        return synced_count
    
    def sync_gift_data(self, room_id):
        """同步礼物数据"""
        redis_key = f"room:{room_id}:gifts"
        
        # 获取Redis中的礼物数据
        gift_list = self.redis_client.lrange(redis_key, 0, -1)
        
        if not gift_list:
            return 0
        
        # 确保房间存在
        room, created = LiveRoom.objects.get_or_create(
            room_id=room_id,
            defaults={
                'title': f'房间 {room_id}',
                'uname': '未知主播'
            }
        )
        
        synced_count = 0
        batch_data = []
        
        for gift_json in gift_list:
            try:
                gift_data = json.loads(gift_json)
                
                # 检查是否已存在（避免重复）
                timestamp = datetime.fromtimestamp(gift_data.get('timestamp', 0))
                timestamp = timezone.make_aware(timestamp)
                
                exists = GiftData.objects.filter(
                    room=room,
                    uid=gift_data.get('uid', 0),
                    gift_id=gift_data.get('gift_id', 0),
                    timestamp=timestamp
                ).exists()
                
                if exists:
                    continue
                
                # 准备数据
                price = Decimal(str(gift_data.get('price', 0)))
                num = gift_data.get('num', 1)
                total_price = price * num
                
                gift_obj = GiftData(
                    room=room,
                    uid=gift_data.get('uid', 0),
                    username=gift_data.get('username', '匿名用户'),
                    gift_name=gift_data.get('gift_name', '未知礼物'),
                    gift_id=gift_data.get('gift_id', 0),
                    num=num,
                    price=price,
                    total_price=total_price,
                    timestamp=timestamp,
                    medal_name=gift_data.get('medal_name', ''),
                    medal_level=gift_data.get('medal_level', 0)
                )
                
                batch_data.append(gift_obj)
                
                # 批量插入
                if len(batch_data) >= self.batch_size:
                    if not self.dry_run:
                        with transaction.atomic():
                            GiftData.objects.bulk_create(batch_data, ignore_conflicts=True)
                    synced_count += len(batch_data)
                    batch_data = []
                    
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"解析礼物数据失败: {e}")
                continue
        
        # 处理剩余数据
        if batch_data:
            if not self.dry_run:
                with transaction.atomic():
                    GiftData.objects.bulk_create(batch_data, ignore_conflicts=True)
            synced_count += len(batch_data)
        
        return synced_count