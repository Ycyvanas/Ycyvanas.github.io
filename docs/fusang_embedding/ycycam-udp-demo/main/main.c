/**
 * @file main.c
 * @brief ycycam-udp - OV3660硬件JPEG编码 + UDP发送
 * 
 * ⚡ 硬件JPEG加速: 跳过软件编码，直接发送OV3660输出的JPEG帧
 * CPU0: 摄像头采集 (硬件JPEG编码)
 * CPU1: UDP发送 (零拷贝)
 * 
 * 目标: VGA 640x480 30+ FPS
 */
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_psram.h"
#include "nvs_flash.h"
#include "esp_camera.h"
#include "driver/gpio.h"
#include "esp_heap_caps.h"

#include "wifi_handler.h"
#include "udp_stream.h"
#include "http_server.h"

static const char *TAG = "ycycam-udp";

// 系统心跳LED
#define HEARTBEAT_LED_GPIO  38

// 帧缓存 - 使用PSRAM DMA对齐
static uint8_t *jpeg_frame_buf = NULL;
static size_t jpeg_frame_len = 0;
static SemaphoreHandle_t frame_mutex = NULL;
static volatile uint32_t frame_id_counter = 0;

// 统计
static volatile uint32_t capture_fps = 0;
static volatile uint32_t send_fps = 0;

// LED闪烁周期配置 (毫秒)
static volatile uint32_t led_blink_period = 1000;
static volatile bool led_enabled = true;

// ==================== 系统心跳LED ====================
static void heartbeat_task(void *pvParameter) {
    bool led_state = false;
    gpio_reset_pin(HEARTBEAT_LED_GPIO);
    gpio_set_direction(HEARTBEAT_LED_GPIO, GPIO_MODE_OUTPUT);

    ESP_LOGI(TAG, "❤️ 系统心跳LED已启动 (GPIO%d)", HEARTBEAT_LED_GPIO);

    while (1) {
        if (led_enabled) {
            led_state = !led_state;
            gpio_set_level(HEARTBEAT_LED_GPIO, led_state);
        } else {
            led_state = false;
            gpio_set_level(HEARTBEAT_LED_GPIO, false);
        }
        // 使用可配置的闪烁周期
        vTaskDelay(pdMS_TO_TICKS(led_blink_period / 2));
    }
}

// 获取/设置LED配置
uint32_t get_led_blink_period(void) {
    return led_blink_period;
}

void set_led_blink_period(uint32_t period_ms) {
    if (period_ms >= 50 && period_ms <= 10000) {  // 50ms到10秒范围
        led_blink_period = period_ms;
    }
}

bool get_led_enabled(void) {
    return led_enabled;
}

void set_led_enabled(bool enable) {
    led_enabled = enable;
}

// ==================== CPU0: 硬件JPEG采集任务 ====================
static void capture_task(void *pvParameter) {
    ESP_LOGI(TAG, "📸 采集任务启动 (CPU%d) - OV3660硬件JPEG加速", xPortGetCoreID());

    camera_fb_t *fb = NULL;
    uint32_t fps_counter = 0;
    uint32_t last_report = xTaskGetTickCount();

    while (1) {
        // 获取硬件JPEG编码后的帧
        fb = esp_camera_fb_get();
        if (fb && fb->format == PIXFORMAT_JPEG) {
            // 零拷贝：直接复制PSRAM中的JPEG数据
            if (frame_mutex && xSemaphoreTake(frame_mutex, 0) == pdTRUE) {
                if (jpeg_frame_buf && fb->len < 256 * 1024) {
                    memcpy(jpeg_frame_buf, fb->buf, fb->len);
                    jpeg_frame_len = fb->len;
                }
                xSemaphoreGive(frame_mutex);
            }

            esp_camera_fb_return(fb);
            fps_counter++;
        } else if (fb) {
            // 不是JPEG格式，直接归还
            esp_camera_fb_return(fb);
        }

        // 每秒报告采集FPS
        uint32_t now = xTaskGetTickCount();
        if (now - last_report >= pdMS_TO_TICKS(1000)) {
            capture_fps = fps_counter;
            ESP_LOGI(TAG, "📸 采集: %lu FPS | JPEG大小: %u 字节",
                     capture_fps, (unsigned int)jpeg_frame_len);
            fps_counter = 0;
            last_report = now;
        }
    }
}

// ==================== CPU1: UDP发送任务 ====================
static void udp_send_task(void *pvParameter) {
    ESP_LOGI(TAG, "📡 UDP发送任务启动 (CPU%d)", xPortGetCoreID());

    uint8_t *frame_copy = NULL;
    size_t frame_copy_len = 0;
    uint32_t fps_counter = 0;
    uint32_t last_report = xTaskGetTickCount();

    // 分配帧拷贝缓冲 - 先尝试PSRAM，失败则用DRAM
    frame_copy = heap_caps_malloc(256 * 1024, MALLOC_CAP_SPIRAM);
    if (!frame_copy) {
        frame_copy = heap_caps_malloc(256 * 1024, MALLOC_CAP_8BIT);
    }
    if (!frame_copy) {
        ESP_LOGE(TAG, "❌ 帧缓冲分配失败！");
        vTaskDelete(NULL);
        return;
    }
    ESP_LOGI(TAG, "✅ 发送帧缓冲已分配");

    while (1) {
        // 等待新的硬件JPEG帧
        if (!jpeg_frame_buf || !frame_mutex) {
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        if (xSemaphoreTake(frame_mutex, pdMS_TO_TICKS(3)) != pdTRUE) {
            continue;
        }

        if (jpeg_frame_len == 0) {
            xSemaphoreGive(frame_mutex);
            vTaskDelay(pdMS_TO_TICKS(1));
            continue;
        }

        // 快速拷贝JPEG帧
        memcpy(frame_copy, jpeg_frame_buf, jpeg_frame_len);
        frame_copy_len = jpeg_frame_len;
        xSemaphoreGive(frame_mutex);

        // UDP发送硬件编码的JPEG帧 (零编码延迟!)
        udp_stream_send_frame(frame_copy, frame_copy_len, frame_id_counter++);
        fps_counter++;

        // 限制发送帧率在80FPS左右 (12.5ms间隔，FreeRTOS tick精度限制)
        vTaskDelay(pdMS_TO_TICKS(12));

        // 每秒报告发送FPS
        uint32_t now = xTaskGetTickCount();
        if (now - last_report >= pdMS_TO_TICKS(1000)) {
            send_fps = fps_counter;
            ESP_LOGI(TAG, "📡 发送: %lu FPS | 帧ID: %lu | 模式: 硬件JPEG VGA",
                     send_fps, frame_id_counter);
            fps_counter = 0;
            last_report = now;
        }
    }
}

void app_main(void) {
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "   ycycam-udp - OV3660 硬件JPEG加速");
    ESP_LOGI(TAG, "   VGA 640x480 | 零CPU编码延迟");
    ESP_LOGI(TAG, "========================================");

    // 初始化NVS (WiFi需要)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // PSRAM信息
    bool psram_inited = esp_psram_is_initialized();
    size_t psram_size = esp_psram_get_size();
    if (psram_inited && psram_size > 0) {
        ESP_LOGI(TAG, "✅ PSRAM已启用: %d KB", (int)(psram_size / 1024));
    } else {
        ESP_LOGE(TAG, "❌ PSRAM未启用！硬件JPEG需要PSRAM");
        return;
    }

    // 帧互斥锁和缓冲区 - 256KB足够VGA JPEG
    frame_mutex = xSemaphoreCreateMutex();
    jpeg_frame_buf = heap_caps_malloc(256 * 1024, MALLOC_CAP_SPIRAM);
    if (!jpeg_frame_buf) {
        ESP_LOGE(TAG, "❌ JPEG帧缓冲分配失败！");
        return;
    }
    ESP_LOGI(TAG, "✅ JPEG帧缓冲分配成功: 256 KB PSRAM");

    // 启动系统心跳LED任务
    xTaskCreatePinnedToCore(heartbeat_task, "heartbeat", 2048, NULL, 5, NULL, 0);

    // 初始化摄像头 - VGA硬件JPEG模式
    ESP_LOGI(TAG, "正在初始化摄像头 (硬件JPEG VGA)...");
    extern esp_err_t camera_init(void);
    ret = camera_init();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "❌ 摄像头初始化失败！");
        return;
    }
    ESP_LOGI(TAG, "✅ 摄像头 VGA 硬件JPEG模式初始化成功！");

    // 启动WiFi AP+STA
    ESP_LOGI(TAG, "正在启动 WiFi AP+STA...");
    wifi_init_apsta();

    // 启动HTTP配置服务器
    ESP_LOGI(TAG, "正在启动 HTTP 配置服务器...");
    http_server_start();
    ESP_LOGI(TAG, "✅ HTTP服务器: http://192.168.4.1");
    ESP_LOGI(TAG, "✅ WiFi配置: http://192.168.4.1/wifi");

    // 初始化UDP流 - 使用STA网络广播地址
    const char *target_ip = "192.168.2.255";  // STA网络广播地址
    ret = udp_stream_init(target_ip, 5000);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "❌ UDP初始化失败！");
        return;
    }
    ESP_LOGI(TAG, "✅ UDP已启动: 目标 %s:5000", target_ip);
    ESP_LOGI(TAG, "🌐 接收端地址: http://192.168.2.239:8000");

    // 启动UDP命令监听（端口5001）
    udp_cmd_listener_start();

    // ===== 双核架构 最高优先级 =====
    // CPU0: 采集任务 (最高优先级，不丢失硬件帧)
    xTaskCreatePinnedToCore(capture_task, "capture", 4096, NULL, configMAX_PRIORITIES - 1, NULL, 0);

    // CPU1: UDP发送任务 (次高优先级)
    xTaskCreatePinnedToCore(udp_send_task, "udp_send", 4096, NULL, configMAX_PRIORITIES - 2, NULL, 1);

    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "🎉 系统启动完成! 硬件JPEG加速已启用");
    ESP_LOGI(TAG, "📶 WiFi AP: ycycam (12345678)");
    ESP_LOGI(TAG, "📡 UDP端口: 5000 (广播)");
    ESP_LOGI(TAG, "📊 目标帧率: 30+ FPS (VGA 640x480)");
    ESP_LOGI(TAG, "========================================");
}
