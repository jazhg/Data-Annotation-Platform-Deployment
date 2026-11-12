from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from annotator import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.entry_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('evaluation/<int:index>/', views.evaluation_view, name='evaluation'),
    path('study-image/<path:image_path>/', views.study_image_view, name='study_image'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
