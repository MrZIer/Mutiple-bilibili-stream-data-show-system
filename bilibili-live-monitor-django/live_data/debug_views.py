from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
import logging
import traceback

logger = logging.getLogger(__name__)

def debug_dashboard(request):
    """调试版本的dashboard"""
    logger.info("调试Dashboard开始")
    
    context = {
        'now': timezone.now(),
        'system_stats': None,
        'active_rooms': [],
        'error': None,
        'error_detail': None,
        'debug_info': {}
    }
    
    try:
        # 尝试初始化服务
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        context['debug_info']['service_init'] = '成功'
        context['debug_info']['connection_status'] = service.connection_status
        
        # 尝试获取系统统计
        try:
            system_stats = service.get_system_stats()
            context['system_stats'] = system_stats
            context['debug_info']['stats_success'] = '成功'
        except Exception as e:
            context['error'] = f"获取系统统计失败: {str(e)}"
            context['debug_info']['stats_error'] = str(e)
        
        # 尝试获取房间列表
        try:
            active_rooms = service.get_available_rooms()
            context['active_rooms'] = active_rooms[:5]  # 只显示前5个
            context['debug_info']['rooms_count'] = len(active_rooms)
        except Exception as e:
            context['debug_info']['rooms_error'] = str(e)
    
    except Exception as e:
        context['error'] = f"服务初始化失败: {str(e)}"
        context['error_detail'] = traceback.format_exc()
        context['debug_info']['service_error'] = str(e)
    
    logger.info(f"调试Dashboard上下文: {context['debug_info']}")
    
    return render(request, 'live_data/dashboard_debug.html', context)

def simple_test(request):
    """最简单的测试视图"""
    return HttpResponse("""
    <html>
    <head><title>简单测试</title></head>
    <body>
        <h1>✅ Django正常工作</h1>
        <p>时间: {}</p>
        <p>方法: {}</p>
        <p>路径: {}</p>
        <a href="/live/">返回Dashboard</a>
    </body>
    </html>
    """.format(timezone.now(), request.method, request.path))