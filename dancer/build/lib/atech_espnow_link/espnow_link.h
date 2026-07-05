/**
 * @file espnow_link.h
 * @brief Board-to-board broadcast link over ESP-NOW for synced light shows.
 *
 * One conductor broadcasts {pattern, hue, clock} to the ESP-NOW broadcast
 * address; dancers receive it and render animations phase-locked to the
 * conductor's millisecond clock. No router, no pairing, no port pins used.
 */

#ifndef ESPNOW_LINK_H
#define ESPNOW_LINK_H

#include <Arduino.h>

class EspNowLink {
public:
    EspNowLink();

    void begin();
    void update();

    // conductor side
    void broadcast(uint8_t pattern, uint8_t hue);

    // dancer side
    bool linked() const;                 // packet received within last 3 s
    uint8_t pattern() const;
    uint8_t hue() const;

    // conductor-synchronized milliseconds (== millis() until a packet arrives)
    uint32_t syncedClock() const;

    // pattern renderer for the 3x3 NeoPixel grid, deterministic in (i, t)
    // patterns: 0 solid, 1 breathe, 2 rainbow chase, 3 sparkle
    static void pixelColor(int i, uint32_t t, uint8_t pattern, uint8_t hue,
                           uint8_t &r, uint8_t &g, uint8_t &b);
    static void hsvToRgb(uint8_t h, uint8_t v, uint8_t &r, uint8_t &g, uint8_t &b);
    static uint16_t hsvTo565(uint8_t h);

private:
    static void onRecv(const uint8_t *mac, const uint8_t *data, int len);
    static EspNowLink *s_self;

    volatile uint8_t _pattern;
    volatile uint8_t _hue;
    volatile uint32_t _lastRxMs;
    volatile int32_t _clockOffset;       // conductorClock - local millis()
    uint8_t _seq;
    bool _ready;
};

#endif
