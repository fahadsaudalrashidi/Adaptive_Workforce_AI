import sys
import os

# إضافة مسار مجلد backend ومجلد api لكي يرى بايثون ملفات config و main بسهولة تامة
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, "api"))

from api.main import app