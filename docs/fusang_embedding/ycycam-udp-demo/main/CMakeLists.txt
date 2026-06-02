idf_component_register(SRCS "main.c" "udp_stream.c" "wifi_handler.c" "camera_driver.c" "http_server.c"
                    INCLUDE_DIRS "."
                    REQUIRES esp_wifi nvs_flash esp_psram espressif__esp_jpeg esp32-camera lwip esp_netif esp_driver_gpio esp_http_server)
