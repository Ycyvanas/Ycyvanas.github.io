/**
 * @file receiver.cpp
 * @brief ycycam-udp 高性能C++接收端
 *
 * 编译: g++ receiver.cpp -o receiver -lopencv_core -lopencv_highgui -lopencv_imgproc -lopencv_imgcodecs
 *
 * 用于高帧率、低延迟场景，比Python版本性能更好
 */

#include <iostream>
#include <vector>
#include <unordered_map>
#include <deque>
#include <string>
#include <cstring>
#include <chrono>
#include <thread>
#include <iomanip>

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>

#ifdef OPENCV_AVAILABLE
#include <opencv2/opencv.hpp>
#endif

// 配置常量
const int UDP_PORT = 5000;
const int MAX_PAYLOAD = 1400;
const int HEADER_SIZE = 12;  // 4 + 2 + 2 + 4
const int MAX_FRAME_SIZE = 256 * 1024;
const int MAX_FRAMES_BUFFER = 5;

// UDP数据包头部
struct PacketHeader {
    uint32_t frame_id;
    uint16_t packet_id;
    uint16_t total_packets;
    uint32_t frame_size;
};

// 统计信息
class Stats {
public:
    uint64_t frames_complete = 0;
    uint64_t packets_received = 0;
    uint64_t bytes_received = 0;
    uint64_t frames_lost = 0;
    int32_t last_frame_id = -1;
    std::chrono::steady_clock::time_point start_time = std::chrono::steady_clock::now();
    std::deque<double> frame_times;

    void on_packet(int size) {
        packets_received++;
        bytes_received += size;
    }

    void on_frame(int frame_id) {
        frames_complete++;
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start_time).count();
        frame_times.push_back(elapsed);

        if (frame_times.size() > 100) {
            frame_times.pop_front();
        }

        // 检测丢帧
        if (last_frame_id >= 0 && frame_id > last_frame_id + 1) {
            frames_lost += frame_id - last_frame_id - 1;
        }
        last_frame_id = frame_id;
    }

    double get_fps() const {
        if (frame_times.size() < 2) return 0;
        double elapsed = frame_times.back() - frame_times.front();
        if (elapsed <= 0) return 0;
        return (frame_times.size() - 1) / elapsed;
    }

    double get_bandwidth_mbps() const {
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start_time).count();
        if (elapsed <= 0) return 0;
        return (bytes_received * 8.0) / (1024 * 1024) / elapsed;
    }

    double get_loss_rate() const {
        uint64_t total = frames_complete + frames_lost;
        if (total == 0) return 0;
        return frames_lost * 100.0 / total;
    }

    void print_status() const {
        std::cout << "\rFPS: " << std::fixed << std::setprecision(1) << std::setw(5) << get_fps()
                  << " | Frames: " << std::setw(5) << frames_complete
                  << " | Packets: " << std::setw(6) << packets_received
                  << " | BW: " << std::setw(5) << std::setprecision(2) << get_bandwidth_mbps() << " Mbps"
                  << " | Loss: " << std::setw(4) << std::setprecision(1) << get_loss_rate() << "%"
                  << std::flush;
    }
};

// 帧缓冲区 - 按帧ID组包
class FrameBuffer {
public:
    struct FrameData {
        std::unordered_map<int, std::vector<uint8_t>> packets;
        int total_packets = 0;
        int frame_size = 0;
    };

    std::unordered_map<int, FrameData> frames;

    std::vector<uint8_t> add_packet(int frame_id, int packet_id,
                                     int total_packets, int frame_size,
                                     const uint8_t* data, int data_len) {
        auto& frame = frames[frame_id];
        frame.total_packets = total_packets;
        frame.frame_size = frame_size;
        frame.packets[packet_id] = std::vector<uint8_t>(data, data + data_len);

        // 检查是否完整
        if ((int)frame.packets.size() == total_packets) {
            return assemble_frame(frame_id);
        }

        // 清理旧帧
        if ((int)frames.size() > MAX_FRAMES_BUFFER) {
            cleanup_old_frames(frame_id);
        }

        return {};
    }

private:
    std::vector<uint8_t> assemble_frame(int frame_id) {
        auto& frame = frames[frame_id];
        std::vector<uint8_t> full_data;
        full_data.reserve(frame.frame_size);

        for (int i = 0; i < frame.total_packets; i++) {
            auto it = frame.packets.find(i);
            if (it == frame.packets.end()) {
                // 丢包，丢弃整个帧
                frames.erase(frame_id);
                return {};
            }
            full_data.insert(full_data.end(), it->second.begin(), it->second.end());
        }

        frames.erase(frame_id);

        // 验证大小
        if ((int)full_data.size() != frame.frame_size) {
            std::cerr << "\n警告: 帧大小不匹配: " << full_data.size()
                      << " != " << frame.frame_size << std::endl;
            return {};
        }

        return full_data;
    }

    void cleanup_old_frames(int current_frame_id) {
        std::vector<int> to_delete;
        for (auto& [fid, _] : frames) {
            if (fid < current_frame_id - MAX_FRAMES_BUFFER) {
                to_delete.push_back(fid);
            }
        }
        for (int fid : to_delete) {
            frames.erase(fid);
        }
    }
};

// 解析网络字节序的头部
PacketHeader parse_header(const uint8_t* data) {
    PacketHeader h;
    h.frame_id = ntohl(*reinterpret_cast<const uint32_t*>(data));
    h.packet_id = ntohs(*reinterpret_cast<const uint16_t*>(data + 4));
    h.total_packets = ntohs(*reinterpret_cast<const uint16_t*>(data + 6));
    h.frame_size = ntohl(*reinterpret_cast<const uint32_t*>(data + 8));
    return h;
}

void print_usage(const char* prog) {
    std::cout << "用法: " << prog << " [选项]\n"
              << "选项:\n"
              << "  -p <port>    UDP端口 (默认: 5000)\n"
              << "  -h           显示帮助\n"
              << "  --no-display 无头模式\n";
}

int main(int argc, char* argv[]) {
    int port = UDP_PORT;
    bool display_enabled = true;

    // 解析命令行参数
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "-p" && i + 1 < argc) {
            port = atoi(argv[++i]);
        } else if (arg == "-h" || arg == "--help") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--no-display") {
            display_enabled = false;
        }
    }

    std::cout << "============================================\n"
              << "  ycycam-udp C++ 接收端\n"
              << "============================================\n"
              << "监听端口: " << port << "\n"
              << "============================================\n\n";

    // 创建UDP socket
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) {
        perror("socket创建失败");
        return 1;
    }

    // 设置socket选项
    int opt = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    int buf_size = 2 * 1024 * 1024;  // 2MB接收缓冲区
    setsockopt(sock, SOL_SOCKET, SO_RCVBUF, &buf_size, sizeof(buf_size));

    // 绑定地址
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);

    if (bind(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
        perror("bind失败");
        close(sock);
        return 1;
    }

    // 设置非阻塞模式
    fcntl(sock, F_SETFL, O_NONBLOCK);

    std::cout << "等待视频流... (按 Ctrl+C 退出)\n\n";

    FrameBuffer frame_buffer;
    Stats stats;
    std::vector<uint8_t> buffer(MAX_PAYLOAD);

    auto last_stats = std::chrono::steady_clock::now();

    try {
        while (true) {
            sockaddr_in client_addr{};
            socklen_t addr_len = sizeof(client_addr);

            int n = recvfrom(sock, buffer.data(), buffer.size(), 0,
                           reinterpret_cast<sockaddr*>(&client_addr), &addr_len);

            if (n < 0) {
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
                continue;
            }

            if (n < HEADER_SIZE) {
                continue;
            }

            stats.on_packet(n);

            // 解析头部
            PacketHeader h = parse_header(buffer.data());
            const uint8_t* packet_data = buffer.data() + HEADER_SIZE;
            int data_len = n - HEADER_SIZE;

            // 添加到帧缓冲区
            std::vector<uint8_t> jpeg_data = frame_buffer.add_packet(
                h.frame_id, h.packet_id, h.total_packets, h.frame_size,
                packet_data, data_len);

            if (!jpeg_data.empty()) {
                stats.on_frame(h.frame_id);

#ifdef OPENCV_AVAILABLE
                if (display_enabled) {
                    cv::Mat img = cv::imdecode(jpeg_data, cv::IMREAD_COLOR);
                    if (!img.empty()) {
                        // 叠加状态信息
                        std::ostringstream oss;
                        oss << std::fixed << std::setprecision(1)
                            << "FPS: " << stats.get_fps()
                            << " | Frame: " << h.frame_id;
                        cv::putText(img, oss.str(), cv::Point(10, 25),
                                    cv::FONT_HERSHEY_SIMPLEX, 0.5,
                                    cv::Scalar(0, 255, 0), 1);

                        cv::imshow("ycycam-udp", img);
                        int key = cv::waitKey(1);
                        if (key == 27 || key == 'q') {  // ESC或q退出
                            break;
                        }
                    }
                }
#endif
            }

            // 输出统计信息
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration<double>(now - last_stats).count();
            if (elapsed >= 1.0) {
                stats.print_status();
                last_stats = now;
            }
        }
    } catch (...) {
        std::cout << "\n\n正在退出...\n";
    }

    close(sock);
#ifdef OPENCV_AVAILABLE
    if (display_enabled) {
        cv::destroyAllWindows();
    }
#endif

    // 最终统计
    auto now = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(now - stats.start_time).count();

    std::cout << "\n\n============================================\n"
              << "  会话统计\n"
              << "============================================\n"
              << "运行时间: " << std::fixed << std::setprecision(1) << elapsed << " 秒\n"
              << "接收帧数: " << stats.frames_complete << "\n"
              << "接收包数: " << stats.packets_received << "\n"
              << "接收数据: " << std::setprecision(1) << stats.bytes_received / 1024.0 / 1024.0 << " MB\n"
              << "平均FPS: " << std::setprecision(1) << stats.frames_complete / elapsed << "\n"
              << "平均带宽: " << std::setprecision(2) << stats.bytes_received * 8.0 / 1024.0 / 1024.0 / elapsed << " Mbps\n"
              << "丢帧率: " << std::setprecision(1) << stats.get_loss_rate() << "%\n"
              << "============================================\n";

    return 0;
}
