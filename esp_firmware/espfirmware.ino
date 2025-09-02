// Combined TB6612FNG + INA219 firmware
#include <INA219_WE.h>
#include <Wire.h>

// Motor pins for ESP32
const uint8_t PWMA = 25, AIN1 = 21, AIN2 = 17;
const uint8_t PWMB = 26, BIN1 = 22, BIN2 = 23;
const int8_t  STBY = -1;

// INA219 settings
#define S_SDA 32
#define S_SCL 33
#define INA219_ADDRESS 0x42
INA219_WE ina219 = INA219_WE(INA219_ADDRESS);

float loadVoltage_V = 12.0;
float current_mA = 0.0;
bool ina219_available = false;

void setup() {
  Serial.begin(115200);
  
  // Motor pins
  pinMode(AIN1,OUTPUT); pinMode(AIN2,OUTPUT);
  pinMode(BIN1,OUTPUT); pinMode(BIN2,OUTPUT);
  pinMode(PWMA,OUTPUT); pinMode(PWMB,OUTPUT);
  if (STBY>=0){ pinMode(STBY,OUTPUT); digitalWrite(STBY, HIGH); }
  stopBoth();
  
  // INA219 setup
  Wire.begin(S_SDA, S_SCL);
  if(ina219.init()){
    ina219.setADCMode(BIT_MODE_9);
    ina219.setPGain(PG_320);
    ina219.setBusRange(BRNG_16);
    ina219.setShuntSizeInOhms(0.01);
    ina219_available = true;
    Serial.println(F("{\"boot\":true,\"ina219\":true}"));
  } else {
    Serial.println(F("{\"boot\":true,\"ina219\":false}"));
  }
}

void loop() {
  static uint32_t lastHeartbeat = 0;
  static uint32_t lastBatteryRead = 0;
  
  // Handle serial commands
  if (Serial.available()){
    String line = Serial.readStringUntil('\n');
    line.trim();
    handle(line);
  }
  
  // Update battery reading every 100ms
  if (millis() - lastBatteryRead > 100 && ina219_available){
    lastBatteryRead = millis();
    updateBattery();
  }
  
  // Send heartbeat with battery info every 500ms
  if (millis() - lastHeartbeat > 500){
    lastHeartbeat = millis();
    sendStatus();
  }
}

void updateBattery(){
  if (ina219_available){
    float shuntVoltage_mV = ina219.getShuntVoltage_mV();
    float busVoltage_V = ina219.getBusVoltage_V();
    current_mA = ina219.getCurrent_mA();
    loadVoltage_V = busVoltage_V + (shuntVoltage_mV/1000);
  }
}

void sendStatus(){
  Serial.print(F("{\"ok\":true,\"voltage\":"));
  Serial.print(loadVoltage_V, 2);
  Serial.print(F(",\"current\":"));
  Serial.print(current_mA, 1);
  Serial.print(F(",\"ts\":"));
  Serial.print(millis());
  Serial.println('}');
}

void handle(const String& line){
  if (line.length()==0) return;
  
  if (line.startsWith("STATUS")){
    sendStatus();
    return;
  }
  
  if (line.startsWith("STOP")){
    stopBoth();
    Serial.print(F("{\"ack\":\"STOP\",\"voltage\":"));
    Serial.print(loadVoltage_V, 2);
    Serial.println('}');
    return;
  }
  
  if (line.startsWith("PWM")){
    long l=0,r=0;
    if (sscanf(line.c_str(),"PWM %ld %ld",&l,&r)==2){
      driveA((int)constrain(l,-255,255));
      driveB((int)constrain(r,-255,255));
      Serial.print(F("{\"ack\":\"PWM\",\"L\":"));Serial.print((int)l);
      Serial.print(F(",\"R\":"));Serial.print((int)r);
      Serial.print(F(",\"voltage\":"));Serial.print(loadVoltage_V, 2);
      Serial.println('}');
      return;
    }
  }
  
  Serial.print(F("{\"err\":\"bad_cmd\",\"voltage\":"));
  Serial.print(loadVoltage_V, 2);
  Serial.println('}');
}

void driveA(int spd){
  if (spd>=0){ digitalWrite(AIN1,HIGH); digitalWrite(AIN2,LOW);  analogWrite(PWMA,spd); }
  else        { digitalWrite(AIN1,LOW);  digitalWrite(AIN2,HIGH); analogWrite(PWMA,-spd); }
}

void driveB(int spd){
  if (spd>=0){ digitalWrite(BIN1,HIGH); digitalWrite(BIN2,LOW);  analogWrite(PWMB,spd); }
  else        { digitalWrite(BIN1,LOW);  digitalWrite(BIN2,HIGH); analogWrite(PWMB,-spd); }
}

void stopBoth(){
  analogWrite(PWMA,0); analogWrite(PWMB,0);
  digitalWrite(AIN1,LOW); digitalWrite(AIN2,LOW);
  digitalWrite(BIN1,LOW); digitalWrite(BIN2,LOW);
  if (STBY>=0) digitalWrite(STBY,LOW);
}