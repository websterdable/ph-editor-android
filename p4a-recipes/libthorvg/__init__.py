from pythonforandroid.recipe import Recipe

class LibThorvgRecipe(Recipe):
    name = 'libthorvg'
    version = '1.0.0'
    # Пустой рецепт: ничего не делаем
    def build_arch(self, arch):
        pass
    def get_recipe_env(self, arch, **kwargs):
        return {}
    def should_build(self, arch):
        return False
