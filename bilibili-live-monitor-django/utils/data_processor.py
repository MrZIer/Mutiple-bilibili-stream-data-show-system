import json
import os
from datetime import datetime
from django.conf import settings
from .redis_handler import RoomDataManager
from live_data.models import Room, DataExport

class JSONExporter:
    """JSON数据导出器"""
    
    def __init__(self):
        self.room_manager = RoomDataManager()
        self.export_path = settings.LIVE_MONITOR_CONFIG['JSON_EXPORT_PATH']
        
        # 确保导出目录存在
        os.makedirs(self.export_path, exist_ok=True)
    
    def export_room_data(self, room_id):
        """导出单个房间数据"""
        try:
            # 获取Redis中的数据
            dashboard_data = self.room_manager.get_room_dashboard_data(room_id)
            
            # 获取房间信息
            try:
                room = Room.objects.get(room_id=room_id)
                room_info = {
                    'room_id': room.room_id,
                    'uname': room.uname,
                    'title': room.title,
                    'area_name': room.area_name,
                    'parent_area_name': room.parent_area_name
                }
            except Room.DoesNotExist:
                room_info = {
                    'room_id': room_id,
                    'uname': f'主播{room_id}',
                    'title': f'直播间{room_id}',
                    'area_name': '未知',
                    'parent_area_name': '未知'
                }
            
            # 构建导出数据结构
            export_data = {
                'room_info': room_info,
                'export_time': datetime.now().isoformat(),
                'current_data': dashboard_data['current'],
                'stream_data': dashboard_data['stream'],
                'recent_danmaku': dashboard_data['danmaku'],
                'recent_gifts': dashboard_data['gifts'],
                'statistics': {
                    'total_danmaku': dashboard_data['current'].get('total_danmaku', 0),
                    'total_gifts': dashboard_data['current'].get('total_gifts', 0),
                    'current_popularity': dashboard_data['current'].get('popularity', 0),
                    'data_points': len(dashboard_data['stream'])
                }
            }
            
            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"room_{room_id}_{timestamp}.json"
            filepath = os.path.join(self.export_path, filename)
            
            # 写入JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            # 记录导出信息
            file_size = os.path.getsize(filepath)
            data_count = len(dashboard_data['stream'])
            
            # 保存导出记录
            room_obj, created = Room.objects.get_or_create(
                room_id=room_id,
                defaults={
                    'uname': room_info['uname'],
                    'title': room_info['title'],
                    'area_name': room_info['area_name'],
                    'parent_area_name': room_info['parent_area_name']
                }
            )
            
            DataExport.objects.create(
                room=room_obj,
                file_path=filepath,
                data_count=data_count,
                file_size=file_size,
                status='success'
            )
            
            return {
                'success': True,
                'filepath': filepath,
                'data_count': data_count,
                'file_size': file_size
            }
            
        except Exception as e:
            # 记录失败的导出
            try:
                room_obj, created = Room.objects.get_or_create(room_id=room_id)
                DataExport.objects.create(
                    room=room_obj,
                    file_path='',
                    status='failed'
                )
            except:
                pass
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_all_active_rooms(self):
        """导出所有活跃房间数据"""
        active_rooms = self.room_manager.cache.get_active_rooms()
        results = []
        
        for room_id in active_rooms:
            result = self.export_room_data(room_id)
            result['room_id'] = room_id
            results.append(result)
        
        return results