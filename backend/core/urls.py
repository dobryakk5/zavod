from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('admin/post/<int:post_id>/generate-image/', views.generate_post_image, name='generate_post_image'),
    path('admin/post/<int:post_id>/generate-video/', views.generate_post_video, name='generate_post_video'),
    path('admin/post/<int:post_id>/quick-publish/', views.quick_publish_post, name='quick_publish_post'),
    path('admin/schedule/<int:schedule_id>/publish-now/', views.publish_schedule_now, name='publish_schedule_now'),
]
