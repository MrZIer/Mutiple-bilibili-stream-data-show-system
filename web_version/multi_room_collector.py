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
from typing import List, Dict, Set
import concurrent.futures

# 使用简化的Redis保存器
from simple_redis_saver import get_redis_saver

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MultiRoomCollector:
    """多房间实时数据收集器"""
    
    def __init__(self, room_ids: List[int], display_mode='console'):
        self.room_ids = list(set(room_ids))  # 去重
        self.redis_saver = get_redis_saver()
        self.logger = logging.getLogger('MultiRoomCollector')
        self.display_mode = display_mode  # 'console', 'web', 'both'
        self._running = False
        
        # 单个房间收集器
        self.room_collectors: Dict[int, RealTimeDataCollector] = {}
        
        # 全局统计
        self.global_stats = {
            'total_danmaku': 0,
            'total_gifts': 0,
            'total_popularity_updates': 0,
            'start_time': datetime.now(),
            'active_rooms': set(),
            'failed_rooms': set(),
            'room_stats': {}
        }
        
        # 显示更新间隔
        self.display_update_interval = 2  # 2秒更新一次全局显示
        
    def display_global_header(self):
        """显示全局信息头部"""
        if self.display_mode in ['console', 'both']:
            print("\n" + "="*100)
            print(f"🎬 多房间直播监控系统 - 监控 {len(self.room_ids)} 个直播间")
            print(f"📺 房间列表: {', '.join(map(str, self.room_ids))}")
            print(f"🚀 启动时间: {self.global_stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*100)
            print("📊 全局统计 | 💬 总弹幕 | 🎁 总礼物 | 🏠 活跃房间")
            print("-"*100)
    
    def display_global_stats(self):
        """显示全局实时统计"""
        if self.display_mode in ['console', 'both']:
            runtime = datetime.now() - self.global_stats['start_time']
            runtime_str = str(runtime).split('.')[0]
            
            active_count = len(self.global_stats['active_rooms'])
            failed_count = len(self.global_stats['failed_rooms'])
            
            # 清屏重绘（可选）
            # os.system('cls' if os.name == 'nt' else 'clear')
            
            stats_line = (
                f"⏱️ 运行: {runtime_str} | "
                f"🏠 活跃: {active_count}/{len(self.room_ids)} | "
                f"❌ 失败: {failed_count} | "
                f"💬 总弹幕: {self.global_stats['total_danmaku']} | "
                f"🎁 总礼物: {self.global_stats['total_gifts']}"
            )
            
            print(f"\r{stats_line}", end='', flush=True)
            
            # 显示每个房间的简要统计
            room_stats = []
            for room_id in self.room_ids:
                if room_id in self.room_collectors:
                    collector = self.room_collectors[room_id]
                    danmaku_count = collector.local_stats['danmaku_count']
                    gift_count = collector.local_stats['gift_count']
                    popularity = collector.local_stats['current_popularity']
                    
                    status = "🟢" if room_id in self.global_stats['active_rooms'] else "🔴"
                    room_stats.append(f"{status}{room_id}(💬{danmaku_count}/🎁{gift_count}/👥{popularity:,})")
            
            if room_stats:
                print(f"\n房间状态: {' | '.join(room_stats[:5])}")  # 只显示前5个房间的详情
                if len(room_stats) > 5:
                    print(f"          ...还有 {len(room_stats)-5} 个房间")
    
    async def start_monitoring(self):
        """开始多房间监控"""
        self._running = True
        self.display_global_header()
        
        try:
            # 创建所有房间的收集器
            tasks = []
            
            # 为每个房间创建监控任务
            for room_id in self.room_ids:
                collector = RealTimeDataCollector(
                    room_id, 
                    self.redis_saver, 
                    self.update_global_stats,
                    display_mode='silent'  # 单个房间使用静默模式
                )
                self.room_collectors[room_id] = collector
                
                # 创建房间监控任务
                task = asyncio.create_task(
                    self.monitor_single_room(collector),
                    name=f"Room-{room_id}"
                )
                tasks.append(task)
            
            # 添加全局显示更新任务
            display_task = asyncio.create_task(
                self.global_display_updater(),
                name="GlobalDisplay"
            )
            tasks.append(display_task)
            
            self.logger.info(f"🚀 启动 {len(self.room_ids)} 个房间的监控任务...")
            
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"❌ 多房间监控异常: {e}")
        finally:
            self._running = False
            await self.cleanup_all_rooms()
    
    async def monitor_single_room(self, collector):
        """监控单个房间"""
        room_id = collector.room_id
        max_retries = 3
        retry_count = 0
        
        while self._running and retry_count < max_retries:
            try:
                self.logger.info(f"🔗 启动房间 {room_id} 监控...")
                
                # 标记为活跃房间
                self.global_stats['active_rooms'].add(room_id)
                self.global_stats['failed_rooms'].discard(room_id)
                
                # 开始监控
                await collector.start_monitoring()
                
                # 如果正常结束，退出重试循环
                break
                
            except Exception as e:
                retry_count += 1
                self.logger.error(f"❌ 房间 {room_id} 监控失败 (第{retry_count}次): {e}")
                
                # 标记为失败房间
                self.global_stats['failed_rooms'].add(room_id)
                self.global_stats['active_rooms'].discard(room_id)
                
                if retry_count < max_retries:
                    wait_time = min(10 * retry_count, 60)  # 递增等待时间，最多60秒
                    self.logger.info(f"⏳ 房间 {room_id} 将在 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"💀 房间 {room_id} 超过最大重试次数，放弃监控")
    
    async def global_display_updater(self):
        """全局显示更新器"""
        while self._running:
            try:
                self.display_global_stats()
                await asyncio.sleep(self.display_update_interval)
            except Exception as e:
                self.logger.error(f"❌ 全局显示更新失败: {e}")
                await asyncio.sleep(1)
    
    def update_global_stats(self, room_id: int, stat_type: str, count: int = 1):
        """更新全局统计"""
        if stat_type == 'danmaku':
            self.global_stats['total_danmaku'] += count
        elif stat_type == 'gift':
            self.global_stats['total_gifts'] += count
        elif stat_type == 'popularity':
            self.global_stats['total_popularity_updates'] += count
        
        # 更新房间统计
        if room_id not in self.global_stats['room_stats']:
            self.global_stats['room_stats'][room_id] = {'danmaku': 0, 'gifts': 0, 'popularity': 0}
        
        self.global_stats['room_stats'][room_id][stat_type] += count
    
    async def cleanup_all_rooms(self):
        """清理所有房间资源"""
        self.logger.info("🧹 正在清理所有房间资源...")
        
        cleanup_tasks = []
        for collector in self.room_collectors.values():
            if collector.danmaku_client:
                cleanup_tasks.append(collector.danmaku_client.disconnect())
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
    
    def stop_monitoring(self):
        """停止所有监控"""
        self._running = False
        for collector in self.room_collectors.values():
            collector.stop_monitoring()
        
        print(f"\n🛑 所有房间监控已停止")
    
    def print_final_stats(self):
        """打印最终统计报告"""
        print("\n" + "="*100)
        print("📊 多房间监控最终报告")
        print("="*100)
        
        runtime = datetime.now() - self.global_stats['start_time']
        runtime_str = str(runtime).split('.')[0]
        
        print(f"⏱️ 总运行时间: {runtime_str}")
        print(f"🏠 监控房间数: {len(self.room_ids)}")
        print(f"✅ 成功房间数: {len(self.global_stats['active_rooms'])}")
        print(f"❌ 失败房间数: {len(self.global_stats['failed_rooms'])}")
        print(f"💬 总收集弹幕: {self.global_stats['total_danmaku']} 条")
        print(f"🎁 总收集礼物: {self.global_stats['total_gifts']} 个")
        
        print(f"\n📋 各房间详细统计:")
        print("-" * 80)
        
        for room_id in self.room_ids:
            if room_id in self.room_collectors:
                collector = self.room_collectors[room_id]
                status = "✅" if room_id in self.global_stats['active_rooms'] else "❌"
                
                print(f"{status} 房间 {room_id}:")
                print(f"  主播: {collector.room_info.get('uname', 'Unknown')}")
                print(f"  标题: {collector.room_info.get('title', 'Unknown')[:50]}...")
                print(f"  弹幕: {collector.local_stats['danmaku_count']} 条")
                print(f"  礼物: {collector.local_stats['gift_count']} 个")
                print(f"  人气: {collector.local_stats['current_popularity']:,}")
                
                # 显示最新弹幕
                if collector.recent_danmaku:
                    latest_danmaku = list(collector.recent_danmaku)[0]
                    print(f"  最新弹幕: [{latest_danmaku['send_time_formatted']}] {latest_danmaku['username']}: {latest_danmaku['message'][:30]}...")
                
                print()
        
        if self.global_stats['failed_rooms']:
            print(f"❌ 失败房间: {', '.join(map(str, self.global_stats['failed_rooms']))}")
        
        print("="*100)


class RealTimeDataCollector:
    """单个房间的数据收集器（修改版）"""
    
    def __init__(self, room_id, redis_saver=None, global_stats_callback=None, display_mode='console'):
        self.room_id = room_id
        self.redis_saver = redis_saver or get_redis_saver()
        self.global_stats_callback = global_stats_callback
        self.logger = logging.getLogger(f'Room-{room_id}')
        self.room = live.LiveRoom(room_display_id=room_id)
        self._running = False
        self.display_mode = display_mode
        
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
        
    async def get_room_basic_info(self):
        """获取房间基础信息，包括UP主详细信息"""
        try:
            self.logger.info(f"正在获取房间 {self.room_id} 详细信息...")
            
            # 获取房间信息
            room_info = await self.room.get_room_info()
            
            # 获取UP主信息
            anchor_info = room_info.get('anchor_info', {})
            base_info = anchor_info.get('base_info', {})
            live_info = anchor_info.get('live_info', {})
            
            # 房间信息
            room_data = room_info.get('room_info', {})
            
            # 构造完整的房间和UP主信息
            complete_info = {
                # 基础房间信息
                'room_id': str(self.room_id),
                'title': room_data.get('title', f'直播间{self.room_id}'),
                'area_name': room_data.get('area_name', ''),
                'parent_area_name': room_data.get('parent_area_name', ''),
                'live_status': str(room_data.get('live_status', 0)),
                'online': str(room_data.get('online', 0)),
                'cover': room_data.get('user_cover', ''),
                'keyframe': room_data.get('keyframe', ''),
                'background': room_data.get('background', ''),
                'description': room_data.get('description', ''),
                'tags': room_data.get('tags', ''),
                
                # UP主详细信息
                'uname': base_info.get('uname', f'主播{self.room_id}'),
                'face': base_info.get('face', ''),  # 头像
                'uid': str(base_info.get('uid', 0)),
                'gender': str(base_info.get('gender', 0)),  # 性别 0:保密 1:男 2:女
                'official_verify': base_info.get('official_verify', {}),  # 认证信息
                
                # 直播信息
                'live_time': str(live_info.get('live_time', 0)),  # 开播时间
                'round_status': str(live_info.get('round_status', 0)),
                'broadcast_type': str(live_info.get('broadcast_type', 0)),
                
                # 扩展信息
                'attention': str(room_data.get('attention', 0)),  # 关注数
                'hot_words': room_data.get('hot_words', []),  # 热词
                'hot_words_status': str(room_data.get('hot_words_status', 0)),
                
                # 时间戳
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'info_version': '2.0'  # 版本标识
            }
            
            # 处理性别显示
            gender_map = {0: '保密', 1: '男', 2: '女'}
            complete_info['gender_text'] = gender_map.get(int(complete_info['gender']), '未知')
            
            # 处理认证信息
            if complete_info['official_verify']:
                verify_info = complete_info['official_verify']
                complete_info['is_verified'] = verify_info.get('type', -1) >= 0
                complete_info['verify_desc'] = verify_info.get('desc', '')
            else:
                complete_info['is_verified'] = False
                complete_info['verify_desc'] = ''
            
            # 处理直播状态
            status_map = {0: '未开播', 1: '直播中', 2: '轮播中'}
            complete_info['live_status_text'] = status_map.get(int(complete_info['live_status']), '未知')
            
            self.room_info = complete_info
            
            # 保存到Redis
            success = self.redis_saver.save_room_info(self.room_id, complete_info)
            if success:
                self.logger.info(f"✅ 房间 {self.room_id} 详细信息已保存: {complete_info['uname']} ({complete_info['title'][:30]}...)")
                if self.display_mode != 'silent':
                    self.display_room_header()
            
            return complete_info
            
        except Exception as e:
            self.logger.error(f"❌ 房间 {self.room_id} 详细信息获取失败: {e}")
            # 返回基础信息作为备用
            basic_info = {
                'room_id': str(self.room_id),
                'uname': f'主播{self.room_id}',
                'title': f'直播间{self.room_id}',
                'area_name': '未知',
                'parent_area_name': '未知',
                'live_status': '0',
                'online': '0',
                'created_at': datetime.now().isoformat(),
                'error': str(e)
            }
            self.room_info = basic_info
            return basic_info
    
    async def init_room_info(self):
        """初始化房间信息 - 增强版"""
        return await self.get_room_basic_info()
    
    def display_room_header(self):
        """显示房间信息头部 - 增强版"""
        if self.display_mode in ['console', 'both']:
            print("\n" + "="*100)
            print(f"🎬 直播间监控 - {self.room_info.get('uname', 'Unknown')}")
            
            # 显示认证信息
            if self.room_info.get('is_verified'):
                print(f"✅ 认证: {self.room_info.get('verify_desc', '')}")
            
            print(f"📺 标题: {self.room_info.get('title', 'Unknown')}")
            print(f"🏷️ 分区: {self.room_info.get('parent_area_name', '')} > {self.room_info.get('area_name', '')}")
            print(f"📍 房间号: {self.room_id} | UID: {self.room_info.get('uid', 'Unknown')}")
            print(f"👤 性别: {self.room_info.get('gender_text', '未知')} | 关注: {self.room_info.get('attention', 0)}")
            print(f"🔴 状态: {self.room_info.get('live_status_text', '未知')}")
            
            # 显示头像和封面URL
            if self.room_info.get('face'):
                print(f"👤 头像: {self.room_info['face']}")
            if self.room_info.get('cover'):
                print(f"🖼️ 封面: {self.room_info['cover']}")
            
            print("="*100)
            print("📊 实时统计 | 💬 弹幕 | 🎁 礼物")
            print("-"*100)
    
    async def monitor_room_info(self):
        """定期更新房间和UP主信息"""
        while self._running:
            try:
                # 每5分钟更新一次房间信息
                await asyncio.sleep(300)
                
                if self._running:
                    self.logger.info(f"🔄 更新房间 {self.room_id} 信息...")
                    await self.get_room_basic_info()
                    
            except Exception as e:
                self.logger.error(f"❌ 房间 {self.room_id} 信息更新失败: {e}")
                await asyncio.sleep(60)  # 出错后1分钟后重试
    
    async def start_monitoring(self):
        """开始监控 - 增强版"""
        self._running = True
        
        try:
            # 初始化房间信息
            room_info = await self.init_room_info()
            if not room_info:
                raise Exception("房间信息获取失败")
            
            # 启动监控任务
            tasks = [
                asyncio.create_task(self.monitor_popularity()),
                asyncio.create_task(self.monitor_danmaku()),
                asyncio.create_task(self.monitor_room_info())  # 添加房间信息监控
            ]
            
            # 如果是单独显示模式，添加显示更新任务
            if self.display_mode != 'silent':
                tasks.append(asyncio.create_task(self.display_updater()))
            
            # 等待任务完成或异常
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"❌ 房间 {self.room_id} 监控异常: {e}")
            raise
        finally:
            self._running = False
    
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
                    if self.global_stats_callback:
                        self.global_stats_callback(self.room_id, 'popularity', 1)
                
                await asyncio.sleep(30)  # 30秒更新一次
                
            except Exception as e:
                self.logger.error(f"❌ 房间 {self.room_id} 人气监控失败: {e}")
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
            self.logger.error(f"❌ 房间 {self.room_id} 弹幕监控失败: {e}")
            # 可以选择使用模拟数据或重新抛出异常
            raise
    
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
                original_timestamp = current_time
                send_time_ms = int(current_time.timestamp() * 1000)
                
                # 尝试从B站原始数据获取时间戳
                if len(info) > 0 and isinstance(info[0], list) and len(info[0]) > 4:
                    try:
                        send_time_ms = int(info[0][4])
                        original_timestamp = datetime.fromtimestamp(send_time_ms / 1000)
                    except:
                        pass
                
                # 构造弹幕数据
                danmaku_data = {
                    'username': username,
                    'message': message,
                    'uid': uid,
                    'send_time_ms': send_time_ms,
                    'send_time': int(send_time_ms / 1000),
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
                    if self.global_stats_callback:
                        self.global_stats_callback(self.room_id, 'danmaku', 1)
                    
                    # 只在非静默模式下显示
                    if self.display_mode != 'silent':
                        self.display_danmaku(danmaku_data)
                
        except Exception as e:
            self.logger.error(f"❌ 房间 {self.room_id} 处理弹幕失败: {e}")
    
    async def handle_gift(self, event):
        """处理礼物事件"""
        try:
            data = event.get('data', {})
            current_time = datetime.now()
            
            gift_data = {
                'username': data.get('uname', '匿名用户'),
                'gift_name': data.get('giftName', '未知礼物'),
                'gift_id': data.get('giftId', 0),
                'num': data.get('num', 1),
                'price': data.get('price', 0),
                'coin_type': data.get('coin_type', 'silver'),
                'gift_timestamp': int(current_time.timestamp()),
                'gift_time_formatted': current_time.strftime('%H:%M:%S'),
                'gift_date': current_time.strftime('%Y-%m-%d'),
                'gift_datetime': current_time.strftime('%Y-%m-%d %H:%M:%S'),
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
                if self.global_stats_callback:
                    self.global_stats_callback(self.room_id, 'gift', gift_data['num'])
                
                # 只在非静默模式下显示
                if self.display_mode != 'silent':
                    self.display_gift(gift_data)
                
        except Exception as e:
            self.logger.error(f"❌ 房间 {self.room_id} 处理礼物失败: {e}")
    
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
    
    def print_final_stats(self):
        """打印最终统计信息"""
        if self.display_mode == 'silent':
            return
            
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
        print("="*80)


def signal_handler(signum, frame):
    """信号处理器"""
    print("\n\n🛑 收到停止信号，正在关闭所有监控...")
    sys.exit(0)


def run_real_time_monitor(room_ids, duration=None):
    """运行实时监控 - 支持单个房间或多个房间"""
    
    # 标准化输入
    if isinstance(room_ids, int):
        room_ids = [room_ids]
    elif isinstance(room_ids, str):
        # 支持逗号分隔的字符串
        room_ids = [int(x.strip()) for x in room_ids.split(',') if x.strip().isdigit()]
    
    if not room_ids:
        print("❌ 错误: 未提供有效的房间ID")
        return
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    async def monitor():
        if len(room_ids) == 1:
            # 单房间模式
            collector = RealTimeDataCollector(room_ids[0], display_mode='console')
            
            try:
                print(f"🚀 启动房间 {room_ids[0]} 实时监控...")
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
        else:
            # 多房间模式
            collector = MultiRoomCollector(room_ids, display_mode='console')
            
            try:
                print(f"🚀 启动多房间监控系统...")
                print(f"📺 监控房间: {', '.join(map(str, room_ids))}")
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
    # 支持多种输入方式
    
    # 方式1: 单个房间
    # room_ids = 1962481108
    
    # 方式2: 多个房间列表
    room_ids = [
        1962481108,  # 房间1
        17961,  # 房间2
        4190942,  # 房间3     
        # 可以继续添加更多房间...
    ]
    
    # 方式3: 从命令行参数获取
    if len(sys.argv) > 1:
        try:
            # 支持多种格式: python script.py 123456 或 python script.py 123456,789012,345678
            args = ' '.join(sys.argv[1:])
            if ',' in args:
                room_ids = [int(x.strip()) for x in args.split(',') if x.strip().isdigit()]
            else:
                room_ids = [int(x) for x in sys.argv[1:] if x.isdigit()]
        except ValueError:
            print("❌ 错误: 请提供有效的房间ID")
            sys.exit(1)
    
    print(f"🎯 准备监控 {len(room_ids) if isinstance(room_ids, list) else 1} 个直播间")
    if isinstance(room_ids, list):
        print(f"📋 房间列表: {', '.join(map(str, room_ids))}")
    else:
        print(f"📋 房间: {room_ids}")
    
    # 运行监控
    run_real_time_monitor(room_ids)