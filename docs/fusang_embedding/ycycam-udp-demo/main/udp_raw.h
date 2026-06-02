/**
 * @file udp_raw.h
 * @brief UDP原始像素传输 (无JPEG编码，零延迟)
 * 
 * 协议: 每个UDP包 = 4字节头部 + 像素数据
 * 头部: frame_id(2字节) + packet_id(1字节) + total_packets(1字节)
 * 
 * QVGA 320x240 RGB565 = 153,600 字节
 * 每包1400字节数据 = 约110包/帧
 * 40FPS = 4400包/秒，带宽约49Mbps (WiFi可以承受)
 */
#ifndef UDP_RAW_H
#define UDP_RAW_H

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief 初始化UDP原始传输
 */
esp_err_t udp_raw_init(const char *target_ip, uint16_t port);

/**
 * @brief 发送一帧RGB565数据（自动分包）
 * @param rgb_data RGB565数据指针
 * @param width 宽度
 * @param height 高度
 * @param frame_id 帧序号
 */
esp_err_t udp_raw_send_frame(const uint16_t *rgb_data, int width, int height, uint16_t frame_id);

/**
 * @brief 停止UDP传输
 */
void udp_raw_stop(void);

#ifdef __cplusplus
}
#endif

#endif // UDP_RAW_H
