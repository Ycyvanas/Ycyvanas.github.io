/**
 * @file udp_stream.c
 * @brief UDP视频流传输实现
 */
#include "udp_stream.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_camera.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include "string.h"

static const char *TAG = "udp_stream";

static int udp_socket = -1;
static struct sockaddr_in dest_addr;
static bool initialized = false;

// 统计信息
static uint32_t stats_frames = 0;
static uint32_t stats_packets = 0;
static uint64_t stats_bytes = 0;

esp_err_t udp_stream_init(const char *target_ip, uint16_t port)
{
    if (initialized) {
        ESP_LOGW(TAG, "UDP stream already initialized");
        return ESP_OK;
    }

    // 创建UDP socket
    udp_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (udp_socket < 0) {
        ESP_LOGE(TAG, "Failed to create UDP socket: %d", udp_socket);
        return ESP_FAIL;
    }

    // 设置广播权限
    int broadcast_enable = 1;
    if (setsockopt(udp_socket, SOL_SOCKET, SO_BROADCAST, &broadcast_enable, sizeof(broadcast_enable)) < 0) {
        ESP_LOGE(TAG, "Failed to set broadcast option");
        close(udp_socket);
        udp_socket = -1;
        return ESP_FAIL;
    }

    // 设置目标地址
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_port = htons(port);

    if (target_ip == NULL || strlen(target_ip) == 0) {
        // 使用广播地址
        dest_addr.sin_addr.s_addr = inet_addr(UDP_BROADCAST_IP);
        ESP_LOGI(TAG, "Using broadcast mode");
    } else {
        // 使用指定IP
        if (inet_aton(target_ip, &dest_addr.sin_addr) == 0) {
            ESP_LOGE(TAG, "Invalid IP address: %s", target_ip);
            close(udp_socket);
            udp_socket = -1;
            return ESP_ERR_INVALID_ARG;
        }
    }

    initialized = true;
    stats_frames = 0;
    stats_packets = 0;
    stats_bytes = 0;

    ESP_LOGI(TAG, "UDP stream initialized: %s:%d", target_ip ? target_ip : UDP_BROADCAST_IP, port);
    return ESP_OK;
}

esp_err_t udp_stream_send_frame(const uint8_t *jpeg_data, size_t jpeg_len, uint32_t frame_id)
{
    if (!initialized || udp_socket < 0) {
        return ESP_ERR_INVALID_STATE;
    }

    if (jpeg_len == 0 || jpeg_data == NULL) {
        return ESP_ERR_INVALID_ARG;
    }

    if (jpeg_len > UDP_MAX_FRAME_SIZE) {
        ESP_LOGE(TAG, "Frame too large: %zu bytes (max %d)", jpeg_len, UDP_MAX_FRAME_SIZE);
        return ESP_ERR_INVALID_SIZE;
    }

    // 计算需要的总包数（最大化单包数据量减少包数）
    const size_t data_per_packet = UDP_PAYLOAD_SIZE - sizeof(udp_packet_header_t);
    const uint16_t total_packets = (jpeg_len + data_per_packet - 1) / data_per_packet;

    uint8_t packet_buffer[UDP_PAYLOAD_SIZE];
    udp_packet_header_t *header = (udp_packet_header_t *)packet_buffer;
    uint8_t *data_ptr = packet_buffer + sizeof(udp_packet_header_t);

    size_t bytes_sent = 0;
    uint16_t packet_id = 0;

    while (bytes_sent < jpeg_len) {
        size_t chunk_size = jpeg_len - bytes_sent;
        if (chunk_size > data_per_packet) {
            chunk_size = data_per_packet;
        }

        // 填充包头
        header->frame_id = htonl(frame_id);
        header->packet_id = htons(packet_id);
        header->total_packets = htons(total_packets);
        header->frame_size = htonl(jpeg_len);

        // 复制数据
        memcpy(data_ptr, jpeg_data + bytes_sent, chunk_size);

        // 发送UDP包
        ssize_t sent = sendto(udp_socket, packet_buffer, sizeof(udp_packet_header_t) + chunk_size, 0,
                            (struct sockaddr *)&dest_addr, sizeof(dest_addr));

        if (sent < 0) {
            ESP_LOGE(TAG, "Failed to send UDP packet %d/%d", packet_id, total_packets);
            return ESP_FAIL;
        }

        bytes_sent += chunk_size;
        packet_id++;
        stats_packets++;
        stats_bytes += sent;
    }

    stats_frames++;

    if (frame_id % 30 == 0) {
        ESP_LOGI(TAG, "Frame %lu sent: %zu bytes, %d packets", frame_id, jpeg_len, total_packets);
    }

    return ESP_OK;
}

esp_err_t udp_stream_set_target(const char *target_ip, uint16_t port)
{
    if (!initialized || udp_socket < 0) {
        return ESP_ERR_INVALID_STATE;
    }

    if (target_ip == NULL || strlen(target_ip) == 0) {
        dest_addr.sin_addr.s_addr = inet_addr(UDP_BROADCAST_IP);
    } else {
        if (inet_aton(target_ip, &dest_addr.sin_addr) == 0) {
            ESP_LOGE(TAG, "Invalid IP address: %s", target_ip);
            return ESP_ERR_INVALID_ARG;
        }
    }

    dest_addr.sin_port = htons(port);
    ESP_LOGI(TAG, "Target updated: %s:%d", target_ip ? target_ip : UDP_BROADCAST_IP, port);
    return ESP_OK;
}

void udp_stream_get_stats(uint32_t *frames_sent, uint32_t *packets_sent, uint64_t *bytes_sent)
{
    if (frames_sent) *frames_sent = stats_frames;
    if (packets_sent) *packets_sent = stats_packets;
    if (bytes_sent) *bytes_sent = stats_bytes;
}

void udp_stream_stop(void)
{
    if (udp_socket >= 0) {
        close(udp_socket);
        udp_socket = -1;
    }
    initialized = false;
    ESP_LOGI(TAG, "UDP stream stopped");
}

// LED配置外部声明
extern void set_led_blink_period(uint32_t period_ms);
extern void set_led_enabled(bool enable);

/**
 * @brief UDP命令监听线程（监听5001端口）
 */
static void udp_cmd_listener_task(void *pvParameter)
{
    int cmd_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (cmd_socket < 0) {
        ESP_LOGE(TAG, "Failed to create command socket");
        vTaskDelete(NULL);
        return;
    }

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(5001);
    server_addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(cmd_socket, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        ESP_LOGE(TAG, "Failed to bind command socket");
        close(cmd_socket);
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "UDP command listener started on port 5001");

    char buffer[128];
    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);

    while (1) {
        int len = recvfrom(cmd_socket, buffer, sizeof(buffer) - 1, 0,
                          (struct sockaddr *)&client_addr, &addr_len);
        if (len > 0) {
            buffer[len] = '\0';
            ESP_LOGI(TAG, "UDP cmd received: %s", buffer);

            // 解析命令: period=xxx 或 enable=1/0 或 wb_mode=x
            if (strncmp(buffer, "period=", 7) == 0) {
                uint32_t period = (uint32_t)atoi(buffer + 7);
                if (period >= 50 && period <= 10000) {
                    set_led_blink_period(period);
                    ESP_LOGI(TAG, "LED period set to: %ums", period);
                }
            }
            else if (strncmp(buffer, "enable=", 7) == 0) {
                int enable = atoi(buffer + 7);
                set_led_enabled(enable ? true : false);
                ESP_LOGI(TAG, "LED %s", enable ? "enabled" : "disabled");
            }
            else if (strncmp(buffer, "wb_mode=", 8) == 0) {
                int mode = atoi(buffer + 8);
                if (mode >= 0 && mode <= 5) {
                    // 获取传感器并设置白平衡模式
                    sensor_t *s = esp_camera_sensor_get();
                    if (s) {
                        if (mode == 5) {
                            // 夜间模式：特殊白平衡设置（暖色调 + 降噪）
                            s->set_whitebal(s, 0);      // 关闭自动白平衡
                            s->set_awb_gain(s, 0);      // 关闭AWB增益
                            s->set_wb_mode(s, 3);       // 先应用白炽灯预设作为基础
                            
                            // 夜间模式优化
                            s->set_brightness(s, 2);    // 亮度+2 (提高夜间可见度)
                            s->set_contrast(s, 1);      // 对比度+1
                            s->set_denoise(s, 3);       // 最强降噪
                            s->set_sharpness(s, 0);     // 关闭锐化（不放大噪点）
                            s->set_gainceiling(s, 2);   // 增益上限提高（允许更高增益）
                            ESP_LOGI(TAG, "白平衡模式: 🌙 夜间模式 (高亮度 + 强降噪)");
                        } else {
                            // 常规模式
                            s->set_wb_mode(s, mode);
                            // 如果不是自动模式，关闭自动白平衡以应用预设
                            if (mode != 0) {
                                s->set_whitebal(s, 0);
                                s->set_awb_gain(s, 1);
                            } else {
                                // 自动模式：开启自动白平衡
                                s->set_whitebal(s, 1);
                                s->set_awb_gain(s, 1);
                            }
                            // 恢复常规图像设置
                            s->set_brightness(s, 1);
                            s->set_contrast(s, 1);
                            s->set_denoise(s, 3);
                            s->set_sharpness(s, 0);
                            s->set_gainceiling(s, 0);   // 恢复最小增益上限
                            
                            const char *mode_names[] = {"自动", "晴天", "阴天", "白炽灯", "荧光灯"};
                            ESP_LOGI(TAG, "白平衡模式: %s", mode_names[mode]);
                        }
                    }
                }
            }
            else if (strncmp(buffer, "whitebal=", 9) == 0) {
                int enable = atoi(buffer + 9);
                sensor_t *s = esp_camera_sensor_get();
                if (s) {
                    s->set_whitebal(s, enable);
                    ESP_LOGI(TAG, "自动白平衡: %s", enable ? "开启" : "关闭");
                }
            }
            else if (strncmp(buffer, "awb_gain=", 9) == 0) {
                int enable = atoi(buffer + 9);
                sensor_t *s = esp_camera_sensor_get();
                if (s) {
                    s->set_awb_gain(s, enable);
                    ESP_LOGI(TAG, "AWB增益: %s", enable ? "开启" : "关闭");
                }
            }
        }
    }
}

void udp_cmd_listener_start(void)
{
    xTaskCreatePinnedToCore(udp_cmd_listener_task, "udp_cmd", 4096, NULL, 5, NULL, 1);
}
