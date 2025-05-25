from typing import Any

import django_filters as filters
from rest_framework.filters import SearchFilter

from .models import Ingredient, Recipe, Tag


class RecipeFilter(filters.FilterSet):
    """
    This filter allows you to filter recipes
    by tags, favourited sign and buying list sign
    """
    tags = filters.ModelMultipleChoiceFilter(field_name="tags__slug", to_field_name="slug",
        queryset=Tag.objects.all(), )
    is_favorited = filters.CharFilter(method="get_is_favorited")
    is_in_shopping_cart = filters.CharFilter(method="filter_shopping_cart")

    class Meta:
        model = Recipe
        fields = ["author", "tags", "is_favorited", "is_in_shopping_cart"]

    def get_is_favorited(self, queryset: Any, obj: Any, value: Any) -> Any:
        user = self.request.user
        if obj:
            return queryset.filter(favorite__user=user)
        return queryset

    def filter_shopping_cart(self, queryset: Any, is_in_shopping_cart: Any, slug: Any) -> Any:
        user = self.request.user
        if not user.is_authenticated:
            return queryset
        is_in_shopping_cart = self.request.query_params.get("is_in_shopping_cart")
        if is_in_shopping_cart:
            return queryset.filter(is_in_shopping_cart__user=self.request.user).distinct()
        return queryset


class IngredientFilter(filters.FilterSet):
    """
    This filter allows you to filter ingredients
    by their names
    """
    name = filters.CharFilter(field_name="name", lookup_expr="startswith")

    class Meta:
        model = Ingredient
        fields = ("name",)


class IngredientSearchFilter(SearchFilter):
    """
    This filter allows you to search ingredients
    by typing several first letters
    """
    search_param = "name"
