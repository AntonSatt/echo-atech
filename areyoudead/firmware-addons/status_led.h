/**
 * @file status_led.h
 * @brief Solid-color node status indicator on an external NeoPixel grid.
 *
 * Hackathon addition (MagasinX 2026): drives an Atech 3x3 NeoPixel grid
 * plugged into Atech port 9 (GPIO 40/41 on the 14-port ESP32-S3 board).
 * Color = adaptive controller state, steady (no blinking):
 *   white  = booting        yellow = calibrating
 *   green  = sensing (dim = idle room, bright = activity)
 *   red    = alert          orange = degraded (no CSI yield)
 */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

void status_led_start(void);

#ifdef __cplusplus
}
#endif
