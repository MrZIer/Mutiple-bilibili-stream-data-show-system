import logging
from django.core.management.base import BaseCommand
from live_data.services import get_data_collector

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '启动B站直播监控'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rooms',
            type=str,
            help='指定要监控的房间ID，用逗号分隔',
            default='17961,52032'
        )

    def handle(self, *args, **options):
        room_ids_str = options['rooms']
        room_ids = [int(rid.strip()) for rid in room_ids_str.split(',')]
        
        self.stdout.write(f"🚀 开始监控房间: {room_ids}")
        
        collector = get_data_collector()
        try:
            collector.start_monitoring_multiple_rooms(room_ids)
            self.stdout.write(
                self.style.SUCCESS('✅ 监控已启动，按 Ctrl+C 停止')
            )
            
            # 保持运行
            import time
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stdout.write("🛑 收到停止信号...")
            collector.stop_all_monitoring()
            self.stdout.write(
                self.style.SUCCESS('✅ 监控已停止')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 监控出错: {e}')
            )