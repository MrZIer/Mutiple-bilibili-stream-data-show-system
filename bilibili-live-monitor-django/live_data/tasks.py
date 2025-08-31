from celery import shared_task
import json
from datetime import datetime
from utils.bilibili_client import fetch_live_data
from utils.redis_handler import save_to_redis
from utils.data_processor import process_data
import logging
from django.core.management import call_command
from django.conf import settings
from datetime import datetime, timedelta
from .services import DataMigrationService

logger = logging.getLogger(__name__)

class DataMigrationScheduler:
    """数据迁移调度器"""
    
    def __init__(self):
        self.migration_service = DataMigrationService()
    
    def run_scheduled_migration(self):
        """执行定时迁移任务"""
        try:
            logger.info("开始执行定时数据迁移任务")
            
            # 获取配置
            cleanup_redis = getattr(settings, 'AUTO_CLEANUP_REDIS', True)
            max_age_hours = getattr(settings, 'MIGRATION_MAX_AGE_HOURS', 6)  # 6小时迁移一次
            
            # 执行迁移
            results = self.migration_service.migrate_all_data(
                cleanup_redis=cleanup_redis,
                max_age_hours=max_age_hours
            )
            
            # 记录结果
            total_success = sum(r['success'] for r in results.values())
            total_failed = sum(r['failed'] for r in results.values())
            
            logger.info(
                f"定时迁移完成: 成功 {total_success} 条, 失败 {total_failed} 条"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"定时迁移任务失败: {e}", exc_info=True)
            return None

@shared_task
def collect_live_data():
    live_data = fetch_live_data()
    processed_data = process_data(live_data)
    save_to_redis(processed_data)

    # Save data as JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f'live_data_{timestamp}.json', 'w') as json_file:
        json.dump(processed_data, json_file)

# 如果使用APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from django_apscheduler.jobstores import DjangoJobStore
    from django_apscheduler.models import DjangoJobExecution
    import atexit
    
    # 创建调度器
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    
    def start_scheduler():
        """启动定时任务调度器"""
        if not scheduler.running:
            # 添加定时任务 - 每6小时执行一次迁移
            scheduler.add_job(
                DataMigrationScheduler().run_scheduled_migration,
                trigger=CronTrigger(hour="*/6"),  # 每6小时执行一次
                id='migrate_redis_data',
                max_instances=1,
                replace_existing=True,
                name='迁移Redis数据到数据库'
            )
            
            # 添加清理任务 - 每天凌晨2点清理过期日志
            scheduler.add_job(
                cleanup_old_migration_logs,
                trigger=CronTrigger(hour=2, minute=0),  # 每天凌晨2点
                id='cleanup_migration_logs',
                max_instances=1,
                replace_existing=True,
                name='清理过期迁移日志'
            )
            
            scheduler.start()
            atexit.register(lambda: scheduler.shutdown())
            
            logger.info("定时任务调度器已启动")
    
    def cleanup_old_migration_logs():
        """清理过期的迁移日志"""
        try:
            from .models import DataMigrationLog
            from django.utils import timezone
            
            # 删除30天前的日志
            cutoff_date = timezone.now() - timedelta(days=30)
            deleted_count = DataMigrationLog.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
            
            logger.info(f"清理了 {deleted_count} 条过期迁移日志")
            
        except Exception as e:
            logger.error(f"清理迁移日志失败: {e}")

except ImportError:
    logger.warning("APScheduler not available, using simple cron job approach")
    
    def start_scheduler():
        """简单的调度器启动（如果没有APScheduler）"""
        logger.info("使用简单调度模式，请使用系统cron或任务计划器")
        pass