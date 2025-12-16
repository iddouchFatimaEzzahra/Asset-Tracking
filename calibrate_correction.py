#!/usr/bin/env python3
"""
Script pour calculer les coefficients de correction empirique
pour le modèle Random Forest
"""

import pandas as pd
import numpy as np
import pickle
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

print("\n" + "="*70)
print("  CALIBRATION DES COEFFICIENTS DE CORRECTION")
print("="*70 + "\n")

# ════════════════════════════════════════════════════════
# 1. CHARGER LE MODÈLE ET LES DONNÉES
# ════════════════════════════════════════════════════════

print("📦 Chargement du modèle...")
with open('knn_model.pkl', 'rb') as f:
    model_data = pickle.load(f)

if isinstance(model_data, dict):
    model_x = model_data['model_x']
    model_y = model_data['model_y']
    scaler = model_data['scaler']
    model_type_x = model_data.get('model_type_x', 'Unknown')
    model_type_y = model_data.get('model_type_y', 'Unknown')
    print(f"✅ Modèle X : {model_type_x}")
    print(f"✅ Modèle Y : {model_type_y}\n")
else:
    model_x = model_data
    model_y = model_data
    scaler = None
    print("⚠️  Ancien format détecté, même modèle pour X et Y\n")
print("📦 Chargement des données...")
print("📦 Chargement des données...")
data = pd.read_csv('fingerprinting_data.csv')
print(f"✅ {len(data)} positions chargées\n")

def rssi_to_distance(rssi):
    rssi = np.asarray(rssi, dtype=float)
    measuredPower = -84.0
    n = 2.8
    ratio = (measuredPower - rssi) / (10.0 * n)
    distance = 0.25 * (10.0 ** ratio)
    distance = np.clip(distance, 0.03, 0.45)
    return distance

print("🔮 Prédiction de toutes les positions...")

dist_A = rssi_to_distance(data['rssi_A'].values)
dist_B = rssi_to_distance(data['rssi_B'].values)

X_base = data[['rssi_A', 'rssi_B']].values
rssi_diff = data['rssi_A'] - data['rssi_B']
rssi_sum = data['rssi_A'] + data['rssi_B']
rssi_ratio = data['rssi_A'] / (data['rssi_B'] - 0.01)

X_features = np.column_stack([
    X_base,
    rssi_diff,
    rssi_sum,
    rssi_ratio,
    dist_A,
    dist_B
])

X_scaled = scaler.transform(X_features)
# ════════════════════════════════════════════════════════
# 2. PRÉDIRE TOUTES LES POSITIONS
# ════════════════════════════════════════════════════════

print("🔮 Prédiction de toutes les positions...")

# Prédire X et Y séparément (en mètres)
x_pred_m = model_x.predict(X_scaled)
y_pred_m = model_y.predict(X_scaled)

predictions = np.column_stack([x_pred_m, y_pred_m])

# Positions réelles
y_true = data[['x_cm', 'y_cm']].values / 100.0  # en mètres

print("✅ Prédictions effectuées\n")

# ════════════════════════════════════════════════════════
# 3. CALCULER LES COEFFICIENTS DE CORRECTION
# ════════════════════════════════════════════════════════

print("📐 Calcul des coefficients de correction linéaire...")
print("    Formule: x_corr = a_x * x_pred + b_x\n")

# Séparer X et Y
x_pred = predictions[:, 0] * 100  # en cm
y_pred = predictions[:, 1] * 100  # en cm
x_true = y_true[:, 0] * 100       # en cm
y_true_cm = y_true[:, 1] * 100    # en cm

# Régression linéaire pour X
reg_x = LinearRegression()
reg_x.fit(x_pred.reshape(-1, 1), x_true)
a_x = reg_x.coef_[0]
b_x = reg_x.intercept_

# Régression linéaire pour Y
reg_y = LinearRegression()
reg_y.fit(y_pred.reshape(-1, 1), y_true_cm)
a_y = reg_y.coef_[0]
b_y = reg_y.intercept_

print("="*70)
print("🎯 COEFFICIENTS DE CORRECTION À UTILISER :")
print("="*70)
print(f"""
a_x = {a_x}
b_x = {b_x}
a_y = {a_y}
b_y = {b_y}
""")
print("="*70)

# ════════════════════════════════════════════════════════
# 4. APPLIQUER LA CORRECTION ET MESURER L'AMÉLIORATION
# ════════════════════════════════════════════════════════

x_corrected = a_x * x_pred + b_x
y_corrected = a_y * y_pred + b_y

# Erreurs AVANT correction
errors_before = np.sqrt((x_pred - x_true)**2 + (y_pred - y_true_cm)**2)
mean_error_before = np.mean(errors_before)
median_error_before = np.median(errors_before)
max_error_before = np.max(errors_before)

# Erreurs APRÈS correction
errors_after = np.sqrt((x_corrected - x_true)**2 + (y_corrected - y_true_cm)**2)
mean_error_after = np.mean(errors_after)
median_error_after = np.median(errors_after)
max_error_after = np.max(errors_after)

print("\n📊 AMÉLIORATION DE LA PRÉCISION :")
print("="*70)
print(f"AVANT correction :")
print(f"  Erreur moyenne : {mean_error_before:.2f} cm")
print(f"  Erreur médiane : {median_error_before:.2f} cm")
print(f"  Erreur max     : {max_error_before:.2f} cm")
print()
print(f"APRÈS correction :")
print(f"  Erreur moyenne : {mean_error_after:.2f} cm")
print(f"  Erreur médiane : {median_error_after:.2f} cm")
print(f"  Erreur max     : {max_error_after:.2f} cm")
print()
print(f"📈 Amélioration : {((mean_error_before - mean_error_after) / mean_error_before * 100):.1f}%")
print("="*70)

# ════════════════════════════════════════════════════════
# 5. VISUALISATION (OPTIONNEL)
# ════════════════════════════════════════════════════════

try:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Graphique X
    axes[0].scatter(x_pred, x_true, alpha=0.6, label='Brut')
    axes[0].scatter(x_corrected, x_true, alpha=0.6, label='Corrigé')
    axes[0].plot([0, 30], [0, 30], 'r--', label='Idéal')
    axes[0].set_xlabel('X prédit (cm)')
    axes[0].set_ylabel('X réel (cm)')
    axes[0].set_title(f'Correction X (R²={reg_x.score(x_pred.reshape(-1, 1), x_true):.3f})')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Graphique Y
    axes[1].scatter(y_pred, y_true_cm, alpha=0.6, label='Brut')
    axes[1].scatter(y_corrected, y_true_cm, alpha=0.6, label='Corrigé')
    axes[1].plot([0, 30], [0, 30], 'r--', label='Idéal')
    axes[1].set_xlabel('Y prédit (cm)')
    axes[1].set_ylabel('Y réel (cm)')
    axes[1].set_title(f'Correction Y (R²={reg_y.score(y_pred.reshape(-1, 1), y_true_cm):.3f})')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('correction_calibration.png', dpi=150, bbox_inches='tight')
    print("\n📊 Graphique sauvegardé : correction_calibration.png")
    
except Exception as e:
    print(f"\n⚠️  Impossible de créer le graphique : {e}")

print("\n✅ Calibration terminée !")
print("\n💡 Copie ces coefficients dans tracking_ml.py (ligne ~195)\n")