from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import LiveRoom, DanmakuData, GiftData, MonitoringTask, DataMigrationLog
import json

@admin.register(LiveRoom)
class LiveRoomAdmin(admin.ModelAdmin):
    list_display = ['room_id', 'title', 'uname', 'online', 'status', 'updated_at']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['room_id', 'title', 'uname']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

@admin.register(DanmakuData)
class DanmakuDataAdmin(admin.ModelAdmin):
    list_display = ['room', 'username', 'message_preview', 'timestamp', 'user_level', 'medal_info']
    list_filter = ['room', 'timestamp', 'user_level', 'is_admin', 'is_vip']
    search_fields = ['username', 'message', 'room__title']
    date_hierarchy = 'timestamp'
    readonly_fields = ['created_at']
    list_per_page = 50
    
    def message_preview(self, obj):
        """显示弹幕内容预览"""
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = '弹幕内容'
    
    def medal_info(self, obj):
        """显示粉丝牌信息"""
        if obj.medal_name:
            return f"{obj.medal_name} Lv.{obj.medal_level}"
        return "-"
    medal_info.short_description = '粉丝牌'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('room')

@admin.register(GiftData)
class GiftDataAdmin(admin.ModelAdmin):
    list_display = ['room', 'username', 'gift_name', 'num', 'total_price', 'timestamp']
    list_filter = ['room', 'gift_name', 'timestamp']
    search_fields = ['username', 'gift_name', 'room__title']
    date_hierarchy = 'timestamp'
    readonly_fields = ['created_at']
    list_per_page = 50
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('room')

@admin.register(MonitoringTask)
class MonitoringTaskAdmin(admin.ModelAdmin):
    list_display = [
        'task_name', 
        'status', 
        'room_count', 
        'collected_danmaku', 
        'collected_gifts', 
        'runtime_display',
        'error_count'
    ]
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['task_name']
    readonly_fields = ['created_at', 'updated_at', 'runtime_display']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('task_name', 'status', 'room_ids')
        }),
        ('运行状态', {
            'fields': ('start_time', 'end_time', 'runtime_display')
        }),
        ('统计信息', {
            'fields': ('collected_danmaku', 'collected_gifts', 'error_count', 'last_error')
        }),
        ('时间戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def room_count(self, obj):
        """显示监控房间数量"""
        try:
            room_list = json.loads(obj.room_ids)
            return len(room_list)
        except:
            return 0
    room_count.short_description = '房间数量'
    
    def runtime_display(self, obj):
        """显示运行时间"""
        if obj.start_time and obj.end_time:
            runtime = obj.end_time - obj.start_time
            return str(runtime).split('.')[0]
        elif obj.start_time:
            runtime = timezone.now() - obj.start_time
            return f"{str(runtime).split('.')[0]} (运行中)"
        return "-"
    runtime_display.short_description = '运行时间'
    
    def get_readonly_fields(self, request, obj=None):
        """根据对象状态设置只读字段"""
        readonly = list(self.readonly_fields)
        if obj and obj.status == 'running':
            readonly.extend(['room_ids'])
        return readonly

@admin.register(DataMigrationLog)
class DataMigrationLogAdmin(admin.ModelAdmin):
    list_display = [
        'migration_type', 
        'status', 
        'start_time', 
        'duration',
        'success_rate',
        'total_records'
    ]
    list_filter = ['migration_type', 'status', 'start_time']
    search_fields = ['migration_type']
    readonly_fields = ['duration', 'success_rate', 'created_at']
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('基本信息', {
            'fields': ('migration_type', 'status')
        }),
        ('时间信息', {
            'fields': ('start_time', 'end_time', 'duration')
        }),
        ('统计信息', {
            'fields': ('total_records', 'success_records', 'failed_records', 'success_rate')
        }),
        ('错误信息', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        })
    )
    
    def duration(self, obj):
        """显示持续时间"""
        if obj.start_time and obj.end_time:
            duration = obj.end_time - obj.start_time
            return str(duration).split('.')[0]
        elif obj.start_time:
            duration = timezone.now() - obj.start_time
            return f"{str(duration).split('.')[0]} (进行中)"
        return "-"
    duration.short_description = '持续时间'
    
    def success_rate(self, obj):
        """显示成功率"""
        if obj.total_records > 0:
            rate = (obj.success_records / obj.total_records) * 100
            color = 'green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
            return format_html(
                '<span style="color: {}">{:.1f}%</span>',
                color, rate
            )
        return "-"
    success_rate.short_description = '成功率'

# 自定义管理后台站点配置
admin.site.site_header = 'B站直播监控管理后台'
admin.site.site_title = 'B站直播监控'
admin.site.index_title = '数据管理'

# 添加自定义操作
def export_danmaku_csv(modeladmin, request, queryset):
    """导出弹幕数据为CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="danmaku_data.csv"'
    response.write('\ufeff')  # BOM for Excel
    
    writer = csv.writer(response)
    writer.writerow(['房间ID', '用户名', '弹幕内容', '发送时间', '用户等级', '粉丝牌'])
    
    for obj in queryset:
        writer.writerow([
            obj.room.room_id,
            obj.username,
            obj.message,
            obj.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            obj.user_level,
            f"{obj.medal_name} Lv.{obj.medal_level}" if obj.medal_name else ""
        ])
    
    return response
export_danmaku_csv.short_description = "导出选中的弹幕数据为CSV"

def export_gift_csv(modeladmin, request, queryset):
    """导出礼物数据为CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="gift_data.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response)
    writer.writerow(['房间ID', '用户名', '礼物名称', '数量', '单价', '总价', '发送时间'])
    
    for obj in queryset:
        writer.writerow([
            obj.room.room_id,
            obj.username,
            obj.gift_name,
            obj.num,
            obj.price,
            obj.total_price,
            obj.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response
export_gift_csv.short_description = "导出选中的礼物数据为CSV"

# 将自定义操作添加到相应的Admin类
DanmakuDataAdmin.actions = [export_danmaku_csv]
GiftDataAdmin.actions = [export_gift_csv]