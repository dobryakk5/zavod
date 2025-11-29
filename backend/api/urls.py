from django.urls import path

from .views import (
    ClientSummaryView,
    LoginView,
    LogoutView,
    PostsListView,
    RefreshTokenView,
    ScheduleListView,
    TelegramAuthView,
)

app_name = 'api'

urlpatterns = [
    path('auth/telegram', TelegramAuthView.as_view(), name='telegram-auth'),
    path('auth/token/', LoginView.as_view(), name='token'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('client/summary/', ClientSummaryView.as_view(), name='client-summary'),
    path('posts/', PostsListView.as_view(), name='posts'),
    path('schedules/', ScheduleListView.as_view(), name='schedules'),
]
