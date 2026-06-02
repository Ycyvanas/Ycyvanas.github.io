/**
 * @file camera_driver.c
 * @brief ESP32-S3摄像头驱动 - OV3660 硬件JPEG加速
 */
#include "camera_driver.h"
#include "esp_log.h"
#include "esp_psram.h"
#include "nvs_flash.h"

static const char *TAG = "camera_driver";
static bool camera_ready = false;

esp_err_t camera_init(void) {
    // 检测PSRAM
    bool psram_available = esp_psram_is_initialized();
    size_t psram_size = esp_psram_get_size();

    if (psram_available) {
        ESP_LOGI(TAG, "PSRAM可用: %d KB", (int)(psram_size / 1024));
    } else {
        ESP_LOGE(TAG, "❌ PSRAM未启用！硬件JPEG需要PSRAM");
        return ESP_ERR_NOT_SUPPORTED;
    }

    // OV3660配置 - VGA硬件JPEG模式 ⚡
    camera_config_t config = {
        .pin_pwdn = CAM_PIN_PWDN,
        .pin_reset = CAM_PIN_RESET,
        .pin_xclk = CAM_PIN_XCLK,
        .pin_sccb_sda = CAM_PIN_SIOD,
        .pin_sccb_scl = CAM_PIN_SIOC,
        .pin_d7 = CAM_PIN_D7,
        .pin_d6 = CAM_PIN_D6,
        .pin_d5 = CAM_PIN_D5,
        .pin_d4 = CAM_PIN_D4,
        .pin_d3 = CAM_PIN_D3,
        .pin_d2 = CAM_PIN_D2,
        .pin_d1 = CAM_PIN_D1,
        .pin_d0 = CAM_PIN_D0,
        .pin_vsync = CAM_PIN_VSYNC,
        .pin_href = CAM_PIN_HREF,
        .pin_pclk = CAM_PIN_PCLK,

        .xclk_freq_hz = 20000000,        // 20MHz XCLK (硬件JPEG稳定频率)
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,

        .pixel_format = PIXFORMAT_JPEG,    // ⚡ 硬件JPEG编码！
        .frame_size = FRAMESIZE_VGA,       // VGA 640x480
        .jpeg_quality = 12,                // JPEG质量 0-63
        .fb_count = 4,                     // 4帧缓冲，充分利用PSRAM带宽
        .fb_location = CAMERA_FB_IN_PSRAM, // PSRAM DMA对齐
        .grab_mode = CAMERA_GRAB_WHEN_EMPTY, // WHEN_EMPTY稳定
    };

    ESP_LOGI(TAG, "=== OV3660 硬件JPEG配置 ===");
    ESP_LOGI(TAG, "分辨率: VGA 640x480");
    ESP_LOGI(TAG, "格式: JPEG (硬件编码)");
    ESP_LOGI(TAG, "XCLK: 20 MHz");
    ESP_LOGI(TAG, "帧缓冲: 4个 (PSRAM)");

    // 初始化摄像头
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "❌ 摄像头初始化失败: %s", esp_err_to_name(err));
        return err;
    }

    // 获取传感器并优化配置
    sensor_t *s = esp_camera_sensor_get();
    if (!s) {
        ESP_LOGE(TAG, "❌ 无法获取传感器句柄");
        return ESP_ERR_NOT_FOUND;
    }

    ESP_LOGI(TAG, "✅ 传感器ID: 0x%04X (OV3660)", s->id);

    // OV3660图像质量优化
    s->set_brightness(s, 1);         // 亮度 +1
    s->set_contrast(s, 1);           // 对比度 +1
    s->set_saturation(s, 1);         // 饱和度 +1
    s->set_sharpness(s, 0);          // 锐度关闭 (不放大噪点)
    s->set_denoise(s, 3);            // 降噪最强

    s->set_whitebal(s, 1);           // 白平衡开
    s->set_awb_gain(s, 1);           // AWB增益开
    s->set_wb_mode(s, 0);            // 自动白平衡模式

    s->set_exposure_ctrl(s, 1);      // 自动曝光开
    s->set_gain_ctrl(s, 1);          // 自动增益开
    s->set_gainceiling(s, 0);        // 增益上限最小 (减少噪点)

    s->set_bpc(s, 1);                // 坏点校正开
    s->set_wpc(s, 1);                // 白点校正开
    s->set_raw_gma(s, 1);            // Gamma校正开
    s->set_lenc(s, 1);               // 镜头校正开

    ESP_LOGI(TAG, "✅ OV3660硬件JPEG加速已启用！");
    ESP_LOGI(TAG, "✅ 图像质量优化已应用");
    ESP_LOGI(TAG, "✅ JPEG编码由OV3660硬件完成，零CPU占用！");

    camera_ready = true;
    return ESP_OK;
}

bool camera_is_ready(void) {
    return camera_ready;
}

// 以下是从原ycycam复制的NVS函数（保持接口兼容）

void camera_save_framesize(int index) {
    nvs_handle_t nvs_handle;
    if (nvs_open("camera", NVS_READWRITE, &nvs_handle) == ESP_OK) {
        nvs_set_u8(nvs_handle, "framesize", index);
        nvs_commit(nvs_handle);
        nvs_close(nvs_handle);
        ESP_LOGI(TAG, "分辨率设置已保存: %d", index);
    }
}

void camera_save_xclk(int index) {
    nvs_handle_t nvs_handle;
    if (nvs_open("camera", NVS_READWRITE, &nvs_handle) == ESP_OK) {
        nvs_set_u8(nvs_handle, "xclk", index);
        nvs_commit(nvs_handle);
        nvs_close(nvs_handle);
        ESP_LOGI(TAG, "XCLK设置已保存: %d", index);
    }
}

int camera_get_saved_framesize_index(void) {
    return 5;  // 默认VGA (index 5 = 640x480)
}

int camera_get_saved_xclk_index(void) {
    return 2;  // 默认20MHz
}
