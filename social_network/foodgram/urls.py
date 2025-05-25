from django.conf.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FavoriteView,
    IngredientsView,
    RecipeView,
    ShoppingCartView,
    TagView,
    download_shopping_cart,
    recipe_create,
    recipe_edit,
    recipe_delete,
    favorites,
    shopping_list,
    profile,
    shopping_list_remove,
    favorite_remove,
    favorite_add,
    add_comment,
    delete_comment,
    CommentView,
    ProfileView,
    my_subscriptions,
    generate_recipe_by_text,
    generate_recipe_image,
    ask_ai
)

# This block defines the URLs that will provide access to each view.

router = DefaultRouter()
router.register(r"tags", TagView, basename="tags")
router.register(r"ingredients", IngredientsView, basename="ingredients")
router.register(r"recipes", RecipeView, basename="recipes")

urlpatterns = [
    path(
        "recipes/download_shopping_cart/",
        download_shopping_cart,
        name="download"
    ),
    path(
        "recipes/generate-by-text/",
        generate_recipe_by_text,
        name="generate_recipe"
    ),
    path(
        "recipes/generate-image/",
        generate_recipe_image,
        name="generate_image"
    ),
    path(
        "recipes/<int:recipe_id>/favorite/",
        FavoriteView.as_view(),
        name="favorite"
    ),
    path(
        "recipes/<int:recipe_id>/shopping_cart/",
        ShoppingCartView.as_view(),
        name="shopping_cart"
    ),
    path(
        "recipes/<int:recipe_id>/comments/",
        CommentView.as_view(),
        name="recipe_comments"
    ),
    path(
        "recipes/<int:recipe_id>/comments/<int:comment_id>/",
        CommentView.as_view(),
        name="recipe_comment_detail"
    ),
    path(
        "profile/<str:username>/",
        ProfileView.as_view(),
        name="profile_api"
    ),
    path("", include(router.urls)),
    path('recipes/create/', recipe_create, name='recipe_create'),
    path('recipes/<int:pk>/edit/', recipe_edit, name='recipe_edit'),
    path('recipes/<int:pk>/delete/', recipe_delete, name='recipe_delete'),
    path('favorites/', favorites, name='favorites'),
    path('shopping-list/', shopping_list, name='shopping_list'),
    path(
        'shopping-list/<int:recipe_id>/remove/',
        shopping_list_remove,
        name='shopping_list_remove'
    ),
    path('profile/', profile, name='profile'),
    path(
        'recipes/<int:recipe_id>/favorite_remove/',
        favorite_remove,
        name='favorite_remove'
    ),
    path(
        'recipes/<int:recipe_id>/favorite_add/',
        favorite_add,
        name='favorite_add'
    ),
    path(
        'recipes/<int:recipe_id>/comments/add/',
        add_comment,
        name='add_comment'
    ),
    path(
        'recipes/<int:recipe_id>/comments/<int:comment_id>/delete/',
        delete_comment,
        name='delete_comment'
    ),
    path('my-subscriptions/', my_subscriptions, name='my_subscriptions'),
    path("ask/", ask_ai, name="ask_ai")
]
