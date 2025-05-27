import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Type

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from .config import settings
from models import RecipeResponse, GeneratedRecipe, RecipeByIngredientsRequest, RecipesResponse, \
    RecipeHistoryResponse, DrinkPairingResponse, ChefAdvice, SEODescription, TelegramPost, TelegramPostsResponse, \
    CleanedQuestion, Keywords, DietAdaptationRequest, IngredientReplacementRequest, \
    PortionAdjustmentRequest

load_dotenv()

client = genai.Client(api_key=settings.GEMINI_API_KEY)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def calculate_fingerprint(recipe_data: dict) -> str:
    """Рассчитывает fingerprint рецепта на основе его данных"""
    # Сортируем данные для консистентности
    sorted_data = json.dumps(recipe_data, sort_keys=True)
    # Создаем хеш
    return hashlib.md5(sorted_data.encode()).hexdigest()


def find_similar_recipe(db: Session, prompt: str, cooking_time: int = None, difficulty: str = None) -> List[
    GeneratedRecipe]:
    """Получение последних 50 рецептов из БД"""
    return db.query(GeneratedRecipe).order_by(GeneratedRecipe.created_at.desc()).limit(50).all()


async def generate_text(prompt: str) -> str:
    try:
        response = await client.aio.models.generate_content(model='gemini-2.5-flash-preview-05-20', contents=prompt)
        return response.text
    except Exception as e:
        raise Exception(f"Ошибка при генерации текста: {str(e)}")


async def generate_image(prompt: str) -> bytes:
    """
    Генерация изображения с помощью Gemini.
    
    Args:
        prompt (str): Текстовое описание желаемого изображения
        
    Returns:
        bytes: Бинарные данные изображения в формате PNG
        
    Raises:
        Exception: При ошибке генерации изображения
    """
    try:
        response = client.models.generate_content(model="gemini-2.0-flash-preview-image-generation",
            contents=[{"parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))

        if not response.candidates:
            raise Exception("Нет кандидатов в ответе")

        candidate = response.candidates[0]

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            block_msg = response.prompt_feedback.block_reason_message
            raise Exception(f"Генерация заблокирована: {block_reason} - {block_msg}")

        if not candidate.content or not candidate.content.parts:
            raise Exception("Нет частей контента в ответе")

        for part in candidate.content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                if not part.inline_data.data:
                    raise Exception("Нет данных изображения")

                try:
                    # Пробуем декодировать base64
                    image_data = base64.b64decode(part.inline_data.data)
                    return image_data
                except Exception as e:
                    logger.error(f"Ошибка декодирования base64: {e}")
                    # Если не base64, возвращаем как есть
                    return part.inline_data.data

        raise Exception("Изображение не было сгенерировано")

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        raise Exception(f"Ошибка при генерации изображения: {str(e)}")


async def generate_recipe(prompt: str, cooking_time: int = None, difficulty: str = None, db: Session = None,
        response_schema: Optional[Type[BaseModel]] = None) -> RecipeResponse:
    try:
        # Получаем последние 50 рецептов для контекста
        context_recipes = []
        if db:
            context_recipes = find_similar_recipe(db, prompt, cooking_time, difficulty)
            context_recipes = [RecipeResponse(**recipe.recipe_data) for recipe in context_recipes]

        recipe_prompt = f"""
        Ты - шеф-повар. Сгенерируй рецепт на основе запроса: "{prompt}"
        {f'Время приготовления должно быть {cooking_time} минут' if cooking_time else ''}
        {f'Сложность должна быть {difficulty}' if difficulty else ''}
        
        Рецепт должен содержать:
        1. Название блюда
        2. Описание блюда
        3. Список ингредиентов с точными количествами и единицами измерения
        4. Пошаговые инструкции приготовления (минимум 5 шагов)
        5. Время приготовления
        6. Сложность - easy, medium, hard
        7. Промпт для генерации изображения
        
        Важно: 
        - названия всех ингредиентов должны быть с маленькой буквы

        
        Также сгенерируй детальный промпт для создания фотографии этого блюда. 
        Промпт должен описывать внешний вид, подачу, освещение и стиль фотографии.
        
        Вот список последних сгенерированных рецептов, чтобы избежать повторений:
        {[recipe.model_dump() for recipe in context_recipes]}
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=recipe_prompt,
            config={"response_mime_type": "application/json", "response_schema": response_schema or RecipeResponse})

        print("Gemini response:", response.text)
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при генерации рецепта: {str(e)}")


async def generate_recipes_by_ingredients(request: RecipeByIngredientsRequest, db: Session = None) -> List[
    RecipeResponse]:
    """Генерация рецептов по списку ингредиентов"""
    try:
        # Формируем список ингредиентов для промпта
        ingredients_list = []
        for ing in request.ingredients:
            ing_str = ing.name.lower()
            if ing.amount and ing.unit:
                ing_str += f" {ing.amount} {ing.unit}"
            ingredients_list.append(ing_str)

        ingredients_str = ", ".join(ingredients_list)

        # Формируем промпт
        prompt = f"""
        Ты - шеф-повар. Сгенерируй {request.count} рецептов, используя следующие ингредиенты: {ingredients_str}
        {f'Время приготовления должно быть {request.cooking_time} минут' if request.cooking_time else ''}
        {f'Сложность должна быть {request.difficulty}' if request.difficulty else ''}
        
        Важно: 
        1. для каждого ингредиента обязательно укажи точное количество и единицу измерения (граммы, миллилитры, штуки и т.д.)
        2. названия всех ингредиентов должны быть с маленькой буквы
        
        Для каждого рецепта также сгенерируй детальный промпт для создания фотографии этого блюда.
        Промпт должен описывать внешний вид, подачу, освещение и стиль фотографии.
        """

        # Генерируем рецепты
        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": RecipesResponse})

        print("Gemini response:", response.text)
        recipes_response = response.parsed

        # Сохраняем рецепты в БД
        if db:
            for recipe in recipes_response.recipes:
                recipe_dict = recipe.model_dump()
                fingerprint = calculate_fingerprint(recipe_dict)

                db_recipe = GeneratedRecipe(fingerprint=fingerprint, recipe_data=recipe_dict, prompt=ingredients_str)
                db.add(db_recipe)
            db.commit()

        return recipes_response.recipes
    except Exception as e:
        raise Exception(f"Ошибка при генерации рецептов: {str(e)}")


async def generate_daily_recipe(db: Session, days_not_shown: int = 7) -> RecipeResponse:
    """Генерация рецепта дня"""
    try:
        # Ищем рецепт, который не показывался последние N дней
        not_shown_date = datetime.now() - timedelta(days=days_not_shown)
        recipe = db.query(GeneratedRecipe).filter(
            or_(GeneratedRecipe.last_shown_at == None, GeneratedRecipe.last_shown_at < not_shown_date)).order_by(
            func.random()).first()

        # Если нашли подходящий рецепт
        if recipe:
            # Обновляем дату последнего показа
            recipe.last_shown_at = datetime.now()
            db.commit()
            return RecipeResponse(**recipe.recipe_data)

        # Если не нашли, генерируем новый
        prompt = """
        Сгенерируй интересный рецепт дня. Это должно быть что-то особенное и вдохновляющее.
        
        Важно: для каждого ингредиента обязательно укажи точное количество и единицу измерения (граммы, миллилитры, штуки и т.д.)
        
        Также сгенерируй детальный промпт для создания фотографии этого блюда.
        Промпт должен описывать внешний вид, подачу, освещение и стиль фотографии.
        """
        recipe = await generate_recipe(prompt, db=db)

        # Обновляем дату последнего показа
        db_recipe = db.query(GeneratedRecipe).filter(
            GeneratedRecipe.fingerprint == calculate_fingerprint(recipe.model_dump())).first()
        if db_recipe:
            db_recipe.last_shown_at = datetime.now()
            db.commit()

        return recipe
    except Exception as e:
        raise Exception(f"Ошибка при генерации рецепта дня: {str(e)}")


async def generate_recipe_history(recipe: RecipeResponse,
        additional_context: Optional[str] = None) -> RecipeHistoryResponse:
    """Генерация истории и фактов о блюде"""
    try:
        prompt = f"""
        Расскажи историю и интересные факты о блюде на основе его рецепта:
        
        Название: {recipe.name}
        Описание: {recipe.description}
        Ингредиенты: {[f"{ing.name} {ing.amount} {ing.unit}" for ing in recipe.ingredients]}
        {f'Дополнительный контекст: {additional_context}' if additional_context else ''}
        
        Включи:
        1. Историю происхождения блюда
        2. 3-5 интересных фактов
        3. Культурное значение блюда
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": RecipeHistoryResponse})
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при генерации истории блюда: {str(e)}")


async def generate_drink_pairings(recipe: RecipeResponse,
        additional_context: Optional[str] = None) -> DrinkPairingResponse:
    """Генерация рекомендаций по напиткам"""
    try:
        prompt = f"""
        Предложи напитки, которые хорошо сочетаются с блюдом:
        
        Название: {recipe.name}
        Описание: {recipe.description}
        Ингредиенты: {[f"{ing.name} {ing.amount} {ing.unit}" for ing in recipe.ingredients]}
        {f'Дополнительный контекст: {additional_context}' if additional_context else ''}
        
        Включи:
        1. 3-5 рекомендуемых напитков с описанием
        2. Причины, почему они хорошо сочетаются с блюдом
        3. Общие рекомендации по выбору напитков
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": DrinkPairingResponse})
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при генерации рекомендаций по напиткам: {str(e)}")


async def generate_chef_advice(recipe: RecipeResponse, additional_context: Optional[str] = None) -> ChefAdvice:
    """Генерация советов от шеф-повара"""
    try:
        prompt = f"""
        Дай профессиональные советы по приготовлению блюда:
        
        Название: {recipe.name}
        Описание: {recipe.description}
        Ингредиенты: {[f"{ing.name} {ing.amount} {ing.unit}" for ing in recipe.ingredients]}
        Шаги приготовления: {recipe.steps}
        {f'Дополнительный контекст: {additional_context}' if additional_context else ''}
        
        Включи:
        1. Советы по приготовлению
        2. Вариации рецепта
        3. Распространенные ошибки
        4. Рекомендации по подаче
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": ChefAdvice})
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при генерации советов шеф-повара: {str(e)}")


async def generate_seo_description(recipe: RecipeResponse, additional_context: Optional[str] = None) -> SEODescription:
    """Генерация SEO-описания"""
    try:
        prompt = f"""
        Создай SEO-оптимизированное описание для блюда:
        
        Название: {recipe.name}
        Описание: {recipe.description}
        Ингредиенты: {[f"{ing.name} {ing.amount} {ing.unit}" for ing in recipe.ingredients]}
        Шаги приготовления: {recipe.steps}
        {f'Дополнительный контекст: {additional_context}' if additional_context else ''}
        
        Включи:
        1. SEO-оптимизированный заголовок
        2. Meta-описание
        3. Ключевые слова
        4. Полное SEO-описание
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": SEODescription})
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при генерации SEO-описания: {str(e)}")


async def adapt_recipe_for_diet(request: DietAdaptationRequest, db: Session = None) -> RecipeResponse:
    """Адаптация рецепта под диетические ограничения"""
    try:
        prompt = f"""
        Адаптируй рецепт под следующие диетические ограничения: {', '.join(request.dietary_restrictions)}
        {f'Дополнительные требования: {request.additional_requirements}' if request.additional_requirements else ''}
        
        Исходный рецепт:
        Название: {request.recipe.name}
        Описание: {request.recipe.description}
        Ингредиенты: {[f"{ing.name} {ing.amount} {ing.unit}" for ing in request.recipe.ingredients]}
        Шаги приготовления: {request.recipe.steps}
        
        Правила адаптации:
        1. Замени неподходящие ингредиенты на диетические аналоги
        2. Сохрани пропорции и вкусовые качества
        3. Адаптируй процесс приготовления если нужно
        4. Укажи точные количества и единицы измерения
        5. Названия ингредиентов должны быть с маленькой буквы
        
        Также сгенерируй детальный промпт для создания фотографии адаптированного блюда.
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": RecipeResponse})
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при адаптации рецепта: {str(e)}")


async def replace_recipe_ingredients(request: IngredientReplacementRequest, db: Session = None) -> RecipeResponse:
    """Замена ингредиентов в рецепте"""
    try:
        prompt = f"""
        Замени ингредиенты в рецепте согласно списку замен:
        
        Исходный рецепт:
        Название: {request.recipe.name}
        Описание: {request.recipe.description}
        Ингредиенты: {[f"{ing.name} {ing.amount} {ing.unit}" for ing in request.recipe.ingredients]}
        Шаги приготовления: {request.recipe.steps}
        
        Замены:
        {[f"- {rep.original} -> {rep.replacement} {rep.amount if rep.amount else ''} {rep.unit if rep.unit else ''}" for rep in request.replacements]}
        
        {f'Дополнительные заметки: {request.additional_notes}' if request.additional_notes else ''}
        
        Правила замены:
        1. Сохрани пропорции и вкусовые качества
        2. Адаптируй процесс приготовления если нужно
        3. Укажи точные количества и единицы измерения
        4. Названия ингредиентов должны быть с маленькой буквы
        
        Также сгенерируй детальный промпт для создания фотографии блюда с новыми ингредиентами.
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": RecipeResponse})
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при замене ингредиентов: {str(e)}")


async def adjust_recipe_portions(request: PortionAdjustmentRequest) -> RecipeResponse:
    """Корректировка количества порций в рецепте"""
    try:
        prompt = f"""
        Скорректируй рецепт для {request.target_portions} порций.
        
        Исходный рецепт:
        Название: {request.recipe.name}
        Описание: {request.recipe.description}
        Ингредиенты: {[f"{ing.name} {ing.amount} {ing.unit}" for ing in request.recipe.ingredients]}
        Шаги приготовления: {request.recipe.steps}
        Время приготовления: {request.recipe.cooking_time} минут
        Сложность: {request.recipe.difficulty}
        
        Правила корректировки:
        1. Пересчитай количество каждого ингредиента пропорционально
        2. Сохрани пропорции между ингредиентами
        3. Адаптируй время приготовления если нужно
        4. Укажи точные количества и единицы измерения
        5. Названия ингредиентов должны быть с маленькой буквы
        
        Также сгенерируй детальный промпт для создания фотографии блюда.
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": RecipeResponse})
        return response.parsed
    except Exception as e:
        raise Exception(f"Ошибка при корректировке порций: {str(e)}")


async def get_recipes_from_django(limit: int = 50, auth_token: str = None) -> List[dict]:
    """Получение рецептов через Django API"""
    try:
        response = requests.get(f"{settings.DJANGO_API_URL}recipes/", 
            headers={"Authorization": f"Token {auth_token or settings.DJANGO_AUTH_TOKEN}"},
            params={"limit": limit})
        if response.status_code == 200:
            return response.json().get("results", [])
        logger.error(f"Ошибка при получении рецептов: {response.status_code} - {response.text}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении рецептов: {e}")
        return []


async def get_comments_from_django(limit: int = 50, auth_token: str = None) -> List[dict]:
    """Получение комментариев через Django API"""
    try:
        # Получаем комментарии через эндпоинт рецептов
        recipes = await get_recipes_from_django(limit, auth_token)
        comments = []
        for recipe in recipes:
            recipe_id = recipe.get("id")
            if recipe_id:
                response = requests.get(f"{settings.DJANGO_API_URL}recipes/{recipe_id}/comments/",
                    headers={"Authorization": f"Token {auth_token}"})
                if response.status_code == 200:
                    comments.extend(response.json())
        return comments[:limit]
    except Exception as e:
        logger.error(f"Ошибка при получении комментариев: {e}")
        return []


async def generate_telegram_posts(count: int = 1, include_comments: bool = True, include_recipes: bool = True,
        max_length: int = 2500, auth_token: str = None) -> List[TelegramPost]:
    """Генерация постов для телеграм канала"""
    try:
        # Получаем рецепты и комментарии через Django API
        recipes = []
        comments = []

        if include_recipes:
            recipes = await get_recipes_from_django(auth_token=auth_token)
        if include_comments:
            comments = await get_comments_from_django(auth_token=auth_token)

        # Формируем промпт
        prompt = f"""
        Сгенерируй {count} постов для кулинарного телеграм канала.
        
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
        
        Правила:
        1. Заголовок должен быть привлекательным
        2. Контент должен быть подробным и информативным:
           - Для рецептов: описание, ингредиенты, пошаговая инструкция, советы
           - Для советов шефа: профессиональные рекомендации, секреты, техники
           - Для винных пар: описание напитков, причины сочетания, сервировка
           - Для диетических версий: замена ингредиентов, калорийность, польза
           - Для истории блюда: происхождение, традиции, интересные факты
        3. Добавь 3-5 хештегов
        4. Максимум {max_length} символов
        5. Используй эмодзи для разделения блоков текста
        6. Укажи ID рецепта/комментария если есть
        
        Для каждого рецепта укажи:
        - ID основного рецепта
        - ID связанных рецептов
        - Вариации рецепта
        - Тип диеты
        - Исключенные аллергены
        - Замены ингредиентов
        
        Рецепты для вдохновения: {recipes[:5]}
        Комментарии: {comments[:5]}
        """

        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": TelegramPostsResponse})

        return response.parsed.posts
    except Exception as e:
        logger.error(f"Ошибка при генерации постов: {e}")
        raise Exception(f"Ошибка при генерации постов: {str(e)}")


async def clean_question(question: str) -> CleanedQuestion:
    """Очистка вопроса с помощью Gemini"""
    try:
        prompt = f"""
        Очисти вопрос пользователя и определи его намерение.
        Вопрос: {question}
        
        Верни структурированный ответ с:
        1. Оригинальным вопросом
        2. Очищенным вопросом
        3. Намерением пользователя (поиск ингредиента/рецепта/техники)
        """

        logger.debug(f"Отправка запроса на очистку вопроса: {question}")
        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": CleanedQuestion})
        logger.debug(f"Получен ответ: {response.text}")
        return response.parsed
    except Exception as e:
        logger.error(f"Ошибка при очистке вопроса: {e}")
        return CleanedQuestion(original_question=question, cleaned_question=question, intent="unknown")


async def extract_keywords(question: str) -> Keywords:
    """Извлечение ключевых слов из вопроса"""
    try:
        prompt = f"""
        Извлеки ключевые слова и категории из вопроса для поиска рецептов.
        Вопрос: {question}
        
        Верни структурированный ответ с:
        1. Списком ключевых слов
        2. Категориями поиска (ингредиенты, техники, типы блюд)
        3. Типом поиска (ингредиент/рецепт/техника)
        """

        logger.debug(f"Отправка запроса на извлечение ключевых слов: {question}")
        response = await client.aio.models.generate_content(model='gemini-2.0-flash', contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": Keywords})
        logger.debug(f"Получен ответ: {response.text}")
        return response.parsed
    except Exception as e:
        logger.error(f"Ошибка при извлечении ключевых слов: {e}")
        return Keywords(keywords=[question], categories=[], search_type="unknown")
