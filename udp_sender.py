import tkinter as tk
from tkinter import ttk
import socket
import threading
import time

class UDPSenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("触发器配置 - UDP发送工具")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        # 设置UDP目标
        self.udp_host = "127.0.0.1"
        self.udp_port = 12345
        
        # 创建UDP套接字
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title_label = ttk.Label(
            self.main_frame, 
            text="触发器配置 - UDP发送工具", 
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # 说明标签
        info_label = ttk.Label(
            self.main_frame,
            text=f"发送UDP消息到 {self.udp_host}:{self.udp_port}\n选择武器类型发送配置命令",
            justify=tk.CENTER
        )
        info_label.pack(pady=(0, 20))
        
        # 创建按钮框架
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # 创建三个武器按钮
        self.create_weapon_button(button_frame, "手枪", "手枪")
        self.create_weapon_button(button_frame, "主武器", "主武器")
        self.create_weapon_button(button_frame, "副武器", "副武器")
        
        # 状态标签
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(
            self.main_frame,
            textvariable=self.status_var,
            font=("Arial", 10),
            foreground="green"
        )
        status_label.pack(pady=20)
        
    def create_weapon_button(self, parent, text, weapon_name):
        """创建武器按钮"""
        button = ttk.Button(
            parent,
            text=text,
            command=lambda: self.send_weapon_command(weapon_name),
            width=15
        )
        button.pack(side=tk.LEFT, padx=10, expand=True)
        
    def send_weapon_command(self, weapon_name):
        """发送武器命令"""
        try:
            # 更新状态
            self.status_var.set(f"正在发送: {weapon_name}...")
            self.root.update()
            
            # 发送UDP消息
            self.udp_socket.sendto(weapon_name.encode('utf-8'), (self.udp_host, self.udp_port))
            
            # 更新状态
            self.status_var.set(f"已发送: {weapon_name}")
            
            # 启动一个线程来重置状态
            threading.Thread(target=self.reset_status, daemon=True).start()
            
        except Exception as e:
            self.status_var.set(f"发送错误: {e}")
            
    def reset_status(self):
        """重置状态消息"""
        time.sleep(2)
        self.status_var.set("就绪")
        
    def __del__(self):
        """清理资源"""
        if hasattr(self, "udp_socket"):
            self.udp_socket.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = UDPSenderApp(root)
    root.mainloop()
