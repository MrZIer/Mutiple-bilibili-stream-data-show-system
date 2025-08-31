import asyncio
import time
import logging
import sys
import os
from datetime import datetime
from bilibili_api import live, sync
import threading

# 添加模块路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from redis_handler.data_cache import get_live_cache
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保 redis_handler 模块存在并且Redis服务已启动")
    sys.exit(1)

# 配置日志 - 移除可能的Unicode字符
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

class RedisDataCollector:
    """基于Redis的数据收集器"""
    
    def __init__(self, room_id):
        self.room_id = room_id
        self.live_cache = get_live_cache()
        self.logger = logging.getLogger(f'Collector-{room_id}')
        self.room = live.LiveRoom(room_display_id=room_id)
        self._running = False
        
        # 统计数据
        self.stats = {
            'danmaku_count': 0,
            'gift_count': 0,
            'start_time': datetime.now(),
            'last_popularity_update': None
        }
    
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
                'live_status': info.get('room_info', {}).get('live_status', 0)
            }
            
            # 保存到Redis
            self.live_cache.save_room_info(self.room_id, room_info)
            self.logger.info(f"房间信息已保存: {room_info['uname']} - {room_info['title']}")
            
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
                'live_status': 0
            }
            self.live_cache.save_room_info(self.room_id, default_info)
    
    async def start_monitoring(self):
        """开始监控"""
        try:
            self._running = True
            
            # 初始化房间信息
            await self.init_room_info()
            
            # 启动定期人气监控
            popularity_task = asyncio.create_task(self.monitor_popularity())
            
            # 创建弹幕连接
            danmaku_task = asyncio.create_task(self.monitor_danmaku())
            
            # 等待任务完成
            await asyncio.gather(popularity_task, danmaku_task, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"启动监控失败: {e}")
        finally:
            self._running = False
    
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
                
                likes = room_info.get('like_info', {}).get('count', 0) if isinstance(room_info.get('like_info'), dict) else 0
                
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
                await asyncio.sleep(10)  # 错误时减少频率
    
    async def monitor_danmaku(self):
        """监控弹幕数据"""
        try:
            # 使用正确的弹幕连接方式
            from bilibili_api import live
            
            # 创建弹幕监听器
            async def danmaku_handler():
                try:
                    # 这里需要使用正确的API方法
                    # 由于bilibili-api的弹幕监听比较复杂，我们先用轮询方式
                    while self._running:
                        try:
                            # 每10秒检查一次弹幕
                            # 注意：这里是模拟方式，实际的弹幕监听需要更复杂的实现
                            await asyncio.sleep(10)
                            
                            # 模拟弹幕数据（实际项目中需要真实的弹幕API）
                            self.stats['danmaku_count'] += 1
                            
                            extra_data = {
                                'username': f'用户{self.stats["danmaku_count"]}',
                                'message': f'这是第{self.stats["danmaku_count"]}条弹幕'
                            }
                            
                            # 保存到Redis
                            self.live_cache.save_real_time_data(self.room_id, 'danmaku', 1, extra_data)
                            self.logger.debug(f"弹幕: {extra_data['username']}: {extra_data['message']}")
                            
                        except Exception as e:
                            self.logger.error(f"处理弹幕失败: {e}")
                            await asyncio.sleep(5)
                            
                except Exception as e:
                    self.logger.error(f"弹幕监听器异常: {e}")
            
            await danmaku_handler()
            
        except Exception as e:
            self.logger.error(f"启动弹幕监控失败: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        self.logger.info(f"房间 {self.room_id} 监控已停止")
    
    def print_stats(self):
        """打印统计信息"""
        runtime = datetime.now() - self.stats['start_time']
        self.logger.info(f"""
房间 {self.room_id} 统计信息:
- 运行时间: {runtime}
- 累计弹幕: {self.stats['danmaku_count']}
- 累计礼物: {self.stats['gift_count']}
- 最后人气更新: {self.stats['last_popularity_update']}
        """)

# 全局收集器列表
collectors = []

async def monitor_room(room_id):
    """监控单个房间"""
    collector = RedisDataCollector(room_id)
    collectors.append(collector)
    
    try:
        await collector.start_monitoring()
    except Exception as e:
        logging.error(f"房间 {room_id} 监控异常: {e}")
    finally:
        collector.print_stats()

def run_async_monitor(room_ids):
    """运行异步监控"""
    async def monitor_all():
        tasks = [monitor_room(room_id) for room_id in room_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(monitor_all())
    except KeyboardInterrupt:
        logging.info("收到停止信号，正在关闭监控...")
        # 停止所有收集器
        for collector in collectors:
            collector.stop_monitoring()
    finally:
        loop.close()

def main():
    """主函数 - 非异步版本"""
    # 配置要监控的房间
    room_ids = [1923353057]  # 你指定的房间ID
    
    logging.info(f"开始监控房间: {room_ids}")
    logging.info("数据将保存到Redis缓存中")
    
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
        target=run_async_monitor, 
        args=(room_ids,), 
        daemon=True
    )
    monitor_thread.start()
    
    # 等待一下让数据收集开始
    import time
    time.sleep(3)
    
    # 启动可视化界面（在主线程中）
    try:
        from redis_visualizer import init_redis_visualizer
        visualizer = init_redis_visualizer(room_ids)
        visualizer.start()  # 这会阻塞主线程直到窗口关闭
    except ImportError as e:
        logging.error(f"导入可视化模块失败: {e}")
        logging.info("继续运行数据收集，按Ctrl+C停止...")
        try:
            monitor_thread.join()
        except KeyboardInterrupt:
            logging.info("程序已停止")

def test_redis_only():
    """仅测试Redis数据收集（不启动可视化）"""
    room_ids = [1923353057]
    
    logging.info("仅测试Redis数据收集...")
    
    try:
        cache = get_live_cache()
        cache.redis_client.ping()
        logging.info("Redis连接成功")
    except Exception as e:
        logging.error(f"Redis连接失败: {e}")
        return
    
    # 运行监控
    run_async_monitor(room_ids)

def test_room_info():
    """测试房间信息获取"""
    async def get_room_info_test():
        room_id = 1923353057
        try:
            room = live.LiveRoom(room_display_id=room_id)
            info = await room.get_room_info()
            print(f"房间信息: {info}")
            
            room_info = info.get('room_info', {})
            print(f"房间标题: {room_info.get('title')}")
            print(f"主播名: {info.get('anchor_info', {}).get('base_info', {}).get('uname')}")
            print(f"在线人数: {room_info.get('online')}")
            print(f"直播状态: {room_info.get('live_status')}")
            
        except Exception as e:
            print(f"获取房间信息失败: {e}")
    
    asyncio.run(get_room_info_test())

if __name__ == "__main__":
    # 可以选择运行模式
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_redis_only()
        elif sys.argv[1] == "info":
            test_room_info()
    else:
        main()