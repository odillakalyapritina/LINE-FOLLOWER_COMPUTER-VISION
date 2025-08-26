#include <WiFi.h>
#include <WebServer.h>

// Konfigurasi WiFi
const char* ssid = "Dil’s iPhone";
const char* password = "asdfghjkl";

// Konfigurasi pin motor sesuai spesifikasi
const int enA = 13;      // Enable motor kanan (PWM)
const int in1 = 12;      // IN1 - Maju motor kanan
const int in2 = 14;      // IN2 - Mundur motor kanan

const int enB = 15;      // Enable motor kiri (PWM)
const int in3 = 27;      // IN3 - Mundur motor kiri
const int in4 = 26;      // IN4 - Maju motor kiri

// Kecepatan motor
const int fullSpeed = 150;    // Kecepatan penuh (0-255)
const int turnSpeed = 100;    // Kecepatan belok
const int hardTurnSpeed = 100; // Kecepatan belok tajam

WebServer server(80);

void setup() {
  Serial.begin(115200);
  
  // Inisialisasi pin motor
  pinMode(enA, OUTPUT);
  pinMode(enB, OUTPUT);
  pinMode(in1, OUTPUT);
  pinMode(in2, OUTPUT);
  pinMode(in3, OUTPUT);
  pinMode(in4, OUTPUT);
  
  // Stop motor awal
  stopMotor();
  
  // Koneksi WiFi
  WiFi.begin(ssid, password);
  Serial.print("Menghubungkan ke WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\nTerhubung WiFi!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  
  // Setup HTTP endpoints
  server.on("/forward", []() { handleCommand("MAJU"); forward(); });
  server.on("/right", []() { handleCommand("BELOK KANAN"); right(); });
  server.on("/hard_right", []() { handleCommand("BELOK KANAN TAJAM"); hardRight(); });
  server.on("/left", []() { handleCommand("BELOK KIRI"); left(); });
  server.on("/hard_left", []() { handleCommand("BELOK KIRI TAJAM"); hardLeft(); });
  server.on("/stop", []() { handleCommand("BERHENTI"); stopMotor(); });
  
  server.begin();
  Serial.println("Server HTTP dimulai");
}

void loop() {
  server.handleClient();
}

void handleCommand(String cmd) {
  Serial.println("Perintah: " + cmd);
  server.send(200, "text/plain", "OK: " + cmd);
}

// ====================================================
// FUNGSI GERAKAN MOTOR DENGAN KONFIGURASI PIN BARU
// ====================================================

void forward() {
  // Motor kanan maju (in1 HIGH)
  digitalWrite(in1, HIGH);
  digitalWrite(in2, LOW);
  
  // Motor kiri maju (in4 HIGH)
  digitalWrite(in3, LOW);
  digitalWrite(in4, HIGH);
  
  analogWrite(enA, fullSpeed);
  analogWrite(enB, fullSpeed);
}

void right() {
  // Motor kanan pelan (maju)
  digitalWrite(in1, HIGH);
  digitalWrite(in2, LOW);
  
  // Motor kiri maju penuh
  digitalWrite(in3, LOW);
  digitalWrite(in4, HIGH);
  
  analogWrite(enA, turnSpeed);
  analogWrite(enB, fullSpeed);
}

void hardRight() {
  // Motor kanan mundur (in2 HIGH)
  digitalWrite(in1, LOW);
  digitalWrite(in2, HIGH);
  
  // Motor kiri maju penuh
  digitalWrite(in3, LOW);
  digitalWrite(in4, HIGH);
  
  analogWrite(enA, hardTurnSpeed);
  analogWrite(enB, hardTurnSpeed);
}

void left() {
  // Motor kanan maju penuh
  digitalWrite(in1, HIGH);
  digitalWrite(in2, LOW);
  
  // Motor kiri pelan (maju)
  digitalWrite(in3, LOW);
  digitalWrite(in4, HIGH);
  
  analogWrite(enA, fullSpeed);
  analogWrite(enB, turnSpeed);
}

void hardLeft() {
  // Motor kanan maju penuh
  digitalWrite(in1, HIGH);
  digitalWrite(in2, LOW);
  
  // Motor kiri mundur (in3 HIGH)
  digitalWrite(in3, HIGH);
  digitalWrite(in4, LOW);
  
  analogWrite(enA, hardTurnSpeed);
  analogWrite(enB, hardTurnSpeed);
}

void stopMotor() {
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
  digitalWrite(in3, LOW);
  digitalWrite(in4, LOW);
  analogWrite(enA, 0);
  analogWrite(enB, 0);
}