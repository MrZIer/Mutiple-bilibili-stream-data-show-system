from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseRedirect

def root_redirect(request):
    return HttpResponseRedirect('/live/')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_redirect),  # 根路径重定向到 /live/
    path('live/', include('live_data.urls')),  # 包含live_data应用的URL
]

# 开发环境下提供静态文件服务
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)