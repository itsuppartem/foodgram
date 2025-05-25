import pytest


class TestIngredients:
    @pytest.mark.django_db(transaction=True)
    def test_ingredient_list(self, ingredients_list):
        ingredient_1 = ingredients_list[0]
        ingredient_2 = ingredients_list[1]
        ingredient_3 = ingredients_list[2]

        assert (ingredient_1['id'] == 1), 'Проверьте, что id ингредиента создается правильно.'

        assert (ingredient_1['name'] == 'jija'), 'Проверьте, что имя ингредиента создается правильно.'

        assert (ingredient_1[
                    'measurement_unit'] == 'l'), 'Проверьте, что единица измерения ингредиента создается правильно.'

        assert (ingredient_2['id'] == 2), 'Проверьте, что id ингредиента создается правильно.'

        assert (ingredient_2['name'] == 'fingers'), 'Проверьте, что имя ингредиента создается правильно.'

        assert (ingredient_2[
                    'measurement_unit'] == 'kg'), 'Проверьте, что единица измерения ингредиента создается правильно.'

        assert (ingredient_3['id'] == 3), 'Проверьте, что id ингредиента создается правильно.'

        assert (ingredient_3['name'] == 'powder'), 'Проверьте, что имя ингредиента создается правильно.'

        assert (ingredient_3[
                    'measurement_unit'] == 'gr'), 'Проверьте, что единица измерения ингредиента создается правильно.'
