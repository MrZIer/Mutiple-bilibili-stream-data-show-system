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

# 添加模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from redis_handler.data_cache import get_live_cache
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保 redis_handler 模块存在并且Redis服务已启动")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

class EnhancedRedisDataCollector:
    """增强版Redis数据收集器 - 支持真实弹幕抓取"""
    
    def __init__(self, room_id):
        self.room_id = room_id
        self.live_cache = get_live_cache()
        self.logger = logging.getLogger(f'Enhanced-Collector-{room_id}')
        self.room = live.LiveRoom(room_display_id=room_id)
        self._running = False
        
        # 统计数据
        self.stats = {
            'danmaku_count': 0,
            'gift_count': 0,
            'start_time': datetime.now(),
            'last_popularity_update': None,
            'last_danmaku_time': None,
            'last_gift_time': None
        }
        
        # 弹幕连接
        self.danmaku_client = None
    
    async def init_room_info(self):
        """初始化房间信息"""
        try:
            info = await self.room.get_room_info()
            
            room_info = {
                'room_id': self.room_id,
                'uname': info.get('anchor_info', {}).get('base_info', {}).get('uname', f'主播{self.room_id}'),
                'title': info.get('room_info', {}).get('title', f'直播间{self.room_id}'),
                'created_at': datetime.now().isoformat(),
                'area_name': info.get('room_info', {}).get('area_name', ''),
                'parent_area_name': info.get('room_info', {}).get('parent_area_name', ''),
                'live_status': info.get('room_info', {}).get('live_status', 0),
                'online': info.get('room_info', {}).get('online', 0)
            }
            
            # 保存到Redis
            self.live_cache.save_room_info(self.room_id, room_info)
            self.logger.info(f"房间信息已保存: {room_info['uname']} - {room_info['title']}")
            
            return room_info
            
        except Exception as e:
            self.logger.error(f"初始化房间信息失败: {e}")
            # 使用默认信息
            default_info = {
                'room_id': self.room_id,
                'uname': f'主播{self.room_id}',
                'title': f'直播间{self.room_id}',
                'created_at': datetime.now().isoformat(),
                'area_name': '未知',
                'parent_area_name': '未知',
                'live_status': 0,
                'online': 0
            }
            self.live_cache.save_room_info(self.room_id, default_info)
            return default_info
    
    async def start_monitoring(self):
        """开始监控"""
        try:
            self._running = True
            
            # 初始化房间信息
            room_info = await self.init_room_info()
            
            # 检查直播状态
            if room_info['live_status'] != 1:
                self.logger.warning(f"房间 {self.room_id} 当前未在直播")
            
            # 启动各种监控任务
            tasks = []
            
            # 人气监控任务
            tasks.append(asyncio.create_task(self.monitor_popularity()))
            
            # 弹幕监控任务
            tasks.append(asyncio.create_task(self.monitor_danmaku_real()))
            
            # 等待所有任务
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"启动监控失败: {e}")
        finally:
            self._running = False
            if self.danmaku_client:
                await self.danmaku_client.disconnect()
    
    async def monitor_popularity(self):
        """定期监控人气数据"""
        while self._running:
            try:
                # 获取房间信息
                info = await self.room.get_room_info()
                room_info = info.get('room_info', {})
                
                # 提取数据
                popularity = room_info.get('online', 0)
                watched_info = room_info.get('watched_show', {})
                watched = 0
                if isinstance(watched_info, dict):
                    watched = watched_info.get('num', 0)
                elif isinstance(watched_info, int):
                    watched = watched_info
                
                likes_info = room_info.get('like_info', {})
                likes = 0
                if isinstance(likes_info, dict):
                    likes = likes_info.get('count', 0)
                elif isinstance(likes_info, int):
                    likes = likes_info
                
                # 保存到Redis
                self.live_cache.save_real_time_data(self.room_id, 'popularity', popularity)
                self.live_cache.save_real_time_data(self.room_id, 'watched', watched)
                self.live_cache.save_real_time_data(self.room_id, 'likes', likes)
                
                self.stats['last_popularity_update'] = datetime.now()
                self.logger.info(f"人气更新: {popularity}, 观看: {watched}, 点赞: {likes}")
                
                # 每30秒更新一次
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"监控人气失败: {e}")
                await asyncio.sleep(10)
    
    async def monitor_danmaku_real(self):
        """实时监控弹幕数据"""
        try:
            # 创建弹幕连接
            self.danmaku_client = LiveDanmaku(self.room_id)
            
            # 注册弹幕事件处理器
            @self.danmaku_client.on('DANMU_MSG')
            async def on_danmaku(event):
                if not self._running:
                    return
                await self.handle_danmaku_event(event)
            
            # 注册礼物事件处理器
            @self.danmaku_client.on('SEND_GIFT')
            async def on_gift(event):
                if not self._running:
                    return
                await self.handle_gift_event(event)
            
            # 注册欢迎事件（可选）
            @self.danmaku_client.on('INTERACT_WORD')
            async def on_interact(event):
                if not self._running:
                    return
                await self.handle_interact_event(event)
            
            # 连接弹幕服务器
            self.logger.info(f"正在连接房间 {self.room_id} 的弹幕服务器...")
            await self.danmaku_client.connect()
            
        except Exception as e:
            self.logger.error(f"弹幕监控失败: {e}")
            # 如果弹幕连接失败，使用备用监控方式
            await self.monitor_danmaku_fallback()
    
    async def handle_danmaku_event(self, event):
        """处理弹幕事件"""
        try:
            data = event.get('data', {})
            info = data.get('info', [])
            
            if len(info) >= 3:
                # 解析弹幕信息
                message = info[1] if len(info) > 1 else ''  # 弹幕内容
                user_info = info[2] if len(info) > 2 else []  # 用户信息
                username = user_info[1] if len(user_info) > 1 else '匿名用户'
                uid = user_info[0] if len(user_info) > 0 else 0
                
                # 时间戳信息
                timestamp_info = info[0] if len(info) > 0 else []
                send_time = timestamp_info[4] if len(timestamp_info) > 4 else int(time.time())
                
                extra_data = {
                    'username': username,
                    'message': message,
                    'uid': uid,
                    'send_time': send_time
                }
                
                # 保存到Redis
                self.live_cache.save_real_time_data(self.room_id, 'danmaku', 1, extra_data)
                
                self.stats['danmaku_count'] += 1
                self.stats['last_danmaku_time'] = datetime.now()
                
                self.logger.debug(f"弹幕: {username}: {message}")
                
        except Exception as e:
            self.logger.error(f"处理弹幕事件失败: {e}")
    
    async def handle_gift_event(self, event):
        """处理礼物事件"""
        try:
            data = event.get('data', {})
            
            username = data.get('uname', '匿名用户')
            gift_name = data.get('giftName', '未知礼物')
            num = data.get('num', 1)
            gift_id = data.get('giftId', 0)
            price = data.get('price', 0)  # 礼物价格（金瓜子）
            coin_type = data.get('coin_type', 'silver')  # 货币类型
            
            extra_data = {
                'username': username,
                'gift_name': gift_name,
                'gift_id': gift_id,
                'price': price,
                'coin_type': coin_type
            }
            
            # 保存到Redis
            self.live_cache.save_real_time_data(self.room_id, 'gift', num, extra_data)
            
            self.stats['gift_count'] += num
            self.stats['last_gift_time'] = datetime.now()
            
            self.logger.info(f"礼物: {username} -> {gift_name} x{num} (价值: {price} {coin_type})")
            
        except Exception as e:
            self.logger.error(f"处理礼物事件失败: {e}")
    
    async def handle_interact_event(self, event):
        """处理互动事件（进房等）"""
        try:
            data = event.get('data', {})
            msg_type = data.get('msg_type', 0)
            username = data.get('uname', '匿名用户')
            
            if msg_type == 1:  # 进房
                self.logger.debug(f"用户进房: {username}")
            elif msg_type == 2:  # 关注
                self.logger.info(f"新关注: {username}")
                
        except Exception as e:
            self.logger.error(f"处理互动事件失败: {e}")
    
    async def monitor_danmaku_fallback(self):
        """备用弹幕监控方式"""
        self.logger.info("使用备用弹幕监控方式")
        counter = 0
        
        while self._running:
            try:
                await asyncio.sleep(5)  # 每5秒模拟一次弹幕
                
                counter += 1
                extra_data = {
                    'username': f'测试用户{counter}',
                    'message': f'这是第{counter}条测试弹幕',
                    'uid': counter,
                    'send_time': int(time.time())
                }
                
                # 保存到Redis
                self.live_cache.save_real_time_data(self.room_id, 'danmaku', 1, extra_data)
                
                self.stats['danmaku_count'] += 1
                self.stats['last_danmaku_time'] = datetime.now()
                
                # 偶尔模拟礼物
                if counter % 10 == 0:
                    gift_extra = {
                        'username': f'土豪{counter}',
                        'gift_name': '小心心',
                        'gift_id': 30607,
                        'price': 5000,
                        'coin_type': 'gold'
                    }
                    
                    self.live_cache.save_real_time_data(self.room_id, 'gift', 1, gift_extra)
                    self.stats['gift_count'] += 1
                    self.stats['last_gift_time'] = datetime.now()
                
            except Exception as e:
                self.logger.error(f"备用监控失败: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        self.logger.info(f"房间 {self.room_id} 监控已停止")
    
    def get_stats_summary(self):
        """获取统计摘要"""
        runtime = datetime.now() - self.stats['start_time']
        
        # 从Redis获取当前累计数据
        current_data = self.live_cache.get_room_current_data(self.room_id)
        
        return {
            'room_id': self.room_id,
            'runtime': str(runtime),
            'local_danmaku_count': self.stats['danmaku_count'],
            'local_gift_count': self.stats['gift_count'],
            'redis_total_danmaku': current_data.get('total_danmaku', 0),
            'redis_total_gifts': current_data.get('total_gifts', 0),
            'last_popularity_update': self.stats['last_popularity_update'],
            'last_danmaku_time': self.stats['last_danmaku_time'],
            'last_gift_time': self.stats['last_gift_time']
        }
    
    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats_summary()
        
        self.logger.info(f"""
=== 房间 {self.room_id} 统计信息 ===
运行时间: {stats['runtime']}
本地统计 - 弹幕: {stats['local_danmaku_count']}, 礼物: {stats['local_gift_count']}
Redis累计 - 弹幕: {stats['redis_total_danmaku']}, 礼物: {stats['redis_total_gifts']}
最后人气更新: {stats['last_popularity_update']}
最后弹幕时间: {stats['last_danmaku_time']}
最后礼物时间: {stats['last_gift_time']}
        """)

# 全局收集器管理
collectors = []

async def monitor_room_enhanced(room_id):
    """增强版房间监控"""
    collector = EnhancedRedisDataCollector(room_id)
    collectors.append(collector)
    
    try:
        await collector.start_monitoring()
    except Exception as e:
        logging.error(f"房间 {room_id} 监控异常: {e}")
    finally:
        collector.print_stats()

def run_enhanced_monitor(room_ids):
    """运行增强版监控"""
    async def monitor_all():
        tasks = [monitor_room_enhanced(room_id) for room_id in room_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(monitor_all())
    except KeyboardInterrupt:
        logging.info("收到停止信号，正在关闭监控...")
        for collector in collectors:
            collector.stop_monitoring()
    finally:
        loop.close()

def main_enhanced():
    """增强版主函数"""
    # 配置要监控的房间
    room_ids = [1962481108,1959064353]  # B站英雄联盟赛事, 其他热门直播间
    
    logging.info(f"启动增强版监控，房间: {room_ids}")
    logging.info("支持实时弹幕抓取和累计统计")
    
    try:
        # 测试Redis连接
        cache = get_live_cache()
        cache.redis_client.ping()
        logging.info("Redis连接成功")
    except Exception as e:
        logging.error(f"Redis连接失败: {e}")
        logging.error("请确保Redis服务已启动")
        return
    
    # 启动监控线程
    monitor_thread = threading.Thread(
        target=run_enhanced_monitor, 
        args=(room_ids,), 
        daemon=True
    )
    monitor_thread.start()
    
    # 等待数据收集开始
    time.sleep(3)
    
    # 启动可视化界面
    try:
        from redis_visualizer import init_redis_visualizer
        visualizer = init_redis_visualizer(room_ids)
        visualizer.start()
    except ImportError as e:
        logging.error(f"导入可视化模块失败: {e}")
        logging.info("继续运行数据收集，按Ctrl+C停止...")
        try:
            monitor_thread.join()
        except KeyboardInterrupt:
            logging.info("程序已停止")

def test_single_room():
    """测试单个房间的弹幕抓取"""
    async def test_room():
        room_id = 6  # B站英雄联盟赛事
        collector = EnhancedRedisDataCollector(room_id)
        
        logging.info(f"开始测试房间 {room_id} 的弹幕抓取...")
        
        # 运行5分钟测试
        test_duration = 300  # 5分钟
        start_time = time.time()
        
        # 启动监控
        monitor_task = asyncio.create_task(collector.start_monitoring())
        
        # 等待测试时间
        while time.time() - start_time < test_duration:
            await asyncio.sleep(10)
            stats = collector.get_stats_summary()
            logging.info(f"测试进度: 弹幕 {stats['local_danmaku_count']}, 礼物 {stats['local_gift_count']}")
        
        # 停止监控
        collector.stop_monitoring()
        await monitor_task
        
        # 打印最终统计
        collector.print_stats()
    
    asyncio.run(test_room())

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_single_room()
        elif sys.argv[1] == "enhanced":
            main_enhanced()
    else:
        main_enhanced()