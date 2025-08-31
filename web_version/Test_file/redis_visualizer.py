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
import logging
from redis_handler.data_cache import get_live_cache
from config.redis_config import get_redis_client

class RedisLiveDataVisualizer:
    """基于Redis的直播数据可视化器"""
    
    def __init__(self, room_ids):
        self.room_ids = room_ids
        self.live_cache = get_live_cache()
        self.redis_client = get_redis_client()
        self.logger = logging.getLogger(__name__)
        
        # 初始化数据结构
        self.room_display_data = {}
        self._init_display_data()
        
        # 设置matplotlib - 修复字体问题
        self._setup_matplotlib_font()
        
        # 创建图形
        self.fig, self.axes = plt.subplots(len(room_ids), 3, figsize=(20, 6*len(room_ids)))
        if len(room_ids) == 1:
            self.axes = self.axes.reshape(1, -1)
        
        self.fig.suptitle('B站直播数据实时监控 (Redis驱动)', fontsize=18, fontweight='bold')
        
        # 初始化图表
        self.lines = {}
        self._init_charts()
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    def _setup_matplotlib_font(self):
        """设置matplotlib字体，避免特殊字符显示问题"""
        import matplotlib.font_manager as fm
        
        # 尝试设置支持更多字符的字体
        try:
            # 首先尝试使用系统默认中文字体
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans', 'Arial Unicode MS', 'sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
            
            # 设置字体回退策略
            plt.rcParams['font.family'] = 'sans-serif'
            
            self.logger.info("字体设置完成")
        except Exception as e:
            self.logger.warning(f"字体设置失败: {e}，使用默认字体")
            # 使用基本的ASCII字符
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
            plt.rcParams['axes.unicode_minus'] = False
    
    def _get_safe_text(self, text):
        """获取安全的显示文本，移除可能导致字体问题的特殊字符"""
        # 定义字符替换映射
        char_map = {
            '🔴': '[LIVE]',
            '📺': '[TV]',
            '📊': '[CHART]',
            '📈': '[TREND]',
            '📋': '[INFO]',
            '💬': '[MSG]',
            '💭': '[CHAT]',
            '🎁': '[GIFT]',
            '🔥': '[HOT]',
            '👀': '[VIEW]',
            '👍': '[LIKE]',
            '🏠': '[ROOM]',
            '📁': '[FILE]',
            '🗃️': '[DATA]',
            '🕒': '[TIME]',
            '⚡': '[FAST]',
            '💾': '[SAVE]',
            '✅': '[OK]',
            '❌': '[ERROR]'
        }
        
        # 替换特殊字符
        safe_text = text
        for emoji, replacement in char_map.items():
            safe_text = safe_text.replace(emoji, replacement)
        
        return safe_text
    
    def _init_display_data(self):
        """初始化显示数据结构"""
        for room_id in self.room_ids:
            # 从Redis加载历史数据
            stream_data = self.live_cache.get_room_stream_data(room_id, 30)
            current_data = self.live_cache.get_room_current_data(room_id)
            recent_danmaku = self.live_cache.get_recent_danmaku(room_id, 10)
            
            # 处理时序数据
            timestamps = []
            popularity_data = []
            danmaku_counts = []
            gift_counts = []
            
            for data in stream_data:
                if data.get('type') == 'metrics':
                    timestamps.append(data.get('timestamp', 0))
                    popularity_data.append(data.get('popularity', 0))
                    danmaku_counts.append(data.get('danmaku_count', 0))
                    gift_counts.append(data.get('gift_count', 0))
            
            self.room_display_data[room_id] = {
                'timestamps': deque(timestamps[-30:], maxlen=30),
                'popularity': deque(popularity_data[-30:], maxlen=30),
                'danmaku_counts': deque(danmaku_counts[-30:], maxlen=30),
                'gift_counts': deque(gift_counts[-30:], maxlen=30),
                'current_data': current_data,
                'recent_danmaku': recent_danmaku,
                'last_update': datetime.now()
            }
            
            self.logger.info(f"房间 {room_id} 显示数据已初始化，历史数据点: {len(timestamps)}")
    
    def _init_charts(self):
        """初始化图表"""
        for i, room_id in enumerate(self.room_ids):
            # 获取房间信息
            room_info_key = f'room:{room_id}:info'
            room_info = self.redis_client.hgetall(room_info_key)
            uname = room_info.get('uname', f'房间{room_id}')
            
            # 左侧：累计弹幕和礼物数量图表（双Y轴）
            ax1 = self.axes[i, 0]
            ax1_right = ax1.twinx()
            
            # 左Y轴显示弹幕（蓝色）
            line1, = ax1.plot([], [], 'b-', label='累计弹幕', linewidth=2, marker='o', markersize=4)
            ax1.set_ylabel('累计弹幕数', color='blue', fontweight='bold')
            ax1.tick_params(axis='y', labelcolor='blue')
            
            # 右Y轴显示礼物（绿色）
            line2, = ax1_right.plot([], [], 'g-', label='累计礼物', linewidth=2, marker='s', markersize=4)
            ax1_right.set_ylabel('累计礼物数', color='green', fontweight='bold')
            ax1_right.tick_params(axis='y', labelcolor='green')
            
            ax1.set_title(f'{uname}\n累计数据趋势 (Redis)', fontsize=11, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.set_xlabel('数据点序号')
            
            # 添加图例
            lines = [line1, line2]
            labels = ['累计弹幕', '累计礼物']
            ax1.legend(lines, labels, loc='upper left')
            
            # 中间：状态信息面板
            ax2 = self.axes[i, 1]
            ax2.axis('off')
            ax2.set_title(f'{uname}\n实时状态 (Redis)', fontsize=11, fontweight='bold')
            
            # 右侧：弹幕显示区域
            ax3 = self.axes[i, 2]
            ax3.axis('off')
            ax3.set_title(f'{uname}\n实时弹幕 (Redis)', fontsize=11, fontweight='bold')
            ax3.set_xlim(0, 1)
            ax3.set_ylim(0, 1)
            
            self.lines[room_id] = {
                'danmaku_line': line1,
                'gift_line': line2,
                'ax1': ax1,
                'ax1_right': ax1_right,
                'ax2': ax2,
                'ax3': ax3
            }
    
    def update_from_redis(self):
        """从Redis更新数据"""
        for room_id in self.room_ids:
            try:
                # 获取最新数据
                current_data = self.live_cache.get_room_current_data(room_id)
                recent_stream = self.live_cache.get_room_stream_data(room_id, 1)
                recent_danmaku = self.live_cache.get_recent_danmaku(room_id, 10)
                
                room_display = self.room_display_data[room_id]
                
                # 更新当前状态
                room_display['current_data'] = current_data
                room_display['recent_danmaku'] = recent_danmaku
                room_display['last_update'] = datetime.now()
                
                # 如果有新的时序数据，添加到显示队列
                if recent_stream:
                    latest_data = recent_stream[-1]
                    if latest_data.get('type') == 'metrics':
                        room_display['timestamps'].append(latest_data.get('timestamp', 0))
                        room_display['popularity'].append(latest_data.get('popularity', 0))
                        room_display['danmaku_counts'].append(latest_data.get('danmaku_count', 0))
                        room_display['gift_counts'].append(latest_data.get('gift_count', 0))
                
            except Exception as e:
                self.logger.error(f"从Redis更新房间 {room_id} 数据失败: {e}")
    
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
        # 从Redis更新数据
        self.update_from_redis()
        
        for room_id in self.room_ids:
            room_display = self.room_display_data[room_id]
            lines = self.lines[room_id]
            current_data = room_display['current_data']
            
            # 获取房间信息
            room_info_key = f'room:{room_id}:info'
            room_info = self.redis_client.hgetall(room_info_key)
            uname = room_info.get('uname', f'房间{room_id}')
            
            # 更新累计数据图表（双Y轴）
            if len(room_display['timestamps']) > 0:
                # 使用序号作为X轴
                x_data = list(range(len(room_display['timestamps'])))
                danmaku_data = list(room_display['danmaku_counts'])
                gift_data = list(room_display['gift_counts'])
                
                # 更新线条数据
                lines['danmaku_line'].set_data(x_data, danmaku_data)
                lines['gift_line'].set_data(x_data, gift_data)
                
                # 更新X轴范围
                lines['ax1'].set_xlim(0, max(len(x_data), 10))
                
                # 分别设置左右Y轴范围
                if danmaku_data:
                    max_danmaku = max(danmaku_data)
                    lines['ax1'].set_ylim(0, max_danmaku * 1.1 if max_danmaku > 0 else 10)
                
                if gift_data:
                    max_gifts = max(gift_data)
                    lines['ax1_right'].set_ylim(0, max_gifts * 1.1 if max_gifts > 0 else 5)
            
            # 更新状态信息面板
            lines['ax2'].clear()
            lines['ax2'].axis('off')
            lines['ax2'].set_title(f'{uname}\n实时状态 (Redis)', fontsize=11, fontweight='bold')
            
            # 计算增长率
            danmaku_growth = ""
            gift_growth = ""
            if len(room_display['danmaku_counts']) >= 2:
                recent_danmaku = list(room_display['danmaku_counts'])[-2:]
                danmaku_growth = f" (+{recent_danmaku[-1] - recent_danmaku[-2]})"
            
            if len(room_display['gift_counts']) >= 2:
                recent_gifts = list(room_display['gift_counts'])[-2:]
                gift_growth = f" (+{recent_gifts[-1] - recent_gifts[-2]})"
            
            # 使用安全的文本（移除表情符号）
            status_text = f"""房间ID: {room_id}
数据源: Redis缓存

人气值: {self.format_number(current_data.get('popularity', 0))}
观看数: {self.format_number(current_data.get('watched', 0))}
点赞数: {self.format_number(current_data.get('likes', 0))}

累计弹幕: {current_data.get('total_danmaku', 0)}{danmaku_growth}
累计礼物: {current_data.get('total_gifts', 0)}{gift_growth}

Redis实时: 蓝色=弹幕 | 绿色=礼物
更新时间: {room_display['last_update'].strftime('%H:%M:%S')}"""
            
            lines['ax2'].text(0.05, 0.5, status_text, fontsize=10,
                            verticalalignment='center', transform=lines['ax2'].transAxes,
                            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgreen",
                                    alpha=0.8, edgecolor="darkgreen", linewidth=1))
            
            # 更新弹幕显示区域
            lines['ax3'].clear()
            lines['ax3'].axis('off')
            lines['ax3'].set_title(f'{uname}\n实时弹幕 (Redis)', fontsize=11, fontweight='bold')
            lines['ax3'].set_xlim(0, 1)
            lines['ax3'].set_ylim(0, 1)
            
            # 弹幕背景
            rect = Rectangle((0, 0), 1, 1, facecolor='#f0fff0', alpha=0.5,
                           edgecolor='lightgray', linewidth=1)
            lines['ax3'].add_patch(rect)
            
            # 显示弹幕
            recent_danmaku = room_display['recent_danmaku']
            if recent_danmaku:
                y_positions = np.linspace(0.05, 0.95, min(len(recent_danmaku), 10))[::-1]
                
                for i, danmaku in enumerate(recent_danmaku[:10]):
                    if i < len(y_positions):
                        try:
                            timestamp = danmaku.get('timestamp', '')[:19].replace('T', ' ')
                            username = danmaku.get('username', '')
                            message = danmaku.get('message', '')
                            
                            # 使用安全的文本格式
                            danmaku_text = f"[{timestamp.split(' ')[1][:8]}] {username}: {message}"
                            
                            alpha = 1.0 - (i * 0.08)
                            color = '#006400' if i < 3 else '#606060'
                            weight = 'bold' if i < 2 else 'normal'
                            
                            lines['ax3'].text(0.02, y_positions[i], danmaku_text,
                                            fontsize=8, transform=lines['ax3'].transAxes,
                                            verticalalignment='bottom', color=color,
                                            alpha=alpha, weight=weight, wrap=True)
                        except Exception as e:
                            self.logger.error(f"显示弹幕出错: {e}")
                            continue
            else:
                lines['ax3'].text(0.5, 0.5, '等待Redis弹幕数据...',
                                fontsize=14, transform=lines['ax3'].transAxes,
                                horizontalalignment='center', verticalalignment='center',
                                color='gray', style='italic')
        
        return [line for lines in self.lines.values()
                for line in [lines['danmaku_line'], lines['gift_line']]]
    
    def start(self):
        """启动可视化"""
        self.logger.info("启动Redis驱动的可视化界面")
        self.ani = animation.FuncAnimation(self.fig, self.animate, interval=1000,
                                         blit=False, cache_frame_data=False)
        plt.show()

# 全局可视化器
_redis_visualizer = None

def get_redis_visualizer():
    return _redis_visualizer

def init_redis_visualizer(room_ids):
    global _redis_visualizer
    _redis_visualizer = RedisLiveDataVisualizer(room_ids)
    return _redis_visualizer