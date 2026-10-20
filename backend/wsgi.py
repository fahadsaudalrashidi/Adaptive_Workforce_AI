import sys
import os

# إضافة مجلد backend إلى مسار بايثون لضمان رؤية config و api
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.main import app