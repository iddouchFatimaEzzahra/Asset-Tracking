#!/usr/bin/env python3
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
import pickle

print("\n" + "="*60)
print("  ENTRAÎNEMENT MODÈLE ML AMÉLIORÉ")
print("="*60 + "\n")

# Charger données
data = pd.read_csv('fingerprinting_data.csv')
print(f"✅ {len(data)} positions chargées")

def rssi_to_distance(rssi):
    rssi = np.asarray(rssi, dtype=float)
    measuredPower = -84.0  # RSSI à 25 cm (comme dans les scanners)
    n = 2.8                # même exponent n que dans tes scanners

    # Formule log-distance à partir de 25 cm
    ratio = (measuredPower - rssi) / (10.0 * n)
    distance = 0.25 * (10.0 ** ratio)  # en mètres

    # Optionnel : limiter la distance dans la boîte
    distance = np.clip(distance, 0.03, 0.45)
    return distance

dist_A = rssi_to_distance(data['rssi_A'].values)
dist_B = rssi_to_distance(data['rssi_B'].values)

# ════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ════════════════════════════════════════════════════════

# Features de base
X_base = data[['rssi_A', 'rssi_B']].values

# Features avancées
rssi_diff = data['rssi_A'] - data['rssi_B']
rssi_sum = data['rssi_A'] + data['rssi_B']
rssi_ratio = data['rssi_A'] / (data['rssi_B'] - 0.01)

X = np.column_stack([
    X_base,
    rssi_diff,
    rssi_sum,
    rssi_ratio,
    dist_A,
    dist_B
])

print(f"📊 Features créées : {X.shape[1]} (rssi_A, rssi_B, diff, sum, ratio, dist_A, dist_B)")

# Targets (position en mètres)
y = data[['x_cm', 'y_cm']].values / 100.0

# Split train/test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(f"📊 Train: {len(X_train)} | Test: {len(X_test)}")

# ════════════════════════════════════════════════════════
# NORMALISATION
# ════════════════════════════════════════════════════════

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ════════════════════════════════════════════════════════
# ENTRAÎNER PLUSIEURS MODÈLES
# ════════════════════════════════════════════════════════

print("\n🔧 Test de plusieurs modèles (séparés pour X et Y)...\n")

models = {
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=3,
        random_state=42
    ),
    "KNN k=5": lambda: __import__('sklearn.neighbors', fromlist=['KNeighborsRegressor']).KNeighborsRegressor(
        n_neighbors=5,
        weights='distance'
    ),
    "KNN k=7": lambda: __import__('sklearn.neighbors', fromlist=['KNeighborsRegressor']).KNeighborsRegressor(
        n_neighbors=7,
        weights='distance'
    )
}

y_train_x = y_train[:, 0]
y_train_y = y_train[:, 1]
y_test_x = y_test[:, 0]
y_test_y = y_test[:, 1]

best_models = {
    "x": {"model": None, "name": None, "mae": float('inf')},
    "y": {"model": None, "name": None, "mae": float('inf')}
}

for axis, (y_tr, y_te) in {
    "x": (y_train_x, y_test_x),
    "y": (y_train_y, y_test_y)
}.items():
    print(f"\n══════ Axe {axis.upper()} ══════\n")
    for name, make_model in models.items():
        model = make_model()
        model.fit(X_train_scaled, y_tr)
        preds = model.predict(X_test_scaled)

        errors_cm = np.abs(preds - y_te) * 100.0
        mean_error = np.mean(errors_cm)
        median_error = np.median(errors_cm)
        max_error = np.max(errors_cm)

        print(f"📈 {name} (axe {axis.upper()}) :")
        print(f"   MAE        : {mean_error:.2f} cm")
        print(f"   Médiane    : {median_error:.2f} cm")
        print(f"   Erreur max : {max_error:.2f} cm")
        print()

        if mean_error < best_models[axis]["mae"]:
            best_models[axis]["mae"] = mean_error
            best_models[axis]["model"] = model
            best_models[axis]["name"] = name

print("\n🏆 Meilleurs modèles :")
print(f"   Axe X : {best_models['x']['name']} ({best_models['x']['mae']:.2f} cm)")
print(f"   Axe Y : {best_models['y']['name']} ({best_models['y']['mae']:.2f} cm)")

# ════════════════════════════════════════════════════════
# SAUVEGARDER LE MEILLEUR MODÈLE
# ════════════════════════════════════════════════════════

print("\n💾 Sauvegarde des modèles et du scaler...")

with open('knn_model.pkl', 'wb') as f:
    pickle.dump({
        'model_x': best_models['x']['model'],
        'model_y': best_models['y']['model'],
        'scaler': scaler,
        'model_type_x': best_models['x']['name'],
        'model_type_y': best_models['y']['name']
    }, f)

print("✅ Modèles + scaler sauvegardés : knn_model.pkl")
print("\n⚠️  IMPORTANT : Mettre à jour tracking_ml.py pour utiliser model_x/model_y")
print("="*60 + "\n")