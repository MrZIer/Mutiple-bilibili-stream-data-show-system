import asyncio
import threading
import time
import logging
import random
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction, DatabaseError
from django.conf import settings
from typing import List, Dict, Any, Tuple

from .collectors import get_data_collector, LiveDataCollector
# 导入模型
from .models import LiveRoom, DanmakuData, GiftData, DataMigrationLog

# 导入Redis处理器
try:
    from utils.redis_handler import get_redis_client
except ImportError:
    # 如果utils.redis_handler不存在，创建一个简单的Redis客户端
    import redis
    def get_redis_client():
        return redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

logger = logging.getLogger(__name__)

class DataMigrationService:
    """数据迁移服务"""
    
    def __init__(self):
        try:
            self.redis_client = get_redis_client()
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self.redis_client = None
        
        self.batch_size = getattr(settings, 'MIGRATION_BATCH_SIZE', 1000)
        self.max_retries = getattr(settings, 'MIGRATION_MAX_RETRIES', 3)
    
    def migrate_all_data(self, cleanup_redis=True, max_age_hours=24):
        """
        迁移所有数据到数据库
        
        Args:
            cleanup_redis: 是否清理Redis中已迁移的数据
            max_age_hours: 只迁移指定小时内的数据
        """
        logger.info("开始执行数据迁移任务")
        
        if not self.redis_client:
            logger.error("Redis客户端未初始化")
            return {
                'danmaku': {'success': 0, 'failed': 0, 'errors': ['Redis连接失败']},
                'gifts': {'success': 0, 'failed': 0, 'errors': ['Redis连接失败']},
                'rooms': {'success': 0, 'failed': 0, 'errors': ['Redis连接失败']}
            }
        
        results = {
            'danmaku': {'success': 0, 'failed': 0, 'errors': []},
            'gifts': {'success': 0, 'failed': 0, 'errors': []},
            'rooms': {'success': 0, 'failed': 0, 'errors': []}
        }
        
        try:
            # 1. 迁移房间信息
            room_result = self.migrate_room_data(cleanup_redis, max_age_hours)
            results['rooms'] = room_result
            
            # 2. 迁移弹幕数据
            danmaku_result = self.migrate_danmaku_data(cleanup_redis, max_age_hours)
            results['danmaku'] = danmaku_result
            
            # 3. 迁移礼物数据
            gift_result = self.migrate_gift_data(cleanup_redis, max_age_hours)
            results['gifts'] = gift_result
            
            # 4. 清理过期的Redis键（可选）
            if cleanup_redis:
                self.cleanup_expired_redis_data(max_age_hours)
            
            logger.info(f"数据迁移完成: {results}")
            return results
            
        except Exception as e:
            logger.error(f"数据迁移过程中发生错误: {e}", exc_info=True)
            return results
    
    def migrate_room_data(self, cleanup_redis=True, max_age_hours=24):
        """迁移房间数据"""
        log_entry = DataMigrationLog.objects.create(
            migration_type='room',
            start_time=timezone.now()
        )
        
        try:
            # 获取所有房间键
            room_keys = self.redis_client.keys('room:*:info')
            total_records = len(room_keys)
            log_entry.total_records = total_records
            log_entry.save()
            
            success_count = 0
            failed_count = 0
            errors = []
            
            logger.info(f"开始迁移房间数据，共 {total_records} 个房间")
            
            for room_key in room_keys:
                try:
                    # 提取房间ID
                    room_id = int(room_key.split(':')[1])
                    
                    # 获取房间信息
                    room_data = self.redis_client.hgetall(room_key)
                    if not room_data:
                        continue
                    
                    # 检查或创建房间记录
                    room, created = LiveRoom.objects.get_or_create(
                        room_id=room_id,
                        defaults={
                            'title': room_data.get('title', ''),
                            'uname': room_data.get('uname', ''),
                            'face': room_data.get('face', ''),
                            'online': int(room_data.get('online', 0)),
                            'status': int(room_data.get('status', 0))
                        }
                    )
                    
                    # 如果不是新创建的，更新信息
                    if not created:
                        room.title = room_data.get('title', room.title)
                        room.uname = room_data.get('uname', room.uname)
                        room.face = room_data.get('face', room.face)
                        room.online = int(room_data.get('online', room.online))
                        room.status = int(room_data.get('status', room.status))
                        room.save()
                    
                    success_count += 1
                    
                except Exception as e:
                    failed_count += 1
                    error_msg = f"房间 {room_key} 迁移失败: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 更新日志
            log_entry.end_time = timezone.now()
            log_entry.success_records = success_count
            log_entry.failed_records = failed_count
            log_entry.status = 'completed' if failed_count == 0 else 'partial'
            if errors:
                log_entry.error_message = '\n'.join(errors[:10])
            log_entry.save()
            
            logger.info(f"房间数据迁移完成: 成功 {success_count}, 失败 {failed_count}")
            
            return {
                'success': success_count,
                'failed': failed_count,
                'errors': errors
            }
            
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.end_time = timezone.now()
            log_entry.save()
            raise
    
    def migrate_danmaku_data(self, cleanup_redis=True, max_age_hours=24):
        """迁移弹幕数据"""
        log_entry = DataMigrationLog.objects.create(
            migration_type='danmaku',
            start_time=timezone.now()
        )
        
        try:
            # 获取所有弹幕列表键
            danmaku_keys = self.redis_client.keys('room:*:danmaku')
            total_keys = len(danmaku_keys)
            
            success_count = 0
            failed_count = 0
            errors = []
            
            logger.info(f"开始迁移弹幕数据，共 {total_keys} 个房间")
            
            # 计算时间阈值
            time_threshold = timezone.now() - timedelta(hours=max_age_hours)
            
            for danmaku_key in danmaku_keys:
                try:
                    # 提取房间ID
                    room_id = int(danmaku_key.split(':')[1])
                    
                    # 获取房间对象
                    try:
                        room = LiveRoom.objects.get(room_id=room_id)
                    except LiveRoom.DoesNotExist:
                        room = LiveRoom.objects.create(
                            room_id=room_id,
                            title=f"房间 {room_id}",
                            uname="未知主播"
                        )
                    
                    # 分批处理弹幕数据
                    batch_success, batch_failed, batch_errors = self._migrate_danmaku_batch(
                        danmaku_key, room, time_threshold, cleanup_redis
                    )
                    
                    success_count += batch_success
                    failed_count += batch_failed
                    errors.extend(batch_errors)
                    
                except Exception as e:
                    error_msg = f"处理房间 {danmaku_key} 弹幕时出错: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 更新日志
            log_entry.end_time = timezone.now()
            log_entry.total_records = success_count + failed_count
            log_entry.success_records = success_count
            log_entry.failed_records = failed_count
            log_entry.status = 'completed' if failed_count == 0 else 'partial'
            if errors:
                log_entry.error_message = '\n'.join(errors[:20])
            log_entry.save()
            
            logger.info(f"弹幕数据迁移完成: 成功 {success_count}, 失败 {failed_count}")
            
            return {
                'success': success_count,
                'failed': failed_count,
                'errors': errors
            }
            
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.end_time = timezone.now()
            log_entry.save()
            raise
    
    def _migrate_danmaku_batch(self, danmaku_key: str, room: LiveRoom, 
                              time_threshold: datetime, cleanup_redis: bool) -> Tuple[int, int, List[str]]:
        """分批迁移弹幕数据"""
        success_count = 0
        failed_count = 0
        errors = []
        
        try:
            # 获取列表长度
            list_length = self.redis_client.llen(danmaku_key)
            if list_length == 0:
                return success_count, failed_count, errors
            
            # 分批处理
            for start in range(0, list_length, self.batch_size):
                end = min(start + self.batch_size - 1, list_length - 1)
                
                try:
                    # 获取一批弹幕数据
                    danmaku_batch = self.redis_client.lrange(danmaku_key, start, end)
                    
                    danmaku_objects = []
                    
                    for danmaku_json in danmaku_batch:
                        try:
                            danmaku_data = json.loads(danmaku_json)
                            
                            # 解析时间戳
                            timestamp = datetime.fromtimestamp(
                                danmaku_data.get('timestamp', 0),
                                tz=timezone.get_current_timezone()
                            )
                            
                            # 检查时间阈值
                            if timestamp < time_threshold:
                                continue
                            
                            # 创建弹幕对象
                            danmaku_obj = DanmakuData(
                                room=room,
                                uid=danmaku_data.get('uid', 0),
                                username=danmaku_data.get('username', ''),
                                message=danmaku_data.get('message', ''),
                                timestamp=timestamp,
                                medal_name=danmaku_data.get('medal_name', ''),
                                medal_level=danmaku_data.get('medal_level', 0),
                                user_level=danmaku_data.get('user_level', 0),
                                is_admin=danmaku_data.get('is_admin', False),
                                is_vip=danmaku_data.get('is_vip', False)
                            )
                            
                            danmaku_objects.append(danmaku_obj)
                            
                        except Exception as e:
                            failed_count += 1
                            errors.append(f"解析弹幕数据失败: {e}")
                    
                    # 批量插入数据库
                    if danmaku_objects:
                        try:
                            with transaction.atomic():
                                DanmakuData.objects.bulk_create(
                                    danmaku_objects,
                                    ignore_conflicts=True
                                )
                            
                            success_count += len(danmaku_objects)
                            
                        except DatabaseError as e:
                            failed_count += len(danmaku_objects)
                            errors.append(f"批量插入弹幕数据失败: {e}")
                    
                except Exception as e:
                    errors.append(f"处理弹幕批次 {start}-{end} 失败: {e}")
            
            # 清理Redis数据
            if cleanup_redis and failed_count == 0:
                try:
                    current_length = self.redis_client.llen(danmaku_key)
                    if current_length > 1000:  # 保留最新的1000条
                        self.redis_client.ltrim(danmaku_key, 0, 999)
                except Exception as e:
                    errors.append(f"清理Redis弹幕数据失败: {e}")
        
        except Exception as e:
            errors.append(f"迁移弹幕数据失败: {e}")
        
        return success_count, failed_count, errors
    
    def migrate_gift_data(self, cleanup_redis=True, max_age_hours=24):
        """迁移礼物数据"""
        log_entry = DataMigrationLog.objects.create(
            migration_type='gift',
            start_time=timezone.now()
        )
        
        try:
            # 获取所有礼物列表键
            gift_keys = self.redis_client.keys('room:*:gifts')
            total_keys = len(gift_keys)
            
            success_count = 0
            failed_count = 0
            errors = []
            
            logger.info(f"开始迁移礼物数据，共 {total_keys} 个房间")
            
            # 计算时间阈值
            time_threshold = timezone.now() - timedelta(hours=max_age_hours)
            
            for gift_key in gift_keys:
                try:
                    # 提取房间ID
                    room_id = int(gift_key.split(':')[1])
                    
                    # 获取房间对象
                    try:
                        room = LiveRoom.objects.get(room_id=room_id)
                    except LiveRoom.DoesNotExist:
                        room = LiveRoom.objects.create(
                            room_id=room_id,
                            title=f"房间 {room_id}",
                            uname="未知主播"
                        )
                    
                    # 分批处理礼物数据
                    batch_success, batch_failed, batch_errors = self._migrate_gift_batch(
                        gift_key, room, time_threshold, cleanup_redis
                    )
                    
                    success_count += batch_success
                    failed_count += batch_failed
                    errors.extend(batch_errors)
                    
                except Exception as e:
                    error_msg = f"处理房间 {gift_key} 礼物时出错: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 更新日志
            log_entry.end_time = timezone.now()
            log_entry.total_records = success_count + failed_count
            log_entry.success_records = success_count
            log_entry.failed_records = failed_count
            log_entry.status = 'completed' if failed_count == 0 else 'partial'
            if errors:
                log_entry.error_message = '\n'.join(errors[:20])
            log_entry.save()
            
            logger.info(f"礼物数据迁移完成: 成功 {success_count}, 失败 {failed_count}")
            
            return {
                'success': success_count,
                'failed': failed_count,
                'errors': errors
            }
            
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.end_time = timezone.now()
            log_entry.save()
            raise
    
    def _migrate_gift_batch(self, gift_key: str, room: LiveRoom, 
                           time_threshold: datetime, cleanup_redis: bool) -> Tuple[int, int, List[str]]:
        """分批迁移礼物数据"""
        success_count = 0
        failed_count = 0
        errors = []
        
        try:
            # 获取列表长度
            list_length = self.redis_client.llen(gift_key)
            if list_length == 0:
                return success_count, failed_count, errors
            
            # 分批处理
            for start in range(0, list_length, self.batch_size):
                end = min(start + self.batch_size - 1, list_length - 1)
                
                try:
                    # 获取一批礼物数据
                    gift_batch = self.redis_client.lrange(gift_key, start, end)
                    
                    gift_objects = []
                    
                    for gift_json in gift_batch:
                        try:
                            gift_data = json.loads(gift_json)
                            
                            # 解析时间戳
                            timestamp = datetime.fromtimestamp(
                                gift_data.get('timestamp', 0),
                                tz=timezone.get_current_timezone()
                            )
                            
                            # 检查时间阈值
                            if timestamp < time_threshold:
                                continue
                            
                            # 创建礼物对象
                            gift_obj = GiftData(
                                room=room,
                                uid=gift_data.get('uid', 0),
                                username=gift_data.get('username', ''),
                                gift_name=gift_data.get('gift_name', ''),
                                gift_id=gift_data.get('gift_id', 0),
                                num=gift_data.get('num', 1),
                                price=gift_data.get('price', 0),
                                total_price=gift_data.get('total_price', 0),
                                timestamp=timestamp,
                                medal_name=gift_data.get('medal_name', ''),
                                medal_level=gift_data.get('medal_level', 0)
                            )
                            
                            gift_objects.append(gift_obj)
                            
                        except Exception as e:
                            failed_count += 1
                            errors.append(f"解析礼物数据失败: {e}")
                    
                    # 批量插入数据库
                    if gift_objects:
                        try:
                            with transaction.atomic():
                                GiftData.objects.bulk_create(
                                    gift_objects,
                                    ignore_conflicts=True
                                )
                            
                            success_count += len(gift_objects)
                            
                        except DatabaseError as e:
                            failed_count += len(gift_objects)
                            errors.append(f"批量插入礼物数据失败: {e}")
                    
                except Exception as e:
                    errors.append(f"处理礼物批次 {start}-{end} 失败: {e}")
            
            # 清理Redis数据
            if cleanup_redis and failed_count == 0:
                try:
                    current_length = self.redis_client.llen(gift_key)
                    if current_length > 500:  # 保留最新的500条礼物记录
                        self.redis_client.ltrim(gift_key, 0, 499)
                except Exception as e:
                    errors.append(f"清理Redis礼物数据失败: {e}")
        
        except Exception as e:
            errors.append(f"迁移礼物数据失败: {e}")
        
        return success_count, failed_count, errors
    
    def cleanup_expired_redis_data(self, max_age_hours=24):
        """清理过期的Redis数据"""
        try:
            logger.info(f"开始清理 {max_age_hours} 小时前的Redis数据")
            
            # 清理过期的统计数据
            stats_keys = self.redis_client.keys('room:*:stats:*')
            deleted_count = 0
            
            for key in stats_keys:
                try:
                    # 检查键的创建时间或TTL
                    ttl = self.redis_client.ttl(key)
                    if ttl == -1:  # 没有设置过期时间
                        # 设置过期时间
                        self.redis_client.expire(key, max_age_hours * 3600)
                    
                    deleted_count += 1
                    
                except Exception as e:
                    logger.error(f"处理键 {key} 时出错: {e}")
            
            logger.info(f"Redis清理完成，处理了 {deleted_count} 个键")
            
        except Exception as e:
            logger.error(f"清理Redis数据时出错: {e}")
    
    def get_migration_stats(self, days=7):
        """获取迁移统计信息"""
        start_date = timezone.now() - timedelta(days=days)
        
        logs = DataMigrationLog.objects.filter(
            created_at__gte=start_date
        ).order_by('-created_at')
        
        stats = {
            'total_migrations': logs.count(),
            'successful_migrations': logs.filter(status='completed').count(),
            'failed_migrations': logs.filter(status='failed').count(),
            'partial_migrations': logs.filter(status='partial').count(),
            'recent_logs': []
        }
        
        for log in logs[:10]:  # 最近10条记录
            stats['recent_logs'].append({
                'type': log.migration_type,
                'status': log.status,
                'start_time': log.start_time,
                'total_records': log.total_records,
                'success_records': log.success_records,
                'failed_records': log.failed_records,
                'error_message': log.error_message[:200] if log.error_message else None
            })
        
        return stats

# 全局收集器实例
_collector = None

def get_data_collector() -> LiveDataCollector:
    """获取全局数据收集器实例"""
    global _collector
    if _collector is None:
        _collector = LiveDataCollector()
    return _collector

def start_default_monitoring():
    """启动默认房间监控"""
    collector = get_data_collector()
    default_rooms = settings.LIVE_MONITOR_CONFIG.get('DEFAULT_ROOM_IDS', [])
    
    if default_rooms:
        collector.start_monitoring_multiple_rooms(default_rooms)
        logger.info(f"启动默认房间监控: {default_rooms}")
    else:
        logger.warning("未配置默认监控房间")