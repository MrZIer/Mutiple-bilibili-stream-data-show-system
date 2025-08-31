from django.core.management.base import BaseCommand
from django.core.management import call_command
import time
import threading
import signal
import sys
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '启动定时同步调度器'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=5,  # 修改：从300秒改为5秒
            help='同步间隔时间（秒）'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,  # 修改：减少批处理大小以适应更频繁的同步
            help='批处理大小'
        )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True
        self.sync_thread = None
    
    def handle(self, *args, **options):
        self.interval = options['interval']
        self.batch_size = options['batch_size']
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.stdout.write(f"⏰ 启动定时同步调度器，间隔: {self.interval}秒")
        
        # 启动同步线程
        self.sync_thread = threading.Thread(target=self.sync_loop, daemon=True)
        self.sync_thread.start()
        
        try:
            # 主线程等待
            while self.running:
                time.sleep(0.1)  # 减少主线程睡眠时间，提高响应性
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def sync_loop(self):
        """同步循环"""
        sync_count = 0
        while self.running:
            try:
                start_time = datetime.now()
                sync_count += 1
                
                # 每10次同步显示一次详细信息，减少日志输出
                if sync_count % 10 == 1:
                    self.stdout.write(f"🔄 [{start_time.strftime('%Y-%m-%d %H:%M:%S')}] 开始同步数据 (第{sync_count}次)...")
                    verbosity = 1
                else:
                    verbosity = 0
                
                # 执行同步命令
                call_command(
                    'sync_redis_to_db',
                    data_type='all',
                    batch_size=self.batch_size,
                    verbosity=verbosity  # 控制输出详细程度
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                if sync_count % 10 == 1:
                    self.stdout.write(f"✅ 同步完成，耗时: {duration:.2f}秒")
                
            except Exception as e:
                self.stdout.write(f"❌ 同步失败: {e}")
                logger.error(f"同步失败: {e}")
            
            # 等待下一次同步
            for i in range(self.interval * 10):  # 0.1秒为单位的精细控制
                if not self.running:
                    break
                time.sleep(0.1)
    
    def signal_handler(self, signum, frame):
        """信号处理器"""
        self.stdout.write("🛑 收到停止信号...")
        self.stop()
    
    def stop(self):
        """停止调度器"""
        self.running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=5)
        self.stdout.write("🏁 定时同步调度器已停止")