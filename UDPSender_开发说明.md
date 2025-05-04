# UDPSender 开发指南 (C++)

## 功能概述

UDPSender 是一个简单的 UDP 消息发送工具，主要用于向触发器硬件设备发送配置命令。当前版本使用 Python 和 Tkinter 实现，需要重写为 C++ 版本。

## 核心功能要求

1. **UDP 通信**
   - 目标 IP: 127.0.0.1
   - 目标端口: 12345
   - 使用 UDP 协议发送简单文本命令

2. **用户界面**
   - 白色主题界面 (适配 Windows 11)
   - 固定窗口大小 (400x300)
   - 包含三个武器类型按钮: "手枪"、"主武器"、"副武器"
   - 状态显示区域，显示发送状态和错误信息

3. **操作流程**
   - 用户点击对应武器按钮
   - 程序发送对应武器名称的 UTF-8 编码字符串
   - 显示发送状态，2秒后自动重置为"就绪"状态

## C++ 实现建议

### 开发环境

- Visual Studio 2019/2022
- C++17 或更高版本
- 使用 Windows API 或第三方 GUI 库 (如 Qt, wxWidgets)

### 网络通信实现

```cpp
// 使用 Winsock2 实现 UDP 通信
#include <WinSock2.h>
#include <WS2tcpip.h>
#pragma comment(lib, "ws2_32.lib")

// 初始化 Winsock
WSADATA wsaData;
WSAStartup(MAKEWORD(2, 2), &wsaData);

// 创建 UDP 套接字
SOCKET udpSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

// 设置目标地址
sockaddr_in serverAddr;
serverAddr.sin_family = AF_INET;
serverAddr.sin_port = htons(12345);
inet_pton(AF_INET, "127.0.0.1", &serverAddr.sin_addr);

// 发送数据
const char* message = "手枪";
sendto(udpSocket, message, strlen(message), 0, 
       (sockaddr*)&serverAddr, sizeof(serverAddr));

// 关闭套接字
closesocket(udpSocket);
WSACleanup();
```


### 多线程处理

使用 `std::thread` 或 Windows API 的线程函数实现状态重置功能:

```cpp
// 使用 std::thread
#include <thread>
#include <chrono>

void resetStatus() {
    std::this_thread::sleep_for(std::chrono::seconds(2));
    // 更新 UI 状态为"就绪"
}

// 创建线程
std::thread t(resetStatus);
t.detach();  // 分离线程
```

## 代码结构建议

```
UDPSender/
├── src/
│   ├── main.cpp              // 程序入口
│   ├── UDPSender.cpp         // 主应用类实现
│   ├── UDPSender.h           // 主应用类定义
│   ├── NetworkManager.cpp    // 网络通信管理
│   ├── NetworkManager.h      // 网络通信接口
│   └── UIComponents.cpp      // UI 组件实现
├── include/                  // 外部依赖头文件
├── libs/                     // 外部依赖库
└── build/                    // 构建输出目录
```

如有任何问题，请联系梁宇：18123939181。
