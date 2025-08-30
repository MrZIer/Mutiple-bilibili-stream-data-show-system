import asyncio
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle
from datetime import datetime
import numpy as np
from collections import deque
import threading
import queue
import json
import os
from data_storage import get_storage

class LiveDataVisualizer:
    def __init__(self, room_ids):
        self.room_ids = room_ids
        self.data_queue = queue.Queue()
        self.storage = get_storage()
        
        # 从JSON文件加载历史数据
        self.room_data = {}
        self._load_historical_data()
        
        # 设置matplotlib
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 创建图形
        self.fig, self.axes = plt.subplots(len(room_ids), 3, figsize=(20, 6*len(room_ids)))
        if len(room_ids) == 1:
            self.axes = self.axes.reshape(1, -1)
        
        self.fig.suptitle('🔴 B站直播间数据实时监控 (双轴显示)', fontsize=18, fontweight='bold')
        
        # 初始化图表
        self.lines = {}
        for i, room_id in enumerate(room_ids):
            room_info = self.storage.get_room_info(room_id) if self.storage else {}
            room_title = room_info.get('title', f'房间{room_id}')
            uname = room_info.get('uname', f'主播{room_id}')
            
            # 左侧：累计弹幕和礼物数量图表（双Y轴）
            ax1 = self.axes[i, 0]
            
            # 创建双Y轴
            ax1_right = ax1.twinx()  # 创建右侧Y轴
            
            # 左Y轴显示弹幕（蓝色）
            line1, = ax1.plot([], [], 'b-', label='💬 累计弹幕', linewidth=2, marker='o', markersize=4)
            ax1.set_ylabel('累计弹幕数', color='blue', fontweight='bold')
            ax1.tick_params(axis='y', labelcolor='blue')
            
            # 右Y轴显示礼物（绿色）
            line2, = ax1_right.plot([], [], 'g-', label='🎁 累计礼物', linewidth=2, marker='s', markersize=4)
            ax1_right.set_ylabel('累计礼物数', color='green', fontweight='bold')
            ax1_right.tick_params(axis='y', labelcolor='green')
            
            ax1.set_title(f'📺 {uname}\n📊 累计数据趋势 (双轴)', fontsize=11, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.set_xlabel('数据点序号')
            
            # 添加图例
            lines = [line1, line2]
            labels = ['💬 累计弹幕', '🎁 累计礼物']
            ax1.legend(lines, labels, loc='upper left')
            
            # 中间：状态信息面板
            ax2 = self.axes[i, 1]
            ax2.axis('off')
            ax2.set_title(f'📈 {uname}\n📋 实时状态', fontsize=11, fontweight='bold')
            
            # 右侧：弹幕显示区域
            ax3 = self.axes[i, 2]
            ax3.axis('off')
            ax3.set_title(f'💬 {uname}\n💭 实时弹幕', fontsize=11, fontweight='bold')
            ax3.set_xlim(0, 1)
            ax3.set_ylim(0, 1)
            
            self.lines[room_id] = {
                'total_danmaku': line1,
                'total_gifts': line2,
                'ax1': ax1,          # 左Y轴（弹幕）
                'ax1_right': ax1_right,  # 右Y轴（礼物）
                'ax2': ax2,
                'ax3': ax3
            }
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    def _load_historical_data(self):
        """从JSON文件加载历史数据"""
        for room_id in self.room_ids:
            if self.storage:
                json_data = self.storage.load_data(room_id)
                if json_data:
                    data = json_data.get('data', {})
                    real_time = json_data.get('real_time', {})
                    recent_danmaku = json_data.get('recent_danmaku', [])
                    
                    # 直接从JSON的数组中读取累计数据
                    total_danmaku_at_time = data.get('total_danmaku_at_time', [])
                    total_gifts_at_time = data.get('total_gifts_at_time', [])
                    
                    self.room_data[room_id] = {
                        'timestamps': deque(data.get('timestamps', [])[-30:], maxlen=30),
                        'popularity': deque(data.get('popularity', [])[-30:], maxlen=30),
                        'watched': deque(data.get('watched', [])[-30:], maxlen=30),
                        'likes': deque(data.get('likes', [])[-30:], maxlen=30),
                        'total_danmaku_history': deque(total_danmaku_at_time[-30:], maxlen=30),
                        'total_gifts_history': deque(total_gifts_at_time[-30:], maxlen=30),
                        'danmaku_count': real_time.get('total_danmaku', 0),
                        'gift_count': real_time.get('total_gifts', 0),
                        'danmaku_messages': deque([
                            f"[{msg['timestamp'].split('T')[1][:8]}] {msg['username']}: {msg['message']}"
                            for msg in recent_danmaku[-10:]
                            if isinstance(msg, dict) and 'timestamp' in msg and 'username' in msg
                        ], maxlen=10),
                        'last_update': datetime.now(),
                        'current_likes': real_time.get('current_likes', 0)
                    }
                    
                    print(f"📊 加载房间 {room_id} 历史数据: 时间点{len(data.get('timestamps', []))}个, 累计弹幕{self.room_data[room_id]['danmaku_count']}, 累计礼物{self.room_data[room_id]['gift_count']}")
                else:
                    self._init_empty_room_data(room_id)
            else:
                self._init_empty_room_data(room_id)
    
    def _init_empty_room_data(self, room_id):
        """初始化空的房间数据"""
        self.room_data[room_id] = {
            'timestamps': deque(maxlen=30),
            'popularity': deque(maxlen=30),
            'watched': deque(maxlen=30),
            'likes': deque(maxlen=30),
            'total_danmaku_history': deque(maxlen=30),
            'total_gifts_history': deque(maxlen=30),
            'danmaku_count': 0,
            'gift_count': 0,
            'danmaku_messages': deque(maxlen=10),
            'last_update': datetime.now(),
            'current_likes': 0
        }
    
    def add_data(self, room_id, data_type, value, extra_data=None):
        """线程安全的数据添加方法"""
        self.data_queue.put({
            'room_id': room_id,
            'type': data_type,
            'value': value,
            'extra_data': extra_data,
            'timestamp': datetime.now()
        })
    
    def process_queue(self):
        """处理数据队列"""
        while not self.data_queue.empty():
            try:
                item = self.data_queue.get_nowait()
                room_id = item['room_id']
                data_type = item['type']
                value = item['value']
                extra_data = item.get('extra_data')
                timestamp = item['timestamp']
                
                if room_id in self.room_data:
                    room = self.room_data[room_id]
                    
                    if data_type == 'popularity':
                        room['timestamps'].append(timestamp)
                        room['popularity'].append(value)
                        room['last_update'] = timestamp
                        
                        # 同时添加当前的累计数据到历史记录
                        room['total_danmaku_history'].append(room['danmaku_count'])
                        room['total_gifts_history'].append(room['gift_count'])
                        
                    elif data_type == 'watched':
                        if len(room['timestamps']) > len(room['watched']):
                            room['watched'].append(value)
                        room['last_update'] = timestamp
                    elif data_type == 'likes':
                        room['current_likes'] = value
                        if len(room['timestamps']) > len(room['likes']):
                            room['likes'].append(value)
                        room['last_update'] = timestamp
                    elif data_type == 'danmaku':
                        room['danmaku_count'] += 1
                        if extra_data:
                            danmaku_text = f"[{timestamp.strftime('%H:%M:%S')}] {extra_data['username']}: {extra_data['message']}"
                            room['danmaku_messages'].append(danmaku_text)
                        
                        # 更新最新的累计数据
                        if room['total_danmaku_history']:
                            room['total_danmaku_history'][-1] = room['danmaku_count']
                            
                    elif data_type == 'gift':
                        room['gift_count'] += value
                        
                        # 更新最新的累计数据
                        if room['total_gifts_history']:
                            room['total_gifts_history'][-1] = room['gift_count']
                
                # 保存到JSON文件
                if self.storage:
                    self.storage.save_data(room_id, data_type, value, extra_data)
                        
            except queue.Empty:
                break
            except Exception as e:
                print(f"处理数据时出错: {e}")
    
    def format_number(self, num):
        """格式化数字显示"""
        if num >= 10000:
            return f"{num/10000:.1f}万"
        elif num >= 1000:
            return f"{num/1000:.1f}k"
        else:
            return str(num)
    
    def animate(self, frame):
        """动画更新函数"""
        self.process_queue()
        
        for room_id in self.room_ids:
            room = self.room_data[room_id]
            lines = self.lines[room_id]
            room_info = self.storage.get_room_info(room_id) if self.storage else {}
            uname = room_info.get('uname', f'主播{room_id}')
            
            # 更新累计数据图表（双Y轴）
            if len(room['timestamps']) > 0:
                # 使用简单的序号作为横坐标
                times = list(range(len(room['timestamps'])))
                total_danmaku_data = list(room['total_danmaku_history'])
                total_gifts_data = list(room['total_gifts_history'])
                
                # 确保数据长度一致
                min_len = min(len(times), len(total_danmaku_data), len(total_gifts_data))
                if min_len > 0:
                    times = times[:min_len]
                    total_danmaku_data = total_danmaku_data[:min_len]
                    total_gifts_data = total_gifts_data[:min_len]
                    
                    # 更新线条数据
                    lines['total_danmaku'].set_data(times, total_danmaku_data)
                    lines['total_gifts'].set_data(times, total_gifts_data)
                    
                    # 更新X轴范围（两个轴共享）
                    lines['ax1'].set_xlim(0, max(len(times), 10))
                    
                    # 分别设置左右Y轴范围
                    # 左Y轴（弹幕）
                    if total_danmaku_data:
                        max_danmaku = max(total_danmaku_data)
                        if max_danmaku > 0:
                            lines['ax1'].set_ylim(0, max_danmaku * 1.1)
                        else:
                            lines['ax1'].set_ylim(0, 10)
                    else:
                        lines['ax1'].set_ylim(0, 10)
                    
                    # 右Y轴（礼物）
                    if total_gifts_data:
                        max_gifts = max(total_gifts_data)
                        if max_gifts > 0:
                            lines['ax1_right'].set_ylim(0, max_gifts * 1.1)
                        else:
                            lines['ax1_right'].set_ylim(0, 5)
                    else:
                        lines['ax1_right'].set_ylim(0, 5)
            
            # 更新状态信息面板
            lines['ax2'].clear()
            lines['ax2'].axis('off')
            lines['ax2'].set_title(f'📈 {uname}\n📋 实时状态', fontsize=11, fontweight='bold')
            
            current_popularity = room['popularity'][-1] if room['popularity'] else 0
            current_watched = room['watched'][-1] if room['watched'] else 0
            current_likes = room['current_likes']
            
            # 显示JSON文件路径
            json_file = ""
            if self.storage and room_id in self.storage.room_files:
                json_file = os.path.basename(self.storage.room_files[room_id])
            
            # 计算数据增长速度
            danmaku_rate = ""
            gift_rate = ""
            if len(room['total_danmaku_history']) >= 2:
                recent_danmaku = list(room['total_danmaku_history'])[-2:]
                danmaku_rate = f" (+{recent_danmaku[-1] - recent_danmaku[-2]})"
            
            if len(room['total_gifts_history']) >= 2:
                recent_gifts = list(room['total_gifts_history'])[-2:]
                gift_rate = f" (+{recent_gifts[-1] - recent_gifts[-2]})"
            
            status_text = f"""🏠 房间ID: {room_id}
📁 数据文件: {json_file}

🔥 人气值: {self.format_number(current_popularity)}
👀 观看数: {self.format_number(current_watched)}
👍 点赞数: {self.format_number(current_likes)}

💬 累计弹幕: {room['danmaku_count']}{danmaku_rate}
🎁 累计礼物: {room['gift_count']}{gift_rate}

📊 双轴显示: 蓝色=弹幕 | 绿色=礼物
🕒 更新时间: {room['last_update'].strftime('%H:%M:%S')}"""
            
            lines['ax2'].text(0.05, 0.5, status_text, fontsize=10, 
                            verticalalignment='center', transform=lines['ax2'].transAxes,
                            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", 
                                    alpha=0.8, edgecolor="navy", linewidth=1))
            
            # 更新弹幕显示区域
            lines['ax3'].clear()
            lines['ax3'].axis('off')
            lines['ax3'].set_title(f'💬 {uname}\n💭 实时弹幕', fontsize=11, fontweight='bold')
            lines['ax3'].set_xlim(0, 1)
            lines['ax3'].set_ylim(0, 1)
            
            # 添加弹幕背景
            rect = Rectangle((0, 0), 1, 1, facecolor='#f0f8ff', alpha=0.5, 
                           edgecolor='lightgray', linewidth=1)
            lines['ax3'].add_patch(rect)
            
            # 显示弹幕消息
            danmaku_messages = list(room['danmaku_messages'])
            if danmaku_messages:
                y_positions = np.linspace(0.05, 0.95, min(len(danmaku_messages), 10))[::-1]
                
                for i, message in enumerate(danmaku_messages[-10:]):
                    if i < len(y_positions):
                        alpha = 1.0 - (i * 0.08)
                        color = '#000080' if i < 3 else '#606060'
                        weight = 'bold' if i < 2 else 'normal'
                        
                        lines['ax3'].text(0.02, y_positions[i], message, 
                                        fontsize=8, transform=lines['ax3'].transAxes,
                                        verticalalignment='bottom', color=color, 
                                        alpha=alpha, weight=weight, wrap=True)
            else:
                lines['ax3'].text(0.5, 0.5, '💭 等待弹幕数据中...', 
                                fontsize=14, transform=lines['ax3'].transAxes,
                                horizontalalignment='center', verticalalignment='center',
                                color='gray', style='italic')
        
        return [line for lines in self.lines.values() 
                for line in [lines['total_danmaku'], lines['total_gifts']]]
    
    def start(self):
        """启动可视化"""
        self.ani = animation.FuncAnimation(self.fig, self.animate, interval=1000, 
                                         blit=False, cache_frame_data=False)
        plt.show()

# 全局可视化器
_visualizer = None

def get_visualizer():
    return _visualizer

def init_visualizer(room_ids):
    global _visualizer
    _visualizer = LiveDataVisualizer(room_ids)
    return _visualizer