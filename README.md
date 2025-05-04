# 触发器配置器 (Trigger Configurator)

一个用于配置触发器设置的简单应用程序，具有USB HID通信功能。

## 功能特点

- 多种配置模式:
  - 通用模式 (General Mode)
  - 赛车模式 (Racing Mode)
  - 后座力模式 (Recoil Mode)
  - 狙击模式 (Sniper Mode)
  - 锁定模式 (Trigger Lock)
- USB HID通信
- 简洁直观的用户界面
- 中文界面支持

## 系统要求

- Python 3.6+
- hidapi

## 安装

1. 安装所需的包:
   ```
   pip install -r requirements.txt
   ```

2. 运行应用程序:
   ```
   python trigger_config_gui.py
   ```

## USB HID通信协议

应用程序使用USB HID协议与设备通信，采用以下帧格式:

### 命令帧格式

| 字节位置 | 描述 | 值/范围 |
|---------|------|---------|
| 0 | 报告ID | 0 (固定值) |
| 1 | 命令头 | 0xAA (固定值) |
| 2 | 命令类型 | 0x01(模式设置) 或 0x02(参数设置) |
| 3 | 数据长度 | 数据字节数 |
| 4+ | 数据 | 根据命令类型不同而变化 |
| N-2 | 校验和 | (命令类型 + 所有数据字节)的和 & 0xFF |
| N-1 | 命令尾 | 0x55 (固定值) |
| N+ | 填充 | 0x00 (填充至64字节) |

### 模式设置命令 (0x01)

数据格式: [模式ID]

模式ID定义:
- 0x10: 通用模式 (General)
- 0x11: 赛车模式 (Racing)
- 0x12: 后座力模式 (Recoil)
- 0x13: 狙击模式 (Sniper)
- 0x14: 锁定模式 (Lock)

### 参数设置命令 (0x02)

数据格式: [参数ID, 值高字节, 值低字节]

参数ID采用分组编码:
- 赛车模式参数: 0x21-0x2F
  - 0x21: 阻尼开始位置 (DAMPING_START)
  - 0x22: 阻尼强度 (DAMPING_STRENGTH)

- 后座力模式参数: 0x31-0x3F
  - 0x31: 振动开始位置 (VIB_START_POS)
  - 0x32: 振动初始强度 (VIB_START_STRENGTH)
  - 0x33: 振动强度 (VIB_INTENSITY)
  - 0x34: 振动频率 (VIB_FREQUENCY)
  - 0x35: 从振动开始位置开始输出数据 (VIB_START_DATA)

- 狙击模式参数: 0x41-0x4F
  - 0x41: 开始位置 (START_POS)
  - 0x42: 触发行程 (TRIGGER_STROKE)
  - 0x43: 阻力 (RESISTANCE)
  - 0x44: 从断开开始位置开始输出数据 (BREAK_START_DATA)

- 锁定模式参数: 0x51-0x5F
  - 0x51: 锁定阻尼开始位置 (LOCK_DAMPING_START)

### 单片机解析示例代码

以下是单片机上解析这种消息格式的示例代码:

```c
// 接收缓冲区
uint8_t rxBuffer[64];
uint8_t rxIndex = 0;
bool messageStarted = false;

void processHidReport(uint8_t *report, uint8_t length) {
  // 寻找命令头
  for(int i = 0; i < length; i++) {
    uint8_t byte = report[i];
    
    if(!messageStarted && byte == 0xAA) {
      // 找到命令头
      messageStarted = true;
      rxIndex = 0;
      rxBuffer[rxIndex++] = byte;
    }
    else if(messageStarted) {
      // 保存字节到缓冲区
      rxBuffer[rxIndex++] = byte;
      
      // 检查是否到达命令尾
      if(byte == 0x55 && rxIndex >= 5) {
        // 完整命令接收完毕，处理命令
        processCommand();
        messageStarted = false;
      }
      
      // 防止缓冲区溢出
      if(rxIndex >= sizeof(rxBuffer)) {
        messageStarted = false;
      }
    }
  }
}

void processCommand() {
  // 检查命令格式是否正确
  if(rxBuffer[0] != 0xAA || rxBuffer[rxIndex-1] != 0x55) {
    return; // 命令格式错误
  }
  
  uint8_t cmdType = rxBuffer[1];
  uint8_t dataLen = rxBuffer[2];
  
  // 计算校验和
  uint8_t checksum = 0;
  for(int i = 1; i < rxIndex-2; i++) {
    checksum += rxBuffer[i];
  }
  checksum &= 0xFF;
  
  // 验证校验和
  if(checksum != rxBuffer[rxIndex-2]) {
    return; // 校验和错误
  }
  
  // 根据命令类型处理
  switch(cmdType) {
    case 0x01: // 模式设置
      if(dataLen >= 1) {
        setMode(rxBuffer[3]);
      }
      break;
      
    case 0x02: // 参数设置
      if(dataLen >= 3) {
        uint8_t paramId = rxBuffer[3];
        uint16_t value = (rxBuffer[4] << 8) | rxBuffer[5];
        setParameter(paramId, value);
      }
      break;
  }
}
```

## 使用方法

1. 选择所需的模式
2. 调整所选模式的参数
3. 更改会通过USB HID自动发送到设备
4. 设备连接状态会在界面底部显示

## USB设备设置

默认情况下，应用程序使用以下USB设备标识符:
- 供应商ID (VID): 0x2341 (Arduino默认)
- 产品ID (PID): 0x8036 (Arduino Leonardo默认)

如果您的设备使用不同的VID/PID，请在`trigger_config_gui.py`文件开头修改这些常量。
