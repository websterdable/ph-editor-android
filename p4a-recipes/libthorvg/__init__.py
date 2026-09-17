from pythonforandroid.recipe import Recipe


class LibThorvgRecipe(Recipe):
    name = 'libthorvg'
    version = '1.0.0'

    def should_build(self, arch):
        # Говорим p4a: не собирай эту библиотеку
        return False

    def build_arch(self, arch):
        # Ничего не делаем
        pass

    def get_recipe_env(self, arch, **kwargs):
        return {}


# Именно этой переменной ждёт p4a
recipe = LibThorvgRecipe()
