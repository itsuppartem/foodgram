from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from database import Base
from datetime import datetime

class RecipeRequest(BaseModel):
    prompt: str = Field(..., description="Текстовый запрос для генерации рецепта")
    cooking_time: Optional[int] = Field(None, description="Время приготовления в минутах")
    difficulty: Optional[str] = Field(None, description="Сложность рецепта")

class IngredientRequest(BaseModel):
    name: str = Field(..., description="Название ингредиента")
    amount: Optional[float] = Field(None, description="Количество ингредиента")
    unit: Optional[str] = Field(None, description="Единица измерения")

class RecipeByIngredientsRequest(BaseModel):
    ingredients: List[IngredientRequest] = Field(..., description="Список ингредиентов")
    count: Optional[int] = Field(1, description="Количество рецептов для генерации")
    cooking_time: Optional[int] = Field(None, description="Желаемое время приготовления в минутах")
    difficulty: Optional[str] = Field(None, description="Желаемая сложность рецепта")

class Ingredient(BaseModel):
    name: str
    amount: float
    unit: str

class RecipeResponse(BaseModel):
    name: str
    description: str
    ingredients: List[Ingredient]
    steps: List[str] = Field(..., description="Шаги приготовления")
    cooking_time: int
    difficulty: str
    image_generation_prompt: str = Field(..., description="Промпт для генерации изображения блюда")

class RecipesResponse(BaseModel):
    recipes: List[RecipeResponse]

class GeneratedRecipe(Base):
    __tablename__ = "generated_recipes"

    id = Column(Integer, primary_key=True, index=True)
    fingerprint = Column(String, unique=True, index=True)
    recipe_data = Column(JSONB)
    prompt = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_shown_at = Column(DateTime(timezone=True), nullable=True)

class DietAdaptationRequest(BaseModel):
    recipe: RecipeResponse = Field(..., description="Исходный рецепт для адаптации")
    dietary_restrictions: List[str] = Field(..., description="Список диетических ограничений")
    additional_requirements: Optional[str] = Field(None, description="Дополнительные требования к адаптации")

class IngredientReplacement(BaseModel):
    original: str = Field(..., description="Исходный ингредиент")
    replacement: str = Field(..., description="Заменяющий ингредиент")
    amount: Optional[float] = Field(None, description="Количество")
    unit: Optional[str] = Field(None, description="Единица измерения")

class IngredientReplacementRequest(BaseModel):
    recipe: RecipeResponse = Field(..., description="Исходный рецепт")
    replacements: List[IngredientReplacement] = Field(..., description="Список замен ингредиентов")
    additional_notes: Optional[str] = Field(None, description="Дополнительные заметки по заменам")

class PortionAdjustmentRequest(BaseModel):
    recipe: RecipeResponse = Field(..., description="Исходный рецепт")
    target_portions: int = Field(..., description="Целевое количество порций")
    original_portions: Optional[int] = Field(4, description="Исходное количество порций")

class RecipeHistoryRequest(BaseModel):
    recipe: RecipeResponse = Field(..., description="Рецепт для генерации истории")
    additional_context: Optional[str] = Field(None, description="Дополнительный контекст")

class RecipeHistoryResponse(BaseModel):
    history: str = Field(..., description="История происхождения блюда")
    interesting_facts: List[str] = Field(..., description="Список интересных фактов")
    cultural_significance: Optional[str] = Field(None, description="Культурное значение блюда")

class DrinkPairing(BaseModel):
    name: str = Field(..., description="Название напитка")
    type: str = Field(..., description="Тип напитка (вино, коктейль и т.д.)")
    description: str = Field(..., description="Описание напитка")
    pairing_reason: str = Field(..., description="Причина сочетания с блюдом")

class DrinkPairingResponse(BaseModel):
    pairings: List[DrinkPairing] = Field(..., description="Список рекомендуемых напитков")
    general_advice: str = Field(..., description="Общие рекомендации по выбору напитков")

class ChefAdvice(BaseModel):
    tips: List[str] = Field(..., description="Советы по приготовлению")
    variations: List[str] = Field(..., description="Вариации рецепта")
    common_mistakes: List[str] = Field(..., description="Распространенные ошибки")
    serving_suggestions: List[str] = Field(..., description="Рекомендации по подаче")

class SEODescription(BaseModel):
    title: str = Field(..., description="SEO-оптимизированный заголовок")
    meta_description: str = Field(..., description="Meta-описание")
    keywords: List[str] = Field(..., description="Ключевые слова")
    full_description: str = Field(..., description="Полное SEO-описание")

class DjangoAuthRequest(BaseModel):
    email: str = Field(..., description="Email пользователя")
    password: str = Field(..., description="Пароль пользователя")

class DjangoAuthResponse(BaseModel):
    auth_token: str = Field(..., description="Токен авторизации Django")

class TelegramPostRequest(BaseModel):
    count: int = 1
    include_comments: bool = True
    include_recipes: bool = True
    max_length: int = 2500
    email: str
    password: str

class TelegramPost(BaseModel):
    title: str = Field(..., description="Заголовок поста")
    content: str = Field(..., description="Содержание поста")
    hashtags: List[str] = Field(..., description="Список хештегов")
    recipe_id: Optional[int] = Field(None, description="ID рецепта")
    comment_id: Optional[int] = Field(None, description="ID комментария")
    category: str = Field(..., description="Категория поста")
    recipe_variations: Optional[List[str]] = Field(None, description="Вариации рецепта")
    related_recipes: Optional[List[int]] = Field(None, description="ID связанных рецептов")
    dietary_type: Optional[str] = Field(None, description="Тип диеты")
    allergen_free: Optional[List[str]] = Field(None, description="Исключенные аллергены")
    ingredient_replacements: Optional[List[IngredientReplacement]] = Field(None, description="Замены ингредиентов")

class TelegramPostsResponse(BaseModel):
    posts: List[TelegramPost]

class QuestionRequest(BaseModel):
    question: str = Field(..., description="Вопрос пользователя")

class QuestionResponse(BaseModel):
    answer: str = Field(..., description="Ответ на вопрос")
    relevant_recipes: List[dict] = Field(..., description="Релевантные рецепты")

class Comment(BaseModel):
    id: int
    text: str
    author: str
    created_at: datetime

class CleanedQuestion(BaseModel):
    original_question: str = Field(..., description="Исходный вопрос")
    cleaned_question: str = Field(..., description="Очищенный вопрос")
    intent: str = Field(..., description="Намерение пользователя")

class Keywords(BaseModel):
    keywords: List[str] = Field(..., description="Список ключевых слов")
    categories: List[str] = Field(..., description="Категории поиска")
    search_type: str = Field(..., description="Тип поиска (ингредиент/рецепт/техника)") 