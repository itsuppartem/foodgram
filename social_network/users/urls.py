from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

# This block defines the URLs that will provide access to each view.

router = DefaultRouter()
router.register('users', views.CustomUserViewSet, basename='users')

urlpatterns = [
    path('', include(router.urls)),
    path('users/me/', views.me, name='me'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('auth/token/login/', views.token_login, name='token_login'),
    path('auth/token/logout/', views.logout_view, name='token_logout'),
    path('unsubscribe/<str:username>/', views.unsubscribe_view, name='unsubscribe'),
    path('subscribe/<str:username>/', views.subscribe_view, name='subscribe'),
]
