/**
 * @file wifi_handler.h
 * @brief WiFi AP+STA模式管理 + NVS配置存储
 */
#ifndef WIFI_HANDLER_H
#define WIFI_HANDLER_H

#include "esp_err.h"
#include "esp_wifi.h"

#ifdef __cplusplus
extern "C" {
#endif

// WiFi AP配置
#define WIFI_AP_SSID    "ycycam"
#define WIFI_AP_PASS    "12345678"
#define WIFI_AP_CHANNEL  6
#define MAX_STA_CONN     4

/**
 * @brief 初始化WiFi AP+STA模式
 */
esp_err_t wifi_init_apsta(void);

/**
 * @brief 获取STA连接状态
 */
bool wifi_is_sta_connected(void);

/**
 * @brief 获取STA IP地址字符串
 */
const char* wifi_get_sta_ip(void);

/**
 * @brief 保存WiFi配置到NVS
 */
esp_err_t wifi_save_config(const char *ssid, const char *password);

/**
 * @brief 从NVS加载WiFi配置
 */
esp_err_t wifi_load_config(char *ssid, size_t ssid_len, char *password, size_t pass_len);

/**
 * @brief 使用新配置重新连接WiFi
 */
esp_err_t wifi_reconnect(const char *ssid, const char *password);

#ifdef __cplusplus
}
#endif

#endif // WIFI_HANDLER_H
