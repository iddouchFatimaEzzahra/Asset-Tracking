# Asset Tracking BLE – Projet IOT ENSA Oujda

Ce projet implémente un système complet de localisation d’un **beacon BLE** posé sur un **carton (~30×30 cm)** à l’aide :

- de **3 ESP32** (1 beacon mobile, 2 scanners fixes),
- de scripts **Python** (collecte, entraînement ML, calibration, tracking temps réel),
- de la plateforme **ThingsBoard Cloud**,
- d’une **interface web** pour visualiser la position du beacon.

---

## Architecture générale

- **Beacon ESP32**  
  Diffuse en continu un signal BLE (`AssetBeacon`).

- **Scanner A / Scanner B (ESP32)**  
  - Placés aux coins du carton.  
  - Scannent le beacon, mesurent le **RSSI**, estiment la **distance** (lookup table + modèle log-distance).  
  - Envoient `scanner_id`, `scanner_x`, `scanner_y`, `rssi`, `distance` vers **ThingsBoard** (HTTP/JSON).

- **ThingsBoard Cloud**  
  - Stocke les télémétries des scanners.  
  - Fournit une **API REST** utilisée par les scripts Python.  
  - Affiche des **dashboards** (RSSI, distances, position du beacon).

- **Scripts Python**  
  - [collect_more_data.py](cci:7://file:///c:/Users/hp/Documents/Arduino/collect_more_data.py:0:0-0:0) : collecte de données de fingerprinting sur une grille de positions.  
  - [train_model.py](cci:7://file:///c:/Users/hp/Documents/Arduino/train_model.py:0:0-0:0) : création des features, test de plusieurs modèles (KNN, Random Forest) et sauvegarde du meilleur couple `(model_x, model_y)` dans `knn_model.pkl`.  
  - [calibrate_correction.py](cci:7://file:///c:/Users/hp/Documents/Arduino/calibrate_correction.py:0:0-0:0) : calcul des coefficients de **correction linéaire** `(a_x, b_x, a_y, b_y)` et analyse avant/après (R², erreurs).  
  - [tracking_ml.py](cci:7://file:///c:/Users/hp/Documents/Arduino/tracking_ml.py:0:0-0:0) : localisation **temps réel** :  
    - lecture des RSSI/distances sur ThingsBoard,  
    - prédiction de `(x, y)` avec le modèle ML + correction,  
    - filtrage temporel pour lisser la position,  
    - renvoi de la position du beacon vers ThingsBoard.

- **Interface web**  
  - [asset_tracking_carton.html](cci:7://file:///c:/Users/hp/Documents/Arduino/asset_tracking_carton.html:0:0-0:0) :  
    - représente le carton et les scanners en 2D,  
    - lit la dernière position `(x, y)` du beacon via l’API ThingsBoard,  
    - affiche le beacon qui se déplace sur le carton en temps réel.

---

## Déroulement simplifié

1. **Collecte de données** :  
   `python collect_more_data.py` → génère `fingerprinting_data.csv`.

2. **Entraînement ML** :  
   `python train_model.py` → choisit le meilleur modèle pour X (par ex. **KNN k=7**) et pour Y (par ex. **Random Forest**) → `knn_model.pkl`.

3. **Calibration** :  
   `python calibrate_correction.py` → calcule les coefficients `(a_x, b_x, a_y, b_y)` pour améliorer les prédictions (R² de X et Y élevés) et génère les figures de calibration.

4. **Tracking temps réel** :  
   `python tracking_ml.py` + dashboards ThingsBoard + [asset_tracking_carton.html](cci:7://file:///c:/Users/hp/Documents/Arduino/asset_tracking_carton.html:0:0-0:0)  
   → visualisation en temps réel de la position du beacon sur le carton.
