import asyncio
import threading
import time
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict
from django.conf import settings

from utils.bilibili_client import get_bilibili_client, get_async_bilibili_client, LiveDanmakuCollector
from utils.redis_handler import get_room_manager
from .models import Room

logger = logging.getLogger('live_data')

class LiveDataCollector:
    """直播数据收集器"""
    
    def __init__(self):
        self.bilibili_client = get_bilibili_client()
        self.async_client = get_async_bilibili_client()
        self.room_manager = get_room_manager()
        self.is_running = False
        self.collection_threads = {}
        self.danmaku_collectors = {}  # 弹幕收集器
        self.collection_interval = settings.LIVE_MONITOR_CONFIG.get('COLLECTION_INTERVAL', 30)
        
    def start_monitoring_room(self, room_id: int):
        """开始监控单个房间"""
        if room_id in self.collection_threads:
            logger.warning(f"房间 {room_id} 已在监控中")
            return
        
        # 启动监控线程
        thread = threading.Thread(
            target=self._monitor_room_loop,
            args=(room_id,),
            daemon=True,
            name=f"Monitor-Room-{room_id}"
        )
        thread.start()
        self.collection_threads[room_id] = thread
        
        # 启动弹幕监听
        self._start_danmaku_monitoring(room_id)
        
        # 更新数据库状态
        try:
            room, created = Room.objects.get_or_create(room_id=room_id)
            room.is_monitoring = True
            room.save()
            logger.info(f"开始监控房间 {room_id}")
        except Exception as e:
            logger.error(f"更新房间 {room_id} 监控状态失败: {e}")
    
    def _start_danmaku_monitoring(self, room_id: int):
        """启动弹幕监听"""
        try:
            # 创建弹幕收集器
            danmaku_collector = LiveDanmakuCollector(
                room_id=room_id,
                redis_cache=self.room_manager.cache
            )
            
            self.danmaku_collectors[room_id] = danmaku_collector
            
            # 在新的事件循环中启动弹幕监听
            def run_danmaku_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(danmaku_collector.start())
                    # 保持连接
                    while room_id in self.danmaku_collectors and self.is_running:
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"房间 {room_id} 弹幕监听异常: {e}")
                finally:
                    loop.close()
            
            danmaku_thread = threading.Thread(
                target=run_danmaku_loop,
                daemon=True,
                name=f"Danmaku-{room_id}"
            )
            danmaku_thread.start()
            
            logger.info(f"房间 {room_id} 弹幕监听已启动")
            
        except Exception as e:
            logger.error(f"启动房间 {room_id} 弹幕监听失败: {e}")
    
    def stop_monitoring_room(self, room_id: int):
        """停止监控单个房间"""
        if room_id in self.collection_threads:
            # 线程会在下次循环时自动退出
            del self.collection_threads[room_id]
        
        # 停止弹幕监听
        if room_id in self.danmaku_collectors:
            try:
                # 异步停止弹幕收集器
                asyncio.run(self.danmaku_collectors[room_id].stop())
                del self.danmaku_collectors[room_id]
                logger.info(f"房间 {room_id} 弹幕监听已停止")
            except Exception as e:
                logger.error(f"停止房间 {room_id} 弹幕监听失败: {e}")
        
        # 更新数据库状态
        try:
            room = Room.objects.get(room_id=room_id)
            room.is_monitoring = False
            room.save()
            logger.info(f"停止监控房间 {room_id}")
        except Room.DoesNotExist:
            logger.warning(f"房间 {room_id} 不存在于数据库中")
    
    def start_monitoring_multiple_rooms(self, room_ids: List[int]):
        """开始监控多个房间"""
        self.is_running = True
        for room_id in room_ids:
            self.start_monitoring_room(room_id)
    
    def stop_all_monitoring(self):
        """停止所有监控"""
        self.is_running = False
        room_ids = list(self.collection_threads.keys())
        for room_id in room_ids:
            self.stop_monitoring_room(room_id)
        
        logger.info("已停止所有房间监控")
    
    def _monitor_room_loop(self, room_id: int):
        """单个房间监控循环"""
        logger.info(f"房间 {room_id} 监控线程启动")
        
        while room_id in self.collection_threads and self.is_running:
            try:
                # 收集数据
                self._collect_room_data(room_id)
                
                # 等待下次收集
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"房间 {room_id} 数据收集出错: {e}")
                time.sleep(10)  # 出错后等待10秒再重试
        
        logger.info(f"房间 {room_id} 监控线程结束")
    
    def _collect_room_data(self, room_id: int):
        """收集单个房间数据"""
        try:
            # 使用Bilibili API获取数据
            room_data = self.bilibili_client.fetch_live_data(room_id)
            
            if not room_data:
                logger.warning(f"房间 {room_id} 未获取到数据")
                return
            
            # 保存房间基本信息到Redis
            self.room_manager.cache.save_room_info(room_id, room_data)
            
            # 保存实时数据到Redis
            self.room_manager.cache.save_real_time_data(
                room_id, 'popularity', room_data['popularity']
            )
            
            if room_data.get('watched'):
                self.room_manager.cache.save_real_time_data(
                    room_id, 'watched', room_data['watched']
                )
            
            # 更新数据库中的房间信息
            self._update_room_in_database(room_id, room_data)
            
            logger.debug(f"房间 {room_id} 数据收集完成 - 人气: {room_data['popularity']}")
            
        except Exception as e:
            logger.error(f"收集房间 {room_id} 数据失败: {e}")
    
    def _update_room_in_database(self, room_id: int, room_data: Dict):
        """更新数据库中的房间信息"""
        try:
            room, created = Room.objects.get_or_create(
                room_id=room_id,
                defaults={
                    'real_room_id': room_data.get('real_room_id', room_id),
                    'uname': room_data.get('uname', f'主播{room_id}'),
                    'title': room_data.get('title', f'直播间{room_id}'),
                    'area_name': room_data.get('area_name', ''),
                    'parent_area_name': room_data.get('parent_area_name', ''),
                    'uid': room_data.get('uid', 0),
                    'cover': room_data.get('cover', ''),
                    'keyframe': room_data.get('keyframe', ''),
                    'live_status': room_data.get('live_status', 0),
                    'is_monitoring': True
                }
            )
            
            if not created:
                # 更新现有房间信息
                room.real_room_id = room_data.get('real_room_id', room.real_room_id)
                room.uname = room_data.get('uname', room.uname)
                room.title = room_data.get('title', room.title)
                room.area_name = room_data.get('area_name', room.area_name)
                room.parent_area_name = room_data.get('parent_area_name', room.parent_area_name)
                room.uid = room_data.get('uid', room.uid)
                room.cover = room_data.get('cover', room.cover)
                room.keyframe = room_data.get('keyframe', room.keyframe)
                room.live_status = room_data.get('live_status', room.live_status)
                room.save()
                
        except Exception as e:
            logger.error(f"更新房间 {room_id} 数据库信息失败: {e}")

    def get_collector_status(self) -> Dict:
        """获取收集器状态"""
        return {
            'is_running': self.is_running,
            'monitoring_rooms': list(self.collection_threads.keys()),
            'danmaku_rooms': list(self.danmaku_collectors.keys()),
            'active_threads': len(self.collection_threads),
            'collection_interval': self.collection_interval
        }

# 全局收集器实例
_collector = None

def get_data_collector() -> LiveDataCollector:
    """获取全局数据收集器实例"""
    global _collector
    if _collector is None:
        _collector = LiveDataCollector()
    return _collector

def start_default_monitoring():
    """启动默认房间监控"""
    collector = get_data_collector()
    default_rooms = settings.LIVE_MONITOR_CONFIG.get('DEFAULT_ROOM_IDS', [])
    
    if default_rooms:
        collector.start_monitoring_multiple_rooms(default_rooms)
        logger.info(f"启动默认房间监控: {default_rooms}")
    else:
        logger.warning("未配置默认监控房间")