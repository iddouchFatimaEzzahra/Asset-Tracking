#!/usr/bin/env python3
"""
Collection de données AMÉLIORÉE avec plus de positions et d'échantillons
"""

import requests
import time
import csv
import numpy as np

# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════

TB_SERVER = "https://thingsboard.cloud"
TB_USERNAME = "iddouch.fatimaezzahra23@ump.ac.ma"
TB_PASSWORD = "iddfati123"

DEVICE_ID_SCANNER_A = "fe53e270-bf4e-11f0-a4c6-e5fe644790a2"
DEVICE_ID_SCANNER_B = "1f471880-bf4f-11f0-a562-d9639f025684"

auth_token = None

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

def get_device_telemetry(device_id):
    token = get_auth_token()
    url = f"{TB_SERVER}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    
    headers = {"X-Authorization": f"Bearer {token}"}
    params = {"keys": "rssi"}
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if 'rssi' in data and len(data['rssi']) > 0:
            return int(data['rssi'][0]['value'])
    return None

# ════════════════════════════════════════════════════════
# COLLECTE AMÉLIORÉE
# ════════════════════════════════════════════════════════

def collect_position(x_cm, y_cm, num_samples=30):
    """Collecter RSSI pour une position avec filtrage des outliers"""
    
    print(f"\n📍 Position : ({x_cm}, {y_cm}) cm")
    print(f"   → Placer le beacon à cette position")
    input("   → Appuyer sur ENTRÉE quand prêt...")
    
    rssi_A_list = []
    rssi_B_list = []
    
    print(f"   → Collecte de {num_samples} échantillons (filtrage auto)...")
    
    collected = 0
    attempts = 0
    max_attempts = num_samples * 3  # Sécurité
    
    while collected < num_samples and attempts < max_attempts:
        attempts += 1
        
        rssi_A = get_device_telemetry(DEVICE_ID_SCANNER_A)
        time.sleep(0.3)
        rssi_B = get_device_telemetry(DEVICE_ID_SCANNER_B)
        
        # Vérifier validité
        if rssi_A and rssi_B and rssi_A != -100 and rssi_B != -100:
            # Filtrer les outliers évidents (trop faible ou trop fort)
            if -95 < rssi_A < -50 and -95 < rssi_B < -50:
                rssi_A_list.append(rssi_A)
                rssi_B_list.append(rssi_B)
                collected += 1
                
                if collected % 5 == 0:
                    print(f"      {collected}/{num_samples} : A={rssi_A} dBm, B={rssi_B} dBm")
            else:
                print(f"      ⚠️  Valeur rejetée : A={rssi_A}, B={rssi_B}")
        
        time.sleep(1)
    
    if len(rssi_A_list) < num_samples:
        print(f"   ⚠️  Seulement {len(rssi_A_list)} échantillons collectés")
        if len(rssi_A_list) < num_samples // 2:
            print(f"   ❌ Pas assez de données, position ignorée")
            return None, None
    
    # Utiliser la médiane (plus robuste que la moyenne)
    rssi_A_median = int(np.median(rssi_A_list))
    rssi_B_median = int(np.median(rssi_B_list))
    
    # Afficher statistiques
    rssi_A_std = np.std(rssi_A_list)
    rssi_B_std = np.std(rssi_B_list)
    
    print(f"   ✅ Médiane : A={rssi_A_median} dBm (σ={rssi_A_std:.1f}), B={rssi_B_median} dBm (σ={rssi_B_std:.1f})")
    
    return rssi_A_median, rssi_B_median

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

def main():
    print("\n" + "="*70)
    print("  COLLECTE DE DONNÉES AMÉLIORÉE - GRILLE 8×8 (64 POSITIONS)")
    print("="*70)
    print("\n💡 AMÉLIORATIONS :")
    print("   • 64 positions au lieu de 36")
    print("   • 30 échantillons par position (au lieu de 20)")
    print("   • Filtrage automatique des outliers")
    print("   • Statistiques de qualité affichées")
    print("\n⏱️  Temps estimé : ~45 minutes")
    print("="*70 + "\n")
    
    # Grille 8×8 (tous les 4cm environ)
    x_positions = [5, 8, 11, 14, 17, 20, 23, 26]
    y_positions = [5, 8, 11, 14, 17, 20, 23, 26]
    
    # Fichier CSV
    filename = "fingerprinting_data.csv"
    
    print(f"📁 Fichier de sortie : {filename}")
    print(f"📊 Nombre total de positions : {len(x_positions) * len(y_positions)}\n")
    
    response = input("Continuer ? (o/n) : ")
    if response.lower() != 'o':
        print("Annulé.")
        return
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['x_cm', 'y_cm', 'rssi_A', 'rssi_B'])
        
        total = len(x_positions) * len(y_positions)
        count = 0
        skipped = 0
        
        for y in y_positions:
            for x in x_positions:
                count += 1
                print(f"\n{'='*70}")
                print(f"  POSITION {count}/{total} - ({count-skipped} collectées, {skipped} ignorées)")
                
                rssi_A, rssi_B = collect_position(x, y)
                
                if rssi_A is not None and rssi_B is not None:
                    writer.writerow([x, y, rssi_A, rssi_B])
                    f.flush()  # Sauvegarder immédiatement
                else:
                    skipped += 1
        
        print("\n" + "="*70)
        print(f"✅ Collecte terminée !")
        print(f"   Positions collectées : {count - skipped}/{total}")
        print(f"   Fichier sauvegardé : {filename}")
        print("="*70 + "\n")
        
        if skipped > 0:
            print(f"⚠️  {skipped} positions ignorées (données insuffisantes)")
        
        print("\n💡 PROCHAINES ÉTAPES :")
        print("   1. python train_model.py")
        print("   2. python calibrate_correction.py")
        print("   3. Mettre à jour tracking_ml.py avec les nouveaux coefficients")
        print()

if __name__ == "__main__":
    if not get_auth_token():
        print("❌ Erreur d'authentification")
        exit(1)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⛔ Collecte interrompue\n")