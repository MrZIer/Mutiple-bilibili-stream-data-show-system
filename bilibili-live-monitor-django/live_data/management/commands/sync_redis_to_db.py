from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from live_data.models import LiveRoom, DanmakuData, GiftData, MonitoringTask, DataMigrationLog
from utils.redis_handler import get_redis_client, safe_decode, safe_json_loads
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
            choices=['danmaku', 'gift', 'room', 'task', 'all'],
            default='all',
            help='指定数据类型'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='批处理大小'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行，不实际写入数据库'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='静默模式，减少输出'
        )
    
    def handle(self, *args, **options):
        start_time = timezone.now()
        
        try:
            self.redis_client = get_redis_client()
        except Exception as e:
            self.stdout.write(f'❌ Redis连接失败: {e}')
            return
        
        self.batch_size = options['batch_size']
        self.dry_run = options['dry_run']
        self.quiet = options['quiet'] or options['verbosity'] == 0
        
        if self.dry_run and not self.quiet:
            self.stdout.write("🔍 试运行模式 - 不会实际写入数据")
        
        # 创建迁移日志
        migration_log = None
        if not self.dry_run:
            migration_log = DataMigrationLog.objects.create(
                migration_type=options['data_type'],
                start_time=start_time,
                status='running'
            )
        
        total_synced = 0
        sync_details = {
            'rooms': 0,
            'danmaku': 0,
            'gifts': 0,
            'tasks': 0
        }
        
        try:
            # 获取要同步的房间列表
            if options['room_id']:
                rooms = [options['room_id']]
            else:
                rooms = self.get_all_monitored_rooms()
            
            if not self.quiet:
                self.stdout.write(f"🎯 开始同步 {len(rooms)} 个房间的数据...")
            
            # 1. 同步房间信息
            if options['data_type'] in ['room', 'all']:
                if not self.quiet:
                    self.stdout.write("🏠 同步房间信息...")
                room_count = self.sync_room_data(rooms)
                sync_details['rooms'] = room_count
                total_synced += room_count
                if not self.quiet and room_count > 0:
                    self.stdout.write(f"  ✅ 房间: {room_count} 个")
            
            # 2. 同步弹幕数据
            if options['data_type'] in ['danmaku', 'all']:
                if not self.quiet:
                    self.stdout.write("💬 同步弹幕数据...")
                for room_id in rooms:
                    count = self.sync_danmaku_data(room_id)
                    sync_details['danmaku'] += count
                    total_synced += count
                    if not self.quiet and count > 0:
                        self.stdout.write(f"  📡 房间 {room_id}: {count} 条弹幕")
            
            # 3. 同步礼物数据
            if options['data_type'] in ['gift', 'all']:
                if not self.quiet:
                    self.stdout.write("🎁 同步礼物数据...")
                for room_id in rooms:
                    count = self.sync_gift_data(room_id)
                    sync_details['gifts'] += count
                    total_synced += count
                    if not self.quiet and count > 0:
                        self.stdout.write(f"  📡 房间 {room_id}: {count} 个礼物")
            
            # 4. 同步监控任务数据
            if options['data_type'] in ['task', 'all']:
                if not self.quiet:
                    self.stdout.write("📋 同步监控任务...")
                task_count = self.sync_monitoring_tasks()
                sync_details['tasks'] = task_count
                total_synced += task_count
                if not self.quiet and task_count > 0:
                    self.stdout.write(f"  ✅ 任务: {task_count} 个")
            
            # 更新迁移日志 - 成功
            if migration_log:
                migration_log.end_time = timezone.now()
                migration_log.total_records = total_synced
                migration_log.success_records = total_synced
                migration_log.failed_records = 0
                migration_log.status = 'completed'
                
                # 添加详细信息
                detail_msg = f"房间:{sync_details['rooms']}, 弹幕:{sync_details['danmaku']}, 礼物:{sync_details['gifts']}, 任务:{sync_details['tasks']}"
                migration_log.error_message = f"同步详情: {detail_msg}"
                migration_log.save()
            
            # 输出总结
            if not self.quiet or total_synced > 0:
                duration = (timezone.now() - start_time).total_seconds()
                self.stdout.write(f'✅ 同步完成！总计处理 {total_synced} 条数据，耗时 {duration:.2f}秒')
                self.stdout.write(f'📊 详情: 房间{sync_details["rooms"]}个, 弹幕{sync_details["danmaku"]}条, 礼物{sync_details["gifts"]}个, 任务{sync_details["tasks"]}个')
            
        except Exception as e:
            # 更新迁移日志 - 失败
            if migration_log:
                migration_log.end_time = timezone.now()
                migration_log.total_records = total_synced
                migration_log.success_records = max(0, total_synced - 1)
                migration_log.failed_records = 1
                migration_log.status = 'failed'
                migration_log.error_message = str(e)
                migration_log.save()
            
            self.stdout.write(f'❌ 同步失败: {e}')
            logger.error(f"数据同步失败: {e}", exc_info=True)
            raise
    
    def get_all_monitored_rooms(self):
        """获取所有被监控的房间ID"""
        try:
            redis_room_ids = set()
            
            # 从弹幕键获取房间ID
            danmaku_keys = self.redis_client.keys("room:*:danmaku")
            
            for key in danmaku_keys:
                try:
                    key_str = safe_decode(key)
                    if not key_str:
                        continue
                    
                    parts = key_str.split(':')
                    if len(parts) >= 3 and parts[0] == 'room':
                        room_id = int(parts[1])
                        redis_room_ids.add(room_id)
                except (ValueError, IndexError) as e:
                    logger.warning(f"解析键名失败: {key} - {e}")
                    continue
            
            # 从数据库获取已存在的房间ID
            db_room_ids = set(LiveRoom.objects.values_list('room_id', flat=True))
            
            # 合并Redis和数据库中的房间ID
            all_room_ids = redis_room_ids.union(db_room_ids)
            
            return list(all_room_ids)
            
        except Exception as e:
            logger.error(f"获取监控房间列表失败: {e}")
            return []
    
    def sync_room_data(self, room_ids):
        """同步房间信息数据"""
        try:
            synced_count = 0
            
            for room_id in room_ids:
                try:
                    # 从Redis获取房间信息
                    room_info_key = f"room:{room_id}:info"
                    
                    # 检查键是否存在以及键的类型
                    if not self.redis_client.exists(room_info_key):
                        # 键不存在，使用默认值创建房间
                        room, created = LiveRoom.objects.get_or_create(
                            room_id=room_id,
                            defaults={
                                'title': f'房间 {room_id}',
                                'uname': '未知主播',
                                'face': '',
                                'online': 0,
                                'status': 0
                            }
                        )
                        if created:
                            synced_count += 1
                        continue
                    
                    # 检查键的类型
                    key_type = self.redis_client.type(room_info_key)
                    key_type_str = safe_decode(key_type)
                    
                    room_data = {}
                    
                    # 根据不同的键类型处理数据
                    if key_type_str == 'string':
                        # 字符串类型，期望是JSON数据
                        room_info_data = self.redis_client.get(room_info_key)
                        if room_info_data:
                            room_data = safe_json_loads(room_info_data) or {}
                    
                    elif key_type_str == 'hash':
                        # 哈希类型，直接获取所有字段
                        hash_data = self.redis_client.hgetall(room_info_key)
                        room_data = {}
                        for field, value in hash_data.items():
                            field_str = safe_decode(field)
                            value_str = safe_decode(value)
                            
                            # 尝试转换数值类型
                            if field_str in ['online', 'status', 'room_id']:
                                try:
                                    room_data[field_str] = int(value_str)
                                except ValueError:
                                    room_data[field_str] = value_str
                            else:
                                room_data[field_str] = value_str
                    
                    elif key_type_str == 'list':
                        # 列表类型，获取最新的一条记录
                        latest_data = self.redis_client.lindex(room_info_key, 0)
                        if latest_data:
                            room_data = safe_json_loads(latest_data) or {}
                    
                    else:
                        logger.warning(f"房间{room_id}信息键类型不支持: {key_type_str}")
                        room_data = {}
                    
                    # 获取或创建房间记录
                    room, created = LiveRoom.objects.get_or_create(
                        room_id=room_id,
                        defaults={
                            'title': room_data.get('title', f'房间 {room_id}'),
                            'uname': room_data.get('uname', '未知主播'),
                            'face': room_data.get('face', ''),
                            'online': self.safe_int(room_data.get('online', 0)),
                            'status': self.safe_int(room_data.get('status', 0))
                        }
                    )
                    
                    # 如果房间已存在，更新信息
                    if not created and room_data:
                        updated = False
                        
                        new_title = room_data.get('title')
                        if new_title and room.title != new_title:
                            room.title = new_title[:200]  # 限制长度
                            updated = True
                        
                        new_uname = room_data.get('uname')
                        if new_uname and room.uname != new_uname:
                            room.uname = new_uname[:100]  # 限制长度
                            updated = True
                        
                        new_online = self.safe_int(room_data.get('online'))
                        if new_online is not None and room.online != new_online:
                            room.online = new_online
                            updated = True
                        
                        new_status = self.safe_int(room_data.get('status'))
                        if new_status is not None and room.status != new_status:
                            room.status = new_status
                            updated = True
                        
                        new_face = room_data.get('face')
                        if new_face and room.face != new_face:
                            room.face = new_face[:500]  # 限制长度
                            updated = True
                        
                        if updated and not self.dry_run:
                            room.save()
                    
                    synced_count += 1
                        
                except Exception as e:
                    logger.warning(f"同步房间{room_id}信息失败: {e}")
                    
                    # 即使出错，也尝试创建基本的房间记录
                    try:
                        room, created = LiveRoom.objects.get_or_create(
                            room_id=room_id,
                            defaults={
                                'title': f'房间 {room_id}',
                                'uname': '未知主播',
                                'face': '',
                                'online': 0,
                                'status': 0
                            }
                        )
                        if created:
                            synced_count += 1
                    except:
                        pass
                    
                    continue
            
            return synced_count
            
        except Exception as e:
            logger.error(f"同步房间数据失败: {e}")
            return 0
    
    def sync_danmaku_data(self, room_id):
        """同步弹幕数据"""
        try:
            redis_key = f"room:{room_id}:danmaku"
            
            # 获取Redis中的弹幕数据
            danmaku_list = self.redis_client.lrange(redis_key, 0, self.batch_size - 1)
            
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
                    danmaku_data = safe_json_loads(danmaku_json)
                    if not danmaku_data:
                        continue
                    
                    # 检查是否已存在（避免重复）
                    timestamp_val = danmaku_data.get('timestamp', 0)
                    if isinstance(timestamp_val, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp_val)
                    else:
                        timestamp = datetime.now()
                    
                    timestamp = timezone.make_aware(timestamp) if timezone.is_naive(timestamp) else timestamp
                    
                    exists = DanmakuData.objects.filter(
                        room=room,
                        uid=danmaku_data.get('uid', 0),
                        message=danmaku_data.get('message', '')[:500],  # 限制长度比较
                        timestamp=timestamp
                    ).exists()
                    
                    if exists:
                        continue
                    
                    # 准备数据
                    danmaku_obj = DanmakuData(
                        room=room,
                        uid=danmaku_data.get('uid', 0),
                        username=danmaku_data.get('username', '匿名用户')[:50],
                        message=danmaku_data.get('message', '')[:500],
                        timestamp=timestamp,
                        medal_name=danmaku_data.get('medal_name', '')[:50],
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
                        
                except Exception as e:
                    logger.warning(f"解析弹幕数据失败: {e}")
                    continue
            
            # 处理剩余数据
            if batch_data:
                if not self.dry_run:
                    with transaction.atomic():
                        DanmakuData.objects.bulk_create(batch_data, ignore_conflicts=True)
                synced_count += len(batch_data)
            
            return synced_count
            
        except Exception as e:
            logger.error(f"同步房间{room_id}弹幕数据失败: {e}")
            return 0
    
    def sync_gift_data(self, room_id):
        """同步礼物数据"""
        try:
            redis_key = f"room:{room_id}:gifts"
            
            # 获取Redis中的礼物数据
            gift_list = self.redis_client.lrange(redis_key, 0, self.batch_size - 1)
            
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
                    gift_data = safe_json_loads(gift_json)
                    if not gift_data:
                        continue
                    
                    # 检查是否已存在
                    timestamp_val = gift_data.get('timestamp', 0)
                    if isinstance(timestamp_val, (int, float)):
                        timestamp = datetime.fromtimestamp(timestamp_val)
                    else:
                        timestamp = datetime.now()
                    
                    timestamp = timezone.make_aware(timestamp) if timezone.is_naive(timestamp) else timestamp
                    
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
                        username=gift_data.get('username', '匿名用户')[:50],
                        gift_name=gift_data.get('gift_name', '未知礼物')[:100],
                        gift_id=gift_data.get('gift_id', 0),
                        num=num,
                        price=price,
                        total_price=total_price,
                        timestamp=timestamp,
                        medal_name=gift_data.get('medal_name', '')[:50],
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
                        
                except Exception as e:
                    logger.warning(f"解析礼物数据失败: {e}")
                    continue
            
            # 处理剩余数据
            if batch_data:
                if not self.dry_run:
                    with transaction.atomic():
                        GiftData.objects.bulk_create(batch_data, ignore_conflicts=True)
                synced_count += len(batch_data)
            
            return synced_count
            
        except Exception as e:
            logger.error(f"同步房间{room_id}礼物数据失败: {e}")
            return 0
    
    def sync_monitoring_tasks(self):
        """同步监控任务数据"""
        try:
            # 从Redis获取任务信息
            task_keys = self.redis_client.keys("task:*")
            synced_count = 0
            
            for task_key in task_keys:
                try:
                    key_str = safe_decode(task_key)
                    if not key_str:
                        continue
                    
                    # 获取任务数据
                    task_data_raw = self.redis_client.get(task_key)
                    if not task_data_raw:
                        continue
                    
                    task_data = safe_json_loads(task_data_raw)
                    if not task_data:
                        continue
                    
                    # 提取任务名称
                    task_name = task_data.get('task_name', key_str.split(':')[-1])
                    
                    # 获取或创建监控任务
                    task, created = MonitoringTask.objects.get_or_create(
                        task_name=task_name[:100],  # 限制长度
                        defaults={
                            'status': task_data.get('status', 'stopped'),
                            'collected_danmaku': task_data.get('collected_danmaku', 0),
                            'collected_gifts': task_data.get('collected_gifts', 0),
                            'error_count': task_data.get('error_count', 0),
                            'last_error': task_data.get('last_error', '')[:500],
                        }
                    )
                    
                    # 设置房间ID列表
                    if 'room_ids' in task_data:
                        task.set_room_ids(task_data['room_ids'])
                    
                    # 更新任务状态
                    if not created:
                        task.status = task_data.get('status', task.status)
                        task.collected_danmaku = task_data.get('collected_danmaku', task.collected_danmaku)
                        task.collected_gifts = task_data.get('collected_gifts', task.collected_gifts)
                        task.error_count = task_data.get('error_count', task.error_count)
                        task.last_error = task_data.get('last_error', task.last_error)[:500]
                    
                    # 设置时间
                    if 'start_time' in task_data:
                        start_timestamp = task_data['start_time']
                        if isinstance(start_timestamp, (int, float)):
                            start_time = datetime.fromtimestamp(start_timestamp)
                            task.start_time = timezone.make_aware(start_time) if timezone.is_naive(start_time) else start_time
                    
                    if 'end_time' in task_data:
                        end_timestamp = task_data['end_time']
                        if isinstance(end_timestamp, (int, float)):
                            end_time = datetime.fromtimestamp(end_timestamp)
                            task.end_time = timezone.make_aware(end_time) if timezone.is_naive(end_time) else end_time
                    
                    if not self.dry_run:
                        task.save()
                    
                    synced_count += 1
                    
                except Exception as e:
                    logger.warning(f"解析任务数据失败: {task_key} - {e}")
                    continue
            
            return synced_count
            
        except Exception as e:
            logger.error(f"同步监控任务失败: {e}")
            return 0
    
    def safe_int(self, value, default=None):
        """安全地转换为整数"""
        if value is None:
            return default
        try:
            if isinstance(value, str) and value.strip() == '':
                return default
            return int(value)
        except (ValueError, TypeError):
            return default