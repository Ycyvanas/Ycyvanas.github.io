/**
 * @file http_server.c
 * @brief 简化版HTTP服务器 - WiFi配置 + 摄像头控制 + LED控制
 */
#include "esp_http_server.h"
#include "wifi_handler.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_camera.h"
#include <string.h>

// LED配置函数外部声明
extern uint32_t get_led_blink_period(void);
extern void set_led_blink_period(uint32_t period_ms);
extern bool get_led_enabled(void);
extern void set_led_enabled(bool enable);

static const char *TAG = "http_server";

/**
 * @brief 主页 - 集成LED控制
 */
static esp_err_t index_handler(httpd_req_t *req) {
    const char *html_format =
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
        "<title>ycycam-udp</title>"
        "<style>body{margin:0;background:#000;color:#fff;font-family:monospace;padding:20px;}"
        ".container{max-width:400px;margin:0 auto;text-align:center;}"
        "h1{color:#0f0;margin-bottom:5px;}"
        ".subtitle{color:#888;margin-bottom:25px;}"
        ".btn{display:block;padding:15px;background:#0f0;color:#000;text-decoration:none;"
        "border-radius:5px;font-weight:bold;font-size:18px;margin-top:15px;}"
        ".section{background:#111;border-radius:12px;padding:20px;margin-top:20px;text-align:left;}"
        ".section h2{color:#0f0;margin-top:0;font-size:18px;}"
        ".toggle{display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid #333;}"
        ".switch{position:relative;width:50px;height:26px;}"
        ".switch input{opacity:0;width:0;height:0;}"
        ".slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:#555;border-radius:26px;}"
        ".slider:before{position:absolute;content:\"\";height:20px;width:20px;left:3px;bottom:3px;background:white;border-radius:50%;}"
        "input:checked + .slider{background:#0f0;}"
        "input:checked + .slider:before{transform:translateX(24px);}"
        ".slider-row{margin-top:15px;}"
        ".slider-label{display:flex;justify-content:space-between;margin-bottom:8px;color:#0af;}"
        "input[type='range']{width:100%;height:8px;background:#222;border-radius:4px;outline:none;}"
        "input[type='range']::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;background:#f50;border-radius:50%;cursor:pointer;}"
        ".value-display{text-align:center;color:#f50;font-weight:bold;padding:8px;background:#222;border-radius:6px;margin-top:10px;}"
        ".presets{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px;}"
        ".preset-btn{padding:8px;background:#333;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px;}"
        ".preset-btn:hover{background:#f50;}"
        ".status-bar{background:#222;padding:10px;border-radius:6px;margin-top:10px;color:#0f0;font-size:13px;}"
        ".info{margin-top:25px;color:#888;font-size:13px;}"
        "</style></head><body>"
        "<div class='container'>"
        "<h1>📷 ycycam-udp</h1>"
        "<div class='subtitle'>UDP视频流 | 端口: 5000 (广播)</div>"

        "<a class='btn' href='/wifi'>⚙️ WiFi配置</a>"
        "<a class='btn' href='/camera' style='background:#0af;color:#fff;'>🎨 摄像头控制</a>"

        "<div class='section'>"
        "<h2>💡 LED 闪烁控制</h2>"
        "<div class='status-bar' id='led_status'>当前周期: %u ms</div>"

        "<div class='toggle'>"
        "<span>LED闪烁</span>"
        "<label class='switch'><input type='checkbox' id='led_enable' %s onchange='setLEDEnable(this.checked)'><span class='slider'></span></label>"
        "</div>"

        "<div class='slider-row'>"
        "<div class='slider-label'>"
        "<span>闪烁周期</span>"
        "<span>50ms ~ 10s</span>"
        "</div>"
        "<input type='range' id='period_range' min='50' max='10000' value='%u' step='50' oninput='updatePeriod(this.value)'>"
        "<div class='value-display' id='period_display'>%u ms</div>"
        "</div>"

        "<div class='presets'>"
        "<button class='preset-btn' onclick='setPreset(100)'>极快 100ms</button>"
        "<button class='preset-btn' onclick='setPreset(500)'>快 500ms</button>"
        "<button class='preset-btn' onclick='setPreset(1000)'>正常 1s</button>"
        "<button class='preset-btn' onclick='setPreset(2000)'>慢 2s</button>"
        "<button class='preset-btn' onclick='setPreset(5000)'>很慢 5s</button>"
        "<button class='preset-btn' onclick='setPreset(10000)'>极慢 10s</button>"
        "</div>"
        "</div>"

        "<div class='info'>"
        "<p>📡 接收端命令:</p>"
        "<code>python3 server/web_receiver.py</code>"
        "</div>"

        "<script>"
        "function setStatus(msg) { document.getElementById('led_status').textContent = msg; }"
        "function updatePeriod(val) {"
        "  document.getElementById('period_display').textContent = val + ' ms';"
        "  fetch('/led_ctrl?period=' + val).then(r=>r.text()).then(s=>setStatus('✓ 周期已设置: ' + val + ' ms'));"
        "}"
        "function setLEDEnable(enable) {"
        "  fetch('/led_ctrl?enable=' + (enable?1:0)).then(r=>r.text()).then(s=>setStatus('✓ LED已' + (enable?'开启':'关闭')));"
        "}"
        "function setPreset(period) {"
        "  document.getElementById('period_range').value = period;"
        "  updatePeriod(period);"
        "}"
        "</script>"
        "</div></body></html>";

    char buf[16384];
    uint32_t current_period = get_led_blink_period();
    bool enabled = get_led_enabled();
    snprintf(buf, sizeof(buf), html_format,
             (unsigned long)current_period,
             enabled ? "checked" : "",
             (unsigned long)current_period,
             (unsigned long)current_period);

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_send(req, buf, strlen(buf));
    return ESP_OK;
}

/**
 * @brief WiFi配置页面
 */
static esp_err_t wifi_config_handler(httpd_req_t *req) {
    const char *html_format =
        "<!DOCTYPE html>"
        "<html lang='zh-CN'>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>WiFi配置 - ycycam-udp</title>"
        "<style>"
        "body{margin:0;background:#000;padding:20px;font-family:monospace;}"
        ".container{max-width:400px;margin:0 auto;background:#111;padding:30px;border-radius:15px;}"
        "h1{color:#0f0;text-align:center;margin-bottom:30px;}"
        ".form-group{margin-bottom:20px;}"
        "label{color:#0af;display:block;margin-bottom:8px;}"
        "input{width:100%;padding:12px;background:#222;border:1px solid #333;border-radius:8px;"
        "color:#fff;font-size:14px;box-sizing:border-box;}"
        "button{width:100%;padding:15px;background:#0f0;color:#000;border:none;border-radius:8px;"
        "font-size:16px;font-weight:bold;cursor:pointer;margin-top:10px;}"
        ".status{padding:15px;background:#222;border-radius:8px;margin-bottom:20px;}"
        ".status p{margin:5px 0;color:#888;font-size:13px;}"
        ".success{color:#0f0;}"
        ".back{text-align:center;margin-top:20px;}"
        ".back a{color:#0af;text-decoration:none;}"
        "</style>"
        "</head>"
        "<body>"
        "<div class='container'>"
        "<h1>📶 WiFi配置</h1>"
        "<div class='status'>"
        "<p>AP: ycycam <span class='success'>(192.168.4.1)</span></p>"
        "<p>STA状态: <span class='%s'>%s</span></p>"
        "<p>STA IP: <span class='success'>%s</span></p>"
        "</div>"
        "<form method='POST' action='/wifi_save'>"
        "<div class='form-group'>"
        "<label for='ssid'>WiFi SSID 名称:</label>"
        "<input type='text' id='ssid' name='ssid' required placeholder='输入WiFi名称'>"
        "</div>"
        "<div class='form-group'>"
        "<label for='password'>WiFi 密码:</label>"
        "<input type='password' id='password' name='password' placeholder='输入WiFi密码'>"
        "</div>"
        "<button type='submit'>💾 保存并连接</button>"
        "</form>"
        "<div class='back'>"
        "<a href='/'>← 返回主页</a>"
        "</div>"
        "</div>"
        "</body>"
        "</html>";

    char buf[4096];
    snprintf(buf, sizeof(buf), html_format,
             wifi_is_sta_connected() ? "success" : "warning",
             wifi_is_sta_connected() ? "已连接" : "未连接",
             wifi_get_sta_ip());

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_send(req, buf, strlen(buf));
    return ESP_OK;
}

/**
 * @brief 摄像头控制页面
 */
static esp_err_t camera_page_handler(httpd_req_t *req) {
    const char *html =
        "<!DOCTYPE html>"
        "<html lang='zh-CN'>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>摄像头控制 - ycycam-udp</title>"
        "<style>"
        "body{margin:0;background:#000;padding:20px;font-family:monospace;}"
        ".container{max-width:400px;margin:0 auto;background:#111;padding:30px;border-radius:15px;}"
        "h1{color:#0f0;text-align:center;margin-bottom:30px;}"
        ".form-group{margin-bottom:20px;}"
        "label{color:#0af;display:block;margin-bottom:8px;}"
        "select{width:100%;padding:12px;background:#222;border:1px solid #333;border-radius:8px;"
        "color:#fff;font-size:14px;box-sizing:border-box;}"
        ".toggle{display:flex;align-items:center;justify-content:space-between;padding:15px 0;border-bottom:1px solid #333;}"
        ".switch{position:relative;width:50px;height:26px;}"
        ".switch input{opacity:0;width:0;height:0;}"
        ".slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:#555;border-radius:26px;}"
        ".slider:before{position:absolute;content:\"\";height:20px;width:20px;left:3px;bottom:3px;background:white;border-radius:50%;}"
        "input:checked + .slider{background:#0f0;}"
        "input:checked + .slider:before{transform:translateX(24px);}"
        "button{width:100%;padding:15px;background:#0af;color:#fff;border:none;border-radius:8px;"
        "font-size:16px;font-weight:bold;cursor:pointer;margin-top:10px;}"
        ".back{text-align:center;margin-top:20px;}"
        ".back a{color:#0af;text-decoration:none;}"
        ".status{padding:15px;background:#222;border-radius:8px;margin-bottom:20px;color:#0f0;}"
        "</style>"
        "</head>"
        "<body>"
        "<div class='container'>"
        "<h1>📷 摄像头控制</h1>"
        "<div class='status' id='status'>就绪</div>"

        "<div class='toggle'>"
        "<span>自动白平衡 (AWB)</span>"
        "<label class='switch'><input type='checkbox' id='awb' checked onchange='setAWB(this.checked)'><span class='slider'></span></label>"
        "</div>"

        "<div class='toggle'>"
        "<span>自动白平衡增益</span>"
        "<label class='switch'><input type='checkbox' id='awb_gain' checked onchange='setAWBGain(this.checked)'><span class='slider'></span></label>"
        "</div>"

        "<div class='form-group'>"
        "<label for='wb_mode'>白平衡模式</label>"
        "<select id='wb_mode' onchange='setWBMode(this.value)'>"
        "<option value='0'>自动</option>"
        "<option value='1'>晴天</option>"
        "<option value='2'>阴天</option>"
        "<option value='3'>白炽灯</option>"
        "<option value='4'>荧光灯</option>"
        "</select>"
        "</div>"

        "<div class='form-group'>"
        "<label for='agc_gain'>AGC增益 (0-30)</label>"
        "<select id='agc_gain' onchange='setAGCGain(this.value)'>"
        "<option value='0'>0 (最低)</option>"
        "<option value='8'>8</option>"
        "<option value='16'>16</option>"
        "<option value='24'>24</option>"
        "<option value='30'>30 (最高)</option>"
        "</select>"
        "</div>"

        "<button onclick='resetCamera()'>🔄 重置默认设置</button>"

        "<div class='back'>"
        "<a href='/'>← 返回主页</a>"
        "</div>"
        "</div>"
        "<script>"
        "function setStatus(msg) { document.getElementById('status').textContent = msg; }"
        "function setAWB(enable) {"
        "  fetch('/cam_ctrl?awb=' + (enable?1:0)).then(r=>r.text()).then(s=>setStatus('AWB: '+(enable?'开启':'关闭')));"
        "}"
        "function setAWBGain(enable) {"
        "  fetch('/cam_ctrl?awb_gain=' + (enable?1:0)).then(r=>r.text()).then(s=>setStatus('AWB增益: '+(enable?'开启':'关闭')));"
        "}"
        "function setWBMode(mode) {"
        "  const modes = ['自动', '晴天', '阴天', '白炽灯', '荧光灯'];"
        "  fetch('/cam_ctrl?wb_mode=' + mode).then(r=>r.text()).then(s=>setStatus('白平衡模式: '+modes[mode]));"
        "}"
        "function setAGCGain(gain) {"
        "  fetch('/cam_ctrl?agc_gain=' + gain).then(r=>r.text()).then(s=>setStatus('AGC增益: '+gain));"
        "}"
        "function resetCamera() {"
        "  fetch('/cam_ctrl?reset=1').then(r=>r.text()).then(s=>setStatus('已重置为默认设置'));"
        "  document.getElementById('awb').checked = true;"
        "  document.getElementById('awb_gain').checked = true;"
        "  document.getElementById('wb_mode').value = '0';"
        "  document.getElementById('agc_gain').value = '0';"
        "}"
        "</script>"
        "</body>"
        "</html>";

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_send(req, html, strlen(html));
    return ESP_OK;
}

/**
 * @brief 摄像头控制API
 */
static esp_err_t camera_ctrl_handler(httpd_req_t *req) {
    char buf[100];
    size_t buf_len = sizeof(buf)-1;

    // 获取查询参数
    if (httpd_req_get_url_query_str(req, buf, buf_len) == ESP_OK) {
        sensor_t *sensor = esp_camera_sensor_get();
        if (!sensor) {
            httpd_resp_send_500(req);
            return ESP_FAIL;
        }

        char val[10];

        // 自动白平衡开关
        if (httpd_query_key_value(buf, "awb", val, sizeof(val)) == ESP_OK) {
            int enable = atoi(val);
            sensor->set_whitebal(sensor, enable);
            httpd_resp_send(req, "OK", 2);
            return ESP_OK;
        }

        // 自动白平衡增益
        if (httpd_query_key_value(buf, "awb_gain", val, sizeof(val)) == ESP_OK) {
            int enable = atoi(val);
            sensor->set_awb_gain(sensor, enable);
            httpd_resp_send(req, "OK", 2);
            return ESP_OK;
        }

        // 白平衡模式
        if (httpd_query_key_value(buf, "wb_mode", val, sizeof(val)) == ESP_OK) {
            int mode = atoi(val);
            sensor->set_wb_mode(sensor, mode);
            httpd_resp_send(req, "OK", 2);
            return ESP_OK;
        }

        // AGC增益
        if (httpd_query_key_value(buf, "agc_gain", val, sizeof(val)) == ESP_OK) {
            int gain = atoi(val);
            sensor->set_agc_gain(sensor, gain);
            httpd_resp_send(req, "OK", 2);
            return ESP_OK;
        }

        // 重置
        if (httpd_query_key_value(buf, "reset", val, sizeof(val)) == ESP_OK) {
            sensor->set_whitebal(sensor, 1);
            sensor->set_awb_gain(sensor, 1);
            sensor->set_wb_mode(sensor, 0);
            sensor->set_agc_gain(sensor, 0);
            httpd_resp_send(req, "OK", 2);
            return ESP_OK;
        }
    }

    httpd_resp_send(req, "OK", 2);
    return ESP_OK;
}

/**
 * @brief LED控制页面
 */
static esp_err_t led_page_handler(httpd_req_t *req) {
    const char *html_format =
        "<!DOCTYPE html>"
        "<html lang='zh-CN'>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>LED控制 - ycycam-udp</title>"
        "<style>"
        "body{margin:0;background:#000;padding:20px;font-family:monospace;}"
        ".container{max-width:400px;margin:0 auto;background:#111;padding:30px;border-radius:15px;}"
        "h1{color:#0f0;text-align:center;margin-bottom:30px;}"
        ".form-group{margin-bottom:20px;}"
        "label{color:#0af;display:block;margin-bottom:8px;}"
        "input[type='range']{width:100%;height:10px;background:#222;border-radius:5px;outline:none;}"
        "input[type='range']::-webkit-slider-thumb{-webkit-appearance:none;width:25px;height:25px;background:#0f0;border-radius:50%;cursor:pointer;}"
        ".toggle{display:flex;align-items:center;justify-content:space-between;padding:15px 0;border-bottom:1px solid #333;}"
        ".switch{position:relative;width:50px;height:26px;}"
        ".switch input{opacity:0;width:0;height:0;}"
        ".slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:#555;border-radius:26px;}"
        ".slider:before{position:absolute;content:\"\";height:20px;width:20px;left:3px;bottom:3px;background:white;border-radius:50%;}"
        "input:checked + .slider{background:#0f0;}"
        "input:checked + .slider:before{transform:translateX(24px);}"
        ".value-display{text-align:center;color:#0f0;font-size:24px;font-weight:bold;padding:10px;background:#222;border-radius:8px;margin-top:10px;}"
        ".presets{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:15px;}"
        ".preset-btn{padding:10px;background:#333;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:12px;}"
        ".preset-btn:hover{background:#0f0;color:#000;}"
        ".back{text-align:center;margin-top:20px;}"
        ".back a{color:#0af;text-decoration:none;}"
        ".status{padding:15px;background:#222;border-radius:8px;margin-bottom:20px;color:#0f0;}"
        "</style>"
        "</head>"
        "<body>"
        "<div class='container'>"
        "<h1>💡 LED控制</h1>"
        "<div class='status' id='status'>当前周期: %lu ms</div>"

        "<div class='toggle'>"
        "<span>LED闪烁开关</span>"
        "<label class='switch'><input type='checkbox' id='led_enable' %s onchange='setLEDEnable(this.checked)'><span class='slider'></span></label>"
        "</div>"

        "<div class='form-group'>"
        "<label for='period_range'>闪烁周期 (50ms - 10s)</label>"
        "<input type='range' id='period_range' min='50' max='10000' value='%lu' step='50' oninput='updatePeriod(this.value)'>"
        "<div class='value-display' id='period_display'>%lu ms</div>"
        "</div>"

        "<div class='presets'>"
        "<button class='preset-btn' onclick='setPreset(100)'>极快 (100ms)</button>"
        "<button class='preset-btn' onclick='setPreset(500)'>快 (500ms)</button>"
        "<button class='preset-btn' onclick='setPreset(1000)'>正常 (1s)</button>"
        "<button class='preset-btn' onclick='setPreset(2000)'>慢 (2s)</button>"
        "<button class='preset-btn' onclick='setPreset(5000)'>很慢 (5s)</button>"
        "<button class='preset-btn' onclick='setPreset(10000)'>极慢 (10s)</button>"
        "</div>"

        "<div class='back'>"
        "<a href='/'>← 返回主页</a>"
        "</div>"
        "</div>"
        "<script>"
        "function setStatus(msg) { document.getElementById('status').textContent = msg; }"
        "function updatePeriod(val) {"
        "  document.getElementById('period_display').textContent = val + ' ms';"
        "  fetch('/led_ctrl?period=' + val).then(r=>r.text()).then(s=>setStatus('周期已设置: ' + val + ' ms'));"
        "}"
        "function setLEDEnable(enable) {"
        "  fetch('/led_ctrl?enable=' + (enable?1:0)).then(r=>r.text()).then(s=>setStatus('LED已' + (enable?'开启':'关闭')));"
        "}"
        "function setPreset(period) {"
        "  document.getElementById('period_range').value = period;"
        "  updatePeriod(period);"
        "}"
        "</script>"
        "</body>"
        "</html>";

    char buf[8192];
    uint32_t current_period = get_led_blink_period();
    bool enabled = get_led_enabled();
    snprintf(buf, sizeof(buf), html_format,
             (unsigned long)current_period,
             enabled ? "checked" : "",
             (unsigned long)current_period,
             (unsigned long)current_period);

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_send(req, buf, strlen(buf));
    return ESP_OK;
}

/**
 * @brief LED控制API
 */
static esp_err_t led_ctrl_handler(httpd_req_t *req) {
    char buf[100];
    size_t buf_len = sizeof(buf)-1;

    if (httpd_req_get_url_query_str(req, buf, buf_len) == ESP_OK) {
        char val[20];

        // 设置闪烁周期
        if (httpd_query_key_value(buf, "period", val, sizeof(val)) == ESP_OK) {
            uint32_t period = (uint32_t)atoi(val);
            set_led_blink_period(period);
            httpd_resp_send(req, "OK", 2);
            return ESP_OK;
        }

        // 设置LED开关
        if (httpd_query_key_value(buf, "enable", val, sizeof(val)) == ESP_OK) {
            int enable = atoi(val);
            set_led_enabled(enable);
            httpd_resp_send(req, "OK", 2);
            return ESP_OK;
        }

        // 获取当前配置
        if (httpd_query_key_value(buf, "get", val, sizeof(val)) == ESP_OK) {
            char resp[64];
            snprintf(resp, sizeof(resp), "{\"period\":%lu,\"enabled\":%d}",
                     (unsigned long)get_led_blink_period(),
                     get_led_enabled() ? 1 : 0);
            httpd_resp_set_type(req, "application/json");
            httpd_resp_send(req, resp, strlen(resp));
            return ESP_OK;
        }
    }

    httpd_resp_send(req, "OK", 2);
    return ESP_OK;
}

/**
 * @brief 保存WiFi配置
 */
static esp_err_t wifi_save_handler(httpd_req_t *req) {
    char buf[512];
    int remaining = req->content_len;

    char ssid[32] = {0};
    char password[64] = {0};

    while (remaining > 0) {
        int recv_len = httpd_req_recv(req, buf, sizeof(buf)-1);
        if (recv_len <= 0) break;
        buf[recv_len] = '\0';
        remaining -= recv_len;

        // 简单解析表单
        char *ssid_ptr = strstr(buf, "ssid=");
        char *pass_ptr = strstr(buf, "password=");

        if (ssid_ptr) {
            ssid_ptr += 5;
            char *end = strchr(ssid_ptr, '&');
            if (end) *end = '\0';
            strncpy(ssid, ssid_ptr, sizeof(ssid)-1);
        }
        if (pass_ptr) {
            pass_ptr += 9;
            strncpy(password, pass_ptr, sizeof(password)-1);
        }
    }

    // URL解码 (简单处理)
    char *src = ssid, *dst = ssid;
    while (*src) {
        if (*src == '+') { *dst++ = ' '; src++; }
        else if (*src == '%' && src[1] && src[2]) {
            char hex[3] = {src[1], src[2], '\0'};
            *dst++ = strtol(hex, NULL, 16);
            src += 3;
        } else {
            *dst++ = *src++;
        }
    }
    *dst = '\0';

    src = password; dst = password;
    while (*src) {
        if (*src == '+') { *dst++ = ' '; src++; }
        else if (*src == '%' && src[1] && src[2]) {
            char hex[3] = {src[1], src[2], '\0'};
            *dst++ = strtol(hex, NULL, 16);
            src += 3;
        } else {
            *dst++ = *src++;
        }
    }
    *dst = '\0';

    ESP_LOGI(TAG, "WiFi配置: SSID='%s'", ssid);

    if (strlen(ssid) > 0) {
        wifi_save_config(ssid, password);
        wifi_reconnect(ssid, password);
    }

    const char *success_html =
        "<!DOCTYPE html>"
        "<html lang='zh-CN'>"
        "<head><meta charset='UTF-8'>"
        "<style>body{margin:0;background:#000;padding:20px;font-family:monospace;}"
        ".container{max-width:400px;margin:0 auto;background:#111;padding:30px;border-radius:15px;text-align:center;}"
        "h1{color:#0f0;margin-bottom:20px;}"
        "p{color:#888;}"
        "a{color:#0af;text-decoration:none;}"
        "</style></head>"
        "<body><div class='container'>"
        "<h1>✅ 配置已保存!</h1>"
        "<p>正在连接WiFi: <strong style='color:#0f0'>%s</strong></p>"
        "<p>请等待5-10秒...</p>"
        "<p style='margin-top:30px;'><a href='/wifi'>← 返回配置页</a></p>"
        "</div></body></html>";

    char resp_buf[2048];
    snprintf(resp_buf, sizeof(resp_buf), success_html, ssid);

    httpd_resp_set_type(req, "text/html; charset=utf-8");
    httpd_resp_send(req, resp_buf, strlen(resp_buf));
    return ESP_OK;
}

/**
 * @brief 启动HTTP服务器
 */
httpd_handle_t http_server_start(void) {
    httpd_handle_t server = NULL;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_open_sockets = 4;
    config.stack_size = 8192;

    if (httpd_start(&server, &config) == ESP_OK) {
        httpd_uri_t index_uri = {
            .uri       = "/",
            .method    = HTTP_GET,
            .handler   = index_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &index_uri);

        httpd_uri_t wifi_config_uri = {
            .uri       = "/wifi",
            .method    = HTTP_GET,
            .handler   = wifi_config_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &wifi_config_uri);

        httpd_uri_t wifi_save_uri = {
            .uri       = "/wifi_save",
            .method    = HTTP_POST,
            .handler   = wifi_save_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &wifi_save_uri);

        httpd_uri_t camera_page_uri = {
            .uri       = "/camera",
            .method    = HTTP_GET,
            .handler   = camera_page_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &camera_page_uri);

        httpd_uri_t camera_ctrl_uri = {
            .uri       = "/cam_ctrl",
            .method    = HTTP_GET,
            .handler   = camera_ctrl_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &camera_ctrl_uri);

        httpd_uri_t led_page_uri = {
            .uri       = "/led",
            .method    = HTTP_GET,
            .handler   = led_page_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &led_page_uri);

        httpd_uri_t led_ctrl_uri = {
            .uri       = "/led_ctrl",
            .method    = HTTP_GET,
            .handler   = led_ctrl_handler,
            .user_ctx  = NULL
        };
        httpd_register_uri_handler(server, &led_ctrl_uri);

        ESP_LOGI(TAG, "✅ HTTP服务器已启动");
        return server;
    }

    ESP_LOGE(TAG, "❌ HTTP服务器启动失败");
    return NULL;
}