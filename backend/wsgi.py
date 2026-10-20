import sys
import os

# إضافة مجلد backend الحالي إلى مسارات بايثون
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# استيراد التطبيق مباشرة
from api.main import app