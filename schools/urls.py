"""
URL configuration for schools app API endpoints.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('schools/<int:school_id>/prompt/',
         views.get_school_prompt, name='school_prompt'),
    path('schools/random/prompt/',
         views.get_random_school_prompt, name='random_school_prompt'),
    path('schools/data/',
         views.create_or_update_school_data, name='create_or_update_school_data'),
    path('schools/invalid-data/',
         views.get_schools_with_invalid_data, name='schools_invalid_data'),
    path('schools/',
         views.display_all_schools_data, name='display_all_schools_data'),
]
