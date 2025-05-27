import base64
import logging
import os
from typing import List

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from config import settings
from database import engine, Base, get_db
from gemini_service import (generate_text, generate_image, generate_recipe, generate_recipes_by_ingredients,
                            generate_daily_recipe, generate_recipe_history, generate_drink_pairings,
                            generate_chef_advice, generate_seo_description, generate_telegram_posts, clean_question,
                            extract_keywords, adapt_recipe_for_diet, replace_recipe_ingredients, adjust_recipe_portions)
from models import (RecipeRequest, RecipeResponse, RecipeByIngredientsRequest, DietAdaptationRequest,
                    IngredientReplacementRequest, PortionAdjustmentRequest, RecipeHistoryRequest,
                    RecipeHistoryResponse, DrinkPairingResponse, ChefAdvice, SEODescription, DjangoAuthRequest,
                    DjangoAuthResponse, TelegramPostRequest, TelegramPostsResponse)

load_dotenv()

# Создаем таблицы при запуске
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Backend", description="""
    API для генерации текста, изображений и рецептов с использованием Google Gemini.
    
    ## Аутентификация
    Все эндпоинты (кроме /health и /docs) требуют API ключ в заголовке X-API-Key.
    
    ## Особенности
    * При генерации рецептов используются последние 50 рецептов как контекст
    * Рецепты не сохраняются в БД
    * Рецепт дня генерируется случайным образом
    """, version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
    allow_headers=["*"], )


class TextRequest(BaseModel):
    prompt: str


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.url.path not in ["/health", "/docs", "/redoc", "/openapi.json", "/api/v1/auth/token",
                                "/api/v1/recipes/generate-random"]:
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != settings.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
    response = await call_next(request)
    return response


@app.get("/health", tags=["Системные"])
async def health_check():
    """
    Проверка работоспособности сервиса.
    
    Returns:
        dict: Статус сервиса
    """
    return {"status": "healthy"}


@app.get("/", tags=["Системные"])
async def root():
    """
    Корневой эндпоинт для проверки доступности API.
    
    Returns:
        dict: Приветственное сообщение
    """
    return {"message": "API is working"}


@app.post("/generate", tags=["Генерация"])
async def generate(request: TextRequest, api_key: str = Depends(verify_api_key)):
    """
    Генерация текста с помощью Gemini.
    
    Args:
        request (TextRequest): Запрос с текстовым промптом
        
    Returns:
        dict: Сгенерированный текст
        
    Raises:
        HTTPException: При ошибке генерации
    """
    try:
        response = await generate_text(request.prompt)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


logger = logging.getLogger(__name__)


@app.post("/generate-image", tags=["Генерация"])
async def generate_image_endpoint(request: TextRequest, api_key: str = Depends(verify_api_key)):
    """
    Генерация изображения с помощью Gemini.
    
    Особенности:
    - Использует модель gemini-2.0-flash-preview-image-generation
    - Поддерживает генерацию изображений по текстовому описанию
    - Возвращает изображение в формате PNG
    - Имеет встроенную защиту от нежелательного контента
    
    Args:
        request (TextRequest): Запрос с параметрами:
            - prompt (str): Текстовое описание желаемого изображения
        api_key (str): API ключ для аутентификации
            
    Returns:
        Response: Сгенерированное изображение в формате PNG
        
    Raises:
        HTTPException: При ошибке генерации или блокировке контента
        
    Примеры запросов:
        ```json
        {
            "prompt": "Красивый пирог с яблоками на белой тарелке"
        }
        ```
        
        ```json
        {
            "prompt": "3D модель свиньи с крыльями и цилиндром, летящей над футуристическим городом"
        }
        ```
    """
    try:
        image_data = await generate_image(request.prompt)
        logger.debug(f"Image data size: {len(image_data)}")

        return Response(content=image_data, media_type="image/png",
            headers={"Content-Length": str(len(image_data)), "Cache-Control": "no-cache"})
    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/generate-by-text", response_model=RecipeResponse, tags=["Рецепты"])
async def generate_recipe_endpoint(request: RecipeRequest, api_key: str = Depends(verify_api_key),
        db: Session = Depends(get_db)):
    """
    Генерация рецепта по текстовому описанию с помощью Gemini.
    
    Args:
        request (RecipeRequest): Запрос с параметрами:
            - prompt (str): Текстовое описание желаемого рецепта
            - cooking_time (int, optional): Желаемое время приготовления в минутах
            - difficulty (str, optional): Желаемая сложность рецепта
        api_key (str): API ключ для аутентификации
        db (Session): Сессия БД для получения контекста
            
    Returns:
        RecipeResponse: Сгенерированный рецепт
    """
    try:
        recipe = await generate_recipe(prompt=request.prompt, cooking_time=request.cooking_time,
            difficulty=request.difficulty, db=db)
        return recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/generate-by-ingredients", response_model=List[RecipeResponse], tags=["Рецепты"])
async def generate_recipes_by_ingredients_endpoint(request: RecipeByIngredientsRequest,
        api_key: str = Depends(verify_api_key), db: Session = Depends(get_db)):
    """
    Генерация рецептов по списку ингредиентов.
    
    Args:
        request (RecipeByIngredientsRequest): Запрос с параметрами:
            - ingredients (List[Ingredient]): Список ингредиентов
            - count (int): Количество рецептов для генерации
            - cooking_time (int, optional): Желаемое время приготовления
            - difficulty (str, optional): Желаемая сложность
        api_key (str): API ключ для аутентификации
        db (Session): Сессия БД для получения контекста
            
    Returns:
        List[RecipeResponse]: Список сгенерированных рецептов
    """
    try:
        recipes = await generate_recipes_by_ingredients(request, db)
        return recipes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/recipes/daily-themed", response_model=RecipeResponse, tags=["Рецепты"])
async def get_daily_recipe(days_not_shown: int = 7, api_key: str = Depends(verify_api_key),
        db: Session = Depends(get_db)):
    """
    Получение рецепта дня.
    
    Args:
        days_not_shown (int): Количество дней, в течение которых рецепт не должен показываться
        api_key (str): API ключ для аутентификации
        db (Session): Сессия БД для получения контекста
            
    Returns:
        RecipeResponse: Рецепт дня
    """
    try:
        recipe = await generate_daily_recipe(db, days_not_shown)
        return recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/adapt", response_model=RecipeResponse, tags=["Рецепты"])
async def adapt_recipe(request: DietAdaptationRequest, api_key: str = Depends(verify_api_key),
        db: Session = Depends(get_db)):
    """
    Адаптация рецепта под диетические ограничения.
    
    Особенности:
    - Анализирует исходный рецепт
    - Учитывает диетические ограничения
    - Заменяет неподходящие ингредиенты
    - Адаптирует процесс приготовления
    
    Args:
        request (DietAdaptationRequest): Запрос с параметрами:
            - recipe (RecipeResponse): Исходный рецепт
            - dietary_restrictions (List[str]): Список ограничений
            - additional_requirements (str, optional): Доп. требования
        api_key (str): API ключ для аутентификации
        db (Session): Сессия БД
            
    Returns:
        RecipeResponse: Адаптированный рецепт
        
    Raises:
        HTTPException: При ошибке адаптации
    """
    try:
        recipe = await adapt_recipe_for_diet(request, db)
        return recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/replace-ingredients", response_model=RecipeResponse, tags=["Рецепты"])
async def replace_ingredients(request: IngredientReplacementRequest, api_key: str = Depends(verify_api_key),
        db: Session = Depends(get_db)):
    """
    Замена ингредиентов в рецепте.
    
    Особенности:
    - Анализирует совместимость замен
    - Корректирует пропорции
    - Адаптирует процесс приготовления
    - Учитывает вкусовые сочетания
    
    Args:
        request (IngredientReplacementRequest): Запрос с параметрами:
            - recipe (RecipeResponse): Исходный рецепт
            - replacements (List[IngredientReplacement]): Список замен
            - additional_notes (str, optional): Доп. заметки
        api_key (str): API ключ для аутентификации
        db (Session): Сессия БД
            
    Returns:
        RecipeResponse: Рецепт с замененными ингредиентами
        
    Raises:
        HTTPException: При ошибке замены ингредиентов
    """
    try:
        recipe = await replace_recipe_ingredients(request, db)
        return recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/adjust-portions", response_model=RecipeResponse, tags=["Рецепты"])
async def adjust_portions(request: PortionAdjustmentRequest, api_key: str = Depends(verify_api_key)):
    """
    Корректировка количества порций в рецепте.
    
    Особенности:
    - Пересчитывает количество ингредиентов
    - Сохраняет пропорции
    - Адаптирует время приготовления
    - Корректирует сложность
    
    Args:
        request (PortionAdjustmentRequest): Запрос с параметрами:
            - recipe (RecipeResponse): Исходный рецепт
            - target_portions (int): Целевое количество порций
            - original_portions (int, optional): Исходное количество порций
        api_key (str): API ключ для аутентификации
            
    Returns:
        RecipeResponse: Рецепт с новым количеством порций
        
    Raises:
        HTTPException: При ошибке корректировки порций
    """
    try:
        recipe = await adjust_recipe_portions(request)
        return recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/history", response_model=RecipeHistoryResponse, tags=["Рецепты"])
async def generate_recipe_history_endpoint(request: RecipeHistoryRequest, api_key: str = Depends(verify_api_key)):
    """
    Генерация истории происхождения рецепта.
    
    Особенности:
    - Анализирует происхождение блюда
    - Собирает интересные факты
    - Описывает культурное значение
    - Учитывает региональные особенности
    
    Args:
        request (RecipeHistoryRequest): Запрос с параметрами:
            - recipe (RecipeResponse): Рецепт для анализа
            - additional_context (str, optional): Доп. контекст
        api_key (str): API ключ для аутентификации
            
    Returns:
        RecipeHistoryResponse: История рецепта, факты и культурное значение
        
    Raises:
        HTTPException: При ошибке генерации истории
    """
    try:
        history = await generate_recipe_history(request.recipe, request.additional_context)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/drink-pairings", response_model=DrinkPairingResponse, tags=["Рецепты"])
async def generate_drink_pairings_endpoint(request: RecipeHistoryRequest, api_key: str = Depends(verify_api_key)):
    """
    Подбор напитков к блюду.
    
    Особенности:
    - Анализирует вкусовой профиль блюда
    - Учитывает сезонность
    - Предлагает различные типы напитков
    - Объясняет причины сочетания
    
    Args:
        request (RecipeHistoryRequest): Запрос с параметрами:
            - recipe (RecipeResponse): Рецепт для анализа
            - additional_context (str, optional): Доп. контекст
        api_key (str): API ключ для аутентификации
            
    Returns:
        DrinkPairingResponse: Список рекомендуемых напитков и общие рекомендации
        
    Raises:
        HTTPException: При ошибке подбора напитков
    """
    try:
        pairings = await generate_drink_pairings(request.recipe, request.additional_context)
        return pairings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/chef-advice", response_model=ChefAdvice, tags=["Рецепты"])
async def generate_chef_advice_endpoint(request: RecipeHistoryRequest, api_key: str = Depends(verify_api_key)):
    """
    Генерация профессиональных советов по приготовлению.
    
    Особенности:
    - Предоставляет советы по приготовлению
    - Предлагает вариации рецепта
    - Предупреждает о возможных ошибках
    - Дает рекомендации по подаче
    
    Args:
        request (RecipeHistoryRequest): Запрос с параметрами:
            - recipe (RecipeResponse): Рецепт для анализа
            - additional_context (str, optional): Доп. контекст
        api_key (str): API ключ для аутентификации
            
    Returns:
        ChefAdvice: Советы шеф-повара, вариации, ошибки и рекомендации по подаче
        
    Raises:
        HTTPException: При ошибке генерации советов
    """
    try:
        advice = await generate_chef_advice(request.recipe, request.additional_context)
        return advice
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/seo-description", response_model=SEODescription, tags=["Рецепты"])
async def generate_seo_description_endpoint(request: RecipeHistoryRequest, api_key: str = Depends(verify_api_key)):
    """
    Генерация SEO-оптимизированного описания рецепта.
    
    Особенности:
    - Создает оптимизированный заголовок
    - Генерирует meta-описание
    - Подбирает ключевые слова
    - Формирует полное SEO-описание
    
    Args:
        request (RecipeHistoryRequest): Запрос с параметрами:
            - recipe (RecipeResponse): Рецепт для анализа
            - additional_context (str, optional): Доп. контекст
        api_key (str): API ключ для аутентификации
            
    Returns:
        SEODescription: SEO-оптимизированное описание рецепта
        
    Raises:
        HTTPException: При ошибке генерации SEO-описания
    """
    try:
        seo = await generate_seo_description(request.recipe, request.additional_context)
        return seo
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/auth/token", response_model=DjangoAuthResponse, tags=["Аутентификация"])
async def get_auth_token(request: DjangoAuthRequest):
    """
    Получение токена авторизации через Django backend.
    
    Args:
        request (DjangoAuthRequest): Запрос с параметрами:
            - email (str): Электронная почта пользователя
            - password (str): Пароль пользователя
            
    Returns:
        DjangoAuthResponse: JWT токен авторизации
        
    Raises:
        HTTPException: При ошибке авторизации
    """
    try:
        response = requests.post(settings.DJANGO_AUTH_URL, json={"email": request.email, "password": request.password})

        if response.status_code == 200:
            return DjangoAuthResponse(auth_token=response.json()["auth_token"])
        else:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/recipes/generate-random", response_model=RecipeResponse, tags=["Рецепты"])
async def generate_random_recipe(request: DjangoAuthRequest, db: Session = Depends(get_db)):
    try:
        auth_response = requests.post(settings.DJANGO_AUTH_URL, json={"email": request.email, "password": request.password})

        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        auth_token = auth_response.json()["auth_token"]

        tags_response = requests.get(f"{settings.DJANGO_API_URL}tags/", headers={"Authorization": f"Token {auth_token}"})
        if tags_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Ошибка при получении тегов")
        tags = tags_response.json()
        if not tags:
            raise HTTPException(status_code=500, detail="Нет доступных тегов")

        ingredients_response = requests.get(f"{settings.DJANGO_API_URL}ingredients/",
            headers={"Authorization": f"Token {auth_token}"})
        if ingredients_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Ошибка при получении ингредиентов")
        existing_ingredients = ingredients_response.json()

        name_prompt = "Придумай оригинальное название блюда в формате: 'Название блюда'"
        name = await generate_text(name_prompt)

        recipe = await generate_recipe(prompt=name, db=db)

        image_data = await generate_image(recipe.image_generation_prompt)

        recipe_ingredients = []
        for ing in recipe.ingredients:
            existing_ing = next((i for i in existing_ingredients if i["name"].lower() == ing.name.lower()), None)

            if existing_ing:
                recipe_ingredients.append({"id": existing_ing["id"], "amount": float(ing.amount)})
            else:
                new_ing_response = requests.post(f"{settings.DJANGO_API_URL}ingredients/",
                    json={"name": ing.name, "measurement_unit": ing.unit},
                    headers={"Authorization": f"Token {auth_token}"})

                if new_ing_response.status_code != 201:
                    raise HTTPException(status_code=500,
                                        detail=f"Ошибка при создании ингредиента: {new_ing_response.text}")

                new_ing = new_ing_response.json()
                recipe_ingredients.append({"id": new_ing["id"], "amount": float(ing.amount)})

        django_response = requests.post(f"{settings.DJANGO_API_URL}recipes/",
            json={"name": recipe.name, "text": recipe.description, "cooking_time": recipe.cooking_time,
                "ingredients": recipe_ingredients, "tags": [tags[0]["id"]],
                "image": f"data:image/png;base64,{base64.b64encode(image_data).decode()}", "steps": recipe.steps},
            headers={"Authorization": f"Token {auth_token}"})

        if django_response.status_code != 201:
            raise HTTPException(status_code=500, detail=f"Ошибка при создании рецепта в Django: {django_response.text}")

        return recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/telegram/generate-posts", response_model=TelegramPostsResponse, tags=["Телеграм"])
async def generate_telegram_posts_endpoint(request: TelegramPostRequest, api_key: str = Depends(verify_api_key)):
    """
    Генерация постов для телеграм канала по всем тематикам.
    
    Особенности:
    - Генерирует посты по 12 категориям
    - Учитывает существующие рецепты и комментарии
    - Адаптирует рецепты под разные диеты
    - Добавляет хештеги и эмодзи
    
    Категории постов:
    - Рецепт дня
    - Советы шефа
    - Винная пара
    - Диетическая версия
    - Из ингредиентов
    - История блюда
    - Без аллергенов
    - Веганская кухня
    - Вегетарианская кухня
    - Безглютеновая кухня
    - Низкокалорийная версия
    - Детская кухня
    
    Args:
        request (TelegramPostRequest): Запрос с параметрами:
            - count (int, optional): Количество постов (по умолчанию 1)
            - include_comments (bool, optional): Включать ли комментарии (по умолчанию True)
            - include_recipes (bool, optional): Включать ли рецепты (по умолчанию True)
            - max_length (int, optional): Максимальная длина поста (по умолчанию 2500)
            - email (str): Email для авторизации в Django
            - password (str): Пароль для авторизации в Django
        api_key (str): API ключ для аутентификации
            
    Returns:
        TelegramPostsResponse: Сгенерированные посты со следующей структурой:
            - title (str): Заголовок поста
            - content (str): Содержание поста
            - hashtags (List[str]): Список хештегов
            - recipe_id (Optional[int]): ID рецепта
            - comment_id (Optional[int]): ID комментария
            - category (str): Категория поста
            - recipe_variations (Optional[List[str]]): Вариации рецепта
            - related_recipes (Optional[List[int]]): ID связанных рецептов
            - dietary_type (Optional[str]): Тип диеты
            - allergen_free (Optional[List[str]]): Исключенные аллергены
            - ingredient_replacements (Optional[List[IngredientReplacement]]): Замены ингредиентов
        
    Raises:
        HTTPException: При ошибке генерации или авторизации
        
    Пример запроса:
        ```json
        {
            "count": 2,
            "include_comments": true,
            "include_recipes": true,
            "max_length": 2500,
            "email": "user@example.com",
            "password": "password123"
        }
        ```
    """
    try:
        auth_response = requests.post(settings.DJANGO_AUTH_URL, json={"email": request.email, "password": request.password})

        if auth_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Неверные учетные данные")

        auth_token = auth_response.json()["auth_token"]

        posts = await generate_telegram_posts(count=request.count, include_comments=request.include_comments,
            include_recipes=request.include_recipes, max_length=request.max_length, auth_token=auth_token)
        return TelegramPostsResponse(posts=posts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Конфигурация Qdrant
QDRANT_CONFIG = {'url': os.getenv('QDRANT_URL', 'http://localhost:6333'), 'api_key': os.getenv('QDRANT_API_KEY', None)}

EMBEDDING_MODEL_NAME = os.getenv('EMBEDDING_MODEL_NAME', 'ai-forever/sbert_large_nlu_ru')


class QuestionRequest(BaseModel):
    question: str = Field(..., description="Вопрос пользователя")


class QuestionResponse(BaseModel):
    answer: str = Field(..., description="Ответ на вопрос")
    relevant_recipes: List[dict] = Field(..., description="Релевантные рецепты")


@app.post("/api/v1/recipes/ask", response_model=QuestionResponse, tags=["Рецепты"])
async def ask_question(request: QuestionRequest, api_key: str = Depends(verify_api_key)):
    try:
        logger.debug(f"Получен вопрос: {request.question}")

        cleaned = await clean_question(request.question)
        logger.debug(f"Очищенный вопрос: {cleaned.model_dump()}")

        keywords_data = await extract_keywords(cleaned.cleaned_question)
        logger.debug(f"Извлеченные ключевые слова: {keywords_data.model_dump()}")

        qdrant_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

        all_recipes = []
        search_terms = keywords_data.keywords + keywords_data.categories
        logger.debug(f"Поисковые термины: {search_terms}")

        for term in search_terms:
            try:
                term_vector = model.encode(term).tolist()

                search_result = qdrant_client.search(collection_name="recipes", query_vector=term_vector, limit=10,
                    query_filter={"should": [{"key": "ingredients", "match": {"text": term}},
                        {"key": "name", "match": {"text": term}}, {"key": "text", "match": {"text": term}},
                        {"key": "tags", "match": {"text": term}}]}, score_threshold=0.1)

                for hit in search_result:
                    recipe = hit.payload
                    score = hit.score

                    if term.lower() in [i.lower() for i in recipe.get('ingredients', [])]:
                        score *= 1.5
                    if term.lower() in recipe.get('name', '').lower():
                        score *= 1.3
                    if term.lower() in recipe.get('text', '').lower():
                        score *= 1.2

                    recipe['relevance_score'] = score
                    all_recipes.append(recipe)

            except Exception as e:
                logger.error(f"Ошибка при поиске по термину {term}: {e}")
                continue

        all_recipes.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        unique_recipes = []
        seen_ids = set()
        for recipe in all_recipes:
            if recipe['id'] not in seen_ids:
                seen_ids.add(recipe['id'])
                unique_recipes.append(recipe)
            else:
                existing_recipe = next(r for r in unique_recipes if r['id'] == recipe['id'])
                if recipe.get('relevance_score', 0) > existing_recipe.get('relevance_score', 0):
                    existing_recipe['relevance_score'] = recipe['relevance_score']

        logger.debug(f"Найдено уникальных рецептов: {len(unique_recipes)}")

        if not unique_recipes:
            return QuestionResponse(answer="К сожалению, я не нашел подходящих рецептов для ответа на ваш вопрос.",
                relevant_recipes=[])

        recipes_context = "\n\n".join([f"Рецепт {i + 1}:\n"
                                       f"Название: {recipe['name']}\n"
                                       f"Описание: {recipe['text']}\n"
                                       f"Ингредиенты:\n" + "\n".join(
            [f"- {ing}: {amount} {unit}" for ing, amount, unit in
                zip(recipe['ingredients'], recipe.get('amounts', [0] * len(recipe['ingredients'])),
                    recipe.get('units', [''] * len(recipe['ingredients'])))]) + f"\nТеги: {', '.join(recipe['tags'])}"
            for i, recipe in enumerate(unique_recipes[:3])])

        prompt = f"""
        Вопрос пользователя: {cleaned.cleaned_question}
        Намерение: {cleaned.intent}
        Тип поиска: {keywords_data.search_type}
        
        Информация из рецептов:
        {recipes_context}
        
        ВАЖНО: 
        2. НЕ генерируй новые рецепты
        4. Если нужно адаптировать порции - используй пропорции из существующего рецепта
        5. При расчете пищевой ценности используй стандартные значения:
           - Белки: 4 ккал/г
           - Жиры: 9 ккал/г
           - Углеводы: 4 ккал/г
        6. При адаптации рецепта сохраняй пропорции ингредиентов
        
        Ответь на вопрос пользователя, используя информацию из рецептов.
        """

        logger.debug(f"Отправка промпта в LLM: {prompt}")

        response = await generate_text(prompt)
        logger.debug(f"Получен ответ от LLM: {response}")

        return QuestionResponse(answer=response, relevant_recipes=unique_recipes[:3])
    except Exception as e:
        logger.error(f"Ошибка в эндпоинте ask_question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Произошла ошибка при обработке вопроса: {str(e)}")
