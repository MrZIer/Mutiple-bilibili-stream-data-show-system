from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.core.cache import cache
import json
import logging
import traceback

logger = logging.getLogger(__name__)

@ensure_csrf_cookie
@never_cache
def dashboard(request):
    """主仪表板页面"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 获取系统统计
        system_stats = service.get_system_stats()
        
        # 获取活跃房间
        active_rooms = service.get_all_rooms_with_uploader_info()[:20]  # 限制显示20个
        
        context = {
            'system_stats': system_stats,
            'active_rooms': active_rooms,
            'now': timezone.now(),
            'page_title': 'Bilibili 直播数据监控'
        }
        
        return render(request, 'live_data/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Dashboard页面加载失败: {e}")
        logger.error(traceback.format_exc())
        
        context = {
            'error': f'页面加载失败: {str(e)}',
            'system_stats': None,
            'active_rooms': [],
            'now': timezone.now(),
            'page_title': 'Bilibili 直播数据监控 - 错误'
        }
        
        return render(request, 'live_data/dashboard.html', context)

@ensure_csrf_cookie
@never_cache
def room_detail(request, room_id):
    """房间详情页面"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 获取房间信息
        room_info = service.get_room_detailed_info(room_id)
        
        if not room_info:
            context = {
                'error': f'房间 {room_id} 不存在或暂无数据',
                'room_id': room_id,
                'now': timezone.now()
            }
            return render(request, 'live_data/room_detail.html', context)
        
        # 获取最近弹幕和礼物
        recent_danmaku = service.get_recent_danmaku(room_id, 50)
        recent_gifts = service.get_recent_gifts(room_id, 20)
        
        context = {
            'room_info': room_info,
            'recent_danmaku': recent_danmaku,
            'recent_gifts': recent_gifts,
            'room_id': room_id,
            'now': timezone.now()
        }
        
        return render(request, 'live_data/room_detail.html', context)
        
    except Exception as e:
        logger.error(f"房间 {room_id} 详情页面加载失败: {e}")
        logger.error(traceback.format_exc())
        
        context = {
            'error': f'房间详情加载失败: {str(e)}',
            'room_id': room_id,
            'now': timezone.now()
        }
        
        return render(request, 'live_data/room_detail.html', context)

@ensure_csrf_cookie
@never_cache
def danmaku_browser(request):
    """弹幕浏览器页面"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 获取可用房间列表
        available_rooms = service.get_all_rooms_with_uploader_info()
        
        # 只保留有弹幕活动的房间
        active_danmaku_rooms = []
        for room in available_rooms:
            if room.get('danmaku_count', 0) > 0 or room.get('live_status') == 1:
                active_danmaku_rooms.append(room)
        
        # 按弹幕活跃度排序
        active_danmaku_rooms.sort(key=lambda x: x.get('danmaku_count', 0), reverse=True)
        
        # 获取系统统计
        system_stats = service.get_system_stats()
        
        context = {
            'available_rooms': active_danmaku_rooms[:50],  # 限制显示50个最活跃的房间
            'system_stats': system_stats,
            'total_rooms': len(available_rooms),
            'active_rooms_count': len(active_danmaku_rooms),
            'now': timezone.now(),
            'page_title': '弹幕实时监控'
        }
        
        return render(request, 'live_data/danmaku_browser.html', context)
        
    except Exception as e:
        logger.error(f"弹幕浏览器页面加载失败: {e}")
        logger.error(traceback.format_exc())
        
        context = {
            'error': f'弹幕浏览器加载失败: {str(e)}',
            'available_rooms': [],
            'system_stats': None,
            'total_rooms': 0,
            'active_rooms_count': 0,
            'now': timezone.now(),
            'page_title': '弹幕实时监控 - 错误'
        }
        
        return render(request, 'live_data/danmaku_browser.html', context)

def dashboard_debug(request):
    """调试页面"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 获取系统统计
        system_stats = service.get_system_stats()
        
        # 获取活跃房间
        active_rooms = service.get_all_rooms_with_uploader_info()[:10]  # 限制显示10个
        
        # 获取调试信息
        debug_info = {
            'redis_status': service.get_connection_status(),
            'rooms_count': len(active_rooms),
            'timestamp': timezone.now().isoformat()
        }
        
        context = {
            'system_stats': system_stats,
            'active_rooms': active_rooms,
            'debug_info': debug_info,
            'now': timezone.now(),
            'page_title': '系统调试'
        }
        
        return render(request, 'live_data/dashboard_debug.html', context)
        
    except Exception as e:
        logger.error(f"调试页面加载失败: {e}")
        logger.error(traceback.format_exc())
        
        context = {
            'error': f'调试页面加载失败: {str(e)}',
            'system_stats': None,
            'active_rooms': [],
            'debug_info': None,
            'now': timezone.now(),
            'page_title': '系统调试 - 错误'
        }
        
        return render(request, 'live_data/dashboard_debug.html', context)

# ===== API接口 =====

@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def api_redis_status(request):
    """Redis连接状态检查API"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 强制重新初始化Redis连接
        service._init_redis_connection()
        
        # 检查连接状态
        connection_status = service.get_connection_status()
        logger.info(f"Redis状态检查API - 状态: {connection_status}")
        
        if connection_status.get('status') == 'connected':
            return JsonResponse({
                'success': True,
                'data': {
                    'status': 'connected',
                    'message': connection_status.get('message', '连接正常'),
                    'timestamp': timezone.now().isoformat(),
                    'redis_info': connection_status.get('info', {})
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': connection_status.get('message', 'Redis连接失败'),
                'data': {
                    'status': 'error',
                    'timestamp': timezone.now().isoformat()
                }
            }, status=503)
            
    except Exception as e:
        logger.error(f"Redis状态检查异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'状态检查异常: {str(e)}',
            'data': {
                'status': 'error',
                'timestamp': timezone.now().isoformat()
            }
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def api_system_stats(request):
    """系统统计数据API"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 检查Redis连接
        connection_status = service.get_connection_status()
        logger.info(f"系统统计API - Redis状态: {connection_status}")
        
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}',
                'data': {
                    'redis_status': 'error',
                    'redis_message': connection_status.get('message', 'Redis连接失败')
                }
            }, status=503)
        
        # 获取系统统计
        try:
            stats = service.get_system_stats()
            logger.info(f"系统统计API - 获取统计数据成功")
            
            # 缓存统计数据30秒
            cache.set('system_stats', stats, 30)
            
            return JsonResponse({
                'success': True,
                'data': {
                    'stats': stats,
                    'timestamp': timezone.now().isoformat(),
                    'cache_status': 'fresh'
                }
            })
            
        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            logger.error(traceback.format_exc())
            
            # 尝试从缓存获取
            cached_stats = cache.get('system_stats')
            if cached_stats:
                return JsonResponse({
                    'success': True,
                    'data': {
                        'stats': cached_stats,
                        'timestamp': timezone.now().isoformat(),
                        'cache_status': 'cached',
                        'warning': '使用缓存数据'
                    }
                })
            
            return JsonResponse({
                'success': False,
                'error': f'获取统计数据失败: {str(e)}',
                'data': {
                    'redis_status': 'connected',
                    'redis_message': '连接正常但数据获取失败'
                }
            }, status=500)
        
    except Exception as e:
        logger.error(f"系统统计API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'API异常: {str(e)}'
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def api_rooms_list(request):
    """获取房间列表API"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 强制重新初始化Redis连接
        service._init_redis_connection()
        
        # 检查Redis连接状态
        connection_status = service.get_connection_status()
        logger.info(f"房间列表API - Redis连接状态: {connection_status}")
        
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}',
                'redis_status': connection_status
            }, status=503)
        
        # 获取请求参数
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        status_filter = request.GET.get('status', 'all')  # all, live, offline
        sort_by = request.GET.get('sort', 'popularity')  # popularity, danmaku, gifts, updated
        
        # 获取所有房间及UP主信息
        try:
            all_rooms = service.get_all_rooms_with_uploader_info()
            logger.info(f"房间列表API - 获取到 {len(all_rooms)} 个房间")
            
            # 过滤房间
            filtered_rooms = all_rooms
            if status_filter == 'live':
                filtered_rooms = [r for r in all_rooms if r.get('live_status') == 1]
            elif status_filter == 'offline':
                filtered_rooms = [r for r in all_rooms if r.get('live_status') != 1]
            
            # 排序
            if sort_by == 'popularity':
                filtered_rooms.sort(key=lambda x: x.get('online', 0), reverse=True)
            elif sort_by == 'danmaku':
                filtered_rooms.sort(key=lambda x: x.get('danmaku_count', 0), reverse=True)
            elif sort_by == 'gifts':
                filtered_rooms.sort(key=lambda x: x.get('gift_count', 0), reverse=True)
            elif sort_by == 'updated':
                filtered_rooms.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            
            # 分页
            total_count = len(filtered_rooms)
            paginated_rooms = filtered_rooms[offset:offset + limit]
            
            # 计算系统统计
            system_stats = {
                'total_rooms': len(all_rooms),
                'active_rooms': len([r for r in all_rooms if r.get('live_status') == 1]),
                'total_danmaku': sum(r.get('danmaku_count', 0) for r in all_rooms),
                'total_gifts': sum(r.get('gift_count', 0) for r in all_rooms),
                'total_online': sum(r.get('online', 0) for r in all_rooms),
                'verified_users': len([r for r in all_rooms if r.get('is_verified')]),
                'areas': len(set(r.get('area_name', '') for r in all_rooms if r.get('area_name'))),
                'last_update': timezone.now().isoformat()
            }
            
            return JsonResponse({
                'success': True,
                'data': {
                    'rooms': paginated_rooms,
                    'stats': system_stats,
                    'pagination': {
                        'total_count': total_count,
                        'offset': offset,
                        'limit': limit,
                        'has_more': offset + limit < total_count
                    },
                    'filters': {
                        'status': status_filter,
                        'sort_by': sort_by
                    },
                    'redis_status': connection_status,
                    'timestamp': timezone.now().isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"获取房间列表失败: {e}")
            logger.error(traceback.format_exc())
            return JsonResponse({
                'success': False,
                'error': f'获取房间列表失败: {str(e)}',
                'redis_status': connection_status
            }, status=500)
        
    except Exception as e:
        logger.error(f"房间列表API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'API异常: {str(e)}'
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def api_room_stats(request, room_id):
    """房间统计API"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 检查Redis连接
        connection_status = service.get_connection_status()
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}'
            }, status=503)
        
        # 获取房间详细信息
        room_info = service.get_room_detailed_info(room_id)
        if not room_info:
            return JsonResponse({
                'success': False,
                'error': f'房间 {room_id} 信息不存在'
            }, status=404)
        
        # 获取房间统计
        room_stats = service.get_room_danmaku_stats(room_id)
        
        # 合并数据
        combined_data = {
            'room_info': room_info,
            'stats': room_stats,
            'timestamp': timezone.now().isoformat()
        }
        
        return JsonResponse({
            'success': True,
            'data': combined_data
        })
        
    except Exception as e:
        logger.error(f"房间 {room_id} 统计API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'获取房间统计失败: {str(e)}'
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def api_room_danmaku(request, room_id):
    """房间弹幕API"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 检查Redis连接
        connection_status = service.get_connection_status()
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}'
            }, status=503)
        
        # 获取请求参数
        limit = min(int(request.GET.get('limit', 50)), 200)  # 最多200条
        since_timestamp = request.GET.get('since')  # 获取指定时间之后的弹幕
        
        # 获取弹幕数据
        danmaku_list = service.get_recent_danmaku(room_id, limit)
        
        # 如果指定了时间戳，过滤数据
        if since_timestamp:
            try:
                since_time = timezone.datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
                danmaku_list = [
                    d for d in danmaku_list 
                    if d.get('timestamp') and timezone.datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')) > since_time
                ]
            except ValueError:
                pass  # 忽略无效的时间戳
        
        return JsonResponse({
            'success': True,
            'data': {
                'danmaku': danmaku_list,
                'count': len(danmaku_list),
                'room_id': room_id,
                'timestamp': timezone.now().isoformat(),
                'has_more': len(danmaku_list) >= limit
            }
        })
        
    except Exception as e:
        logger.error(f"房间 {room_id} 弹幕API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'获取弹幕数据失败: {str(e)}'
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def api_room_gifts(request, room_id):
    """房间礼物API"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 检查Redis连接
        connection_status = service.get_connection_status()
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}'
            }, status=503)
        
        # 获取请求参数
        limit = min(int(request.GET.get('limit', 30)), 100)  # 最多100条
        since_timestamp = request.GET.get('since')  # 获取指定时间之后的礼物
        
        # 获取礼物数据
        gifts_list = service.get_recent_gifts(room_id, limit)
        
        # 如果指定了时间戳，过滤数据
        if since_timestamp:
            try:
                since_time = timezone.datetime.fromisoformat(since_timestamp.replace('Z', '+00:00'))
                gifts_list = [
                    g for g in gifts_list 
                    if g.get('timestamp') and timezone.datetime.fromisoformat(g['timestamp'].replace('Z', '+00:00')) > since_time
                ]
            except ValueError:
                pass  # 忽略无效的时间戳
        
        return JsonResponse({
            'success': True,
            'data': {
                'gifts': gifts_list,
                'count': len(gifts_list),
                'room_id': room_id,
                'timestamp': timezone.now().isoformat(),
                'has_more': len(gifts_list) >= limit
            }
        })
        
    except Exception as e:
        logger.error(f"房间 {room_id} 礼物API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'获取礼物数据失败: {str(e)}'
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["POST"])
def api_batch_room_stats(request):
    """批量获取房间统计API"""
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            return JsonResponse({
                'success': False,
                'error': '请使用JSON格式提交数据'
            }, status=400)
        
        room_ids = data.get('room_ids', [])
        if not room_ids or len(room_ids) > 50:  # 限制最多50个房间
            return JsonResponse({
                'success': False,
                'error': '房间ID列表无效或超过限制(最多50个)'
            }, status=400)
        
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 检查Redis连接
        connection_status = service.get_connection_status()
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}'
            }, status=503)
        
        # 批量获取房间数据
        rooms_data = {}
        for room_id in room_ids:
            try:
                room_id = int(room_id)
                room_info = service.get_room_detailed_info(room_id)
                if room_info:
                    rooms_data[str(room_id)] = room_info
            except (ValueError, TypeError):
                continue
        
        return JsonResponse({
            'success': True,
            'data': {
                'rooms': rooms_data,
                'count': len(rooms_data),
                'timestamp': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"批量房间统计API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'批量获取失败: {str(e)}'
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["POST"])
def api_maintenance_cleanup(request):
    """数据清理维护API"""
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = {}
        
        cleanup_type = data.get('type', 'old_data')  # old_data, cache, all
        hours = int(data.get('hours', 24))  # 清理多少小时前的数据
        
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 检查Redis连接
        connection_status = service.get_connection_status()
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}'
            }, status=503)
        
        results = {}
        
        if cleanup_type in ['old_data', 'all']:
            # 清理旧数据（由Redis过期机制自动处理）
            results['old_data'] = '由Redis自动过期机制处理'
        
        if cleanup_type in ['cache', 'all']:
            # 清理Django缓存
            cache.clear()
            results['cache'] = 'Django缓存已清理'
        
        return JsonResponse({
            'success': True,
            'data': {
                'results': results,
                'cleanup_type': cleanup_type,
                'hours': hours,
                'timestamp': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"数据清理API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'数据清理失败: {str(e)}'
        }, status=500)

@never_cache
@csrf_exempt
@require_http_methods(["GET"])
def api_danmaku_browser_data(request):
    """弹幕浏览器数据API"""
    try:
        from .danmaku_services import DanmakuService
        service = DanmakuService()
        
        # 检查Redis连接
        connection_status = service.get_connection_status()
        if connection_status.get('status') != 'connected':
            return JsonResponse({
                'success': False,
                'error': f'Redis连接失败: {connection_status.get("message", "未知错误")}'
            }, status=503)
        
        # 获取请求参数
        limit = min(int(request.GET.get('limit', 20)), 50)
        
        # 获取活跃房间
        all_rooms = service.get_all_rooms_with_uploader_info()
        active_rooms = [r for r in all_rooms if r.get('danmaku_count', 0) > 0 or r.get('live_status') == 1]
        active_rooms.sort(key=lambda x: x.get('danmaku_count', 0), reverse=True)
        
        # 获取每个房间的最新弹幕
        rooms_with_danmaku = []
        for room in active_rooms[:limit]:
            recent_danmaku = service.get_recent_danmaku(room['room_id'], 5)
            recent_gifts = service.get_recent_gifts(room['room_id'], 3)
            
            room_data = {
                'room_info': room,
                'recent_danmaku': recent_danmaku,
                'recent_gifts': recent_gifts,
                'danmaku_count': len(recent_danmaku),
                'gifts_count': len(recent_gifts)
            }
            rooms_with_danmaku.append(room_data)
        
        return JsonResponse({
            'success': True,
            'data': {
                'rooms': rooms_with_danmaku,
                'total_active_rooms': len(active_rooms),
                'timestamp': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"弹幕浏览器数据API异常: {e}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'获取弹幕浏览器数据失败: {str(e)}'
        }, status=500)