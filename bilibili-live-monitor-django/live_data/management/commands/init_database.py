from django.core.management.base import BaseCommand
from django.db import transaction
from live_data.models import LiveRoom, MonitoringTask
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '初始化数据库，创建必要的初始数据'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='创建测试数据',
        )
    
    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                self.stdout.write("开始初始化数据库...")
                
                # 1. 检查数据库连接
                self.check_database_connection()
                
                # 2. 创建默认监控任务
                self.create_default_task()
                
                # 3. 可选：创建测试数据
                if options['create_test_data']:
                    self.create_test_data()
                
                self.stdout.write(
                    self.style.SUCCESS('数据库初始化完成！')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'数据库初始化失败: {e}')
            )
            raise
    
    def check_database_connection(self):
        """检查数据库连接"""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result:
                self.stdout.write("✅ 数据库连接正常")
    
    def create_default_task(self):
        """创建默认监控任务"""
        task, created = MonitoringTask.objects.get_or_create(
            task_name="默认监控任务",
            defaults={
                'room_ids': '[]',
                'status': 'stopped'
            }
        )
        if created:
            self.stdout.write("✅ 创建默认监控任务")
        else:
            self.stdout.write("ℹ️ 默认监控任务已存在")
    
    def create_test_data(self):
        """创建测试数据"""
        from django.utils import timezone
        from decimal import Decimal
        
        # 创建测试房间
        test_rooms = [
            {'room_id': 123456, 'title': '测试房间1', 'uname': '测试主播1'},
            {'room_id': 789012, 'title': '测试房间2', 'uname': '测试主播2'},
        ]
        
        for room_data in test_rooms:
            room, created = LiveRoom.objects.get_or_create(
                room_id=room_data['room_id'],
                defaults=room_data
            )
            if created:
                self.stdout.write(f"✅ 创建测试房间: {room.title}")