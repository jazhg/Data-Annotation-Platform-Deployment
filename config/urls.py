from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from annotator import views
from annotator.forms import AnnotatorPasswordResetForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.entry_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        form_class=AnnotatorPasswordResetForm,
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.txt',
        subject_template_name='registration/password_reset_subject.txt',
    ), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('evaluation/<int:index>/', views.evaluation_view, name='evaluation'),
    path('study-image/<path:image_path>/', views.study_image_view, name='study_image'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
