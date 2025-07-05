# λ_code/actions/__init__.py
from importlib import import_module
import json, logging

# ここに追加したファイル名を列挙
_modules = ["battle_buff"]          # あとで増やす

for name in _modules:
    import_module(f"actions.{name}")    # import 時にデコレータが走る