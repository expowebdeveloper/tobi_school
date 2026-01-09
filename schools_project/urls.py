"""
URL configuration for schools_project project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('schools.urls')),
    path('', include('schools.urls')),  # Frontend views
]
