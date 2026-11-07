from django.contrib import admin
from django.urls import path
from clinic import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.app_shell, name="app"),
    path("api/session/", views.session_info, name="session"),
    path("api/counters/", views.counters_api, name="counters"),
    path("api/login/", views.login_view, name="login"),
    path("api/logout/", views.logout_view, name="logout"),
    path("api/visits/", views.visits_api, name="visits"),
    path("api/reports/", views.reports_api, name="reports"),
    path("api/archive/", views.archive_api, name="archive"),
    path("api/messages/", views.messages_api, name="messages"),
    path("api/messages/<uuid:message_id>/send/", views.send_message_api, name="send-message"),
]
