/**
 * @file udp_stream.h
 * @brief UDP视频流传输 - 低延迟实时视频
 */
#ifndef UDP_STREAM_H
#define UDP_STREAM_H

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// UDP数据包最大载荷（以太网MTU=1500，IP头20，UDP头8，剩余1472）
#define UDP_PAYLOAD_SIZE  1472  // 最大化单包数据量，减少包数量

// UDP数据包头部结构（8字节）
typedef struct {
    uint32_t frame_id;     // 帧序号（递增）
    uint16_t packet_id;    // 包序号（当前帧内的包）
    uint16_t total_packets;// 当前帧总包数
    uint32_t frame_size;   // 完整帧大小
} udp_packet_header_t;

// UDP配置
#define UDP_DEFAULT_PORT     5000
#define UDP_BROADCAST_IP   "255.255.255.255"  // 广播地址
#define UDP_MAX_FRAME_SIZE (256 * 1024)        // 最大帧大小256KB

/**
 * @brief 初始化UDP流传输
 * @param target_ip 目标IP地址，NULL表示广播
 * @param port 目标端口
 */
esp_err_t udp_stream_init(const char *target_ip, uint16_t port);

/**
 * @brief 发送一帧JPEG数据（自动分包）
 * @param jpeg_data JPEG数据指针
 * @param jpeg_len JPEG数据长度
 * @param frame_id 帧序号
 */
esp_err_t udp_stream_send_frame(const uint8_t *jpeg_data, size_t jpeg_len, uint32_t frame_id);

/**
 * @brief 设置目标IP和端口
 * @param target_ip 新的目标IP
 * @param port 新的端口
 */
esp_err_t udp_stream_set_target(const char *target_ip, uint16_t port);

/**
 * @brief 获取发送统计信息
 * @param frames_sent 已发送帧数（输出）
 * @param packets_sent 已发送包数（输出）
 * @param bytes_sent 已发送字节数（输出）
 */
void udp_stream_get_stats(uint32_t *frames_sent, uint32_t *packets_sent, uint64_t *bytes_sent);

/**
 * @brief 停止UDP流并释放资源
 */
void udp_stream_stop(void);

/**
 * @brief 启动UDP命令监听线程（监听5001端口）
 */
void udp_cmd_listener_start(void);

#ifdef __cplusplus
}
#endif

#endif // UDP_STREAM_H
