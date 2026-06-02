/**
 * @file udp_raw.c
 * @brief UDP原始像素传输实现 (无JPEG编码，零延迟)
 */
#include "udp_raw.h"
#include "esp_log.h"
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

static const char *TAG = "udp_raw";

static int udp_socket = -1;
static struct sockaddr_in dest_addr;
static bool initialized = false;

// 数据包头部 (4字节):
// | frame_id (2字节) | packet_id (1字节) | total_packets (1字节) |
#define HEADER_SIZE 4
#define MAX_DATA_PER_PACKET 1468  // 1472 - 4 = 1468 字节数据
#define MAX_FRAME_WIDTH  320
#define MAX_FRAME_HEIGHT 240

esp_err_t udp_raw_init(const char *target_ip, uint16_t port)
{
    if (initialized) {
        ESP_LOGW(TAG, "Already initialized");
        return ESP_OK;
    }

    // 创建UDP socket
    udp_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (udp_socket < 0) {
        ESP_LOGE(TAG, "Failed to create socket");
        return ESP_FAIL;
    }

    // 设置广播权限
    int broadcast_enable = 1;
    socklen_t optlen = sizeof(broadcast_enable);
    if (setsockopt(udp_socket, SOL_SOCKET, SO_BROADCAST,
                   &broadcast_enable, optlen) < 0) {
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
        // 广播模式
        dest_addr.sin_addr.s_addr = htonl(INADDR_BROADCAST);
        ESP_LOGI(TAG, "Broadcast mode enabled");
    } else {
        if (inet_aton(target_ip, &dest_addr.sin_addr) == 0) {
            ESP_LOGE(TAG, "Invalid IP: %s", target_ip);
            close(udp_socket);
            udp_socket = -1;
            return ESP_ERR_INVALID_ARG;
        }
    }

    initialized = true;
    ESP_LOGI(TAG, "UDP raw stream initialized: port %d", port);
    return ESP_OK;
}

esp_err_t udp_raw_send_frame(const uint16_t *rgb_data, int width, int height, uint16_t frame_id)
{
    if (!initialized || udp_socket < 0) {
        return ESP_ERR_INVALID_STATE;
    }

    if (!rgb_data || width <= 0 || height <= 0) {
        return ESP_ERR_INVALID_ARG;
    }

    const size_t frame_size = width * height * sizeof(uint16_t);
    const size_t data_per_packet = MAX_DATA_PER_PACKET;
    const size_t total_packets = (frame_size + data_per_packet - 1) / data_per_packet;

    uint8_t packet_buffer[HEADER_SIZE + MAX_DATA_PER_PACKET];
    size_t bytes_sent = 0;
    uint8_t packet_id = 0;

    while (bytes_sent < frame_size) {
        size_t chunk_size = frame_size - bytes_sent;
        if (chunk_size > data_per_packet) {
            chunk_size = data_per_packet;
        }

        // 填充头部
        packet_buffer[0] = (frame_id >> 8) & 0xFF;
        packet_buffer[1] = frame_id & 0xFF;
        packet_buffer[2] = packet_id;
        packet_buffer[3] = (uint8_t)total_packets;

        // 复制数据（直接拷贝，无编码）
        memcpy(packet_buffer + HEADER_SIZE, (const uint8_t *)rgb_data + bytes_sent, chunk_size);

        // 发送
        ssize_t sent = sendto(udp_socket, packet_buffer, HEADER_SIZE + chunk_size, 0,
                              (struct sockaddr *)&dest_addr, sizeof(dest_addr));
        if (sent < 0) {
            // 忽略偶尔的发送失败，继续
            continue;
        }

        bytes_sent += chunk_size;
        packet_id++;
    }

    return ESP_OK;
}

void udp_raw_stop(void)
{
    if (udp_socket >= 0) {
        close(udp_socket);
        udp_socket = -1;
    }
    initialized = false;
}
