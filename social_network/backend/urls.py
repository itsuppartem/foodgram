from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from foodgram import views as foodgram_views
from rest_framework import permissions
from users import views as user_views

schema_view = get_schema_view(
    openapi.Info(title="Foodgram API", default_version='v1', description="API для проекта Foodgram",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="itsuppartem@yandex.ru"), license=openapi.License(name="MIT License"), ),
    public=True, permission_classes=(permissions.AllowAny,), )

urlpatterns = [path('admin/', admin.site.urls), path('api/', include('foodgram.urls')),
    path('api/', include('users.urls')),

    # Swagger/Redoc URLs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Шаблонные URL
    path('', foodgram_views.index, name='index'), path('recipes/', foodgram_views.recipe_list, name='recipe_list'),
    path('recipes/create/', foodgram_views.recipe_create, name='recipe_create'),
    path('recipes/<int:pk>/', foodgram_views.recipe_detail, name='recipe_detail'),
    path('recipes/<int:pk>/edit/', foodgram_views.recipe_edit, name='recipe_edit'),
    path('recipes/<int:recipe_id>/favorite/', foodgram_views.favorite_add, name='favorite_add'),
    path('recipes/<int:recipe_id>/shopping-list/', foodgram_views.shopping_list_add, name='shopping_list_add'),
    path('favorites/', foodgram_views.favorites, name='favorites'),
    path('shopping-list/', foodgram_views.shopping_list, name='shopping_list'),
    path('profile/<str:username>/', foodgram_views.profile, name='profile'),
    path('profile/edit/', user_views.profile_edit, name='profile_edit'),

    # URLs для авторизации
    path('login/', user_views.login_view, name='login'), path('signup/', user_views.signup_view, name='signup'),
    path('logout/', user_views.logout_view, name='logout'), ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
