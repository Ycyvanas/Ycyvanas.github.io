/**
 * @file http_server.h
 * @brief HTTP Web服务器 - 主页/视频流/WiFi配置
 */
#ifndef HTTP_SERVER_H
#define HTTP_SERVER_H

#include "esp_err.h"
#include "esp_http_server.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief 启动HTTP Web服务器
 */
httpd_handle_t http_server_start(void);

/**
 * @brief 停止HTTP Web服务器
 */
void http_server_stop(httpd_handle_t server);

#ifdef __cplusplus
}
#endif

#endif // HTTP_SERVER_H
