import asyncio
import threading
import logging
import sys
import os
from django.core.management.base import BaseCommand
from django.conf import settings

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
web_version_path = os.path.join(project_root, 'web_version')
if web_version_path not in sys.path:
    sys.path.insert(0, web_version_path)

try:
    from multi_room_collector import MultiRoomCollector, RealTimeDataCollector
except ImportError as e:
    print(f"❌ 导入收集器模块失败: {e}")
    print(f"请确保 web_version 目录存在于: {web_version_path}")

logger = logging.getLogger('django_collector')

class Command(BaseCommand):
    help = 'Start Bilibili live room data collector'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--rooms',
            type=str,
            default='1962481108,1982728080,1959064353',
            help='Comma-separated room IDs to monitor (default: 1962481108,1982728080,1959064353)'
        )
        parser.add_argument(
            '--mode',
            type=str,
            choices=['single', 'multi'],
            default='multi',
            help='Monitoring mode: single or multi room (default: multi)'
        )
        parser.add_argument(
            '--background',
            action='store_true',
            help='Run in background mode (minimal output)'
        )
        parser.add_argument(
            '--duration',
            type=int,
            help='Duration in seconds to run the collector (default: infinite)'
        )
    
    def handle(self, *args, **options):
        """执行命令"""
        room_ids_str = options['rooms']
        mode = options['mode']
        background = options['background']
        duration = options.get('duration')
        
        # 解析房间ID
        try:
            room_ids = [int(x.strip()) for x in room_ids_str.split(',') if x.strip().isdigit()]
        except ValueError:
            self.stdout.write(
                self.style.ERROR('❌ 错误: 房间ID格式不正确，请使用逗号分隔的数字')
            )
            return
        
        if not room_ids:
            self.stdout.write(
                self.style.ERROR('❌ 错误: 未提供有效的房间ID')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 启动B站直播数据收集器...')
        )
        self.stdout.write(f'📺 监控房间: {", ".join(map(str, room_ids))}')
        self.stdout.write(f'🔧 运行模式: {mode}')
        
        if background:
            self.stdout.write(f'🤫 后台模式: 最小化输出')
        
        if duration:
            self.stdout.write(f'⏱️ 运行时长: {duration} 秒')
        
        self.stdout.write('💡 按 Ctrl+C 停止收集器\n')
        
        try:
            if mode == 'single' and len(room_ids) == 1:
                # 单房间模式
                self._run_single_room(room_ids[0], background, duration)
            else:
                # 多房间模式
                self._run_multi_room(room_ids, background, duration)
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\n🛑 收到停止信号，正在关闭收集器...')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ 收集器运行异常: {e}')
            )
            logger.error(f"Collector error: {e}", exc_info=True)
    
    def _run_single_room(self, room_id, background, duration):
        """运行单房间收集器"""
        async def run():
            display_mode = 'silent' if background else 'console'
            collector = RealTimeDataCollector(room_id, display_mode=display_mode)
            
            try:
                if duration:
                    # 有时间限制
                    monitor_task = asyncio.create_task(collector.start_monitoring())
                    await asyncio.sleep(duration)
                    collector.stop_monitoring()
                    await asyncio.wait_for(monitor_task, timeout=10)
                else:
                    # 无限期运行
                    await collector.start_monitoring()
            except Exception as e:
                logger.error(f"Single room collector error: {e}")
                raise
            finally:
                collector.stop_monitoring()
                if not background:
                    collector.print_final_stats()
        
        asyncio.run(run())
    
    def _run_multi_room(self, room_ids, background, duration):
        """运行多房间收集器"""
        async def run():
            display_mode = 'silent' if background else 'console'
            collector = MultiRoomCollector(room_ids, display_mode=display_mode)
            
            try:
                if duration:
                    # 有时间限制
                    monitor_task = asyncio.create_task(collector.start_monitoring())
                    await asyncio.sleep(duration)
                    collector.stop_monitoring()
                    await asyncio.wait_for(monitor_task, timeout=10)
                else:
                    # 无限期运行
                    await collector.start_monitoring()
            except Exception as e:
                logger.error(f"Multi room collector error: {e}")
                raise
            finally:
                collector.stop_monitoring()
                if not background:
                    collector.print_final_stats()
        
        asyncio.run(run())