import sys
import os

# الحصول على المسار المطلق لمجلد backend
current_dir = os.path.dirname(os.path.abspath(__file__))
# الحصول على المسار للجذر الأساسي (الذي يحتوي على مجلد config ومجلد backend)
parent_dir = os.path.dirname(current_dir)

# إضافة المجلد الرئيسي والجذر إلى بداية مسارات بايثون
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# استيراد التطبيق مباشرة بعد ضبط المسارات
from backend.api.main import app