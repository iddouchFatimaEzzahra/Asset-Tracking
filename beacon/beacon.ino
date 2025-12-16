/*

 * ═══════════════════════════════════════════════════════
 *  CODE BEACON SIMPLIFIÉ - ESP32 #1 (MOBILE)
 *  Projet: Asset Tracking BLE
 *  École: ENSA Oujda - IDSCC
 * ═══════════════════════════════════════════════════════
 * 
 *  Compatible avec la bibliothèque BLE native ESP32 v3.x
 *  IMPORTANT: Supprimer toute autre bibliothèque BLE externe
 */

#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLEAdvertising.h>

// ═══════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════
#define SERVICE_UUID        "f7826da6-4fa2-4e98-8024-bc5b71e0893e"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

BLEServer* pServer = NULL;
BLEAdvertising* pAdvertising = NULL;
uint32_t counter = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("╔═══════════════════════════════════════╗");
  Serial.println("║   BEACON BLE - ASSET TRACKING         ║");
  Serial.println("║   ENSA Oujda - Projet IoT             ║");
  Serial.println("╚═══════════════════════════════════════╝");
  Serial.println();
  
  // ═════════════════════════════════════
  // INITIALISATION BLE
  // ═════════════════════════════════════
  Serial.print("→ Initialisation BLE... ");
  BLEDevice::init("AssetBeacon");
  Serial.println("✓");
  
  // Créer le serveur BLE
  Serial.print("→ Création serveur... ");
  pServer = BLEDevice::createServer();
  Serial.println("✓");
  
  // Créer un service
  Serial.print("→ Création service... ");
  BLEService* pService = pServer->createService(SERVICE_UUID);
  Serial.println("✓");
  
  // Créer une caractéristique
  Serial.print("→ Création caractéristique... ");
  BLECharacteristic* pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
  );
  pCharacteristic->setValue("AssetBeacon");
  Serial.println("✓");
  
  // Démarrer le service
  Serial.print("→ Démarrage service... ");
  pService->start();
  Serial.println("✓");
  
  // Configuration de la publicité
  Serial.print("→ Configuration publicité... ");
  pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);

  pAdvertising->setMaxPreferred(0x12);
  Serial.println("✓");
  
  // Démarrer la publicité
  Serial.print("→ Démarrage diffusion... ");
  BLEDevice::startAdvertising();
  Serial.println("✓");
  
  // ═════════════════════════════════════
  // CONFIRMATION
  // ═════════════════════════════════════
  Serial.println();
  Serial.println("╔═══════════════════════════════════════╗");
  Serial.println("║  ✅ BEACON ACTIF ET EN DIFFUSION !    ║");
  Serial.println("╚═══════════════════════════════════════╝");
  Serial.println();
  Serial.println("📡 INFORMATIONS DU BEACON :");
  Serial.println("   Service UUID : " + String(SERVICE_UUID));
  Serial.println("   Nom BLE      : AssetBeacon");
  Serial.println("   État         : ACTIF");
  Serial.println();
  Serial.println("✅ Les scanners peuvent maintenant détecter ce beacon !");
  Serial.println("💡 Ce beacon émet son signal en continu");
  Serial.println("💡 Déplace-le pour tester la localisation");
  Serial.println();
  Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  Serial.println();
}

void loop() {
  // Le beacon diffuse automatiquement en arrière-plan
  // Afficher un indicateur d'activité
  
  counter++;
  
  if (counter % 50 == 0) {  // Toutes les 5 secondes environ
    Serial.print(".");
    
    if (counter % 600 == 0) {  // Toutes les 60 secondes
      Serial.println(" [" + String(millis() / 1000) + "s] Beacon actif");
    }
  }
  
  delay(100);
}