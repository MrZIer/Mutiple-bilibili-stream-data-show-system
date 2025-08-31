from django.core.management.base import BaseCommand
from django.utils import timezone
from live_data.services import DataMigrationService
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrate data from Redis to database and cleanup Redis'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--no-cleanup',
            action='store_true',
            help='Do not cleanup Redis data after migration'
        )
        parser.add_argument(
            '--max-age',
            type=int,
            default=24,
            help='Maximum age in hours for data to migrate (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without actually migrating data'
        )
        parser.add_argument(
            '--type',
            choices=['all', 'danmaku', 'gifts', 'rooms'],
            default='all',
            help='Type of data to migrate (default: all)'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show migration statistics'
        )
    
    def handle(self, *args, **options):
        """执行数据迁移命令"""
        migration_service = DataMigrationService()
        
        # 显示统计信息
        if options['stats']:
            self.show_stats(migration_service)
            return
        
        # 执行迁移
        cleanup_redis = not options['no_cleanup']
        max_age_hours = options['max_age']
        migration_type = options['type']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🧪 执行干运行模式（不会实际迁移数据）')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 开始数据迁移任务')
        )
        self.stdout.write(f'📊 迁移类型: {migration_type}')
        self.stdout.write(f'⏰ 最大年龄: {max_age_hours} 小时')
        self.stdout.write(f'🧹 清理Redis: {"是" if cleanup_redis else "否"}')
        
        try:
            if migration_type == 'all':
                results = migration_service.migrate_all_data(cleanup_redis, max_age_hours)
                self.display_results(results)
            
            elif migration_type == 'danmaku':
                result = migration_service.migrate_danmaku_data(cleanup_redis, max_age_hours)
                self.display_single_result('弹幕', result)
            
            elif migration_type == 'gifts':
                result = migration_service.migrate_gift_data(cleanup_redis, max_age_hours)
                self.display_single_result('礼物', result)
            
            elif migration_type == 'rooms':
                result = migration_service.migrate_room_data(cleanup_redis, max_age_hours)
                self.display_single_result('房间', result)
            
            self.stdout.write(
                self.style.SUCCESS('✅ 数据迁移任务完成！')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 数据迁移失败: {e}')
            )
            logger.error(f"Migration command failed: {e}", exc_info=True)
    
    def display_results(self, results):
        """显示迁移结果"""
        self.stdout.write('\n📊 迁移结果:')
        self.stdout.write('=' * 50)
        
        for data_type, result in results.items():
            success = result['success']
            failed = result['failed']
            total = success + failed
            
            status_icon = '✅' if failed == 0 else '⚠️' if success > 0 else '❌'
            
            self.stdout.write(
                f"{status_icon} {data_type.upper()}: 总计 {total}, 成功 {success}, 失败 {failed}"
            )
            
            if result['errors']:
                self.stdout.write(f"   错误示例: {result['errors'][0]}")
    
    def display_single_result(self, data_type, result):
        """显示单个类型的迁移结果"""
        success = result['success']
        failed = result['failed']
        total = success + failed
        
        status_icon = '✅' if failed == 0 else '⚠️' if success > 0 else '❌'
        
        self.stdout.write(
            f"{status_icon} {data_type}数据迁移: 总计 {total}, 成功 {success}, 失败 {failed}"
        )
        
        if result['errors']:
            self.stdout.write("错误信息:")
            for error in result['errors'][:5]:  # 只显示前5个错误
                self.stdout.write(f"  - {error}")
    
    def show_stats(self, migration_service):
        """显示迁移统计信息"""
        stats = migration_service.get_migration_stats()
        
        self.stdout.write('\n📈 迁移统计信息 (最近7天):')
        self.stdout.write('=' * 50)
        self.stdout.write(f"总迁移次数: {stats['total_migrations']}")
        self.stdout.write(f"成功迁移: {stats['successful_migrations']}")
        self.stdout.write(f"失败迁移: {stats['failed_migrations']}")
        self.stdout.write(f"部分成功: {stats['partial_migrations']}")
        
        if stats['recent_logs']:
            self.stdout.write('\n📋 最近迁移记录:')
            for log in stats['recent_logs']:
                status_icon = {
                    'completed': '✅',
                    'failed': '❌',
                    'partial': '⚠️',
                    'running': '🔄'
                }.get(log['status'], '❓')
                
                self.stdout.write(
                    f"{status_icon} {log['type']} - {log['start_time'].strftime('%Y-%m-%d %H:%M')} - "
                    f"成功: {log['success_records']}, 失败: {log['failed_records']}"
                )