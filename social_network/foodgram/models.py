from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

User = get_user_model()


class Tag(models.Model):
    """
    This model is used to create tags.
    """
    name: str = models.CharField(max_length=250, verbose_name="Tag", help_text="Tags name")

    color: str = models.CharField(max_length=7, default="#ffffff", verbose_name="HEX colour", help_text="Tags colour")

    slug: str = models.SlugField(unique=True, verbose_name="Slug", help_text="Tags slug")

    class Meta:
        ordering = ["name"]
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self) -> str:
        return self.name


class Ingredient(models.Model):
    """
    This model is used to create ingredients.
    """
    name = models.CharField(max_length=250, verbose_name="Ingredient", help_text="Input ingredients name")

    measurement_unit = models.CharField(max_length=50, verbose_name="Measurement units",
        help_text="Input measurement units", )

    class Meta:
        ordering = ["name"]
        verbose_name = "Ingredient"
        verbose_name_plural = "Ingredients"
        constraints = [models.UniqueConstraint(fields=["name", "measurement_unit"], name="unique_ingredient")]

    def __str__(self):
        return f"{self.name}, {self.measurement_unit}"


class Recipe(models.Model):
    """
    This model is used to create recipe
    """
    author: User = models.ForeignKey(User, verbose_name="Author", on_delete=models.CASCADE, related_name="recipes",
        help_text="This is the author of the recipe")
    tags = models.ManyToManyField(Tag, through="TagsInRecipe", related_name="recipes", verbose_name="Tags",
        help_text="Choose recipes tags", blank=True)
    name = models.CharField(max_length=200, verbose_name="Name", help_text="Input recipes name")
    text = models.TextField(default="", verbose_name="Description", help_text="How this thing should be cooked",
        blank=True)
    cooking_time: int = models.PositiveSmallIntegerField(verbose_name="Cooking time",
        help_text="Input cooking time in minutes", validators=[MinValueValidator(0)], null=True, blank=True)
    ingredients = models.ManyToManyField(Ingredient, through="IngredientInRecipe", verbose_name="Ingredients",
        related_name="recipes", blank=True, help_text="Choose ingredients for your recipe")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")
    image = models.ImageField("Image", upload_to="recipes/media/", blank=True, help_text="Upload image", )
    views_count = models.PositiveIntegerField(default=0, verbose_name="Views count", help_text="Number of recipe views",
        null=True, blank=True)
    favorites_count = models.PositiveIntegerField(default=0, verbose_name="Favorites count",
        help_text="Number of times recipe was favorited", null=True, blank=True)
    difficulty = models.CharField(max_length=20, verbose_name="Difficulty", help_text="Recipe difficulty level",
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='medium')
    image_generation_prompt = models.TextField(verbose_name="Image generation prompt",
        help_text="Prompt for generating recipe image", null=True, blank=True)
    steps = models.JSONField(verbose_name="Cooking steps", help_text="List of cooking steps", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Recipe"
        verbose_name_plural = "Recipes"

    def __str__(self) -> str:
        return self.name

    def to_dict(self) -> Dict[str, Any]:
        return {'id': self.id, 'name': self.name, 'author': self.author.username, 'cooking_time': self.cooking_time}


class TagsInRecipe(models.Model):
    """
    This model is used to create several tags in recipe
    """
    tag = models.ForeignKey(Tag, verbose_name="Тag in recipe", on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, )

    class Meta:
        verbose_name = "Tags in recipe"
        verbose_name_plural = verbose_name


class IngredientInRecipe(models.Model):
    """
    This model is used to create several tags in recipe
    """
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, verbose_name="Ingredient in recipe",
        related_name="ingredients_amount", )
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Recipe",
        related_name="ingredients_amount", )
    amount = models.FloatField(null=True, blank=True, verbose_name="Amount value of ingredient",
        validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "Ingredients amount in recipe"
        verbose_name_plural = verbose_name
        constraints = [models.UniqueConstraint(fields=['ingredient', 'recipe'], name='unique_amount')]


class Favorite(models.Model):
    """
    This model is used to favourite recipes
    """
    recipe = models.ForeignKey(Recipe, related_name="favorite", on_delete=models.CASCADE, verbose_name="Recipe", )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="User", related_name="favorite", )
    when_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-when_added"]
        verbose_name = "Favourited"
        verbose_name_plural = verbose_name
        constraints = [models.UniqueConstraint(fields=['user', 'recipe'], name='unique_favorite')]

    def __str__(self):
        return f"{self.user} added {self.recipe}"


class ShoppingCart(models.Model):
    """
    This model is used to add recipe in Buying List
    """
    recipe = models.ForeignKey(Recipe, related_name="is_in_shopping_cart", on_delete=models.CASCADE,
        verbose_name="Recipe", )
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="User", related_name="is_in_shopping_cart", )
    when_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buying List"
        verbose_name_plural = verbose_name
        constraints = [models.UniqueConstraint(fields=['user', 'recipe'], name='unique_cart')]

    def __str__(self):
        return f"{self.user} added {self.recipe}"


class Comment(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [
            '-created']  # constraints = [  #     models.UniqueConstraint(  #         fields=['recipe', 'author'],  #         name='unique_comment'  #     )  # ]

    def __str__(self):
        return f'Comment by {self.author} on {self.recipe}'


class RecipeHistory(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='history')
    history_text = models.TextField(verbose_name="History text", help_text="History of the recipe")
    interesting_facts = models.JSONField(verbose_name="Interesting facts", help_text="List of interesting facts",
        null=True, blank=True)
    cultural_significance = models.TextField(verbose_name="Cultural significance",
        help_text="Cultural significance of the recipe", null=True, blank=True)


class ChefAdvice(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='chef_advice')
    tips = models.JSONField(verbose_name="Cooking tips", help_text="List of cooking tips", null=True, blank=True)
    variations = models.JSONField(verbose_name="Recipe variations", help_text="List of recipe variations", null=True,
        blank=True)
    common_mistakes = models.JSONField(verbose_name="Common mistakes", help_text="List of common mistakes", null=True,
        blank=True)
    serving_suggestions = models.JSONField(verbose_name="Serving suggestions", help_text="List of serving suggestions",
        null=True, blank=True)


class DrinkPairing(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='drink_pairings')
    name = models.CharField(max_length=200, verbose_name="Drink name", help_text="Name of the drink")
    type = models.CharField(max_length=100, verbose_name="Drink type", help_text="Type of the drink")
    description = models.TextField(verbose_name="Drink description", help_text="Description of the drink")
    pairing_reason = models.TextField(verbose_name="Pairing reason", help_text="Reason for pairing with the recipe")
