from django.core.management.base import BaseCommand
from django.db import connection
from live_data.models import LiveRoom, DanmakuData, GiftData, MonitoringTask, DataMigrationLog

class Command(BaseCommand):
    help = '检查数据库状态和数据完整性'
    
    def handle(self, *args, **options):
        self.stdout.write("开始数据库健康检查...")
        
        # 1. 检查表是否存在
        self.check_tables()
        
        # 2. 检查数据完整性
        self.check_data_integrity()
        
        # 3. 检查索引
        self.check_indexes()
        
        # 4. 统计数据
        self.show_statistics()
        
        self.stdout.write(
            self.style.SUCCESS('数据库健康检查完成！')
        )
    
    def check_tables(self):
        """检查表是否存在"""
        tables = [
            'live_rooms',
            'danmaku_data', 
            'gift_data',
            'monitoring_tasks',
            'data_migration_logs'
        ]
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
            """)
            existing_tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            if table in existing_tables:
                self.stdout.write(f"✅ 表 {table} 存在")
            else:
                self.stdout.write(f"❌ 表 {table} 不存在")
    
    def check_data_integrity(self):
        """检查数据完整性"""
        # 检查外键完整性
        orphaned_danmaku = DanmakuData.objects.filter(room__isnull=True).count()
        orphaned_gifts = GiftData.objects.filter(room__isnull=True).count()
        
        if orphaned_danmaku == 0:
            self.stdout.write("✅ 弹幕数据外键完整")
        else:
            self.stdout.write(f"⚠️ 发现 {orphaned_danmaku} 条孤立弹幕数据")
        
        if orphaned_gifts == 0:
            self.stdout.write("✅ 礼物数据外键完整")
        else:
            self.stdout.write(f"⚠️ 发现 {orphaned_gifts} 条孤立礼物数据")
    
    def check_indexes(self):
        """检查索引"""
        with connection.cursor() as cursor:
            cursor.execute("SHOW INDEX FROM live_rooms")
            indexes = cursor.fetchall()
            self.stdout.write(f"✅ live_rooms 表有 {len(indexes)} 个索引")
    
    def show_statistics(self):
        """显示统计信息"""
        stats = {
            '房间数': LiveRoom.objects.count(),
            '弹幕数': DanmakuData.objects.count(),
            '礼物数': GiftData.objects.count(),
            '监控任务数': MonitoringTask.objects.count(),
            '迁移日志数': DataMigrationLog.objects.count(),
        }
        
        self.stdout.write("\n📊 数据统计:")
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value:,}")