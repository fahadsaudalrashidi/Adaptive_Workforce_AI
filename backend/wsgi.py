import sys
import os

# تحديد المسار المطلق لمجلد backend الحالي وإضافته إلى مسارات بايثون
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.main import app