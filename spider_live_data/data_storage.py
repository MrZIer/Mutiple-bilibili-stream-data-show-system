import json
import os
import asyncio
from datetime import datetime
from bilibili_api import live
import threading
import time

class DataStorage:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.room_files = {}  # 存储房间ID到文件路径的映射
        self.room_info = {}   # 存储房间信息
        self.file_locks = {}  # 文件锁
        
        # 确保数据目录存在
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            print(f"📁 创建数据目录: {data_dir}")
    
    async def init_room_info(self, room_ids):
        """初始化房间信息并创建JSON文件"""
        print("🔍 正在获取直播间信息...")
        for room_id in room_ids:
            try:
                # 获取房间信息
                room = live.LiveRoom(room_display_id=room_id)
                info = await room.get_room_info()
                
                # 提取主播名和房间标题
                uname = info.get('anchor_info', {}).get('base_info', {}).get('uname', f'主播{room_id}')
                title = info.get('room_info', {}).get('title', f'直播间{room_id}')
                
                # 清理文件名中的特殊字符
                safe_uname = self._safe_filename(uname)
                filename = f"{room_id}_{safe_uname}.json"
                filepath = os.path.join(self.data_dir, filename)
                
                self.room_info[room_id] = {
                    'uname': uname,
                    'title': title,
                    'safe_uname': safe_uname
                }
                self.room_files[room_id] = filepath
                self.file_locks[room_id] = threading.Lock()
                
                # 初始化JSON文件
                self._init_json_file(room_id, filepath)
                
                print(f"✅ 初始化房间 {room_id} ({uname}) 数据文件: {filename}")
                
            except Exception as e:
                # 如果获取失败，使用默认信息
                safe_uname = f"主播{room_id}"
                filename = f"{room_id}_{safe_uname}.json"
                filepath = os.path.join(self.data_dir, filename)
                
                self.room_info[room_id] = {
                    'uname': safe_uname,
                    'title': f'直播间{room_id}',
                    'safe_uname': safe_uname
                }
                self.room_files[room_id] = filepath
                self.file_locks[room_id] = threading.Lock()
                
                self._init_json_file(room_id, filepath)
                print(f"⚠️ 无法获取房间 {room_id} 详细信息，使用默认信息: {e}")
    
    def _safe_filename(self, filename):
        """清理文件名中的特殊字符"""
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename[:20]  # 限制长度
    
    def _init_json_file(self, room_id, filepath):
        """初始化JSON文件结构"""
        initial_data = {
            "room_info": {
                "room_id": room_id,
                "uname": self.room_info[room_id]['uname'],
                "title": self.room_info[room_id]['title'],
                "created_at": datetime.now().isoformat()
            },
            "data": {
                "timestamps": [],
                "popularity": [],
                "watched": [],
                "likes": [],
                "total_danmaku_at_time": [],  # 每个时间戳对应的累计弹幕数
                "total_gifts_at_time": []     # 每个时间戳对应的累计礼物数
                # 移除冗余字段: danmaku_count_history 和 gift_count_history
            },
            "real_time": {
                "current_popularity": 0,
                "current_watched": 0,
                "current_likes": 0,
                "total_danmaku": 0,
                "total_gifts": 0,
                "last_update": datetime.now().isoformat()
            },
            "recent_danmaku": [],
            "recent_gifts": []
        }
        
        # 如果文件不存在或为空，创建初始结构
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
        else:
            # 如果文件存在，清理冗余字段
            self._cleanup_json_structure(filepath)
    
    def _cleanup_json_structure(self, filepath):
        """清理现有JSON文件结构，移除冗余字段"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查并添加缺失的字段
            if 'total_danmaku_at_time' not in data['data']:
                data['data']['total_danmaku_at_time'] = []
                print(f"📝 添加 total_danmaku_at_time 字段到 {os.path.basename(filepath)}")
            
            if 'total_gifts_at_time' not in data['data']:
                data['data']['total_gifts_at_time'] = []
                print(f"📝 添加 total_gifts_at_time 字段到 {os.path.basename(filepath)}")
            
            # 移除冗余字段
            removed_fields = []
            if 'danmaku_count_history' in data['data']:
                # 如果有历史数据但没有新字段数据，迁移过来
                if not data['data']['total_danmaku_at_time'] and data['data']['danmaku_count_history']:
                    data['data']['total_danmaku_at_time'] = data['data']['danmaku_count_history'].copy()
                    print(f"📋 迁移 danmaku_count_history 数据到 total_danmaku_at_time")
                
                del data['data']['danmaku_count_history']
                removed_fields.append('danmaku_count_history')
            
            if 'gift_count_history' in data['data']:
                # 如果有历史数据但没有新字段数据，迁移过来
                if not data['data']['total_gifts_at_time'] and data['data']['gift_count_history']:
                    data['data']['total_gifts_at_time'] = data['data']['gift_count_history'].copy()
                    print(f"📋 迁移 gift_count_history 数据到 total_gifts_at_time")
                
                del data['data']['gift_count_history']
                removed_fields.append('gift_count_history')
            
            if removed_fields:
                print(f"🗑️ 移除冗余字段: {removed_fields} 从 {os.path.basename(filepath)}")
            
            # 如果有现有的时间戳数据，为它们填充当前的累计值
            timestamps_count = len(data['data'].get('timestamps', []))
            current_danmaku = data['real_time'].get('total_danmaku', 0)
            current_gifts = data['real_time'].get('total_gifts', 0)
            
            # 补充缺失的累计数据
            while len(data['data']['total_danmaku_at_time']) < timestamps_count:
                data['data']['total_danmaku_at_time'].append(current_danmaku)
            
            while len(data['data']['total_gifts_at_time']) < timestamps_count:
                data['data']['total_gifts_at_time'].append(current_gifts)
            
            # 写回文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"❌ 清理JSON结构时出错 {filepath}: {e}")
    
    def save_data(self, room_id, data_type, value, extra_data=None):
        """保存数据到JSON文件"""
        if room_id not in self.room_files:
            print(f"❌ 房间 {room_id} 未初始化")
            return
        
        filepath = self.room_files[room_id]
        timestamp = datetime.now().isoformat()
        
        with self.file_locks[room_id]:
            try:
                # 读取现有数据
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 更新数据并打印输出
                if data_type == 'popularity':
                    data['data']['timestamps'].append(timestamp)
                    data['data']['popularity'].append(value)
                    data['real_time']['current_popularity'] = value
                    data['real_time']['last_update'] = timestamp
                    
                    # 添加当前时间点的累计弹幕和礼物数
                    current_danmaku = data['real_time'].get('total_danmaku', 0)
                    current_gifts = data['real_time'].get('total_gifts', 0)
                    data['data']['total_danmaku_at_time'].append(current_danmaku)
                    data['data']['total_gifts_at_time'].append(current_gifts)
                    
                    print(f"💾 [房间{room_id}] 人气数据已保存: {value} (累计弹幕: {current_danmaku}, 累计礼物: {current_gifts})")
                    
                    # 保持数据长度限制
                    if len(data['data']['timestamps']) > 1000:
                        for key in ['timestamps', 'popularity', 'total_danmaku_at_time', 'total_gifts_at_time']:
                            if key in data['data']:
                                data['data'][key] = data['data'][key][-1000:]
                
                elif data_type == 'watched':
                    # 确保watched数据与timestamps同步
                    if len(data['data']['timestamps']) > len(data['data']['watched']):
                        data['data']['watched'].append(value)
                    data['real_time']['current_watched'] = value
                    data['real_time']['last_update'] = timestamp
                    print(f"💾 [房间{room_id}] 观看数据已保存: {value}")
                
                elif data_type == 'likes':
                    if len(data['data']['timestamps']) > len(data['data']['likes']):
                        data['data']['likes'].append(value)
                    data['real_time']['current_likes'] = value
                    data['real_time']['last_update'] = timestamp
                    print(f"💾 [房间{room_id}] 点赞数据已保存: {value}")
                
                elif data_type == 'danmaku':
                    data['real_time']['total_danmaku'] += 1
                    if extra_data:
                        danmaku_entry = {
                            'timestamp': timestamp,
                            'username': extra_data['username'],
                            'message': extra_data['message']
                        }
                        data['recent_danmaku'].append(danmaku_entry)
                        print(f"💾 [房间{room_id}] 弹幕已保存: {extra_data['username']}: {extra_data['message']} (总计: {data['real_time']['total_danmaku']})")
                        
                        # 只保留最近100条弹幕
                        if len(data['recent_danmaku']) > 100:
                            data['recent_danmaku'] = data['recent_danmaku'][-100:]
                    
                    # 更新最新时间点的累计弹幕数（如果存在时间戳记录）
                    if data['data']['total_danmaku_at_time']:
                        data['data']['total_danmaku_at_time'][-1] = data['real_time']['total_danmaku']
                
                elif data_type == 'gift':
                    data['real_time']['total_gifts'] += value
                    if extra_data:
                        gift_entry = {
                            'timestamp': timestamp,
                            'username': extra_data['username'],
                            'gift_name': extra_data['gift_name'],
                            'num': value
                        }
                        data['recent_gifts'].append(gift_entry)
                        print(f"💾 [房间{room_id}] 礼物已保存: {extra_data['username']} -> {extra_data['gift_name']} x{value} (总计: {data['real_time']['total_gifts']})")
                        
                        # 只保留最近50条礼物记录
                        if len(data['recent_gifts']) > 50:
                            data['recent_gifts'] = data['recent_gifts'][-50:]
                    
                    # 更新最新时间点的累计礼物数（如果存在时间戳记录）
                    if data['data']['total_gifts_at_time']:
                        data['data']['total_gifts_at_time'][-1] = data['real_time']['total_gifts']
                
                # 写回文件
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                print(f"❌ 保存数据到 {filepath} 时出错: {e}")
    
    def load_data(self, room_id):
        """从JSON文件加载数据"""
        if room_id not in self.room_files:
            return None
        
        filepath = self.room_files[room_id]
        
        with self.file_locks[room_id]:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 确保新字段存在
                if 'total_danmaku_at_time' not in data['data']:
                    data['data']['total_danmaku_at_time'] = []
                if 'total_gifts_at_time' not in data['data']:
                    data['data']['total_gifts_at_time'] = []
                
                return data
            except Exception as e:
                print(f"❌ 从 {filepath} 加载数据时出错: {e}")
                return None
    
    def get_room_info(self, room_id):
        """获取房间信息"""
        return self.room_info.get(room_id, {})
    
    def get_all_room_files(self):
        """获取所有房间文件路径"""
        return self.room_files.copy()

# 全局数据存储实例
_storage = None

def get_storage():
    return _storage

def init_storage(room_ids, data_dir="data"):
    global _storage
    _storage = DataStorage(data_dir)
    
    # 在后台线程中初始化房间信息
    def init_rooms():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_storage.init_room_info(room_ids))
        loop.close()
    
    init_thread = threading.Thread(target=init_rooms, daemon=True)
    init_thread.start()
    init_thread.join(timeout=15)  # 最多等待15秒
    
    return _storage