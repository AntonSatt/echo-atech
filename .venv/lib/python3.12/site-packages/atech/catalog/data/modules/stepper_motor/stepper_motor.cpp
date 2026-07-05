/**
 * @file stepper_motor.cpp
 * @brief Stepper Motor Driver Implementation (NEMA 17 + TMC2209)
 */

#include "stepper_motor.h"

// TMC2209 datasheet: STEP minimum HIGH/LOW time is 100 ns. We pulse at
// micro-second granularity which is comfortably above that. Cap the pulse
// rate so very small period values don't drop below a usable pulse width.
static const uint32_t MAX_STEPS_PER_SECOND = 20000;  // 50 us full period
static const uint32_t MIN_STEPS_PER_SECOND = 1;

StepperMotor::StepperMotor(int stepPin, int dirPin, int enablePin)
    : _stepPin(stepPin)
    , _dirPin(dirPin)
    , _enablePin(enablePin)
    , _position(0)
    , _direction(true)
    , _reversed(true)   // default reversed: matches the intuitive knob-CW = motor-CW feel
    , _enabled(false)
{}

void StepperMotor::begin() {
    pinMode(_stepPin, OUTPUT);
    pinMode(_dirPin, OUTPUT);
    pinMode(_enablePin, OUTPUT);

    digitalWrite(_stepPin, LOW);
    digitalWrite(_dirPin, _direction ? HIGH : LOW);

    disable();  // start with coils released
}

void StepperMotor::enable() {
    digitalWrite(_enablePin, LOW);  // active low
    _enabled = true;
}

void StepperMotor::disable() {
    digitalWrite(_enablePin, HIGH);
    _enabled = false;
}

void StepperMotor::setDirection(bool forward) {
    _direction = forward;
    bool physical = _reversed ? !forward : forward;
    digitalWrite(_dirPin, physical ? HIGH : LOW);
    // TMC2209 needs DIR stable ~20 ns before STEP edge — a few us is plenty.
    delayMicroseconds(2);
}

void StepperMotor::step(uint32_t numSteps, uint32_t stepsPerSecond) {
    if (numSteps == 0) return;
    if (!_enabled) enable();

    if (stepsPerSecond < MIN_STEPS_PER_SECOND) stepsPerSecond = MIN_STEPS_PER_SECOND;
    if (stepsPerSecond > MAX_STEPS_PER_SECOND) stepsPerSecond = MAX_STEPS_PER_SECOND;

    // Half-period in microseconds. 1e6 / freq gives full period; halve for HIGH/LOW phases.
    uint32_t halfPeriod = 500000UL / stepsPerSecond;
    if (halfPeriod < 2) halfPeriod = 2;  // keep above TMC2209 min pulse width with margin

    int32_t delta = _direction ? 1 : -1;
    for (uint32_t i = 0; i < numSteps; ++i) {
        _pulse(halfPeriod);
        _position += delta;
    }
}

void StepperMotor::moveSteps(int32_t signedSteps, uint32_t stepsPerSecond) {
    if (signedSteps == 0) return;
    setDirection(signedSteps > 0);
    uint32_t magnitude = (signedSteps > 0) ? (uint32_t)signedSteps : (uint32_t)(-signedSteps);
    step(magnitude, stepsPerSecond);
}

void StepperMotor::moveTo(int32_t targetPosition, uint32_t stepsPerSecond) {
    int32_t delta = targetPosition - _position;
    if (delta != 0) moveSteps(delta, stepsPerSecond);
}

void StepperMotor::_pulse(uint32_t halfPeriodMicros) {
    digitalWrite(_stepPin, HIGH);
    delayMicroseconds(halfPeriodMicros);
    digitalWrite(_stepPin, LOW);
    delayMicroseconds(halfPeriodMicros);
}
