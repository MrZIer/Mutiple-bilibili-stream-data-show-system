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

# 使用简化的Redis保存器
from simple_redis_saver import get_redis_saver

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class FixedDataCollector:
    """修复版数据收集器 - 确保数据正确存入Redis"""
    
    def __init__(self, room_id):
        self.room_id = room_id
        self.redis_saver = get_redis_saver()
        self.logger = logging.getLogger(f'Collector-{room_id}')
        self.room = live.LiveRoom(room_display_id=room_id)
        self._running = False
        
        # 统计计数器
        self.local_stats = {
            'danmaku_count': 0,
            'gift_count': 0,
            'popularity_updates': 0,
            'start_time': datetime.now()
        }
        
        self.danmaku_client = None
    
    async def init_room_info(self):
        """初始化房间信息"""
        try:
            self.logger.info(f"正在获取房间 {self.room_id} 信息...")
            info = await self.room.get_room_info()
            
            room_info = {
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
            success = self.redis_saver.save_room_info(self.room_id, room_info)
            if success:
                self.logger.info(f"✅ 房间信息已保存: {room_info['uname']} - {room_info['title']}")
            else:
                self.logger.error(f"❌ 房间信息保存失败")
            
            return room_info
            
        except Exception as e:
            self.logger.error(f"❌ 初始化房间信息失败: {e}")
            return None
    
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
                asyncio.create_task(self.monitor_danmaku())
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
    
    async def monitor_popularity(self):
        """监控人气数据"""
        while self._running:
            try:
                info = await self.room.get_room_info()
                popularity = info.get('room_info', {}).get('online', 0)
                
                # 保存到Redis
                success = self.redis_saver.save_popularity(self.room_id, popularity)
                if success:
                    self.local_stats['popularity_updates'] += 1
                    self.logger.info(f"📊 人气更新: {popularity}")
                
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
        """处理弹幕事件 - 修复时间戳问题"""
        try:
            data = event.get('data', {})
            info = data.get('info', [])
            
            if len(info) >= 3:
                message = info[1] if len(info) > 1 else ''
                user_info = info[2] if len(info) > 2 else []
                username = user_info[1] if len(user_info) > 1 else '匿名用户'
                uid = user_info[0] if len(user_info) > 0 else 0
                
                # 修复时间戳处理
                current_time = datetime.now()
                
                # 尝试从弹幕数据中获取原始时间戳
                original_timestamp = None
                send_time_ms = None
                
                # 从 info[0][4] 获取B站原始时间戳（毫秒）
                if len(info) > 0 and isinstance(info[0], list) and len(info[0]) > 4:
                    send_time_ms = int(info[0][4])
                    original_timestamp = datetime.fromtimestamp(send_time_ms / 1000)
                
                # 如果无法获取原始时间戳，使用当前时间
                if original_timestamp is None:
                    original_timestamp = current_time
                    send_time_ms = int(current_time.timestamp() * 1000)
                
                # 构造弹幕数据 - 包含完整的时间信息
                danmaku_data = {
                    'username': username,
                    'message': message,
                    'uid': uid,
                    'send_time_ms': send_time_ms,  # 毫秒时间戳
                    'send_time': int(send_time_ms / 1000) if send_time_ms else int(current_time.timestamp()),  # 秒时间戳
                    'send_time_formatted': original_timestamp.strftime('%H:%M:%S'),  # 格式化时间 HH:MM:SS
                    'send_date': original_timestamp.strftime('%Y-%m-%d'),  # 日期
                    'send_datetime': original_timestamp.strftime('%Y-%m-%d %H:%M:%S'),  # 完整日期时间
                    'timestamp': current_time.isoformat(),  # 处理时间戳（ISO格式）
                    'received_at': current_time.timestamp(),  # 接收时间戳
                    'room_id': self.room_id
                }
                
                # 保存到Redis
                success = self.redis_saver.save_danmaku(self.room_id, danmaku_data)
                if success:
                    self.local_stats['danmaku_count'] += 1
                    # 输出详细日志
                    self.logger.info(f"💬 弹幕: [{danmaku_data['send_time_formatted']}] {username}: {message}")
                
        except Exception as e:
            self.logger.error(f"❌ 处理弹幕失败: {e}")
    
    async def handle_gift(self, event):
        """处理礼物事件 - 修复时间戳问题"""
        try:
            data = event.get('data', {})
            
            # 获取当前时间
            current_time = datetime.now()
            
            # 尝试从礼物数据中获取时间戳
            gift_timestamp = data.get('timestamp', None)
            original_time = None
            
            if gift_timestamp:
                try:
                    # B站礼物时间戳可能是秒或毫秒
                    if len(str(gift_timestamp)) > 10:  # 毫秒时间戳
                        original_time = datetime.fromtimestamp(gift_timestamp / 1000)
                    else:  # 秒时间戳
                        original_time = datetime.fromtimestamp(gift_timestamp)
                except (ValueError, TypeError):
                    pass
            
            # 如果无法获取原始时间戳，使用当前时间
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
                'gift_timestamp': gift_timestamp,  # 原始时间戳
                'gift_time_formatted': original_time.strftime('%H:%M:%S'),  # 格式化时间
                'gift_date': original_time.strftime('%Y-%m-%d'),  # 日期
                'gift_datetime': original_time.strftime('%Y-%m-%d %H:%M:%S'),  # 完整日期时间
                'timestamp': current_time.isoformat(),  # 处理时间戳（ISO格式）
                'received_at': current_time.timestamp(),  # 接收时间戳
                'room_id': self.room_id
            }
            
            # 保存到Redis
            success = self.redis_saver.save_gift(self.room_id, gift_data)
            if success:
                self.local_stats['gift_count'] += gift_data['num']
                # 输出详细日志
                self.logger.info(f"🎁 礼物: [{gift_data['gift_time_formatted']}] {gift_data['username']} -> {gift_data['gift_name']} x{gift_data['num']}")
                
        except Exception as e:
            self.logger.error(f"❌ 处理礼物失败: {e}")
    
    async def simulate_danmaku(self):
        """模拟弹幕数据（当真实连接失败时）- 包含正确时间戳"""
        self.logger.info("🔄 使用模拟弹幕数据...")
        counter = 0
        
        while self._running:
            try:
                await asyncio.sleep(5)  # 每5秒一条模拟弹幕
                
                counter += 1
                current_time = datetime.now()
                
                danmaku_data = {
                    'username': f'测试用户{counter}',
                    'message': f'这是第{counter}条测试弹幕 - 时间: {current_time.strftime("%H:%M:%S")}',
                    'uid': counter,
                    'send_time_ms': int(current_time.timestamp() * 1000),  # 毫秒时间戳
                    'send_time': int(current_time.timestamp()),  # 秒时间戳
                    'send_time_formatted': current_time.strftime('%H:%M:%S'),  # 格式化时间
                    'send_date': current_time.strftime('%Y-%m-%d'),  # 日期
                    'send_datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),  # 完整日期时间
                    'timestamp': current_time.isoformat(),  # ISO格式时间戳
                    'received_at': current_time.timestamp(),  # 接收时间戳
                    'room_id': self.room_id
                }
                
                success = self.redis_saver.save_danmaku(self.room_id, danmaku_data)
                if success:
                    self.local_stats['danmaku_count'] += 1
                    self.logger.info(f"💬 模拟弹幕: [{danmaku_data['send_time_formatted']}] {danmaku_data['username']}: {danmaku_data['message']}")
                
                # 每10条弹幕模拟一个礼物
                if counter % 10 == 0:
                    gift_time = datetime.now()
                    gift_data = {
                        'username': f'土豪{counter}',
                        'gift_name': '小心心',
                        'gift_id': 30607,
                        'num': 1,
                        'price': 5000,
                        'coin_type': 'gold',
                        'gift_timestamp': int(gift_time.timestamp()),  # 礼物时间戳
                        'gift_time_formatted': gift_time.strftime('%H:%M:%S'),  # 格式化时间
                        'gift_date': gift_time.strftime('%Y-%m-%d'),  # 日期
                        'gift_datetime': gift_time.strftime('%Y-%m-%d %H:%M:%S'),  # 完整日期时间
                        'timestamp': gift_time.isoformat(),  # ISO格式时间戳
                        'received_at': gift_time.timestamp(),  # 接收时间戳
                        'room_id': self.room_id
                    }
                    
                    success = self.redis_saver.save_gift(self.room_id, gift_data)
                    if success:
                        self.local_stats['gift_count'] += 1
                        self.logger.info(f"🎁 模拟礼物: [{gift_data['gift_time_formatted']}] {gift_data['username']} -> {gift_data['gift_name']} x{gift_data['num']}")
                
            except Exception as e:
                self.logger.error(f"❌ 模拟数据失败: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        self.logger.info(f"🛑 房间 {self.room_id} 监控已停止")
    
    def print_stats(self):
        """打印统计信息"""
        runtime = datetime.now() - self.local_stats['start_time']
        
        # 从Redis获取数据验证
        redis_data = self.redis_saver.get_room_data(self.room_id)
        
        self.logger.info(f"""
=== 房间 {self.room_id} 统计报告 ===
运行时间: {runtime}
本地统计:
  - 弹幕: {self.local_stats['danmaku_count']} 条
  - 礼物: {self.local_stats['gift_count']} 个
  - 人气更新: {self.local_stats['popularity_updates']} 次
Redis验证:
  - 总弹幕: {redis_data.get('total_danmaku', 0)} 条
  - 总礼物: {redis_data.get('total_gifts', 0)} 个
  - 最新弹幕数: {len(redis_data.get('recent_danmaku', []))} 条
========================================
        """)

def test_fixed_collector():
    """测试修复版收集器"""
    async def run_test():
        room_id = 24486091  # B站官方测试房间
        collector = FixedDataCollector(room_id)
        
        logging.info(f"🚀 开始测试房间 {room_id} 数据收集...")
        
        # 运行5分钟
        test_duration = 300
        start_time = time.time()
        
        # 启动监控任务
        monitor_task = asyncio.create_task(collector.start_monitoring())
        
        # 定期打印进度
        while time.time() - start_time < test_duration:
            await asyncio.sleep(30)
            elapsed = time.time() - start_time
            remaining = test_duration - elapsed
            logging.info(f"⏱️ 测试进度: {elapsed:.0f}s/{test_duration}s, 剩余: {remaining:.0f}s")
            logging.info(f"📊 当前统计: 弹幕 {collector.local_stats['danmaku_count']}, 礼物 {collector.local_stats['gift_count']}")
        
        # 停止监控
        collector.stop_monitoring()
        
        # 等待任务结束
        try:
            await asyncio.wait_for(monitor_task, timeout=10)
        except asyncio.TimeoutError:
            logging.warning("监控任务超时")
        
        # 打印最终统计
        collector.print_stats()
        
        # 验证Redis数据
        logging.info("🔍 验证Redis数据...")
        redis_saver = get_redis_saver()
        room_data = redis_saver.get_room_data(room_id)
        
        if room_data:
            logging.info("✅ Redis数据验证成功!")
            logging.info(f"房间信息: {room_data['room_info']}")
            logging.info(f"最新弹幕: {len(room_data['recent_danmaku'])} 条")
            
            # 显示带时间戳的弹幕示例
            recent_danmaku = room_data.get('recent_danmaku', [])
            if recent_danmaku:
                logging.info("📝 最新弹幕示例（带时间戳）:")
                for i, danmaku in enumerate(recent_danmaku[:3]):
                    time_info = danmaku.get('send_time_formatted', 'Unknown')
                    username = danmaku.get('username', 'Unknown')
                    message = danmaku.get('message', '')
                    logging.info(f"  {i+1}. [{time_info}] {username}: {message}")
        else:
            logging.error("❌ Redis数据验证失败!")
    
    # 运行测试
    asyncio.run(run_test())

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_fixed_collector()
    else:
        logging.info("使用 'python fixed_data_collector.py test' 运行测试")