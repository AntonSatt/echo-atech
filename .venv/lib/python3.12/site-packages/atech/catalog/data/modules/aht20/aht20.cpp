/**
 * @file aht20.cpp
 * @brief AHT20 Temperature & Humidity Sensor implementation for Athera
 *
 * Background FreeRTOS task triggers measurements every ~2s.
 * Public methods return cached values for non-blocking access.
 */

#include "aht20.h"
#include <Arduino.h>

static void measureTaskTrampoline(void* param) {
    ((AHT20*)param)->_measureTaskLoop();
}

AHT20::AHT20(I2CInterface* i2c, uint8_t address)
    : _i2c(i2c)
    , _address(address)
    , _measureTask(nullptr)
    , _temperature(0)
    , _humidity(0)
{
}

bool AHT20::begin() {
    // Wait for sensor power-on
    vTaskDelay(pdMS_TO_TICKS(100));

    if (!isConnected()) {
        Serial.println("AHT20 not responding!");
        return false;
    }

    // Check calibration status and init if needed
    if (!_initCalibration()) {
        Serial.println("AHT20 calibration failed!");
        return false;
    }

    // Start background measurement task on Core 0
    xTaskCreatePinnedToCore(
        measureTaskTrampoline,
        "AHT20",
        2048,
        this,
        1,       // Lower priority than IMU
        &_measureTask,
        0
    );

    Serial.println("AHT20 initialized");
    return true;
}

float AHT20::readTemperature() { return _temperature; }
float AHT20::readHumidity() { return _humidity; }

bool AHT20::isConnected() {
    _i2c->beginTransmission(_address);
    return _i2c->endTransmission() == 0;
}

// ========== Background task ==========

void AHT20::_measureTaskLoop() {
    // Initial delay to let sensor settle
    vTaskDelay(pdMS_TO_TICKS(500));

    while (true) {
        if (_triggerMeasurement()) {
            vTaskDelay(pdMS_TO_TICKS(80));  // Measurement takes ~75ms
            _readMeasurement();
        }
        vTaskDelay(pdMS_TO_TICKS(2000));  // Measure every ~2s
    }
}

// ========== Private methods ==========

bool AHT20::_initCalibration() {
    // Read status byte
    if (_i2c->requestFrom(_address, (size_t)1) < 1) return false;
    uint8_t status = _i2c->read();

    // If not calibrated (bit 3), send init command
    if (!(status & 0x08)) {
        _i2c->beginTransmission(_address);
        _i2c->write((uint8_t)0xBE);
        _i2c->write((uint8_t)0x08);
        _i2c->write((uint8_t)0x00);
        if (_i2c->endTransmission() != 0) return false;
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    return true;
}

bool AHT20::_triggerMeasurement() {
    _i2c->beginTransmission(_address);
    _i2c->write((uint8_t)0xAC);
    _i2c->write((uint8_t)0x33);
    _i2c->write((uint8_t)0x00);
    return _i2c->endTransmission() == 0;
}

bool AHT20::_readMeasurement() {
    if (_i2c->requestFrom(_address, (size_t)7) < 7) return false;

    uint8_t data[7];
    for (int i = 0; i < 7; i++) {
        data[i] = _i2c->read();
    }

    // Check busy bit
    if (data[0] & 0x80) return false;

    // Humidity: data[1], data[2], upper 4 bits of data[3]
    uint32_t humRaw = ((uint32_t)data[1] << 12) |
                      ((uint32_t)data[2] << 4) |
                      ((uint32_t)data[3] >> 4);

    // Temperature: lower 4 bits of data[3], data[4], data[5]
    uint32_t tempRaw = (((uint32_t)data[3] & 0x0F) << 16) |
                       ((uint32_t)data[4] << 8) |
                       (uint32_t)data[5];

    _humidity = (humRaw / 1048576.0f) * 100.0f;
    _temperature = (tempRaw / 1048576.0f) * 200.0f - 50.0f;

    return true;
}
