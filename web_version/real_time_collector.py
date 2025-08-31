import asyncio
import time
import logging
import sys
import os
from datetime import datetime
from bilibili_api import live, sync
import threading
import json
from bilibili_api.live import LiveDanmaku
import signal
from collections import deque

# 使用简化的Redis保存器
from simple_redis_saver import get_redis_saver

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class RealTimeDataCollector:
    """实时数据收集器 - 边爬取边显示"""
    
    def __init__(self, room_id, display_mode='console'):
        self.room_id = room_id
        self.redis_saver = get_redis_saver()
        self.logger = logging.getLogger(f'Collector-{room_id}')
        self.room = live.LiveRoom(room_display_id=room_id)
        self._running = False
        self.display_mode = display_mode  # 'console', 'web', 'both'
        
        # 统计计数器
        self.local_stats = {
            'danmaku_count': 0,
            'gift_count': 0,
            'popularity_updates': 0,
            'start_time': datetime.now(),
            'current_popularity': 0
        }
        
        # 实时显示缓存
        self.recent_danmaku = deque(maxlen=50)  # 最近50条弹幕
        self.recent_gifts = deque(maxlen=20)    # 最近20个礼物
        
        self.danmaku_client = None
        self.room_info = {}
        
        # 显示更新间隔
        self.display_update_interval = 1  # 1秒更新一次显示
        
    async def init_room_info(self):
        """初始化房间信息"""
        try:
            self.logger.info(f"正在获取房间 {self.room_id} 信息...")
            info = await self.room.get_room_info()
            
            self.room_info = {
                'room_id': str(self.room_id),
                'uname': info.get('anchor_info', {}).get('base_info', {}).get('uname', f'主播{self.room_id}'),
                'title': info.get('room_info', {}).get('title', f'直播间{self.room_id}'),
                'area_name': info.get('room_info', {}).get('area_name', ''),
                'parent_area_name': info.get('room_info', {}).get('parent_area_name', ''),
                'live_status': str(info.get('room_info', {}).get('live_status', 0)),
                'online': str(info.get('room_info', {}).get('online', 0)),
                'created_at': datetime.now().isoformat()
            }
            
            # 保存到Redis
            success = self.redis_saver.save_room_info(self.room_id, self.room_info)
            if success:
                self.logger.info(f"✅ 房间信息已保存: {self.room_info['uname']} - {self.room_info['title']}")
                self.display_room_header()
            else:
                self.logger.error(f"❌ 房间信息保存失败")
            
            return self.room_info
            
        except Exception as e:
            self.logger.error(f"❌ 初始化房间信息失败: {e}")
            return None
    
    def display_room_header(self):
        """显示房间信息头部"""
        if self.display_mode in ['console', 'both']:
            print("\n" + "="*80)
            print(f"🎬 直播间监控 - {self.room_info.get('uname', 'Unknown')}")
            print(f"📺 标题: {self.room_info.get('title', 'Unknown')}")
            print(f"🏷️ 分区: {self.room_info.get('parent_area_name', '')} > {self.room_info.get('area_name', '')}")
            print(f"📍 房间号: {self.room_id}")
            print(f"🔴 状态: {'直播中' if self.room_info.get('live_status') == '1' else '未开播'}")
            print("="*80)
            print("📊 实时统计 | 💬 弹幕 | 🎁 礼物")
            print("-"*80)
    
    def display_real_time_stats(self):
        """显示实时统计信息"""
        if self.display_mode in ['console', 'both']:
            runtime = datetime.now() - self.local_stats['start_time']
            runtime_str = str(runtime).split('.')[0]  # 去掉微秒
            
            # 清屏并重新显示（可选，避免刷屏）
            # os.system('cls' if os.name == 'nt' else 'clear')
            
            stats_line = (
                f"⏱️ 运行: {runtime_str} | "
                f"👥 人气: {self.local_stats['current_popularity']:,} | "
                f"💬 弹幕: {self.local_stats['danmaku_count']} | "
                f"🎁 礼物: {self.local_stats['gift_count']}"
            )
            
            # 使用回车覆盖当前行
            print(f"\r{stats_line}", end='', flush=True)
    
    def display_danmaku(self, danmaku_data):
        """显示弹幕"""
        if self.display_mode in ['console', 'both']:
            time_str = danmaku_data['send_time_formatted']
            username = danmaku_data['username']
            message = danmaku_data['message']
            
            # 限制用户名和消息长度
            username = username[:15] + '...' if len(username) > 15 else username
            message = message[:50] + '...' if len(message) > 50 else message
            
            print(f"\n💬 [{time_str}] {username}: {message}")
    
    def display_gift(self, gift_data):
        """显示礼物"""
        if self.display_mode in ['console', 'both']:
            time_str = gift_data['gift_time_formatted']
            username = gift_data['username']
            gift_name = gift_data['gift_name']
            num = gift_data['num']
            
            # 限制用户名长度
            username = username[:15] + '...' if len(username) > 15 else username
            
            print(f"\n🎁 [{time_str}] {username} 送出 {gift_name} x{num}")
    
    async def start_monitoring(self):
        """开始监控"""
        self._running = True
        
        try:
            # 初始化房间信息
            room_info = await self.init_room_info()
            if not room_info:
                self.logger.error("房间信息获取失败，停止监控")
                return
            
            # 启动监控任务
            tasks = [
                asyncio.create_task(self.monitor_popularity()),
                asyncio.create_task(self.monitor_danmaku()),
                asyncio.create_task(self.display_updater())  # 添加显示更新任务
            ]
            
            # 等待任务完成或异常
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"❌ 监控异常: {e}")
        finally:
            self._running = False
            if self.danmaku_client:
                try:
                    await self.danmaku_client.disconnect()
                except:
                    pass
    
    async def display_updater(self):
        """定期更新显示"""
        while self._running:
            try:
                self.display_real_time_stats()
                await asyncio.sleep(self.display_update_interval)
            except Exception as e:
                self.logger.error(f"❌ 显示更新失败: {e}")
                await asyncio.sleep(1)
    
    async def monitor_popularity(self):
        """监控人气数据"""
        while self._running:
            try:
                info = await self.room.get_room_info()
                popularity = info.get('room_info', {}).get('online', 0)
                
                # 更新本地统计
                self.local_stats['current_popularity'] = popularity
                
                # 保存到Redis
                success = self.redis_saver.save_popularity(self.room_id, popularity)
                if success:
                    self.local_stats['popularity_updates'] += 1
                
                await asyncio.sleep(30)  # 30秒更新一次
                
            except Exception as e:
                self.logger.error(f"❌ 人气监控失败: {e}")
                await asyncio.sleep(10)
    
    async def monitor_danmaku(self):
        """监控弹幕和礼物"""
        try:
            self.danmaku_client = LiveDanmaku(self.room_id)
            
            # 弹幕事件处理器
            @self.danmaku_client.on('DANMU_MSG')
            async def on_danmaku(event):
                await self.handle_danmaku(event)
            
            # 礼物事件处理器
            @self.danmaku_client.on('SEND_GIFT')
            async def on_gift(event):
                await self.handle_gift(event)
            
            # 连接弹幕服务器
            self.logger.info(f"🔗 连接房间 {self.room_id} 弹幕服务器...")
            await self.danmaku_client.connect()
            
        except Exception as e:
            self.logger.error(f"❌ 弹幕监控失败: {e}")
            # 使用模拟数据作为备用
            await self.simulate_danmaku()
    
    async def handle_danmaku(self, event):
        """处理弹幕事件"""
        try:
            data = event.get('data', {})
            info = data.get('info', [])
            
            if len(info) >= 3:
                message = info[1] if len(info) > 1 else ''
                user_info = info[2] if len(info) > 2 else []
                username = user_info[1] if len(user_info) > 1 else '匿名用户'
                uid = user_info[0] if len(user_info) > 0 else 0
                
                # 时间戳处理
                current_time = datetime.now()
                original_timestamp = None
                send_time_ms = None
                
                # 从 info[0][4] 获取B站原始时间戳（毫秒）
                if len(info) > 0 and isinstance(info[0], list) and len(info[0]) > 4:
                    try:
                        send_time_ms = int(info[0][4])
                        original_timestamp = datetime.fromtimestamp(send_time_ms / 1000)
                    except:
                        pass
                
                # 如果无法获取原始时间戳，使用当前时间
                if original_timestamp is None:
                    original_timestamp = current_time
                    send_time_ms = int(current_time.timestamp() * 1000)
                
                # 构造弹幕数据
                danmaku_data = {
                    'username': username,
                    'message': message,
                    'uid': uid,
                    'send_time_ms': send_time_ms,
                    'send_time': int(send_time_ms / 1000) if send_time_ms else int(current_time.timestamp()),
                    'send_time_formatted': original_timestamp.strftime('%H:%M:%S'),
                    'send_date': original_timestamp.strftime('%Y-%m-%d'),
                    'send_datetime': original_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': current_time.isoformat(),
                    'received_at': current_time.timestamp(),
                    'room_id': self.room_id
                }
                
                # 添加到本地缓存
                self.recent_danmaku.appendleft(danmaku_data)
                
                # 保存到Redis
                success = self.redis_saver.save_danmaku(self.room_id, danmaku_data)
                if success:
                    self.local_stats['danmaku_count'] += 1
                    # 实时显示弹幕
                    self.display_danmaku(danmaku_data)
                
        except Exception as e:
            self.logger.error(f"❌ 处理弹幕失败: {e}")
    
    async def handle_gift(self, event):
        """处理礼物事件"""
        try:
            data = event.get('data', {})
            
            # 获取当前时间
            current_time = datetime.now()
            
            # 时间戳处理
            gift_timestamp = data.get('timestamp', None)
            original_time = None
            
            if gift_timestamp:
                try:
                    if len(str(gift_timestamp)) > 10:  # 毫秒时间戳
                        original_time = datetime.fromtimestamp(gift_timestamp / 1000)
                    else:  # 秒时间戳
                        original_time = datetime.fromtimestamp(gift_timestamp)
                except (ValueError, TypeError):
                    pass
            
            if original_time is None:
                original_time = current_time
                gift_timestamp = int(current_time.timestamp())
            
            gift_data = {
                'username': data.get('uname', '匿名用户'),
                'gift_name': data.get('giftName', '未知礼物'),
                'gift_id': data.get('giftId', 0),
                'num': data.get('num', 1),
                'price': data.get('price', 0),
                'coin_type': data.get('coin_type', 'silver'),
                'gift_timestamp': gift_timestamp,
                'gift_time_formatted': original_time.strftime('%H:%M:%S'),
                'gift_date': original_time.strftime('%Y-%m-%d'),
                'gift_datetime': original_time.strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp': current_time.isoformat(),
                'received_at': current_time.timestamp(),
                'room_id': self.room_id
            }
            
            # 添加到本地缓存
            self.recent_gifts.appendleft(gift_data)
            
            # 保存到Redis
            success = self.redis_saver.save_gift(self.room_id, gift_data)
            if success:
                self.local_stats['gift_count'] += gift_data['num']
                # 实时显示礼物
                self.display_gift(gift_data)
                
        except Exception as e:
            self.logger.error(f"❌ 处理礼物失败: {e}")
    
    async def simulate_danmaku(self):
        """模拟弹幕数据（当真实连接失败时）"""
        self.logger.info("🔄 使用模拟弹幕数据...")
        counter = 0
        
        while self._running:
            try:
                await asyncio.sleep(3)  # 每3秒一条模拟弹幕
                
                counter += 1
                current_time = datetime.now()
                
                danmaku_data = {
                    'username': f'测试用户{counter}',
                    'message': f'这是第{counter}条测试弹幕',
                    'uid': counter,
                    'send_time_ms': int(current_time.timestamp() * 1000),
                    'send_time': int(current_time.timestamp()),
                    'send_time_formatted': current_time.strftime('%H:%M:%S'),
                    'send_date': current_time.strftime('%Y-%m-%d'),
                    'send_datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': current_time.isoformat(),
                    'received_at': current_time.timestamp(),
                    'room_id': self.room_id
                }
                
                # 添加到本地缓存
                self.recent_danmaku.appendleft(danmaku_data)
                
                success = self.redis_saver.save_danmaku(self.room_id, danmaku_data)
                if success:
                    self.local_stats['danmaku_count'] += 1
                    self.display_danmaku(danmaku_data)
                
                # 每10条弹幕模拟一个礼物
                if counter % 10 == 0:
                    gift_time = datetime.now()
                    gift_data = {
                        'username': f'土豪{counter//10}',
                        'gift_name': '小心心',
                        'gift_id': 30607,
                        'num': 1,
                        'price': 5000,
                        'coin_type': 'gold',
                        'gift_timestamp': int(gift_time.timestamp()),
                        'gift_time_formatted': gift_time.strftime('%H:%M:%S'),
                        'gift_date': gift_time.strftime('%Y-%m-%d'),
                        'gift_datetime': gift_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'timestamp': gift_time.isoformat(),
                        'received_at': gift_time.timestamp(),
                        'room_id': self.room_id
                    }
                    
                    self.recent_gifts.appendleft(gift_data)
                    
                    success = self.redis_saver.save_gift(self.room_id, gift_data)
                    if success:
                        self.local_stats['gift_count'] += 1
                        self.display_gift(gift_data)
                
            except Exception as e:
                self.logger.error(f"❌ 模拟数据失败: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        print(f"\n🛑 房间 {self.room_id} 监控已停止")
    
    def print_final_stats(self):
        """打印最终统计信息"""
        print("\n" + "="*80)
        print("📊 最终统计报告")
        print("="*80)
        
        runtime = datetime.now() - self.local_stats['start_time']
        runtime_str = str(runtime).split('.')[0]
        
        print(f"🏠 房间: {self.room_info.get('uname', 'Unknown')} ({self.room_id})")
        print(f"⏱️ 运行时间: {runtime_str}")
        print(f"💬 收集弹幕: {self.local_stats['danmaku_count']} 条")
        print(f"🎁 收集礼物: {self.local_stats['gift_count']} 个")
        print(f"📊 人气更新: {self.local_stats['popularity_updates']} 次")
        print(f"👥 当前人气: {self.local_stats['current_popularity']:,}")
        
        # 显示最近的弹幕
        if self.recent_danmaku:
            print(f"\n💬 最近弹幕 (最新 {min(5, len(self.recent_danmaku))} 条):")
            for i, danmaku in enumerate(list(self.recent_danmaku)[:5]):
                print(f"  {i+1}. [{danmaku['send_time_formatted']}] {danmaku['username']}: {danmaku['message']}")
        
        # 显示最近的礼物
        if self.recent_gifts:
            print(f"\n🎁 最近礼物 (最新 {min(3, len(self.recent_gifts))} 个):")
            for i, gift in enumerate(list(self.recent_gifts)[:3]):
                print(f"  {i+1}. [{gift['gift_time_formatted']}] {gift['username']} -> {gift['gift_name']} x{gift['num']}")
        
        print("="*80)

def signal_handler(signum, frame):
    """信号处理器"""
    print("\n\n🛑 收到停止信号，正在关闭监控...")
    # 这里可以添加清理逻辑
    sys.exit(0)

def run_real_time_monitor(room_id, duration=None):
    """运行实时监控"""
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    async def monitor():
        collector = RealTimeDataCollector(room_id, display_mode='console')
        
        try:
            print(f"🚀 启动房间 {room_id} 实时监控...")
            print("💡 按 Ctrl+C 停止监控")
            
            if duration:
                print(f"⏱️ 将运行 {duration} 秒")
                
                # 启动监控任务
                monitor_task = asyncio.create_task(collector.start_monitoring())
                
                # 等待指定时间
                await asyncio.sleep(duration)
                
                # 停止监控
                collector.stop_monitoring()
                
                # 等待任务结束
                try:
                    await asyncio.wait_for(monitor_task, timeout=10)
                except asyncio.TimeoutError:
                    print("⚠️ 监控任务超时")
            else:
                # 无限期运行
                await collector.start_monitoring()
                
        except KeyboardInterrupt:
            print("\n🛑 用户中断监控")
        except Exception as e:
            print(f"❌ 监控异常: {e}")
        finally:
            collector.stop_monitoring()
            collector.print_final_stats()
    
    # 运行异步监控
    asyncio.run(monitor())

if __name__ == "__main__":

    room_id = 1962481108

    
    run_real_time_monitor(room_id)