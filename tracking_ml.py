#!/usr/bin/env python3
import requests
import time
import numpy as np
import pickle
from collections import deque

# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════

TB_SERVER = "https://thingsboard.cloud"
TB_USERNAME = "iddouch.fatimaezzahra23@ump.ac.ma"
TB_PASSWORD = "iddfati123"

DEVICE_ID_SCANNER_A = "fe53e270-bf4e-11f0-a4c6-e5fe644790a2"
DEVICE_ID_SCANNER_B = "1f471880-bf4f-11f0-a562-d9639f025684"
DEVICE_ID_BEACON = "59c395b0-bf59-11f0-bcf0-0bef5ca18fec"

auth_token = None

# ════════════════════════════════════════════════════════
# FILTRAGE TEMPOREL - MOYENNE MOBILE PONDÉRÉE
# ════════════════════════════════════════════════════════

class TemporalFilter:
    def __init__(self, window_size=5, alpha=0.3):
        """
        window_size: nombre d'échantillons à garder
        alpha: poids du filtre exponentiel (0-1)
              alpha faible = plus de lissage
              alpha élevé = plus réactif
        """
        self.window_size = window_size
        self.alpha = alpha
        self.position_history = deque(maxlen=window_size)
        self.rssi_history_A = deque(maxlen=window_size)
        self.rssi_history_B = deque(maxlen=window_size)
        self.last_filtered_pos = None
    
    def filter_rssi(self, rssi_A, rssi_B):
        """Filtre les RSSI avec moyenne mobile"""
        self.rssi_history_A.append(rssi_A)
        self.rssi_history_B.append(rssi_B)
        
        # Utiliser la médiane pour éliminer les outliers
        filtered_A = int(np.median(list(self.rssi_history_A)))
        filtered_B = int(np.median(list(self.rssi_history_B)))
        
        return filtered_A, filtered_B
    
    def filter_position(self, x, y):
        """Filtre la position avec moyenne mobile pondérée"""
        self.position_history.append((x, y))
        
        if len(self.position_history) < 2:
            self.last_filtered_pos = (x, y)
            return x, y
        
        # Calcul de la moyenne pondérée
        # Les positions récentes ont plus de poids
        positions = np.array(list(self.position_history))
        weights = np.exp(np.linspace(-2, 0, len(positions)))
        weights /= weights.sum()
        
        filtered_x = np.sum(positions[:, 0] * weights)
        filtered_y = np.sum(positions[:, 1] * weights)
        
        # Filtre exponentiel avec la position précédente
        if self.last_filtered_pos is not None:
            filtered_x = self.alpha * filtered_x + (1 - self.alpha) * self.last_filtered_pos[0]
            filtered_y = self.alpha * filtered_y + (1 - self.alpha) * self.last_filtered_pos[1]
        
        self.last_filtered_pos = (filtered_x, filtered_y)
        return filtered_x, filtered_y
    
    def is_outlier(self, x, y, threshold=0.10):
        """Détecte si une position est aberrante (> 10cm de saut)"""
        if self.last_filtered_pos is None:
            return False
        
        distance = np.sqrt(
            (x - self.last_filtered_pos[0])**2 + 
            (y - self.last_filtered_pos[1])**2
        )
        
        return distance > threshold

# Instance globale du filtre
temporal_filter = TemporalFilter(window_size=1, alpha=1.0)

# ════════════════════════════════════════════════════════
# CHARGER MODÈLE ML + SCALER
# ════════════════════════════════════════════════════════

print("📦 Chargement du modèle ML...")
with open('knn_model.pkl', 'rb') as f:
    model_data = pickle.load(f)

if isinstance(model_data, dict):
    model_x = model_data['model_x']
    model_y = model_data['model_y']
    scaler = model_data['scaler']
    model_type_x = model_data.get('model_type_x', 'Unknown')
    model_type_y = model_data.get('model_type_y', 'Unknown')
    print(f"✅ Modèle X chargé : {model_type_x}")
    print(f"✅ Modèle Y chargé : {model_type_y}")
    print(f"✅ Scaler chargé\n")
else:
    # Compat ancien format éventuel
    model_x = model_data
    model_y = model_data
    scaler = None
    print("⚠️  Ancien modèle sans scaler détecté")
    print("✅ Modèle chargé (même modèle pour X et Y)\n")

# ════════════════════════════════════════════════════════
# FONCTIONS
# ════════════════════════════════════════════════════════

def get_auth_token():
    global auth_token
    if auth_token:
        return auth_token
    
    url = f"{TB_SERVER}/api/auth/login"
    response = requests.post(url, json={
        "username": TB_USERNAME,
        "password": TB_PASSWORD
    })
    
    if response.status_code == 200:
        auth_token = response.json()["token"]
        return auth_token
    return None

def get_device_telemetry(device_id, scanner_name):
    token = get_auth_token()
    url = f"{TB_SERVER}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    
    headers = {"X-Authorization": f"Bearer {token}"}
    params = {"keys": "rssi,distance"}
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        
        rssi = None
        distance = None
        
        if 'rssi' in data and len(data['rssi']) > 0:
            rssi = int(data['rssi'][0]['value'])
        
        if 'distance' in data and len(data['distance']) > 0:
            distance = float(data['distance'][0]['value'])
        
        if rssi and distance:
            return {
                "rssi": rssi,
                "distance": distance,
                "valid": rssi != -100 and distance > 0.01
            }
    
    return None

def send_device_telemetry(device_id, data):
    token = get_auth_token()
    url = f"{TB_SERVER}/api/plugins/telemetry/DEVICE/{device_id}/timeseries/ANY"
    
    headers = {
        "X-Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.status_code == 200

def rssi_to_distance(rssi):
    rssi = float(rssi)
    measuredPower = -84.0
    n = 2.8
    ratio = (measuredPower - rssi) / (10.0 * n)
    distance = 0.25 * (10.0 ** ratio)
    distance = max(0.03, min(0.45, distance))
    return distance
# ════════════════════════════════════════════════════════
# PRÉDICTION ML AVEC FILTRAGE
# ════════════════════════════════════════════════════════

def predict_position_ml(rssi_A, rssi_B):
    """Prédire position avec ML + filtrage temporel"""
    
    # 1. Filtrer les RSSI d'entrée
    filtered_rssi_A, filtered_rssi_B = temporal_filter.filter_rssi(rssi_A, rssi_B)
    
    # 2. Calculer les distances cohérentes avec train_model.py
    dist_A = rssi_to_distance(filtered_rssi_A)
    dist_B = rssi_to_distance(filtered_rssi_B)
    
    # 3. Créer les features (identique à train_model.py)
    rssi_diff = filtered_rssi_A - filtered_rssi_B
    rssi_sum = filtered_rssi_A + filtered_rssi_B
    
    if filtered_rssi_B == 0:
        rssi_ratio = 0
    else:
        rssi_ratio = filtered_rssi_A / (filtered_rssi_B - 0.01)
    
    features = np.array([[
        filtered_rssi_A,
        filtered_rssi_B,
        rssi_diff,
        rssi_sum,
        rssi_ratio,
        dist_A,
        dist_B
    ]])
    
    # 4. Normaliser avec le scaler (si disponible)
    if scaler is not None:
        features_scaled = scaler.transform(features)
    else:
        features_scaled = features
    
    # 5. Prédiction ML séparée pour X et Y (en mètres)
    x = float(model_x.predict(features_scaled)[0])
    y = float(model_y.predict(features_scaled)[0])
    
    # 6. Conversion en centimètres
    x_cm = x * 100.0
    y_cm = y * 100.0
    
    # 7. Correction empirique
    a_x = 1.0034749150752216
    b_x = -0.9102480814066709
    a_y = 1.0940957103426003
    b_y = -1.2482754876048894
    
    x_cm = a_x * x_cm + b_x
    y_cm = a_y * y_cm + b_y
    
    # 8. Retour en mètres
    x = x_cm / 100.0
    y = y_cm / 100.0
    
    # 9. Limiter aux dimensions de la zone
    x = max(0.0, min(0.30, x))
    y = max(0.0, min(0.30, y))
    
    # 10. Filtrage temporel de la position
    if temporal_filter.is_outlier(x, y):
        print(f"  ⚠️  Outlier détecté ! Saut de {np.sqrt((x - temporal_filter.last_filtered_pos[0])**2 + (y - temporal_filter.last_filtered_pos[1])**2)*100:.1f} cm")
        x_filtered, y_filtered = temporal_filter.filter_position(x, y)
    else:
        x_filtered, y_filtered = temporal_filter.filter_position(x, y)
    
    return x_filtered, y_filtered, filtered_rssi_A, filtered_rssi_B

# ════════════════════════════════════════════════════════
# BOUCLE PRINCIPALE
# ════════════════════════════════════════════════════════

def main():
    print("="*70)
    print("  LOCALISATION ML + FILTRAGE TEMPOREL - TEMPS RÉEL")
    print("="*70 + "\n")
    
    iteration = 0
    success_count = 0
    
    while True:
        iteration += 1
        print(f"🔄 Scan #{iteration} - {time.strftime('%H:%M:%S')}")
        
        # Récupérer données
        data_A = get_device_telemetry(DEVICE_ID_SCANNER_A, "Scanner A")
        time.sleep(0.3)
        data_B = get_device_telemetry(DEVICE_ID_SCANNER_B, "Scanner B")
        
        if data_A and data_B:
            rssi_A_raw = data_A['rssi']
            rssi_B_raw = data_B['rssi']
            dist_A = data_A['distance']
            dist_B = data_B['distance']
            
            status_A = "✅" if data_A['valid'] else "⚠️"
            status_B = "✅" if data_B['valid'] else "⚠️"
            
            print(f"  {status_A} Scanner A: RSSI={rssi_A_raw:4d} dBm")
            print(f"  {status_B} Scanner B: RSSI={rssi_B_raw:4d} dBm")
            
            if data_A['valid'] and data_B['valid']:
                # Prédiction ML avec filtrage
                x, y, rssi_A, rssi_B = predict_position_ml(rssi_A_raw, rssi_B_raw)
                
                print(f"  📡 RSSI filtrés : A={rssi_A} dBm, B={rssi_B} dBm")
                print(f"  🤖 Position ML lissée : ({x*100:5.1f}, {y*100:5.1f}) cm")
                
                # Envoyer à ThingsBoard
                payload = {
                    "beacon_x": x,
                    "beacon_y": y,
                    "rssi_A": rssi_A,
                    "rssi_B": rssi_B,
                    "distance_A": dist_A,
                    "distance_B": dist_B
                }
                
                if send_device_telemetry(DEVICE_ID_BEACON, payload):
                    success_count += 1
                    print(f"  ✅ Envoyé ! (total: {success_count})")
            else:
                print(f"  ⚠️  Beacon hors de portée")
        else:
            print("  ❌ Erreur de récupération")
        
        print("-"*70 + "\n")
        time.sleep(3)

if __name__ == "__main__":
    if not get_auth_token():
        print("❌ Erreur d'authentification")
        exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n⛔ Arrêt du programme\n")