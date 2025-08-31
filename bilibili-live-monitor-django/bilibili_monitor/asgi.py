import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import live_data.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bilibili_monitor.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            live_data.routing.websocket_urlpatterns
        )
    ),
})