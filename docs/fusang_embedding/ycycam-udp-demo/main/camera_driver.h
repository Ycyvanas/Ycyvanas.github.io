/**
 * @file camera_driver.h
 * @brief ESP32-S3摄像头驱动 - OV3660
 */
#ifndef CAMERA_DRIVER_H
#define CAMERA_DRIVER_H

#include "esp_err.h"
#include "esp_camera.h"

#ifdef __cplusplus
extern "C" {
#endif

// 摄像头引脚配置 (ESP32-S3 CAM)
// 引脚对应: CAM_Y9→D7, CAM_Y8→D6, CAM_Y7→D5, CAM_Y6→D4, CAM_Y5→D3, CAM_Y4→D2, CAM_Y3→D1, CAM_Y2→D0
#define CAM_PIN_PWDN    2
#define CAM_PIN_RESET   -1
#define CAM_PIN_XCLK    15
#define CAM_PIN_SIOD    4
#define CAM_PIN_SIOC    5
#define CAM_PIN_D7      16   // CAM_Y9
#define CAM_PIN_D6      17   // CAM_Y8
#define CAM_PIN_D5      18   // CAM_Y7
#define CAM_PIN_D4      12   // CAM_Y6
#define CAM_PIN_D3      10   // CAM_Y5
#define CAM_PIN_D2      8    // CAM_Y4
#define CAM_PIN_D1      9    // CAM_Y3
#define CAM_PIN_D0      11   // CAM_Y2
#define CAM_PIN_VSYNC   6
#define CAM_PIN_HREF    7
#define CAM_PIN_PCLK    13

// 摄像头配置
#define CAMERA_XCLK     20000000  // XCLK时钟频率 (恢复到20MHz，避免彩虹噪点)
#define CAMERA_WIDTH    240       // 宽度
#define CAMERA_HEIGHT   240       // 高度

/**
 * @brief 初始化摄像头
 */
esp_err_t camera_init(void);

/**
 * @brief 检查摄像头是否就绪
 */
bool camera_is_ready(void);

#ifdef __cplusplus
}
#endif

#endif // CAMERA_DRIVER_H
