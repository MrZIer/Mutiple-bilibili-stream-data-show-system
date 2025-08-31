from django.contrib import admin
from .models import LiveRoom, DanmakuData, GiftData, MonitoringTask

@admin.register(LiveRoom)
class LiveRoomAdmin(admin.ModelAdmin):
    list_display = ['room_id', 'uname', 'title', 'live_status', 'popularity', 'is_monitoring', 'updated_at']
    list_filter = ['live_status', 'is_monitoring', 'area_name']
    search_fields = ['room_id', 'uname', 'title']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(DanmakuData)
class DanmakuDataAdmin(admin.ModelAdmin):
    list_display = ['room', 'username', 'message_preview', 'send_time', 'received_at']
    list_filter = ['room', 'send_time']
    search_fields = ['username', 'message']
    readonly_fields = ['received_at']
    
    def message_preview(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_preview.short_description = "弹幕内容"

@admin.register(GiftData)
class GiftDataAdmin(admin.ModelAdmin):
    list_display = ['room', 'username', 'gift_name', 'num', 'price', 'coin_type', 'send_time']
    list_filter = ['room', 'gift_name', 'coin_type', 'send_time']
    search_fields = ['username', 'gift_name']

@admin.register(MonitoringTask)
class MonitoringTaskAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'room', 'status', 'danmaku_count', 'gift_count', 'start_time', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['task_id', 'room__uname']
    readonly_fields = ['created_at']