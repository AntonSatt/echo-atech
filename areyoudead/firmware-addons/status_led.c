/**
 * @file status_led.c
 * @brief Solid-color node status on an Atech 3x3 NeoPixel grid (port 9).
 *
 * The Atech grid ships in two hardware variants (GRB WS2812 on pin A,
 * GRBW SK6812 on pin B); like the Atech SDK driver, we drive both port
 * pins with both protocols so either variant lights up. Brightness is
 * kept low (Atech caps at 51/255) — these boards may run on small
 * chargers next to a sensitive CSI radio.
 */
#include "status_led.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "led_strip.h"

#include "adaptive_controller.h"

static const char *TAG = "status_led";

#define STATUS_LED_GPIO_A   40   /* Atech port 9, pin A (GRB variant)  */
#define STATUS_LED_GPIO_B   41   /* Atech port 9, pin B (GRBW variant) */
#define STATUS_LED_COUNT    9    /* 3x3 grid */
#define STATUS_POLL_MS      500

static led_strip_handle_t s_strip_a;
static led_strip_handle_t s_strip_b;

static void set_all(uint8_t r, uint8_t g, uint8_t b)
{
    for (int i = 0; i < STATUS_LED_COUNT; i++) {
        if (s_strip_a) led_strip_set_pixel(s_strip_a, i, r, g, b);
        if (s_strip_b) led_strip_set_pixel_rgbw(s_strip_b, i, r, g, b, 0);
    }
    if (s_strip_a) led_strip_refresh(s_strip_a);
    if (s_strip_b) led_strip_refresh(s_strip_b);
}

static void status_led_task(void *arg)
{
    adapt_state_t last = (adapt_state_t)-1;
    for (;;) {
        adapt_state_t st = adaptive_controller_state();
        if (st != last) {
            last = st;
            switch (st) {
            case ADAPT_STATE_CALIBRATION:
                set_all(40, 32, 0);           /* yellow — learning empty room */
                break;
            case ADAPT_STATE_SENSE_IDLE:
                set_all(0, 18, 0);            /* dim green — healthy, room quiet */
                break;
            case ADAPT_STATE_SENSE_ACTIVE:
                set_all(0, 48, 0);            /* bright green — sensing activity */
                break;
            case ADAPT_STATE_ALERT:
                set_all(48, 0, 0);            /* red — anomaly / alert state */
                break;
            case ADAPT_STATE_DEGRADED:
                set_all(48, 16, 0);           /* orange — connected but no yield */
                break;
            default:                          /* BOOT..TIME_SYNC */
                set_all(12, 12, 12);          /* dim white — starting up */
                break;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(STATUS_POLL_MS));
    }
}

void status_led_start(void)
{
    led_strip_rmt_config_t rmt_config = {
        .resolution_hz = 10 * 1000 * 1000,
        .flags.with_dma = false,
    };

    led_strip_config_t cfg_a = {
        .strip_gpio_num = STATUS_LED_GPIO_A,
        .max_leds = STATUS_LED_COUNT,
        .led_model = LED_MODEL_WS2812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB,
        .flags.invert_out = false,
    };
    if (led_strip_new_rmt_device(&cfg_a, &rmt_config, &s_strip_a) != ESP_OK) {
        s_strip_a = NULL;
        ESP_LOGW(TAG, "strip A (GPIO %d) init failed", STATUS_LED_GPIO_A);
    }

    led_strip_config_t cfg_b = {
        .strip_gpio_num = STATUS_LED_GPIO_B,
        .max_leds = STATUS_LED_COUNT,
        .led_model = LED_MODEL_SK6812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRBW,
        .flags.invert_out = false,
    };
    if (led_strip_new_rmt_device(&cfg_b, &rmt_config, &s_strip_b) != ESP_OK) {
        s_strip_b = NULL;
        ESP_LOGW(TAG, "strip B (GPIO %d) init failed", STATUS_LED_GPIO_B);
    }

    if (!s_strip_a && !s_strip_b) {
        ESP_LOGW(TAG, "no status LED strip available — indicator disabled");
        return;
    }

    set_all(12, 12, 12); /* boot white immediately */
    xTaskCreate(status_led_task, "status_led", 2560, NULL, 2, NULL);
    ESP_LOGI(TAG, "status LED grid on GPIO %d/%d (%d px, poll %d ms)",
             STATUS_LED_GPIO_A, STATUS_LED_GPIO_B, STATUS_LED_COUNT, STATUS_POLL_MS);
}
