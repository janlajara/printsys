"""
URL configuration for printsys project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.shortcuts import redirect

from core.views import dashboard_set_date_range

urlpatterns = [
    path('admin/dashboard/set-date-range/', dashboard_set_date_range, name='dashboard_set_date_range'),
    path('admin/inventory/', lambda request: redirect('/admin', permanent=True)),
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('/admin', permanent=True)),

    # Estimation
    path('api/estimation/', include('estimation.urls')),

    # Microsoft SSO
    path(
        "microsoft_sso/", include("django_microsoft_sso.urls", namespace="django_microsoft_sso")
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)