import asyncio

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Prefetch, Sum, Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import Follow

from . import models, serializers
from .filters import IngredientFilter, RecipeFilter
from .forms import RecipeForm, IngredientForm
from .models import Recipe, IngredientInRecipe, Favorite, Comment, Ingredient
from .pagination import CartCustomPagination
from .permissions import IsOwnerOrReadOnly
from .services.ai_service import AIService
from .utils import custom_delete, custom_post, send_telegram_notify

User = get_user_model()


def index(request):
    latest_recipes = models.Recipe.objects.select_related('author').prefetch_related('ingredients', 'tags').order_by(
        '-created_at')[:6]

    subscription_recipes = []
    has_subscriptions = False
    if request.user.is_authenticated:
        follows = Follow.objects.filter(user=request.user)
        if follows.exists():
            has_subscriptions = True
            authors = [f.author for f in follows]
            subscription_recipes = models.Recipe.objects.filter(author__in=authors).select_related(
                'author').prefetch_related('ingredients', 'tags').order_by('-created_at')[:6]

    return render(request, 'index.html',
                  {'latest_recipes': latest_recipes, 'subscription_recipes': subscription_recipes,
                      'has_subscriptions': has_subscriptions})


def recipe_list(request):
    recipes = models.Recipe.objects.select_related('author').prefetch_related('ingredients', 'tags').all()
    tags = models.Tag.objects.all()

    selected_tags = request.GET.getlist('tags')
    if selected_tags:
        recipes = recipes.filter(tags__slug__in=selected_tags).distinct()

    search_query = request.GET.get('search')
    if search_query:
        recipes = recipes.filter(Q(name__icontains=search_query) | Q(text__icontains=search_query) | Q(
            author__username__icontains=search_query) | Q(ingredients__name__icontains=search_query) | Q(
            tags__name__icontains=search_query)).distinct()

    paginator = Paginator(recipes, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('recipe_list_partial.html',
                                {'recipes': page_obj, 'is_paginated': True, 'page_obj': page_obj})
        return JsonResponse({'html': html})

    return render(request, 'recipe_list.html',
                  {'recipes': page_obj, 'tags': tags, 'is_paginated': True, 'page_obj': page_obj})


def recipe_detail(request, pk):
    recipe = models.Recipe.objects.select_related('author').prefetch_related('ingredients', 'tags',
        'ingredients_amount', 'comments').get(pk=pk)

    recipe.views_count += 1
    recipe.save()

    is_in_shopping_cart = False
    is_subscribed = False
    is_favorited = False
    if request.user.is_authenticated:
        is_in_shopping_cart = models.ShoppingCart.objects.filter(user=request.user, recipe=recipe).exists()
        is_subscribed = Follow.objects.filter(user=request.user, author=recipe.author).exists()
        is_favorited = models.Favorite.objects.filter(user=request.user, recipe=recipe).exists()
    return render(request, 'recipe_detail.html',
                  {'recipe': recipe, 'is_in_shopping_cart': is_in_shopping_cart, 'is_subscribed': is_subscribed,
                      'is_favorited': is_favorited})


@login_required
def favorites(request):
    recipes = models.Recipe.objects.filter(favorite__user=request.user).select_related('author').prefetch_related(
        'ingredients', 'tags')
    favorite_ids = list(recipes.values_list('id', flat=True))
    paginator = Paginator(recipes, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'favorites.html',
                  {'recipes': page_obj, 'favorite_ids': favorite_ids, 'is_paginated': True, 'page_obj': page_obj})


@login_required
def shopping_list(request):
    shopping_cart = models.ShoppingCart.objects.filter(user=request.user).select_related('recipe')

    ingredients_by_recipe = {}
    for cart_item in shopping_cart:
        recipe = cart_item.recipe
        recipe_ingredients = models.IngredientInRecipe.objects.filter(recipe=recipe).select_related('ingredient')

        if recipe not in ingredients_by_recipe:
            ingredients_by_recipe[recipe] = []

        for ingredient in recipe_ingredients:
            ingredients_by_recipe[recipe].append({'name': ingredient.ingredient.name, 'amount': ingredient.amount,
                'unit': ingredient.ingredient.measurement_unit})

    return render(request, 'shopping_list.html',
                  {'ingredients_by_recipe': ingredients_by_recipe, 'shopping_cart': shopping_cart})


@login_required
def shopping_list_add(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    if not models.ShoppingCart.objects.filter(user=request.user, recipe=recipe).exists():
        models.ShoppingCart.objects.create(user=request.user, recipe=recipe)
    return redirect('recipe_detail', pk=recipe_id)


@login_required
def shopping_list_remove(request, recipe_id):
    recipe = get_object_or_404(models.Recipe, id=recipe_id)
    models.ShoppingCart.objects.filter(user=request.user, recipe=recipe).delete()
    if request.GET.get('from_detail') == '1':
        return redirect('recipe_detail', pk=recipe_id)
    return redirect('shopping_list')


@login_required
def profile(request, username):
    user = get_object_or_404(User, username=username)
    if request.method == 'POST' and user == request.user:
        telegram_id = request.POST.get('telegram_id')
        telegram_notify = request.POST.get('telegram_notify') == 'on'
        if telegram_id:
            user.telegram_id = telegram_id
        user.telegram_notify = telegram_notify
        user.save()
        return redirect('profile', username=user.username)

    user_recipes = models.Recipe.objects.filter(author=user).select_related('author').prefetch_related('ingredients',
        'tags')
    total_subscribers = Follow.objects.filter(author=user).count()
    total_favorites = Favorite.objects.filter(recipe__author=user).count()
    total_views = models.Recipe.objects.filter(author=user).aggregate(total_views=Sum('views_count'))[
                      'total_views'] or 0
    paginator = Paginator(user_recipes, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'profile.html', {'user': user, 'recipes': page_obj, 'total_subscribers': total_subscribers,
        'total_favorites': total_favorites, 'total_views': total_views, 'is_paginated': True, 'page_obj': page_obj})


@login_required
def recipe_create(request):
    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.author = request.user

            steps = form.cleaned_data.get('steps')
            if steps:
                recipe.steps = [s.strip() for s in steps.split('\n') if s.strip()]

            recipe.save()
            form.save_m2m()

            ingredient_ids = request.POST.getlist('ingredient')
            amounts = request.POST.getlist('amount')
            for ingredient_id, amount in zip(ingredient_ids, amounts):
                if ingredient_id and amount:
                    IngredientInRecipe.objects.create(recipe=recipe, ingredient_id=ingredient_id, amount=amount)

            return redirect('recipe_detail', pk=recipe.pk)
    else:
        form = RecipeForm()

    return render(request, 'recipe_form.html', {'form': form, 'ingredients': Ingredient.objects.all()})


@login_required
def recipe_edit(request, pk):
    recipe = get_object_or_404(Recipe, id=pk)
    if recipe.author != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            recipe = form.save(commit=False)

            steps = form.cleaned_data.get('steps')
            if steps:
                recipe.steps = [s.strip() for s in steps.split('\n') if s.strip()]

            recipe.save()
            form.save_m2m()

            try:
                recipe.ingredients.clear()
                ingredient_ids = request.POST.getlist('ingredient')
                amounts = request.POST.getlist('amount')
                for ingredient_id, amount in zip(ingredient_ids, amounts):
                    if ingredient_id and amount:
                        IngredientInRecipe.objects.create(recipe=recipe, ingredient_id=ingredient_id, amount=amount)
                return redirect('recipe_detail', pk=recipe.id)
            except Exception as e:
                form.add_error(None, f'Ошибка при сохранении ингредиентов: {str(e)}')
    else:
        form = RecipeForm(instance=recipe)
        if recipe.steps:
            form.initial['steps'] = '\n'.join(recipe.steps)
        ingredients = models.Ingredient.objects.all()
        ingredient_forms = []
        for ing in IngredientInRecipe.objects.filter(recipe=recipe):
            f = IngredientForm(initial={'ingredient': ing.ingredient.id, 'amount': ing.amount})
            ingredient_forms.append(f)

    return render(request, 'recipe_form.html',
                  {'form': form, 'ingredient_forms': ingredient_forms, 'ingredients': ingredients, 'is_edit': True})


@login_required
def recipe_delete(request, pk):
    recipe = get_object_or_404(Recipe, id=pk)
    if recipe.author != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        recipe.delete()
        return redirect('profile', username=request.user.username)

    return render(request, 'recipe_confirm_delete.html', {'recipe': recipe})


@login_required
def favorite_add(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    if not models.Favorite.objects.filter(user=request.user, recipe=recipe).exists():
        models.Favorite.objects.create(user=request.user, recipe=recipe)
        recipe.favorites_count += 1
        recipe.save()
    return redirect('recipe_detail', pk=recipe_id)


@login_required
def favorite_remove(request, recipe_id):
    recipe = get_object_or_404(models.Recipe, id=recipe_id)
    if models.Favorite.objects.filter(user=request.user, recipe=recipe).exists():
        models.Favorite.objects.filter(user=request.user, recipe=recipe).delete()
        if recipe.favorites_count > 0:
            recipe.favorites_count -= 1
            recipe.save()
    return redirect('recipe_detail', pk=recipe_id)


class IngredientsView(viewsets.ModelViewSet):
    """
    Handler function for the processing of the Ingredient objects through
    GET request
    """
    queryset = models.Ingredient.objects.all()
    serializer_class = serializers.IngredientSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, ]
    filter_class = IngredientFilter
    search_fields = ("^name",)
    pagination_class = None

    @swagger_auto_schema(operation_description="Создать новый ингредиент",
        request_body=serializers.IngredientSerializer,
        responses={200: serializers.IngredientSerializer, 201: serializers.IngredientSerializer, 400: "Bad Request"})
    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            name = request.data.get('name')
            measurement_unit = request.data.get('measurement_unit')
            obj = models.Ingredient.objects.filter(name=name, measurement_unit=measurement_unit).first()
            if obj:
                serializer = self.get_serializer(obj)
                return Response(serializer.data, status=200)
            return Response({'error': 'Ингредиент уже существует, но не найден.'}, status=400)


class TagView(viewsets.ModelViewSet):
    """
    Handler function for the processing of the Tag objects through
    GET request
    """
    queryset = models.Tag.objects.all()
    serializer_class = serializers.TagSerializer
    permissions = (AllowAny,)
    pagination_class = None


class RecipeView(viewsets.ModelViewSet):
    """
    Handler function for the processing of the Recipe objects through
    the further requests: GET, POST, PATCH, DEL.
    """
    queryset = models.Recipe.objects.select_related('author').prefetch_related(
        Prefetch('ingredients', queryset=models.Ingredient.objects.only('name', 'measurement_unit')),
        Prefetch('tags', queryset=models.Tag.objects.only('name', 'color', 'slug')), 'ingredients_amount')
    serializer_class = serializers.CreateRecipeSerializer
    permission_classes = (IsOwnerOrReadOnly,)
    filterset_class = RecipeFilter
    pagination_class = CartCustomPagination

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return serializers.ShowRecipeSerializer
        return serializers.CreateRecipeSerializer

    @swagger_auto_schema(operation_description="Получить список рецептов",
        responses={200: serializers.ShowRecipeSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        cache_key = f'recipe_list_{request.query_params}'
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, settings.CACHE_TTL)
        return response

    @swagger_auto_schema(operation_description="Создать новый рецепт", request_body=serializers.CreateRecipeSerializer,
        responses={201: serializers.CreateRecipeSerializer, 400: "Bad Request", 401: "Unauthorized"})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @swagger_auto_schema(operation_description="Обновить рецепт", request_body=serializers.CreateRecipeSerializer,
        responses={200: serializers.CreateRecipeSerializer, 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
            404: "Not Found"})
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class FavoriteView(APIView):
    """
    Handler function for the processing GET, POST, DEL requests for
    Favourite objects.
    """
    permission_classes = [IsAuthenticatedOrReadOnly, ]
    pagination_class = CartCustomPagination
    filter_backends = (DjangoFilterBackend,)

    @swagger_auto_schema(operation_description="Добавить рецепт в избранное",
        responses={201: serializers.FavoriteSerializer, 400: "Bad Request", 404: "Not Found"})
    def post(self, request, recipe_id):
        return custom_post(self, request, recipe_id, serializers.FavoriteSerializer, "recipe")

    @swagger_auto_schema(operation_description="Удалить рецепт из избранного",
        responses={204: "No Content", 404: "Not Found"})
    def delete(self, request, recipe_id):
        return custom_delete(self, request, recipe_id, models.Favorite)


class ShoppingCartView(APIView):
    """
    Handler function for the processing GET, POST, DEL requests for
    Buying list objects.
    """
    permission_classes = [IsAuthenticatedOrReadOnly, ]
    serializer_class = serializers.ShoppingCartSerializer
    filterset_class = RecipeFilter
    pagination_class = CartCustomPagination
    queryset = models.ShoppingCart.objects.all()

    @swagger_auto_schema(operation_description="Добавить рецепт в список покупок",
        responses={201: serializers.ShoppingCartSerializer, 400: "Bad Request", 404: "Not Found"})
    def post(self, request, recipe_id):
        return custom_post(self, request, recipe_id, serializers.ShoppingCartSerializer, "recipe")

    @swagger_auto_schema(operation_description="Удалить рецепт из списка покупок",
        responses={204: "No Content", 404: "Not Found"})
    def delete(self, request, recipe_id):
        return custom_delete(self, request, recipe_id, models.ShoppingCart)


@swagger_auto_schema(method='get', operation_description="Скачать список покупок в PDF",
    responses={200: openapi.Response(description="PDF файл со списком покупок", content={'application/pdf': {}}),
        400: "Bad Request"})
@api_view(["GET"])
@permission_classes([IsAuthenticatedOrReadOnly])
def download_shopping_cart(request):
    cache_key = f'shopping_cart_{request.user.id}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    shopping_cart = models.ShoppingCart.objects.select_related('recipe').prefetch_related(
        'recipe__ingredients_amount__ingredient').filter(user=request.user)

    buying_list = {}
    for record in shopping_cart:
        recipe = record.recipe
        ingredients = models.IngredientInRecipe.objects.filter(recipe=recipe)
        for ingredient in ingredients:
            amount = ingredient.amount
            name = ingredient.ingredient.name
            measurement_unit = ingredient.ingredient.measurement_unit
            if name not in buying_list:
                buying_list[name] = {"measurement_unit": measurement_unit, "amount": amount, }
            else:
                buying_list[name]["amount"] = (buying_list[name]["amount"] + amount)
    wishlist = []
    for name, data in buying_list.items():
        wishlist.append(f"{name} - {data['amount']} ({data['measurement_unit']})\n")
    pdfmetrics.registerFont(TTFont("RunicRegular", "data/RunicRegular.ttf", "UTF-8"))
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = ('attachment; '
                                       'filename="shopping_list.pdf"')
    page = canvas.Canvas(response)
    page.setFont('RunicRegular', size=32)
    page.drawString(200, 800, 'Buying list')
    page.setFont('RunicRegular', size=18)
    height = 760
    for i, (name, data) in enumerate(buying_list.items(), 1):
        page.drawString(55, height, (f'{i}. {name} - {data["amount"]} '
                                     f'{data["measurement_unit"]}'))
        height -= 30
    page.showPage()
    page.save()
    cache.set(cache_key, response, settings.CACHE_TTL)
    return response


class CommentView(APIView):
    """
    Handler function for the processing GET, POST, DEL requests for
    Comment objects.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = serializers.CommentSerializer

    def get_queryset(self, recipe_id):
        return models.Comment.objects.filter(recipe_id=recipe_id).select_related('author')

    @swagger_auto_schema(operation_description="Получить список комментариев к рецепту",
        responses={200: serializers.CommentSerializer(many=True), 404: "Not Found"})
    def get(self, request, recipe_id):
        comments = self.get_queryset(recipe_id)
        serializer = self.serializer_class(comments, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(operation_description="Добавить комментарий к рецепту",
        request_body=serializers.CommentSerializer,
        responses={201: serializers.CommentSerializer, 400: "Bad Request", 404: "Not Found"})
    def post(self, request, recipe_id):
        recipe = get_object_or_404(Recipe, id=recipe_id)
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            comment = serializer.save(author=request.user, recipe=recipe)
            # Уведомление владельцу рецепта
            author = recipe.author
            if author.telegram_id and getattr(author, 'telegram_notify', False):
                url = request.build_absolute_uri(recipe.get_absolute_url()) if hasattr(recipe,
                                                                                       'get_absolute_url') else ''
                msg = f'📝 Новый комментарий к вашему рецепту "{recipe.name}":\n{comment.text}\n{url}'
                send_telegram_notify(author.telegram_id, msg)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(operation_description="Удалить комментарий",
        responses={204: "No Content", 403: "Forbidden", 404: "Not Found"})
    def delete(self, request, recipe_id, comment_id):
        comment = get_object_or_404(Comment, id=comment_id, recipe_id=recipe_id)
        if comment.author != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(APIView):
    """
    Handler function for the processing GET requests for
    User profile objects.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = serializers.ShowRecipeSerializer
    pagination_class = CartCustomPagination

    @swagger_auto_schema(operation_description="Получить профиль пользователя и его рецепты",
        responses={200: serializers.ShowRecipeSerializer(many=True), 404: "Not Found"})
    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        recipes = Recipe.objects.filter(author=user)

        total_subscribers = Follow.objects.filter(author=user).count()
        total_favorites = Favorite.objects.filter(recipe__author=user).count()
        total_views = Recipe.objects.filter(author=user).aggregate(total_views=Sum('views_count'))['total_views'] or 0

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(recipes, request)

        if page is not None:
            serializer = self.serializer_class(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)

        serializer = self.serializer_class(recipes, many=True, context={'request': request})
        return Response(serializer.data)


@login_required
def add_comment(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    if request.method == 'POST':
        text = request.POST.get('text')
        if text:
            Comment.objects.create(recipe=recipe, author=request.user, text=text)
            # Уведомление владельцу рецепта
            author = recipe.author
            print(
                f"[DEBUG] author.telegram_id={getattr(author, 'telegram_id', None)}, author.telegram_notify={getattr(author, 'telegram_notify', None)}")
            if author.telegram_id and getattr(author, 'telegram_notify', False):
                url = request.build_absolute_uri(recipe.get_absolute_url()) if hasattr(recipe,
                                                                                       'get_absolute_url') else ''
                msg = f'📝 Новый комментарий к вашему рецепту "{recipe.name}":\n{text}\n{url}'
                print(f"[DEBUG] Отправляю уведомление: {msg}")
                send_telegram_notify(author.telegram_id, msg)
    return redirect('recipe_detail', pk=recipe_id)


@login_required
def delete_comment(request, recipe_id, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, recipe_id=recipe_id)
    if comment.author == request.user:
        comment.delete()
    return redirect('recipe_detail', pk=recipe_id)


@login_required
def my_subscriptions(request):
    follows = Follow.objects.filter(user=request.user).select_related('author')
    authors = [f.author for f in follows]
    recipes = models.Recipe.objects.filter(author__in=authors).select_related('author').prefetch_related('ingredients',
                                                                                                         'tags').order_by(
        '-created_at')

    paginator = Paginator(recipes, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'my_subscriptions.html',
                  {'recipes': page_obj, 'authors': authors, 'is_paginated': True, 'page_obj': page_obj})


@swagger_auto_schema(method='post', operation_description="Сгенерировать рецепт на основе текстового описания",
    request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=['prompt'],
        properties={'prompt': openapi.Schema(type=openapi.TYPE_STRING),
            'cooking_time': openapi.Schema(type=openapi.TYPE_INTEGER, default=30),
            'difficulty': openapi.Schema(type=openapi.TYPE_STRING, enum=['easy', 'medium', 'hard'], default='medium')}),
    responses={200: openapi.Schema(type=openapi.TYPE_OBJECT,
        properties={'name': openapi.Schema(type=openapi.TYPE_STRING),
            'description': openapi.Schema(type=openapi.TYPE_STRING),
            'ingredients': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
            'steps': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
            'cooking_time': openapi.Schema(type=openapi.TYPE_INTEGER),
            'difficulty': openapi.Schema(type=openapi.TYPE_STRING)}), 400: "Bad Request", 401: "Unauthorized",
        500: "Internal Server Error"})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_recipe_by_text(request):
    try:
        prompt = request.data.get('prompt')
        cooking_time = request.data.get('cooking_time', 30)
        difficulty = request.data.get('difficulty', 'medium')

        if not prompt:
            return Response({'error': 'Необходимо указать название рецепта'}, status=status.HTTP_400_BAD_REQUEST)

        ai_service = AIService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        recipe = loop.run_until_complete(
            ai_service.generate_recipe(prompt=prompt, cooking_time=cooking_time, difficulty=difficulty))
        loop.close()

        return Response(recipe)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(method='post', operation_description="Сгенерировать изображение рецепта",
    request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=['prompt'],
        properties={'prompt': openapi.Schema(type=openapi.TYPE_STRING)}),
    responses={200: openapi.Response(description="Изображение рецепта", content={'image/png': {}}), 400: "Bad Request",
        401: "Unauthorized", 500: "Internal Server Error"})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_recipe_image(request):
    try:
        prompt = request.data.get('prompt')
        if not prompt:
            return Response({'error': 'Необходимо указать промпт для генерации изображения'},
                status=status.HTTP_400_BAD_REQUEST)

        ai_service = AIService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        image_data = loop.run_until_complete(ai_service.generate_image(prompt))
        loop.close()

        if not image_data:
            return Response({'error': 'Не удалось сгенерировать изображение'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return HttpResponse(image_data, content_type='image/png')
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(method='post', operation_description="Задать вопрос AI ассистенту",
    request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=['question'],
        properties={'question': openapi.Schema(type=openapi.TYPE_STRING)}), responses={
        200: openapi.Schema(type=openapi.TYPE_OBJECT, properties={'answer': openapi.Schema(type=openapi.TYPE_STRING)}),
        400: "Bad Request", 401: "Unauthorized", 500: "Internal Server Error"})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ask_ai(request):
    try:
        question = request.data.get('question')
        if not question:
            return Response({'error': 'Необходимо указать вопрос'}, status=status.HTTP_400_BAD_REQUEST)

        ai_service = AIService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(ai_service.ask(question))
        loop.close()

        if 'error' in response:
            return Response({'error': response['error']}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(response)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
