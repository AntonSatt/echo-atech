/**
 * @file stepper_motor.h
 * @brief Stepper Motor Driver Module (NEMA 17 + TMC2209) for Athera
 *
 * Controls a bipolar stepper motor (e.g. NEMA 17) via a TMC2209-LA-T
 * driver chip in legacy STEP/DIR mode (UART configuration not required;
 * the driver runs with whatever microstep / current settings are latched
 * by MS1/MS2/VREF on the carrier board).
 *
 * Pin behaviour:
 * - STEP: rising edge advances the rotor one microstep
 * - DIR:  HIGH = forward, LOW = reverse (mechanical direction depends on wiring)
 * - EN:   active LOW. LOW energises the coils (holding torque),
 *         HIGH disables the output stage (motor coasts, low power)
 *
 * Athera Connector mapping:
 * - Pin 1: VMOT (motor supply, typically 12-24V — supplied externally on driver board)
 * - Pin 4: GND
 * - Pin 5: STEP   (Data Line A)
 * - Pin 6: DIR    (Data Line B)
 * - Pin 7: ENABLE (Data Line C)
 *
 * Motion is blocking: step()/moveSteps()/moveTo() return after the
 * requested number of pulses have been issued. Speeds above a few
 * thousand steps/sec require careful timing — the driver clamps to a
 * safe maximum to avoid stalls from missed pulses.
 */

#ifndef STEPPER_MOTOR_MODULE_H
#define STEPPER_MOTOR_MODULE_H

#include <Arduino.h>

class StepperMotor {
public:
    /**
     * @brief Construct stepper motor controller
     * @param stepPin   GPIO connected to TMC2209 STEP
     * @param dirPin    GPIO connected to TMC2209 DIR
     * @param enablePin GPIO connected to TMC2209 EN (active low)
     */
    StepperMotor(int stepPin, int dirPin, int enablePin);

    /**
     * @brief Initialise pins. Motor starts disabled (coasting).
     */
    void begin();

    /**
     * @brief Run a relative move using the current direction.
     * @param numSteps        Number of microsteps to issue
     * @param stepsPerSecond  Pulse rate (default 800 steps/s)
     */
    void step(uint32_t numSteps, uint32_t stepsPerSecond = 800);

    /**
     * @brief Signed relative move. Positive = forward, negative = reverse.
     */
    void moveSteps(int32_t signedSteps, uint32_t stepsPerSecond = 800);

    /**
     * @brief Absolute move to a position counted from the last
     *        resetPosition() / power-on (no homing performed).
     */
    void moveTo(int32_t targetPosition, uint32_t stepsPerSecond = 800);

    /**
     * @brief Set direction without moving.
     * @param forward true = DIR HIGH, false = DIR LOW (subject to setReversed())
     */
    void setDirection(bool forward);

    /**
     * @brief Globally invert the meaning of "forward" for this motor.
     *
     * When set to true, every subsequent setDirection()/moveSteps() flips the
     * physical DIR pin relative to the requested logical direction. The
     * position counter still tracks the LOGICAL direction the caller asked
     * for, so user code doesn't need to know about the inversion.
     *
     * Use this when the motor is wired such that "forward" feels backwards
     * from the user's POV. Cheaper than re-wiring the motor coils.
     */
    void setReversed(bool reversed) { _reversed = reversed; }

    /** @brief Energise coils (active low EN -> LOW). */
    void enable();

    /** @brief Release coils (active low EN -> HIGH). Motor coasts. */
    void disable();

    /** @brief True if coils are currently energised. */
    bool isEnabled() const { return _enabled; }

    /** @brief Current signed position in microsteps. */
    int32_t getPosition() const { return _position; }

    /** @brief Reset the position counter to zero (no movement). */
    void resetPosition() { _position = 0; }

private:
    int _stepPin, _dirPin, _enablePin;
    int32_t _position;
    bool _direction;   // true = forward (logical, user-facing)
    bool _reversed;    // true = invert physical DIR pin vs logical direction
    bool _enabled;

    void _pulse(uint32_t halfPeriodMicros);
};

#endif // STEPPER_MOTOR_MODULE_H
