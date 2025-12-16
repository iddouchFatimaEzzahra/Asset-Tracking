/*
 * ═══════════════════════════════════════════════════════
 *  SCANNER A - OPTIMISÉ AVEC LOOKUP TABLE
 *  Basé sur vos mesures réelles de calibration
 *  CARTON 33.5cm × 30cm - Asset Tracking ENSA Oujda
 * ═══════════════════════════════════════════════════════
 */

#include <BLEDevice.h>
#include <BLEScan.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ════════════════════════════════════════════════════════
// CONFIGURATION
// ════════════════════════════════════════════════════════

#define SCANNER_ID "A"
float SCANNER_X = 0.05;   // 5 cm du bord gauche
float SCANNER_Y = 0.05;   // 5 cm du bas

// WiFi
const char* ssid = "iddfati";
const char* password = "11111111";

// ThingsBoard
const String THINGSBOARD_TOKEN = "5sFhZlDXeCPuVMvcOWWw";
const String THINGSBOARD_SERVER = "http://thingsboard.cloud";

// ════════════════════════════════════════════════════════
// TABLE DE CALIBRATION - VOS MESURES RÉELLES
// ════════════════════════════════════════════════════════

const int CALIBRATION_POINTS = 5;

// Distances mesurées (en mètres)
float calibrationDistances[CALIBRATION_POINTS] = {
  0.05,   // 5 cm
  0.10,   // 10 cm
  0.15,   // 15 cm
  0.20,   // 20 cm
  0.25    // 25 cm
};

// RSSI mesurés à ces distances
int calibrationRSSI[CALIBRATION_POINTS] = {
  -66,    // RSSI à 5 cm
  -71,    // RSSI à 10 cm
  -74,    // RSSI à 15 cm
  -78,    // RSSI à 20 cm
  -84     // RSSI à 25 cm
};

// ════════════════════════════════════════════════════════
// VARIABLES GLOBALES
// ════════════════════════════════════════════════════════

BLEScan* pBLEScan;
int beaconRSSI = -100;
bool beaconFound = false;
unsigned long scanCount = 0;
unsigned long successCount = 0;

// Buffer filtrage (médian sur 10 échantillons)
const int BUFFER_SIZE = 10;
int rssiBuffer[BUFFER_SIZE];
int bufferIndex = 0;
bool bufferFull = false;

// ════════════════════════════════════════════════════════
// CALLBACK BLE
// ════════════════════════════════════════════════════════

class MyAdvertisedDeviceCallbacks: public BLEAdvertisedDeviceCallbacks {
  void onResult(BLEAdvertisedDevice device) {
    if (device.haveName()) {
      String name = device.getName().c_str();
      
      if (name == "AssetBeacon") {
        beaconRSSI = device.getRSSI();
        beaconFound = true;
      }
    }
  }
};

// ════════════════════════════════════════════════════════
// FONCTION : FILTRAGE RSSI - MÉDIANE (Élimine les valeurs aberrantes)
// ════════════════════════════════════════════════════════

int getFilteredRSSI(int newRSSI) {
  rssiBuffer[bufferIndex] = newRSSI;
  bufferIndex++;
  
  if (bufferIndex >= BUFFER_SIZE) {
    bufferIndex = 0;
    bufferFull = true;
  }
  
  int count = bufferFull ? BUFFER_SIZE : bufferIndex;
  
  // Copier pour tri
  int sorted[BUFFER_SIZE];
  for (int i = 0; i < count; i++) {
    sorted[i] = rssiBuffer[i];
  }
  
  // Tri à bulles
  for (int i = 0; i < count - 1; i++) {
    for (int j = 0; j < count - i - 1; j++) {
      if (sorted[j] > sorted[j + 1]) {
        int temp = sorted[j];
        sorted[j] = sorted[j + 1];
        sorted[j + 1] = temp;
      }
    }
  }
  
  // Retourner la médiane
  return sorted[count / 2];
}

// ════════════════════════════════════════════════════════
// FONCTION : CALCUL DISTANCE - INTERPOLATION LINÉAIRE
// ════════════════════════════════════════════════════════

float calculateDistance(int rssi) {
  if (rssi >= 0 || rssi < -100) {
    return -1.0;
  }
  
  // Si RSSI plus fort que 5cm → très proche (< 5cm)
  if (rssi > calibrationRSSI[0]) {
    // Extrapolation pour < 5cm
    float ratio = (float)(calibrationRSSI[0] - rssi) / 5.0;
    float distance = 0.05 - ratio * 0.01;  // Réduire progressivement
    if (distance < 0.03) distance = 0.03;  // Minimum 3cm
    return distance;
  }
  
  // Si RSSI plus faible que 25cm → très loin (> 25cm)
  if (rssi < calibrationRSSI[CALIBRATION_POINTS - 1]) {
    // Extrapolation pour > 25cm avec formule log-distance
    float measuredPower = -84.0;  // RSSI à 25cm
    float n = 2.8;  // Atténuation plus forte à longue distance
    float ratio = (measuredPower - rssi) / (10.0 * n);
    float distance = 0.25 * pow(10.0, ratio);
    if (distance > 0.45) distance = 0.45;  // Maximum 45cm (diagonale carton)
    return distance;
  }
  
  // Interpolation linéaire entre les points de calibration
  for (int i = 0; i < CALIBRATION_POINTS - 1; i++) {
    int rssi1 = calibrationRSSI[i];
    int rssi2 = calibrationRSSI[i + 1];
    
    // Trouver l'intervalle qui contient notre RSSI
    if (rssi <= rssi1 && rssi >= rssi2) {
      float dist1 = calibrationDistances[i];
      float dist2 = calibrationDistances[i + 1];
      
      // Interpolation linéaire
      // ratio = 0 → distance = dist1
      // ratio = 1 → distance = dist2
      float ratio = (float)(rssi1 - rssi) / (float)(rssi1 - rssi2);
      float distance = dist1 + ratio * (dist2 - dist1);
      
      return distance;
    }
  }
  
  // Fallback (ne devrait jamais arriver)
  return 0.15;
}

// ════════════════════════════════════════════════════════
// FONCTION : ENVOI THINGSBOARD
// ════════════════════════════════════════════════════════

bool sendToThingsBoard(String scannerID, float x, float y, int rssi, float distance) {
  if (WiFi.status() != WL_CONNECTED) return false;
  
  String url = THINGSBOARD_SERVER + "/api/v1/" + THINGSBOARD_TOKEN + "/telemetry";
  
  String json = "{";
  json += "\"scanner_id\":\"" + scannerID + "\",";
  json += "\"scanner_x\":" + String(x, 3) + ",";
  json += "\"scanner_y\":" + String(y, 3) + ",";
  json += "\"rssi\":" + String(rssi) + ",";
  json += "\"distance\":" + String(distance, 3);
  json += "}";
  
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(json);
  http.end();
  
  return (code == 200);
}

// ════════════════════════════════════════════════════════
// SETUP
// ════════════════════════════════════════════════════════

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  // Init buffer
  for (int i = 0; i < BUFFER_SIZE; i++) {
    rssiBuffer[i] = -100;
  }
  
  Serial.println("\n\n╔═══════════════════════════════════════╗");
  Serial.println("║   SCANNER A - LOOKUP TABLE OPTIMISÉ  ║");
  Serial.println("║   Position : (5.0, 5.0) cm           ║");
  Serial.println("╚═══════════════════════════════════════╝\n");
  
  Serial.println("📍 CONFIG :");
  Serial.println("   Scanner   : " + String(SCANNER_ID));
  Serial.println("   Position  : (" + String(SCANNER_X*100,1) + ", " + String(SCANNER_Y*100,1) + ") cm");
  Serial.println();
  Serial.println("📊 CALIBRATION (vos mesures) :");
  for (int i = 0; i < CALIBRATION_POINTS; i++) {
    Serial.print("    ");
    Serial.print(calibrationDistances[i] * 100, 0);
    Serial.print(" cm → RSSI = ");
    Serial.print(calibrationRSSI[i]);
    Serial.println(" dBm");
  }
  Serial.println();
  
  // WiFi
  Serial.println("📶 WiFi...");
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("✅ WiFi OK");
  } else {
    Serial.println("❌ WiFi KO");
    while(1) delay(1000);
  }
  
  // BLE
  Serial.println("📡 BLE...");
  BLEDevice::init("Scanner_A");
  
  pBLEScan = BLEDevice::getScan();
  pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
  pBLEScan->setActiveScan(true);
  pBLEScan->setInterval(100);
  pBLEScan->setWindow(99);
  
  Serial.println("✅ Scanner prêt !\n");
  Serial.println("═══════════════════════════════════════");
  Serial.println("🚀 SCANS EN CONTINU (scan 2s)");
  Serial.println("═══════════════════════════════════════\n");
}

// ════════════════════════════════════════════════════════
// LOOP
// ════════════════════════════════════════════════════════

void loop() {
  beaconFound = false;
  beaconRSSI = -100;
  scanCount++;
  
  Serial.println("┌── SCAN #" + String(scanCount) + " ─ Scanner A (5,5)cm ──┐");
  
  // Scan BLE pendant 2 secondes (plus stable)
  BLEScanResults* pResults = pBLEScan->start(2, false);
  
  if (pResults) {
    Serial.println("│ BLE devices: " + String(pResults->getCount()) + "                     │");
  }
  
  pBLEScan->clearResults();
  
  if (beaconFound) {
    int filtered = getFilteredRSSI(beaconRSSI);
    float dist = calculateDistance(filtered);
    
    Serial.println("│ ★ BEACON DÉTECTÉ !                  │");
    Serial.println("│ RSSI brut  : " + String(beaconRSSI) + " dBm              │");
    Serial.println("│ RSSI filtré: " + String(filtered) + " dBm              │");
    Serial.println("│ Distance   : " + String(dist*100, 1) + " cm                │");
    
    // Afficher quelle méthode de calcul a été utilisée
    if (filtered > calibrationRSSI[0]) {
      Serial.println("│ Méthode    : Extrapolation < 5cm    │");
    } else if (filtered < calibrationRSSI[CALIBRATION_POINTS-1]) {
      Serial.println("│ Méthode    : Extrapolation > 25cm   │");
    } else {
      Serial.println("│ Méthode    : Interpolation lookup   │");
    }
    
    if (dist > 0 && dist < 0.50) {
      bool ok = sendToThingsBoard(SCANNER_ID, SCANNER_X, SCANNER_Y, filtered, dist);
      if (ok) {
        successCount++;
        Serial.println("│ ✅ Envoyé (total: " + String(successCount) + ")          │");
      } else {
        Serial.println("│ ❌ Échec envoi                      │");
      }
    } else {
      Serial.println("│ ⚠️  Distance hors limites           │");
    }
    
  } else {
    Serial.println("│ ❌ Beacon absent                    │");
  }
  
  Serial.println("└─────────────────────────────────────┘\n");
  
  delay(1000);
}