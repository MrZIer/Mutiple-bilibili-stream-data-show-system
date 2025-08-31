from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import DanmakuData, GiftData, LiveRoom, DataMigrationLog
from .services import DataMigrationService
import json

@staff_member_required
def admin_dashboard(request):
    """管理后台仪表板"""
    # 统计数据
    stats = {
        'total_rooms': LiveRoom.objects.count(),
        'total_danmaku': DanmakuData.objects.count(),
        'total_gifts': GiftData.objects.count(),
        'active_rooms': LiveRoom.objects.filter(status=1).count(),
    }
    
    # 最近24小时数据
    last_24h = timezone.now() - timedelta(hours=24)
    recent_stats = {
        'recent_danmaku': DanmakuData.objects.filter(timestamp__gte=last_24h).count(),
        'recent_gifts': GiftData.objects.filter(timestamp__gte=last_24h).count(),
        'recent_gift_value': GiftData.objects.filter(
            timestamp__gte=last_24h
        ).aggregate(total=Sum('total_price'))['total'] or 0,
    }
    
    # 最近迁移记录
    recent_migrations = DataMigrationLog.objects.order_by('-start_time')[:5]
    
    context = {
        'stats': stats,
        'recent_stats': recent_stats,
        'recent_migrations': recent_migrations,
    }
    
    return render(request, 'admin/dashboard.html', context)

@staff_member_required
def trigger_migration(request):
    """触发数据迁移"""
    if request.method == 'POST':
        try:
            migration_service = DataMigrationService()
            
            # 获取参数
            cleanup_redis = request.POST.get('cleanup_redis') == 'true'
            max_age_hours = int(request.POST.get('max_age_hours', 24))
            migration_type = request.POST.get('type', 'all')
            
            # 执行迁移
            if migration_type == 'all':
                results = migration_service.migrate_all_data(cleanup_redis, max_age_hours)
            elif migration_type == 'danmaku':
                results = {'danmaku': migration_service.migrate_danmaku_data(cleanup_redis, max_age_hours)}
            elif migration_type == 'gifts':
                results = {'gifts': migration_service.migrate_gift_data(cleanup_redis, max_age_hours)}
            elif migration_type == 'rooms':
                results = {'rooms': migration_service.migrate_room_data(cleanup_redis, max_age_hours)}
            
            return JsonResponse({
                'success': True,
                'results': results,
                'message': '数据迁移任务已完成'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'message': '数据迁移失败'
            })
    
    return JsonResponse({'success': False, 'message': '不支持的请求方法'})