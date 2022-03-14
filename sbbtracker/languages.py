import importlib
import json

from sbbtracker import settings

lang = settings.get(settings.language)

lang_module = importlib.import_module(f"lang.lang_{lang}")

lang_dict = getattr(lang_module, "lang")


def tr(s):
    """
    Translates a string base on the current
    @param s: input string to translate
    @return: return the translation if it exists, otherwise return the input
    """
    translated = s
    if s in lang_dict:
        translated = lang_dict[s]
        if not translated:
            translated = s
    return translated


available_languages = {
    "English": "en",
    "Japanese": "jp"
}
