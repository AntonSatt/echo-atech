/**
 * @file pir.h
 * @brief PIR (Passive Infrared) Motion Sensor for Athera — AM312 module
 *
 * The AM312 mini PIR module exposes a single 3.3V-compatible digital output
 * that drives HIGH (~3.3V) for roughly 2 s after motion is detected within
 * its ~3-5 m / 100° cone, then returns LOW. The sensor handles its own
 * debouncing and re-trigger window in hardware; this driver only owns the
 * pin read and edge bookkeeping.
 *
 * Power: 2.7-12 V DC — driven directly from the port's 3.3 V rail.
 *
 * After power-on the AM312 needs ~30-60 s to thermally stabilise; the
 * sensor will report spurious motion during that window. `isWarmedUp()`
 * reports true once the conservative warmup period has elapsed since
 * `begin()`.
 *
 * Athera Connector:
 * - Line A: OUT (digital output from the PIR)
 * - Line B: unused
 */

#ifndef PIR_MODULE_H
#define PIR_MODULE_H

#include <Arduino.h>

class PIRSensor {
public:
    static constexpr unsigned long DEFAULT_WARMUP_MS = 30000;  // 30 s

    /**
     * @brief Construct PIR sensor
     * @param pin GPIO connected to the AM312 OUT line
     */
    explicit PIRSensor(int pin);

    /**
     * @brief Initialize the pin and start the warmup clock
     */
    void begin();

    /**
     * @brief Sample the pin and update edge flags.
     * Call once per loop iteration before checking wasTriggered/wasCleared.
     */
    void update();

    /** @brief Current sensor state — HIGH if motion is being detected right now */
    bool isMotionDetected();

    /** @brief True once since the last update() if motion just started (rising edge) */
    bool wasTriggered();

    /** @brief True once since the last update() if motion just ended (falling edge) */
    bool wasCleared();

    /** @brief True once the warmup window has elapsed since begin() */
    bool isWarmedUp();

    /** @brief Milliseconds since the most recent motion event (LONG_MAX if none yet) */
    unsigned long timeSinceLastMotion();

private:
    int _pin;
    bool _lastState;
    bool _triggeredFlag;
    bool _clearedFlag;
    unsigned long _bootMillis;
    unsigned long _lastMotionMillis;
    bool _everTriggered;
};

#endif // PIR_MODULE_H
