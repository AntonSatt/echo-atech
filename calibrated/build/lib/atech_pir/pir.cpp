/**
 * @file pir.cpp
 * @brief AM312 PIR motion sensor implementation.
 *
 * Polled digital input with edge detection — no debouncing needed (the AM312
 * holds its OUT line stable for ~2 s after a trigger), no internal pull
 * configuration (the AM312 actively drives 3.3V on OUT and 0V at rest).
 */

#include "pir.h"
#include <limits.h>

PIRSensor::PIRSensor(int pin)
    : _pin(pin)
    , _lastState(false)
    , _triggeredFlag(false)
    , _clearedFlag(false)
    , _bootMillis(0)
    , _lastMotionMillis(0)
    , _everTriggered(false)
{
}

void PIRSensor::begin() {
    pinMode(_pin, INPUT);
    _bootMillis = millis();
    _lastState = (digitalRead(_pin) == HIGH);
    Serial.printf("PIR initialised on pin %d (warming up for %lums)\n",
                  _pin, (unsigned long)DEFAULT_WARMUP_MS);
}

void PIRSensor::update() {
    bool now = (digitalRead(_pin) == HIGH);
    if (now && !_lastState) {
        _triggeredFlag = true;
        _lastMotionMillis = millis();
        _everTriggered = true;
    } else if (!now && _lastState) {
        _clearedFlag = true;
    }
    _lastState = now;
}

bool PIRSensor::isMotionDetected() {
    return _lastState;
}

bool PIRSensor::wasTriggered() {
    bool f = _triggeredFlag;
    _triggeredFlag = false;  // consume the edge
    return f;
}

bool PIRSensor::wasCleared() {
    bool f = _clearedFlag;
    _clearedFlag = false;
    return f;
}

bool PIRSensor::isWarmedUp() {
    return (millis() - _bootMillis) >= DEFAULT_WARMUP_MS;
}

unsigned long PIRSensor::timeSinceLastMotion() {
    if (!_everTriggered) return ULONG_MAX;
    return millis() - _lastMotionMillis;
}
