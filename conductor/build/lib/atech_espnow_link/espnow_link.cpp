#include "espnow_link.h"

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

namespace {

constexpr uint32_t kMagic = 0x41544C31;  // "ATL1"
constexpr uint8_t kChannel = 1;
const uint8_t kBroadcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

struct __attribute__((packed)) LinkPacket {
    uint32_t magic;
    uint8_t pattern;
    uint8_t hue;
    uint8_t seq;
    uint8_t reserved;
    uint32_t clock;
};

}  // namespace

EspNowLink *EspNowLink::s_self = nullptr;

EspNowLink::EspNowLink()
    : _pattern(0), _hue(0), _lastRxMs(0), _clockOffset(0), _seq(0), _ready(false) {}

void EspNowLink::begin() {
    s_self = this;
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    esp_wifi_set_channel(kChannel, WIFI_SECOND_CHAN_NONE);
    if (esp_now_init() != ESP_OK) {
        return;
    }
    esp_now_register_recv_cb(&EspNowLink::onRecv);
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, kBroadcast, 6);
    peer.channel = 0;  // current channel
    peer.encrypt = false;
    esp_now_add_peer(&peer);
    _ready = true;
}

void EspNowLink::update() {}

void EspNowLink::broadcast(uint8_t pattern, uint8_t hue) {
    if (!_ready) return;
    LinkPacket p;
    p.magic = kMagic;
    p.pattern = pattern;
    p.hue = hue;
    p.seq = _seq++;
    p.reserved = 0;
    p.clock = millis();
    esp_now_send(kBroadcast, reinterpret_cast<const uint8_t *>(&p), sizeof p);
}

void EspNowLink::onRecv(const uint8_t *mac, const uint8_t *data, int len) {
    (void)mac;
    if (s_self == nullptr || len != (int)sizeof(LinkPacket)) return;
    LinkPacket p;
    memcpy(&p, data, sizeof p);
    if (p.magic != kMagic) return;
    s_self->_pattern = p.pattern;
    s_self->_hue = p.hue;
    s_self->_clockOffset = (int32_t)(p.clock - millis());
    s_self->_lastRxMs = millis();
}

bool EspNowLink::linked() const {
    return _lastRxMs != 0 && (millis() - _lastRxMs) < 3000UL;
}

uint8_t EspNowLink::pattern() const { return _pattern; }
uint8_t EspNowLink::hue() const { return _hue; }

uint32_t EspNowLink::syncedClock() const {
    return millis() + (uint32_t)_clockOffset;
}

void EspNowLink::hsvToRgb(uint8_t h, uint8_t v, uint8_t &r, uint8_t &g, uint8_t &b) {
    uint8_t region = h / 43;
    uint8_t rem = (uint8_t)((h - region * 43) * 6);
    uint8_t q = (uint8_t)((v * (255 - rem)) >> 8);
    uint8_t t = (uint8_t)((v * rem) >> 8);
    switch (region) {
        case 0:  r = v; g = t; b = 0; break;
        case 1:  r = q; g = v; b = 0; break;
        case 2:  r = 0; g = v; b = t; break;
        case 3:  r = 0; g = q; b = v; break;
        case 4:  r = t; g = 0; b = v; break;
        default: r = v; g = 0; b = q; break;
    }
}

uint16_t EspNowLink::hsvTo565(uint8_t h) {
    uint8_t r, g, b;
    hsvToRgb(h, 255, r, g, b);
    return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

void EspNowLink::pixelColor(int i, uint32_t t, uint8_t pattern, uint8_t hue,
                            uint8_t &r, uint8_t &g, uint8_t &b) {
    // grid indices: 0 1 2 / 3 4 5 / 6 7 8; clockwise ring position, center = -1
    static const int8_t kRing[9] = {0, 1, 2, 7, -1, 3, 6, 5, 4};
    switch (pattern & 3) {
        case 0:  // solid
            hsvToRgb(hue, 255, r, g, b);
            return;
        case 1: {  // breathe
            float s = 0.5f + 0.5f * sinf((float)(t % 2000UL) * (6.2831853f / 2000.0f));
            hsvToRgb(hue, (uint8_t)(30 + 225 * s), r, g, b);
            return;
        }
        case 2: {  // rainbow chase around the ring
            int rp = kRing[i];
            if (rp < 0) {
                hsvToRgb(hue, 40, r, g, b);
                return;
            }
            int head = (int)((t / 90) % 8);
            int d = (rp - head) & 7;
            uint8_t v = (d == 0) ? 255 : (d == 1) ? 120 : (d == 2) ? 40 : 0;
            hsvToRgb((uint8_t)(hue + rp * 8), v, r, g, b);
            return;
        }
        default: {  // sparkle, deterministic in (i, time slot) so boards match
            uint32_t slot = t / 150;
            uint32_t x = (uint32_t)i * 2654435761UL ^ slot * 2246822519UL;
            x ^= x >> 13;
            x *= 0x85EBCA6BUL;
            x ^= x >> 16;
            if ((x & 7) < 3) {
                hsvToRgb((uint8_t)(hue + ((x >> 8) & 31)), 255, r, g, b);
            } else {
                r = g = b = 0;
            }
            return;
        }
    }
}
