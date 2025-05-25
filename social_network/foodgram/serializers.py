from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator, ValidationError
from django.core.cache import cache
from django.conf import settings
from typing import Dict, Any, List

from users.serializers import CustomUserManipulateSerializer
from . import models

# this block converts information stored in a database,
# defined using Django models, into a format that
# is easily and efficiently passed through an API.


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Tag
        fields = ["id", "name", "color", "slug"]


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=models.Ingredient.objects.all()
    )
    name = serializers.SlugRelatedField(
        source="ingredient",
        read_only=True,
        slug_field="name"
    )
    measurement_unit = serializers.SlugRelatedField(
        source="ingredient",
        read_only=True,
        slug_field="measurement_unit"
    )
    amount = serializers.FloatField(min_value=0)

    class Meta:
        model = models.IngredientInRecipe
        fields = ("id", "name", "measurement_unit", "amount")


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Ingredient
        fields = ["id", "name", "measurement_unit"]


class ShowRecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(read_only=True, many=True)
    image = Base64ImageField()
    author = CustomUserManipulateSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        source="ingredients_amount",
        many=True
    )
    is_favorited = serializers.SerializerMethodField("get_is_favorited")
    is_in_shopping_cart = serializers.SerializerMethodField(
        "get_is_in_shopping_cart"
    )
    views_count = serializers.IntegerField(read_only=True)
    favorites_count = serializers.IntegerField(read_only=True)
    steps = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        read_only=True
    )

    class Meta:
        model = models.Recipe
        fields = [
            "id",
            "tags",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
            "views_count",
            "favorites_count",
            "created_at",
            "updated_at",
            "steps"
        ]

    def get_is_favorited(self, obj: models.Recipe) -> bool:
        request = self.context.get("request")
        if request is None or request.user.is_anonymous:
            return False
        return models.Favorite.objects.filter(
            recipe=obj,
            user=request.user
        ).exists()

    def get_is_in_shopping_cart(self, obj: models.Recipe) -> bool:
        request_user = self.context["request"].user
        if request_user.is_anonymous:
            return False
        return models.ShoppingCart.objects.filter(
            user=request_user,
            recipe=obj
        ).exists()


class AddIngredientToRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=models.Ingredient.objects.all()
    )
    measurement_unit = serializers.SlugRelatedField(
        source="ingredient",
        read_only=True,
        slug_field="measurement_unit"
    )
    amount = serializers.FloatField(min_value=0)

    class Meta:
        model = models.IngredientInRecipe
        fields = ("id", "amount", "measurement_unit")

    def to_representation(self, instance: Any) -> Dict[str, Any]:
        if isinstance(instance, models.Ingredient):
            return {
                'id': instance.id,
                'amount': None,
                'measurement_unit': instance.measurement_unit
            }
        return {
            'id': instance.ingredient.id,
            'amount': instance.amount,
            'measurement_unit': instance.ingredient.measurement_unit
        }


class CreateRecipeSerializer(serializers.ModelSerializer):
    image = Base64ImageField(max_length=None, use_url=True, required=False)
    author = CustomUserManipulateSerializer(read_only=True)
    ingredients = AddIngredientToRecipeSerializer(many=True)
    cooking_time = serializers.IntegerField()
    tags = serializers.SlugRelatedField(
        many=True,
        queryset=models.Tag.objects.all(),
        slug_field="id"
    )
    steps = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True
    )

    class Meta:
        model = models.Recipe
        fields = [
            "tags",
            "author",
            "ingredients",
            "name",
            "image",
            "text",
            "cooking_time",
            "steps"
        ]

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ingredients = self.initial_data.get('ingredients')
        if not ingredients:
            raise ValidationError('Рецепт должен содержать хотя бы один ингредиент')
            
        ingredients_list: List[int] = []
        for ingredient in ingredients:
            ingredient_id = ingredient['id']
            if ingredient_id in ingredients_list:
                raise ValidationError('Ингредиенты не должны повторяться')
            ingredients_list.append(ingredient_id)
            
        if data['cooking_time'] <= 0:
            raise ValidationError('Время приготовления должно быть больше 0')
            
        return data

    def create_bulk(self, recipe: models.Recipe, ingredients_data: List[Dict[str, Any]]) -> None:
        models.IngredientInRecipe.objects.bulk_create([
            models.IngredientInRecipe(
                ingredient=ingredient["id"],
                recipe=recipe,
                amount=ingredient['amount']
            ) for ingredient in ingredients_data
        ])

    def create(self, validated_data: Dict[str, Any]) -> models.Recipe:
        request = self.context.get('request')
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        steps = validated_data.pop('steps', None)
        
        recipe = models.Recipe.objects.create(
            author=request.user,
            **validated_data
        )
        
        if steps:
            recipe.steps = steps
            recipe.save()
            
        recipe.tags.set(tags_data)
        self.create_bulk(recipe, ingredients_data)
        return recipe

    def update(self, instance: models.Recipe, validated_data: Dict[str, Any]) -> models.Recipe:
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        steps = validated_data.pop('steps', None)
        
        models.IngredientInRecipe.objects.filter(recipe=instance).delete()
        self.create_bulk(instance, ingredients_data)
        instance.tags.set(tags_data)
        
        if steps:
            instance.steps = steps
            
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FavoriteSerializer(serializers.ModelSerializer):
    recipe = serializers.PrimaryKeyRelatedField(
        queryset=models.Recipe.objects.all()
    )
    user = serializers.PrimaryKeyRelatedField(
        queryset=models.User.objects.all()
    )

    class Meta:
        model = models.Favorite
        fields = ["recipe", "user"]
        validators = [
            UniqueTogetherValidator(
                queryset=models.Favorite.objects.all(),
                fields=('user', 'recipe'),
                message='You have already favourited this recipe!'
            )
        ]


class ShoppingCartSerializer(FavoriteSerializer):
    class Meta:
        model = models.ShoppingCart
        fields = ["recipe", "user"]


class RecipeSerializer(serializers.ModelSerializer):
    def to_representation(self, instance: models.Recipe) -> Dict[str, Any]:
        cache_key = f'recipe_{instance.id}'
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
            
        data = super().to_representation(instance)
        cache.set(cache_key, data, settings.CACHE_TTL)
        return data

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        ingredients = self.initial_data.get('ingredients', [])
        if not ingredients:
            raise ValidationError('Рецепт должен содержать хотя бы один ингредиент')
            
        ingredients_list: List[int] = []
        for ingredient in ingredients:
            ingredient_id = ingredient['id']
            if ingredient_id in ingredients_list:
                raise ValidationError('Ингредиенты не должны повторяться')
            ingredients_list.append(ingredient_id)
            
        if data['cooking_time'] <= 0:
            raise ValidationError('Время приготовления должно быть больше 0')
            
        return data


class CommentSerializer(serializers.ModelSerializer):
    author = CustomUserManipulateSerializer(read_only=True)

    class Meta:
        model = models.Comment
        fields = ('id', 'author', 'text', 'created')
        read_only_fields = ('author',)

    def to_representation(self, instance: models.Comment) -> Dict[str, Any]:
        representation = super().to_representation(instance)
        representation['author'] = CustomUserManipulateSerializer(
            instance.author,
            context=self.context
        ).data
        return representation
