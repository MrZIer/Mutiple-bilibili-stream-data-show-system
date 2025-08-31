from django.urls import path
from . import views

app_name = 'live_data'

urlpatterns = [
    # ===== 页面路由 =====
    path('', views.dashboard, name='dashboard'),
    path('room/<int:room_id>/', views.room_detail, name='room_detail'),
    path('danmaku/', views.danmaku_browser, name='danmaku_browser'),
    path('debug/', views.dashboard_debug, name='dashboard_debug'),
    
    # ===== API 路由 =====
    # 系统状态和统计
    path('api/redis/status/', views.api_redis_status, name='api_redis_status'),
    path('api/system/stats/', views.api_system_stats, name='api_system_stats'),
    
    # 房间相关API
    path('api/rooms/', views.api_rooms_list, name='api_rooms_list'),
    path('api/room/<int:room_id>/stats/', views.api_room_stats, name='api_room_stats'),
    path('api/room/<int:room_id>/danmaku/', views.api_room_danmaku, name='api_room_danmaku'),
    path('api/room/<int:room_id>/gifts/', views.api_room_gifts, name='api_room_gifts'),
    
    # 弹幕浏览器API
    path('api/danmaku-browser/', views.api_danmaku_browser_data, name='api_danmaku_browser_data'),
    
    # 批量操作API
    path('api/batch/rooms/stats/', views.api_batch_room_stats, name='api_batch_room_stats'),
    
    # 数据维护API
    path('api/maintenance/cleanup/', views.api_maintenance_cleanup, name='api_maintenance_cleanup'),
]