import sys
import os

# الحصول على المسار المطلق لمجلد backend
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# إضافة مجلد backend إلى أعلى قائمة مسارات بايثون
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# تغيير بيئة العمل الحالية لتصبح داخل مجلد backend
os.chdir(BACKEND_DIR)

from api.main import app