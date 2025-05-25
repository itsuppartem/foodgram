from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from djoser.views import UserViewSet as DjoserUserViewSet
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from foodgram.pagination import CartCustomPagination
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from users.forms import UserProfileForm, SignUpForm
from .models import Follow, User
from .serializers import (CustomUserManipulateSerializer, CustomUserSerializer, FollowerSerializer,
                          RepresentationFollowerSerializer, UserSerializer)

User = get_user_model()


class CustomUserViewSet(DjoserUserViewSet):
    """
    Handler function for the processing GET, POST, DEL requests for
    User objects.
    """
    queryset = User.objects.all()
    serializer_class = CustomUserManipulateSerializer
    permission_classes = [AllowAny]
    pagination_class = CartCustomPagination

    @swagger_auto_schema(operation_description="Получить информацию о текущем пользователе",
        responses={200: CustomUserSerializer, 401: "Unauthorized"})
    @action(methods=["get"], detail=False, permission_classes=[IsAuthenticated])
    def me(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=request.user.id)
        serializer = CustomUserSerializer(user)
        return Response(serializer.data)

    @swagger_auto_schema(method='post', operation_description="Подписаться на пользователя",
        responses={201: FollowerSerializer, 400: "Bad Request", 401: "Unauthorized", 404: "Not Found"})
    @swagger_auto_schema(method='delete', operation_description="Отписаться от пользователя",
        responses={204: "No Content", 401: "Unauthorized", 404: "Not Found"})
    @action(methods=["delete", "post"], detail=True, permission_classes=[IsAuthenticated])
    def subscribe(self, request, id):
        user = request.user
        author = get_object_or_404(User, id=id)
        follow = Follow.objects.filter(user=user, author=author)
        data = {"user": user.id, "author": author.id}
        if request.method == "POST":
            serializer = FollowerSerializer(data=data, context=request)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        follow.delete()
        return Response("Deleted", status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(operation_description="Получить список подписок пользователя",
        responses={200: RepresentationFollowerSerializer(many=True), 401: "Unauthorized"})
    @action(methods=["get"], detail=False, permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        user = request.user
        queryset = user.follower.all()
        pages = self.paginate_queryset(queryset)
        serializer = RepresentationFollowerSerializer(pages, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['create', 'list']:
            return []
        return super().get_permissions()


class UserCreateView(APIView):
    @swagger_auto_schema(operation_description="Создать нового пользователя", request_body=UserSerializer,
        responses={201: UserSerializer, 400: "Bad Request"})
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(method='get', operation_description="Получить информацию о текущем пользователе",
    responses={200: UserSerializer, 401: "Unauthorized"})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                login(request, user)
                return redirect('index')
            else:
                messages.error(request, 'Неверный пароль')
        except User.DoesNotExist:
            messages.error(request, 'Пользователь не найден')
    return render(request, 'login.html')


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})


@swagger_auto_schema(method='post', operation_description="Выйти из системы",
    responses={204: "No Content", 302: "Redirect to index"})
@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def logout_view(request):
    if request.method == 'POST':
        if request.user.is_authenticated and hasattr(request.user, 'auth_token'):
            request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    else:
        logout(request)
        return redirect('index')


@login_required
def profile_edit(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен')
            return redirect('profile', username=request.user.username)
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'profile_edit.html', {'form': form})


@login_required
def subscribe_view(request, username):
    author = get_object_or_404(User, username=username)
    if request.user == author:
        messages.error(request, 'Нельзя подписаться на самого себя')
        return redirect('recipe_detail', pk=request.GET.get('recipe_id'))

    if Follow.objects.filter(user=request.user, author=author).exists():
        messages.error(request, 'Вы уже подписаны на этого пользователя')
    else:
        Follow.objects.create(user=request.user, author=author)
        messages.success(request, f'Вы подписались на {author.username}')

    return redirect('recipe_detail', pk=request.GET.get('recipe_id'))


@login_required
def unsubscribe_view(request, username):
    author = get_object_or_404(User, username=username)
    follow = Follow.objects.filter(user=request.user, author=author)

    if follow.exists():
        follow.delete()
        messages.success(request, f'Вы отписались от {author.username}')
    else:
        messages.error(request, 'Вы не были подписаны на этого пользователя')

    recipe_id = request.GET.get('recipe_id')
    if recipe_id:
        return redirect('recipe_detail', pk=recipe_id)
    return redirect('my_subscriptions')


@login_required
def my_subscriptions(request):
    follows = Follow.objects.filter(user=request.user).select_related('author')
    return render(request, 'my_subscriptions.html', {'follows': follows})


@swagger_auto_schema(method='post', operation_description="Получить токен авторизации",
    request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=['email', 'password'],
        properties={'email': openapi.Schema(type=openapi.TYPE_STRING, format='email'),
            'password': openapi.Schema(type=openapi.TYPE_STRING, format='password')}), responses={
        200: openapi.Schema(type=openapi.TYPE_OBJECT,
            properties={'auth_token': openapi.Schema(type=openapi.TYPE_STRING)}), 400: "Bad Request"})
@api_view(['POST'])
@permission_classes([AllowAny])
def token_login(request):
    email = request.data.get('email')
    password = request.data.get('password')

    if not email or not password:
        return Response({'error': 'Please provide both email and password'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
        if user.check_password(password):
            token, _ = Token.objects.get_or_create(user=user)
            return Response({'auth_token': token.key})
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
    except User.DoesNotExist:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)
