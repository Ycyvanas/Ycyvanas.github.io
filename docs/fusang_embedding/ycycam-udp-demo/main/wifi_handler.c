/**
 * @file wifi_handler.c
 * @brief WiFi AP+STA模式管理 + NVS配置存储
 */
#include "wifi_handler.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include <string.h>

static const char *TAG = "wifi_handler";

// 全局WiFi状态
static esp_netif_t *sta_netif = NULL;
static esp_netif_t *ap_netif = NULL;
static bool sta_connected = false;
static char sta_ip[16] = "0.0.0.0";

// NVS配置
#define NVS_NAMESPACE  "wifi_config"
#define NVS_SSID_KEY   "sta_ssid"
#define NVS_PASS_KEY   "sta_pass"

/**
 * @brief WiFi事件处理
 */
static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                               int32_t event_id, void* event_data) {
    if (event_id == WIFI_EVENT_AP_STACONNECTED) {
        wifi_event_ap_staconnected_t* event = (wifi_event_ap_staconnected_t*) event_data;
        ESP_LOGI(TAG, "📱 AP 设备接入: %02x:%02x:%02x:%02x:%02x:%02x, AID=%d",
                 event->mac[0], event->mac[1], event->mac[2],
                 event->mac[3], event->mac[4], event->mac[5], event->aid);
    }
    else if (event_id == WIFI_EVENT_AP_STADISCONNECTED) {
        wifi_event_ap_stadisconnected_t* event = (wifi_event_ap_stadisconnected_t*) event_data;
        ESP_LOGI(TAG, "📱 AP 设备断开: %02x:%02x:%02x:%02x:%02x:%02x, AID=%d",
                 event->mac[0], event->mac[1], event->mac[2],
                 event->mac[3], event->mac[4], event->mac[5], event->aid);
    }
    else if (event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "📡 WiFi STA 启动，正在连接...");
        esp_wifi_connect();
    }
    else if (event_id == WIFI_EVENT_STA_CONNECTED) {
        ESP_LOGI(TAG, "✅ WiFi STA 连接成功");
    }
    else if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "⚠️ WiFi STA 断开连接，尝试重连...");
        sta_connected = false;
        strcpy(sta_ip, "0.0.0.0");
        vTaskDelay(pdMS_TO_TICKS(5000));
        esp_wifi_connect();
    }
    else if (event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        sprintf(sta_ip, IPSTR, IP2STR(&event->ip_info.ip));
        sta_connected = true;
        ESP_LOGI(TAG, "🎉 WiFi STA 获取 IP 成功");
        ESP_LOGI(TAG, "   IP 地址: %s", sta_ip);
    }
}

/**
 * @brief 从NVS加载WiFi配置
 */
esp_err_t wifi_load_config(char *ssid, size_t ssid_len, char *password, size_t pass_len) {
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs_handle);
    if (err != ESP_OK) {
        return err;
    }

    err = nvs_get_str(nvs_handle, NVS_SSID_KEY, ssid, &ssid_len);
    if (err != ESP_OK) {
        nvs_close(nvs_handle);
        return err;
    }

    err = nvs_get_str(nvs_handle, NVS_PASS_KEY, password, &pass_len);
    nvs_close(nvs_handle);

    return err;
}

/**
 * @brief 保存WiFi配置到NVS
 */
esp_err_t wifi_save_config(const char *ssid, const char *password) {
    nvs_handle_t nvs_handle;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs_handle);
    if (err != ESP_OK) {
        return err;
    }

    err = nvs_set_str(nvs_handle, NVS_SSID_KEY, ssid);
    if (err != ESP_OK) {
        nvs_close(nvs_handle);
        return err;
    }

    err = nvs_set_str(nvs_handle, NVS_PASS_KEY, password);
    if (err != ESP_OK) {
        nvs_close(nvs_handle);
        return err;
    }

    err = nvs_commit(nvs_handle);
    nvs_close(nvs_handle);

    ESP_LOGI(TAG, "💾 WiFi 配置已保存: %s", ssid);
    return err;
}

/**
 * @brief 使用新配置重新连接WiFi
 */
esp_err_t wifi_reconnect(const char *ssid, const char *password) {
    wifi_config_t sta_config = {0};
    strncpy((char*)sta_config.sta.ssid, ssid, sizeof(sta_config.sta.ssid)-1);
    strncpy((char*)sta_config.sta.password, password, sizeof(sta_config.sta.password)-1);
    sta_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    sta_config.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;

    esp_wifi_disconnect();
    esp_wifi_set_config(WIFI_IF_STA, &sta_config);
    esp_wifi_connect();

    ESP_LOGI(TAG, "🔄 正在重新连接 WiFi: %s", ssid);
    return ESP_OK;
}

/**
 * @brief 获取STA连接状态
 */
bool wifi_is_sta_connected(void) {
    return sta_connected;
}

/**
 * @brief 获取STA IP地址
 */
const char* wifi_get_sta_ip(void) {
    return sta_ip;
}

/**
 * @brief 初始化WiFi AP+STA模式
 */
esp_err_t wifi_init_apsta(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());

    // 创建网络接口
    ap_netif = esp_netif_create_default_wifi_ap();
    sta_netif = esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    // 注册事件处理器
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                        ESP_EVENT_ANY_ID,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                        IP_EVENT_STA_GOT_IP,
                                                        &wifi_event_handler,
                                                        NULL,
                                                        NULL));

    // 配置AP模式
    wifi_config_t ap_config = {
        .ap = {
            .ssid = WIFI_AP_SSID,
            .ssid_len = strlen(WIFI_AP_SSID),
            .channel = WIFI_AP_CHANNEL,
            .password = WIFI_AP_PASS,
            .max_connection = MAX_STA_CONN,
            .authmode = WIFI_AUTH_WPA2_PSK,
            .pmf_cfg = {
                .required = false,
            },
        },
    };

    // 配置STA模式
    char saved_ssid[32] = {0};
    char saved_pass[64] = {0};
    wifi_config_t sta_config = {0};

    if (wifi_load_config(saved_ssid, sizeof(saved_ssid), saved_pass, sizeof(saved_pass)) == ESP_OK) {
        strncpy((char*)sta_config.sta.ssid, saved_ssid, sizeof(sta_config.sta.ssid)-1);
        strncpy((char*)sta_config.sta.password, saved_pass, sizeof(sta_config.sta.password)-1);
        ESP_LOGI(TAG, "💾 从 NVS 加载 WiFi 配置: %s", saved_ssid);
    } else {
        // 默认配置（空SSID不自动连接）
        ESP_LOGW(TAG, "⚠️ 未找到保存的 WiFi 配置");
    }

    sta_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    sta_config.sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;

    // 设置为AP+STA共存模式
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));

    if (strlen((char*)sta_config.sta.ssid) > 0) {
        ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta_config));
    }

    // 启动WiFi
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "✅ WiFi AP+STA 模式启动");
    ESP_LOGI(TAG, "   AP SSID: %s", WIFI_AP_SSID);
    ESP_LOGI(TAG, "   AP IP: 192.168.4.1");

    return ESP_OK;
}
