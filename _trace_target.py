"""Trace the target dtype through the full pipeline to find sklearn type_of_target issue."""
import sys; sys.path.insert(0, ".")
import pandas as pd, numpy as np
from sklearn.utils.multiclass import type_of_target
from backend.core.adaptive_router import AdaptiveRouter
from backend.core.data_healer import DataHealer
from backend.core.feature_factory import FeatureFactory
from backend.core.semantic_mapper import SemanticMapper

rng = np.random.default_rng(42)
n = 200
df_hr = pd.DataFrame({
    "EmployeeNumber": range(n),
    "Age": rng.integers(22, 60, n),
    "Department": rng.choice(["Sales", "HR", "IT", "Finance"], n),
    "MonthlyIncome": rng.integers(3000, 15000, n),
    "OverTime": rng.choice(["Yes", "No"], n),
    "YearsAtCompany": rng.integers(0, 20, n),
    "JobSatisfaction": rng.integers(1, 5, n),
    "WorkLifeBalance": rng.integers(1, 4, n),
    "Attrition": rng.choice(["Yes", "No"], n, p=[0.16, 0.84]),
})

router = AdaptiveRouter()
contract = router.route(df_hr, "hr_attrition_test.csv")
mapper = SemanticMapper()
sem_map = mapper.map(df_hr)

healer = DataHealer()
df_clean, _ = healer.fit_transform(df_hr, sem_map, "Attrition")
print(f"After DataHealer: Attrition dtype={df_clean['Attrition'].dtype}")
print(f"  sample: {df_clean['Attrition'].head(5).tolist()}")

factory = FeatureFactory()
df_eng, _ = factory.engineer(df_clean, sem_map, contract.dataset_type, "Attrition")
print(f"After FeatureFactory: Attrition dtype={df_eng['Attrition'].dtype}")
print(f"  sample: {df_eng['Attrition'].head(5).tolist()}")
print(f"  unique values: {df_eng['Attrition'].unique().tolist()}")

feature_names = [c for c in df_eng.columns if c != "Attrition"]
print(f"  n_features={len(feature_names)}")

# Simulate ml_router's target extraction
df_sub = df_eng[feature_names + ["Attrition"]].dropna(subset=["Attrition"])
y_raw = df_sub["Attrition"]
print(f"\ny_raw dtype: {y_raw.dtype}")
print(f"y_raw unique: {y_raw.unique().tolist()}")

y_obj = y_raw.to_numpy(dtype=object, na_value=None)
print(f"\ny_obj dtype: {y_obj.dtype}")
print(f"y_obj sample: {y_obj[:5]}")
print(f"y_obj has None: {any(v is None for v in y_obj)}")
print(f"type_of_target(y_obj): {type_of_target(y_obj)}")

# Try alternative extractions
y_str = np.asarray(y_raw.astype(str))
print(f"\ny_str dtype: {y_str.dtype}")
print(f"type_of_target(y_str): {type_of_target(y_str)}")

y_list = np.array(y_raw.tolist())
print(f"\ny_list dtype: {y_list.dtype}")
print(f"type_of_target(y_list): {type_of_target(y_list)}")
