from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from crm import mcp_oauth

urlpatterns = [
    path('admin/', admin.site.urls),
    # OAuth 2.1 endpoints required by Claude.ai for remote MCP connections
    path('.well-known/oauth-protected-resource', mcp_oauth.oauth_protected_resource),
    path('.well-known/oauth-authorization-server', mcp_oauth.oauth_authorization_server),
    path('oauth/register', mcp_oauth.oauth_register),
    path('oauth/authorize', mcp_oauth.oauth_authorize),
    path('oauth/token', mcp_oauth.oauth_token),
    path('', include('crm.urls')),
    path('analytics/', include('analytics.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)