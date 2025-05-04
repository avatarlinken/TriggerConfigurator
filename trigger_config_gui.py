import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import hid
import threading
import time
import traceback
import subprocess
import platform
import socket  # 添加socket模块用于UDP通信
import json

# 根据系统导入相应模块
if platform.system() == 'Windows':
    import winreg

def is_dark_mode():
    system = platform.system()
    
    if system == 'Darwin':  # macOS
        try:
            cmd = 'defaults read -g AppleInterfaceStyle'
            subprocess.check_output(cmd.split())
            return True
        except:
            return False
    elif system == 'Windows':  # Windows
        try:
            # 在Windows上检查深色模式
            if 'winreg' not in globals():
                return False
                
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            reg_keypath = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
            reg_key = winreg.OpenKey(registry, reg_keypath)
            
            # 获取AppsUseLightTheme值，0表示深色模式，1表示浅色模式
            value, _ = winreg.QueryValueEx(reg_key, 'AppsUseLightTheme')
            return value == 0
        except:
            return False
    else:  # 其他系统默认使用浅色主题
        return False

# Define USB HID device constants
VENDOR_ID = 0x2341  # Arduino default VID (change as needed)
PRODUCT_ID = 0x8036  # Arduino Leonardo default PID (change as needed)

# 命令格式常量
CMD_HEADER = 0xAA       # 命令头
CMD_FOOTER = 0x55       # 命令尾

# 命令类型
CMD_TYPE_MODE = 0x01    # 模式设置命令
CMD_TYPE_PARAM = 0x02   # 参数设置命令

# 模式ID
MODE_GENERAL = 0x10     # 通用模式
MODE_RACING = 0x11      # 赛车模式
MODE_RECOIL = 0x12      # 后座力模式
MODE_SNIPER = 0x13      # 狙击模式
MODE_LOCK = 0x14        # 锁定模式

class TriggerConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Trigger Configurator")
        self.root.geometry("1100x650")  # 再次增加窗口宽度以容纳更宽的控制台
        self.root.configure(bg="#1e1e2e")
        self.root.resizable(False, False)
        
        # HID设备通信
        self.device = None
        self.connected = False
        self.stop_monitor = False
        
        # 当前选择
        self.current_mode = None
        
        # 防抖动控制
        self.last_sent_values = {}  # 存储最后发送的参数值
        self.debounce_timers = {}   # 存储参数的防抖动计时器
        self.debounce_delay = 300   # 防抖动延迟（毫秒）
        
        # 存储默认值
        self.default_values = {}    # 存储参数的默认值
        
        # 武器配置数据
        self.current_config_data = None
        
        # UDP通信设置
        self.udp_host = "127.0.0.1"  # UDP监听地址
        self.udp_port = 12345        # UDP监听端口
        self.stop_udp_server = False # 控制UDP服务器线程停止
        
        # 创建样式
        self.create_styles()
        
        # 创建主容器框架（左右分栏）
        self.container_frame = ttk.Frame(self.root, style="Dark.TFrame")
        self.container_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建左侧主框架
        self.main_frame = ttk.Frame(self.container_frame, style="Dark.TFrame", width=550)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建右侧控制台框架
        self.console_frame = ttk.Frame(self.container_frame, style="Dark.TFrame", width=500)
        self.console_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self.console_frame.pack_propagate(False)  # 防止框架自动调整大小
        
        # 创建武器配置框架
        self.create_weapon_config_frame()
        
        # 创建模式选择
        self.create_mode_selection()
        
        # 创建参数框架（最初隐藏）
        self.create_parameter_frames()
        
        # 创建连接框架
        self.create_connection_frame()
        
        # 创建控制台
        self.create_console()
        
        # 初始化为通用模式
        self.select_mode("GENERAL")
        
        # 启动设备监控线程
        self.monitor_thread = threading.Thread(target=self.monitor_device, daemon=True)
        self.monitor_thread.start()
        
        # 启动UDP服务器线程
        self.udp_server_thread = threading.Thread(target=self.run_udp_server, daemon=True)
        self.udp_server_thread.start()
        
        # 初始日志消息
        self.log_message("触发器配置程序已启动")
        self.log_message(f"UDP服务器已启动，监听 {self.udp_host}:{self.udp_port}")
        
    def create_styles(self):
        # 配置ttk样式
        self.style = ttk.Style()
        
        # 检测系统主题
        is_dark = is_dark_mode()
        
        # 根据系统主题设置颜色
        if is_dark:
            bg_color = "#1e1e2e"  # 深色背景
            text_color = "#c0caf5"  # 主文本色
            accent_color = "#7aa2f7"  # 主要强调色
            accent_secondary = "#bb9af7"  # 次要强调色
            success_color = "#9ece6a"  # 成功状态色
            error_color = "#f7768e"  # 错误状态色
            button_bg = "#2c2c3c"  # 按钮背景色
            button_hover = "#3c3c4c"  # 按钮悬停色
            button_active = "#4c4c5c"  # 按钮点击色
            button_text = "#ffffff"  # 按钮文字颜色
            separator_color = "#414868"  # 分隔符色
        else:
            bg_color = "#f0f0f0"  # 浅色背景
            text_color = "#000000"  # 主文本色
            accent_color = "#0066cc"  # 主要强调色
            accent_secondary = "#6600cc"  # 次要强调色
            success_color = "#008800"  # 成功状态色
            error_color = "#cc0000"  # 错误状态色
            button_bg = "#e0e0e0"  # 按钮背景色
            button_hover = "#d0d0d0"  # 按钮悬停色
            button_active = "#c0c0c0"  # 按钮点击色
            button_text = "#000000"  # 按钮文字颜色
            separator_color = "#cccccc"  # 分隔符色
        
        # 基础样式
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("Dark.TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=text_color)
        
        # 通用按钮样式
        self.style.configure("TButton",
            background=button_bg,
            foreground=button_text,
            relief="flat",
            borderwidth=1,
            padding=4  # 添加固定的padding防止位置变动
        )
        self.style.map("TButton",
            background=[("active", button_active), ("pressed", button_active)],
            foreground=[("active", button_text), ("pressed", button_text)]
        )
        
        # 数值调节按钮样式
        self.style.configure("Numpad.TButton",
            background=button_bg,
            foreground=button_text,
            relief="flat",
            borderwidth=1,
            padding=2,
            width=3
        )
        self.style.map("Numpad.TButton",
            background=[("active", button_active), ("pressed", button_active)],
            foreground=[("active", button_text), ("pressed", button_text)]
        )
        
        # 滑块样式
        self.style.configure("TScale",
            background=bg_color,
            troughcolor=button_bg,
            slidercolor=accent_color
        )
        
        # 模式按钮样式
        self.style.configure("Mode.TButton", 
            padding=4, 
            width=12, 
            background=button_bg, 
            foreground=button_text,
            relief="flat",
            borderwidth=1
        )
        self.style.map("Mode.TButton",
            background=[("active", button_hover), ("pressed", button_active)],
            foreground=[("active", button_text), ("pressed", button_text)]
        )
        
        # 激活的模式按钮样式
        self.style.configure("ActiveMode.TButton", 
            background=button_bg, 
            foreground=accent_color,  # 使用蓝色作为激活状态的文字颜色
            relief="solid",
            borderwidth=1
        )
        self.style.map("ActiveMode.TButton",
            background=[("active", button_hover), ("pressed", button_active)],
            foreground=[("active", accent_color), ("pressed", accent_color)]
        )
        
        # 清除和恢复默认按钮样式
        self.style.configure("Clear.TButton",
            background=button_bg,
            foreground=text_color,  # 使用与其他文字相同的颜色
            relief="flat",
            borderwidth=1
        )
        self.style.map("Clear.TButton",
            background=[("active", button_hover), ("pressed", button_active)],
            foreground=[("active", text_color), ("pressed", text_color)],
            relief=[("pressed", "sunken")]
        )
        
        # 参数样式
        self.style.configure("Param.TLabel", 
            font=("Arial", 10), 
            padding=5,
            foreground=text_color,
            background=bg_color
        )
        self.style.configure("Value.TLabel", 
            font=("Arial", 10, "bold"), 
            padding=5,
            foreground=accent_color,
            background=bg_color
        )
        
        # 分隔符样式
        self.style.configure("TSeparator", background=separator_color)
        
        # 组合框样式
        self.style.map("TCombobox", 
            fieldbackground=[("readonly", button_bg)],
            selectbackground=[("readonly", accent_color)],
            selectforeground=[("readonly", button_text)]
        )
        
        # 控制台标签样式
        self.style.configure("Console.TLabel", 
            font=("Consolas", 12, "bold"), 
            padding=5, 
            foreground=success_color,
            background=bg_color
        )
        
        # 状态标签样式
        self.style.configure("Connected.TLabel",
            foreground=success_color,
            font=("Arial", 10, "bold"),
            background=bg_color
        )
        self.style.configure("Disconnected.TLabel",
            foreground=error_color,
            font=("Arial", 10, "bold"),
            background=bg_color
        )
        
        # 帮助图标样式
        self.style.configure("Help.TLabel",
            foreground=accent_secondary,
            font=("Arial", 10, "bold"),
            padding=2,
            background=bg_color
        )

    def create_mode_selection(self):
        # 创建模式框架
        self.mode_frame = ttk.Frame(self.main_frame, style="Dark.TFrame")
        self.mode_frame.pack(fill=tk.X, pady=10)
        
        # 创建模式按钮网格（3x2）
        self.mode_buttons = {}
        
        # 行1
        col1_frame = ttk.Frame(self.mode_frame, style="Dark.TFrame")
        col1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        col2_frame = ttk.Frame(self.mode_frame, style="Dark.TFrame")
        col2_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        col3_frame = ttk.Frame(self.mode_frame, style="Dark.TFrame")
        col3_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 模式按钮带图标
        modes = [
            ("GENERAL", "通用模式", col1_frame, ""),
            ("RACING", "赛车模式", col2_frame, ""),
            ("RECOIL", "后座力模式", col3_frame, ""),
            ("SNIPER", "狙击模式", col1_frame, ""),
            ("LOCK", "锁定模式", col2_frame, "")
        ]
        
        for mode_id, mode_text, parent, icon in modes:
            btn_frame = ttk.Frame(parent, style="Dark.TFrame")
            btn_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # 图标占位符
            icon_label = ttk.Label(btn_frame, text=icon, font=("Arial", 14), style="TLabel")
            icon_label.pack(side=tk.LEFT, padx=5)
            
            # 模式按钮
            btn = ttk.Button(
                btn_frame,
                text=mode_text,
                width=12,
                style="Mode.TButton",
                command=lambda m=mode_id: self.select_mode(m)
            )
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            self.mode_buttons[mode_id] = btn
        
        # 分隔符
        separator = ttk.Separator(self.main_frame, orient="horizontal")
        separator.pack(fill=tk.X, pady=10)

    def create_parameter_frames(self):
        # 所有参数框架的容器
        self.param_container = ttk.Frame(self.main_frame, style="Dark.TFrame")
        self.param_container.pack(fill=tk.BOTH, expand=True)
        
        # 为每种模式创建框架
        self.param_frames = {}
        
        # 通用模式参数
        self.param_frames["GENERAL"] = self.create_general_params()
        
        # 赛车模式参数
        self.param_frames["RACING"] = self.create_racing_params()
        
        # 后座力模式参数
        self.param_frames["RECOIL"] = self.create_recoil_params()
        
        # 狙击模式参数
        self.param_frames["SNIPER"] = self.create_sniper_params()
        
        # 锁定模式参数
        self.param_frames["LOCK"] = self.create_lock_params()
        
        # 初始隐藏所有框架
        for frame in self.param_frames.values():
            frame.pack_forget()
        
        # 创建重置按钮框架
        self.reset_frame = ttk.Frame(self.main_frame, style="Dark.TFrame")
        self.reset_frame.pack(fill=tk.X, pady=10, before=self.param_container)
        
        # 重置按钮
        reset_btn = ttk.Button(
            self.reset_frame,
            text="重置为默认值",
            style="Clear.TButton",
            command=self.reset_to_defaults
        )
        reset_btn.pack(side=tk.RIGHT, padx=10, pady=5)

    def create_general_params(self):
        frame = ttk.Frame(self.param_container, style="Dark.TFrame")
        
        # 通用模式没有参数
        label = ttk.Label(
            frame, 
            text="通用模式激活。\n没有其他参数配置。",
            style="TLabel",
            font=("Arial", 12)
        )
        label.pack(pady=50)
        
        return frame

    def create_racing_params(self):
        frame = ttk.Frame(self.param_container, style="Dark.TFrame")
        
        # 阻尼开始位置
        self.create_slider(
            frame, 
            "阻尼开始位置", 
            "DAMPING_START", 
            0, 192, 0
        )
        
        # 阻尼强度
        self.create_slider(
            frame, 
            "阻尼强度", 
            "DAMPING_STRENGTH", 
            1, 255, 30
        )
        
        return frame

    def create_recoil_params(self):
        frame = ttk.Frame(self.param_container, style="Dark.TFrame")
        
        # 振动开始位置
        self.create_slider(
            frame, 
            "振动开始位置", 
            "VIB_START_POS", 
            0, 192, 0
        )
        
        # 振动初始强度
        self.create_slider(
            frame, 
            "振动初始强度", 
            "VIB_START_STRENGTH", 
            1, 255, 1
        )
        
        # 振动强度
        self.create_slider(
            frame, 
            "振动强度", 
            "VIB_INTENSITY", 
            1, 255, 50
        )
        
        # 振动频率
        self.create_slider(
            frame, 
            "振动频率", 
            "VIB_FREQUENCY", 
            1, 255, 15
        )
        
        # 从振动开始位置开始输出数据
        self.create_toggle(
            frame,
            "从振动开始位置开始输出数据",
            "VIB_START_DATA"
        )
        
        return frame

    def create_sniper_params(self):
        frame = ttk.Frame(self.param_container, style="Dark.TFrame")
        
        # 开始位置
        self.create_slider(
            frame, 
            "开始位置", 
            "START_POS", 
            0, 192, 50
        )
        
        # 触发行程
        self.create_slider(
            frame, 
            "触发行程", 
            "TRIGGER_STROKE", 
            1, 255, 30
        )
        
        # 阻力
        self.create_slider(
            frame, 
            "阻力", 
            "RESISTANCE", 
            1, 255, 1
        )
        
        # 从断开开始位置开始输出数据
        self.create_toggle(
            frame,
            "从断开开始位置开始输出数据",
            "BREAK_START_DATA"
        )
        
        return frame

    def create_lock_params(self):
        frame = ttk.Frame(self.param_container, style="Dark.TFrame")
        
        # 阻尼开始位置
        self.create_slider(
            frame, 
            "阻尼开始位置", 
            "LOCK_DAMPING_START", 
            20, 200, 80
        )
        
        return frame

    def create_slider(self, parent, label_text, param_id, min_val, max_val, default_val):
        frame = ttk.Frame(parent, style="Dark.TFrame")
        frame.pack(fill=tk.X, pady=10)
        
        # 存储默认值
        self.default_values[param_id] = default_val
        
        # 标签和值显示在同一行
        label_frame = ttk.Frame(frame, style="Dark.TFrame")
        label_frame.pack(fill=tk.X)
        
        # 参数标签
        label = ttk.Label(
            label_frame, 
            text=label_text, 
            style="Param.TLabel"
        )
        label.pack(side=tk.LEFT)
        
        # 帮助图标
        help_label = ttk.Label(
            label_frame, 
            text="?", 
            style="TLabel"
        )
        help_label.pack(side=tk.LEFT, padx=5)
        help_label.bind("<Button-1>", lambda e, p=param_id: self.show_help(p))
        
        # 值显示
        value_label = ttk.Label(
            label_frame, 
            text=str(default_val), 
            style="Value.TLabel"
        )
        value_label.pack(side=tk.RIGHT, padx=10)
        
        # 滑块框架
        slider_frame = ttk.Frame(frame, style="Dark.TFrame")
        slider_frame.pack(fill=tk.X, pady=5)
        
        # 减少按钮
        minus_btn = tk.Button(
            slider_frame,
            text="-",
            width=3,
            bg="#1a1a1a",  # 更暗的背景色以增强对比度
            fg="#ffffff",
            relief=tk.RAISED,
            font=("Arial", 12, "bold"),  # 增大字体并使用粗体
            activebackground="#3a3a3a",  # 按下时的背景色
            activeforeground="#ffffff",  # 按下时的前景色
            command=lambda: self.decrement_slider(param_id)
        )
        minus_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # 滑块
        slider_var = tk.IntVar(value=default_val)
        slider = ttk.Scale(
            slider_frame,
            from_=min_val,
            to=max_val,
            orient=tk.HORIZONTAL,
            value=default_val,
            command=lambda v, p=param_id: self.update_slider_value(p, v, True)
        )
        slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 添加滑块释放事件处理
        slider.bind("<ButtonRelease-1>", lambda e, p=param_id: self._on_slider_release(p))
        
        # 增加按钮
        plus_btn = tk.Button(
            slider_frame,
            text="+",
            width=3,
            bg="#1a1a1a",  # 更暗的背景色以增强对比度
            fg="#ffffff",
            relief=tk.RAISED,
            font=("Arial", 12, "bold"),  # 增大字体并使用粗体
            activebackground="#3a3a3a",  # 按下时的背景色
            activeforeground="#ffffff",  # 按下时的前景色
            command=lambda: self.increment_slider(param_id)
        )
        plus_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # 存储引用
        if not hasattr(self, "sliders"):
            self.sliders = {}
            self.slider_values = {}
            self.value_labels = {}
        
        self.sliders[param_id] = slider
        self.slider_values[param_id] = default_val
        self.value_labels[param_id] = value_label

    def create_toggle(self, parent, label_text, param_id):
        frame = ttk.Frame(parent, style="Dark.TFrame")
        frame.pack(fill=tk.X, pady=10)
        
        # 标签
        label = ttk.Label(
            frame, 
            text=label_text, 
            style="Param.TLabel"
        )
        label.pack(side=tk.LEFT)
        
        # 切换变量
        if not hasattr(self, "toggle_vars"):
            self.toggle_vars = {}
        
        self.toggle_vars[param_id] = tk.BooleanVar(value=False)
        
        # 切换按钮（自定义）
        toggle_frame = ttk.Frame(frame, style="Dark.TFrame")
        toggle_frame.pack(side=tk.RIGHT, padx=10)
        
        toggle_bg = tk.Canvas(
            toggle_frame, 
            width=50, 
            height=24, 
            bg="#2b2b2b", 
            highlightthickness=0
        )
        toggle_bg.pack()
        
        # 绘制切换背景
        toggle_bg.create_rectangle(0, 0, 50, 24, fill="#3d3d3d", outline="")
        
        # 绘制切换按钮
        toggle_button = toggle_bg.create_rectangle(2, 2, 24, 22, fill="#2a7fff", outline="")
        
        # 存储引用以更新
        if not hasattr(self, "toggle_widgets"):
            self.toggle_widgets = {}
        
        self.toggle_widgets[param_id] = (toggle_bg, toggle_button)
        
        # 绑定单击事件
        toggle_bg.bind("<Button-1>", lambda e, p=param_id: self.toggle_switch(p))

    def toggle_switch(self, param_id):
        # 切换值
        current_value = self.toggle_vars[param_id].get()
        new_value = not current_value
        self.toggle_vars[param_id].set(new_value)
        
        # 更新视觉切换
        toggle_bg, toggle_button = self.toggle_widgets[param_id]
        
        if new_value:
            toggle_bg.coords(toggle_button, 26, 2, 48, 22)
            toggle_bg.itemconfig(toggle_button, fill="#2a7fff")
        else:
            toggle_bg.coords(toggle_button, 2, 2, 24, 22)
            toggle_bg.itemconfig(toggle_button, fill="#666666")
        
        # 发送更新值 (直接发送，不使用防抖动)
        self._actually_send_parameter(param_id, 1 if new_value else 0)

    def create_connection_frame(self):
        # 创建底部框架
        frame = ttk.Frame(self.main_frame, style="Dark.TFrame")
        frame.pack(fill=tk.X, pady=10)
        
        # 状态标签
        self.status_label = ttk.Label(
            frame, 
            text="设备状态: 未连接", 
            style="TLabel",
            foreground="#ff5555"
        )
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 自动连接提示
        auto_connect_label = ttk.Label(
            frame,
            text="设备将自动连接",
            style="TLabel",
            foreground="#a0a0a0"
        )
        auto_connect_label.pack(side=tk.RIGHT, padx=10)

    def create_console(self):
        """创建控制台显示USB消息"""
        # 控制台标题和按钮框架
        header_frame = ttk.Frame(self.console_frame, style="Dark.TFrame")
        header_frame.pack(fill=tk.X, pady=5)
        
        # 控制台标题
        console_label = ttk.Label(
            header_frame,
            text="USB 消息控制台",
            style="Console.TLabel"
        )
        console_label.pack(side=tk.LEFT, padx=5)
        
        # 清除按钮
        clear_btn = ttk.Button(
            header_frame,
            text="清除",
            style="Clear.TButton",
            command=self.clear_console
        )
        clear_btn.pack(side=tk.RIGHT, padx=5)
        
        # 分隔符
        separator = ttk.Separator(self.console_frame, orient="horizontal")
        separator.pack(fill=tk.X, pady=5)
        
        # 创建文本控件用于显示消息
        self.console = scrolledtext.ScrolledText(
            self.console_frame,
            width=60,  # 再次增加宽度以显示更多信息
            height=32,  # 设置固定高度以匹配主UI
            bg="black",
            fg="#00ff00",
            font=("Consolas", 10),
            wrap=tk.WORD
        )
        self.console.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.console.config(state=tk.DISABLED)  # 设置为只读
    
    def clear_console(self):
        """清除控制台内容"""
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        self.log_message("控制台已清除")

    def log_message(self, message):
        """向控制台添加消息"""
        # 获取当前时间，包含毫秒
        current_time = time.time()
        milliseconds = int((current_time - int(current_time)) * 1000)
        timestamp = time.strftime("%H:%M:%S", time.localtime(current_time)) + f".{milliseconds:03d}"
        
        # 确保在UI线程中更新
        def _update():
            self.console.config(state=tk.NORMAL)
            self.console.insert(tk.END, f"[{timestamp}] {message}\n")
            self.console.see(tk.END)  # 自动滚动到最新消息
            self.console.config(state=tk.DISABLED)
        
        # 如果在主线程中，直接更新；否则使用after方法
        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            self.root.after(0, _update)
        
        # 同时打印到控制台
        print(f"[{timestamp}] {message}")

    def format_hex(self, value):
        """将值格式化为十六进制"""
        if isinstance(value, int):
            return f"0x{value:02X}"
        elif isinstance(value, list):
            return "[" + ", ".join([f"0x{v:02X}" for v in value]) + "]"
        return str(value)
    
    def format_hex_dec(self, value):
        """将值格式化为十六进制和十进制"""
        if isinstance(value, int):
            return f"0x{value:02X} ({value})"
        return str(value)

    def monitor_device(self):
        """监控设备连接状态的后台线程"""
        while not self.stop_monitor:
            try:
                # 检查设备是否已连接
                devices = list(hid.enumerate(VENDOR_ID, PRODUCT_ID))
                
                if devices and not self.connected:
                    self.log_message(f"设备检测到")
                    self.connect_device()
                elif not devices and self.connected:
                    self.log_message(f"设备断开")
                    self.disconnect_device()

            except Exception as e:
                self.log_message(f"监控错误: {e}")
                traceback.print_exc()

            time.sleep(1)

    def connect_device(self):
        """连接到HID设备"""
        try:
            self.log_message("开始连接...")
            
            if self.device:
                self.log_message("关闭现有设备...")
                self.device.close()
                self.device = None
            
            # 列出所有HID设备
            all_devices = list(hid.enumerate())
            self.log_message("所有连接的HID设备:")
            for dev in all_devices:
                self.log_message(f"  VID: {dev['vendor_id']}, PID: {dev['product_id']}, Path: {dev['path']}")
            
            devices = list(hid.enumerate(VENDOR_ID, PRODUCT_ID))
            self.log_message(f"找到 {len(devices)} 个设备，VID={VENDOR_ID}，PID={PRODUCT_ID}")
            
            if not devices:
                self.log_message("没有找到设备")
                self.status_label.config(text="设备状态: 未找到设备")
                return
            
            # 连接到第一个匹配的设备
            self.device = hid.device()
            self.device.open_path(devices[0]['path'])
            self.connected = True
            self.log_message("设备连接成功")
            
            # 更新UI（在主线程中）
            self.root.after(0, self.update_ui_connected)
            
        except Exception as e:
            self.log_message(f"连接错误: {e}")
            traceback.print_exc()
            self.connected = False
            self.device = None
            self.status_label.config(text="设备状态: 连接失败")

    def disconnect_device(self):
        """断开HID设备"""
        self.log_message("断开设备...")
        try:
            if self.device:
                self.device.close()
                self.log_message("设备关闭")
        except Exception as e:
            self.log_message(f"关闭设备错误: {e}")
            traceback.print_exc()
        
        self.device = None
        self.connected = False
        
        # 更新UI（在主线程中）
        self.root.after(0, self.update_ui_disconnected)
        self.log_message("断开完成")

    def update_ui_connected(self):
        """更新UI以反映连接设备状态"""
        self.status_label.config(text="设备状态: 已连接", foreground="#55ff55")

    def update_ui_disconnected(self):
        """更新UI以反映断开设备状态"""
        self.status_label.config(text="设备状态: 未连接", foreground="#ff5555")

    def select_mode(self, mode):
        self.current_mode = mode
        
        # 更新按钮样式
        for m, btn in self.mode_buttons.items():
            if m == mode:
                btn.configure(style="ActiveMode.TButton")
            else:
                btn.configure(style="Mode.TButton")
        
        # 显示相应的参数框架
        for m, frame in self.param_frames.items():
            if m == mode:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()
        
        # 发送当前配置
        self.send_mode(mode)
        self.send_all_parameters()

    def __init_slider_update_flag(self):
        # 初始化标志以避免无限递归
        if not hasattr(self, "_updating_slider"):
            self._updating_slider = {}
    
    def update_slider_value(self, param_id, value, from_slider=True):
        # 初始化更新标志
        self.__init_slider_update_flag()
        
        # 防止无限递归
        if param_id in self._updating_slider and self._updating_slider[param_id]:
            return
            
        try:
            # 设置更新标志
            self._updating_slider[param_id] = True
            
            # 更新存储值
            value = int(float(value))
            self.slider_values[param_id] = value
            
            # 更新显示值
            self.value_labels[param_id].config(text=str(value))
            
            # 如果不是来自滑块的更新，才更新滑块位置
            if not from_slider and param_id in self.sliders:
                self.sliders[param_id].set(value)
            
            # 使用防抖动发送更新值
            self.debounced_send_parameter(param_id, value)
        finally:
            # 重置更新标志
            self._updating_slider[param_id] = False
    
    def debounced_send_parameter(self, param_id, value):
        """使用防抖动机制发送参数，避免短时间内发送相同参数"""
        # 如果已经有一个计时器在运行，取消它
        if param_id in self.debounce_timers and self.debounce_timers[param_id] is not None:
            self.root.after_cancel(self.debounce_timers[param_id])
            self.debounce_timers[param_id] = None
        
        # 检查是否与上次发送的值相同
        if param_id in self.last_sent_values and self.last_sent_values[param_id] == value:
            # 如果相同，只在滑块释放后才发送
            return
        
        # 创建新的计时器
        self.debounce_timers[param_id] = self.root.after(
            self.debounce_delay, 
            lambda: self._actually_send_parameter(param_id, value)
        )
    
    def _actually_send_parameter(self, param_id, value):
        """实际发送参数到设备（在防抖动延迟后）"""
        # 记录最后发送的值
        self.last_sent_values[param_id] = value
        # 清除计时器引用
        self.debounce_timers[param_id] = None
        # 发送参数
        self.send_parameter(param_id, value)

    def increment_slider(self, param_id):
        slider = self.sliders[param_id]
        current = int(float(slider.get()))
        new_value = min(current + 1, slider.cget("to"))
        slider.set(new_value)
        self.update_slider_value(param_id, new_value, False)

    def decrement_slider(self, param_id):
        slider = self.sliders[param_id]
        current = int(float(slider.get()))
        new_value = max(current - 1, slider.cget("from"))
        slider.set(new_value)
        self.update_slider_value(param_id, new_value, False)

    def _on_slider_release(self, param_id):
        """当滑块释放时，确保发送最终值"""
        value = self.slider_values[param_id]
        # 强制发送当前值，无论是否与上次发送的值相同
        if param_id in self.debounce_timers and self.debounce_timers[param_id] is not None:
            self.root.after_cancel(self.debounce_timers[param_id])
            self.debounce_timers[param_id] = None
        self._actually_send_parameter(param_id, value)

    def send_hid_report(self, cmd_type, data):
        """发送HID报告到设备"""
        try:
            if not self.device or not self.connected:
                self.log_message("设备未连接")
                return 0
            
            self.log_message(f"命令类型={self.format_hex_dec(cmd_type)}, 数据={self.format_hex(data)}")
            
            # 确保数据是列表
            if not isinstance(data, list):
                data = [data]
            
            # 计算校验和（简单的所有数据字节相加）
            checksum = (cmd_type + sum(data)) & 0xFF
            
            # 格式化报告: [命令头, 命令类型, 数据长度, ...数据, 校验和, 命令尾, 填充]
            report = [0, CMD_HEADER, cmd_type, len(data)] + data + [checksum, CMD_FOOTER]
            
            # 添加填充以达到64字节
            report = report + [0] * (64 - len(report))
            
            # 格式化报告前10个字节为十六进制显示
            hex_report = ", ".join([f"0x{b:02X}" for b in report[:10]])
            self.log_message(f"USB发送: [{hex_report}...] ({len(report)} 字节)")
            
            try:
                bytes_written = self.device.write(report)
                self.log_message(f"写入 {bytes_written}/{len(report)} 字节")
                
                if bytes_written < len(report):
                    self.log_message(f"警告: 部分写入: {bytes_written}/{len(report)} 字节")
                
                time.sleep(0.01)
                return bytes_written
                
            except Exception as e:
                self.log_message(f"写入失败: {e}")
                traceback.print_exc()
                return 0
                
        except Exception as e:
            self.log_message(f"发送错误: {e}")
            traceback.print_exc()
            return 0

    def send_mode(self, mode):
        """发送模式选择到设备"""
        if not self.connected:
            return
        
        # 将模式映射到模式ID
        mode_ids = {
            "GENERAL": MODE_GENERAL,
            "RACING": MODE_RACING,
            "RECOIL": MODE_RECOIL,
            "SNIPER": MODE_SNIPER,
            "LOCK": MODE_LOCK
        }
        
        mode_id = mode_ids.get(mode, MODE_GENERAL)
        
        # 发送模式命令
        self.send_hid_report(CMD_TYPE_MODE, [mode_id])
        self.log_message(f"发送模式: {mode} (ID: {self.format_hex_dec(mode_id)})")

    def send_parameter(self, param_id, value):
        """发送参数值到设备"""
        if not self.connected:
            return
        
        # 将参数ID映射到数字ID
        param_ids = {
            # 赛车模式参数
            "DAMPING_START": 0x21,
            "DAMPING_STRENGTH": 0x22,
            
            # 后座力模式参数
            "VIB_START_POS": 0x31,
            "VIB_START_STRENGTH": 0x32,
            "VIB_INTENSITY": 0x33,
            "VIB_FREQUENCY": 0x34,
            "VIB_START_DATA": 0x35,
            
            # 狙击模式参数
            "START_POS": 0x41,
            "TRIGGER_STROKE": 0x42,
            "RESISTANCE": 0x43,
            "BREAK_START_DATA": 0x44,
            
            # 锁定模式参数
            "LOCK_DAMPING_START": 0x51
        }
        
        param_numeric_id = param_ids.get(param_id, 0)
        
        if param_numeric_id == 0:
            self.log_message(f"未知参数ID: {param_id}")
            return
        
        # 发送参数命令: [参数ID, 值高字节, 值低字节]
        data = [param_numeric_id, (value >> 8) & 0xFF, value & 0xFF]
        self.send_hid_report(CMD_TYPE_PARAM, data)
        self.log_message(f"发送参数: {param_id} (ID: {self.format_hex_dec(param_numeric_id)}) = {self.format_hex_dec(value)}")

    def send_all_parameters(self):
        """发送所有参数的当前模式"""
        if not self.connected or not self.current_mode:
            return
        
        # 清除所有防抖动计时器
        for param_id in list(self.debounce_timers.keys()):
            if self.debounce_timers[param_id] is not None:
                self.root.after_cancel(self.debounce_timers[param_id])
                self.debounce_timers[param_id] = None
        
        # 根据当前模式准备需要发送的参数列表
        params_to_send = []
        
        if self.current_mode == "RACING":
            mode_params = ["DAMPING_START", "DAMPING_STRENGTH"]
        elif self.current_mode == "RECOIL":
            mode_params = ["VIB_START_POS", "VIB_START_STRENGTH", "VIB_INTENSITY", "VIB_FREQUENCY"]
        elif self.current_mode == "SNIPER":
            mode_params = ["START_POS", "TRIGGER_STROKE", "RESISTANCE"]
        elif self.current_mode == "LOCK":
            mode_params = ["LOCK_DAMPING_START"]
        else:
            mode_params = []
        
        # 收集当前模式的所有参数
        for param_id in mode_params:
            if param_id in self.slider_values:
                params_to_send.append((param_id, self.slider_values[param_id]))
        
        # 添加开关参数
        if hasattr(self, "toggle_vars"):
            if self.current_mode == "RECOIL" and "VIB_START_DATA" in self.toggle_vars:
                value = 1 if self.toggle_vars["VIB_START_DATA"].get() else 0
                params_to_send.append(("VIB_START_DATA", value))
            elif self.current_mode == "SNIPER" and "BREAK_START_DATA" in self.toggle_vars:
                value = 1 if self.toggle_vars["BREAK_START_DATA"].get() else 0
                params_to_send.append(("BREAK_START_DATA", value))
        
        # 按顺序发送参数，并在参数之间添加延迟
        for i, (param_id, value) in enumerate(params_to_send):
            # 发送参数
            self.send_parameter(param_id, value)
            self.last_sent_values[param_id] = value
            
            # 如果不是最后一个参数，添加延迟
            if i < len(params_to_send) - 1:
                # 使用after方法添加延迟，让UI保持响应
                self.root.update()
                time.sleep(0.05)  # 50毫秒的延迟

    def show_help(self, param_id):
        """显示参数帮助信息"""
        help_texts = {
            "DAMPING_START": "阻尼开始位置（0-192）- 设置阻尼效果开始的触发器位置",
            "DAMPING_STRENGTH": "阻尼强度（1-255）- 控制阻尼效果的强度",
            "VIB_START_POS": "振动开始位置（0-192）- 设置振动效果开始的触发器位置",
            "VIB_START_STRENGTH": "振动初始强度（1-255）- 控制振动开始时的初始强度",
            "VIB_INTENSITY": "振动强度（1-255）- 控制振动效果的整体强度",
            "VIB_FREQUENCY": "振动频率（1-255）- 控制振动效果的频率",
            "VIB_START_DATA": "启用时，从振动开始位置开始输出数据",
            "START_POS": "开始位置（0-192）- 设置狙击模式效果开始的触发器位置",
            "TRIGGER_STROKE": "触发行程（1-255）- 控制触发器的行程距离",
            "RESISTANCE": "阻力（1-255）- 控制狙击模式下的阻力大小",
            "BREAK_START_DATA": "启用时，从断开开始位置开始输出数据",
            "LOCK_DAMPING_START": "锁定阻尼开始位置（20-200）- 设置锁定模式下阻尼效果开始的位置" 
        }
        
        text = help_texts.get(param_id, "没有帮助信息")
        messagebox.showinfo(f"帮助: {param_id}", text)

    def reset_to_defaults(self):
        """重置当前模式的所有参数为默认值"""
        if not self.current_mode:
            return
        
        self.log_message(f"重置 {self.current_mode} 模式的所有参数为默认值")
        
        # 重置滑块值
        for param_id, slider in self.sliders.items():
            # 检查参数是否属于当前模式
            belongs_to_current_mode = False
            
            if self.current_mode == "RACING" and param_id in ["DAMPING_START", "DAMPING_STRENGTH"]:
                belongs_to_current_mode = True
            elif self.current_mode == "RECOIL" and param_id in ["VIB_START_POS", "VIB_START_STRENGTH", "VIB_INTENSITY", "VIB_FREQUENCY"]:
                belongs_to_current_mode = True
            elif self.current_mode == "SNIPER" and param_id in ["START_POS", "TRIGGER_STROKE", "RESISTANCE"]:
                belongs_to_current_mode = True
            elif self.current_mode == "LOCK" and param_id in ["LOCK_DAMPING_START"]:
                belongs_to_current_mode = True
                
            if belongs_to_current_mode and param_id in self.default_values:
                default_val = self.default_values[param_id]
                slider.set(default_val)
                self.slider_values[param_id] = default_val
                self.value_labels[param_id].config(text=str(default_val))
                self._actually_send_parameter(param_id, default_val)
        
        # 重置开关值
        if hasattr(self, "toggle_vars"):
            for param_id, toggle_var in self.toggle_vars.items():
                # 检查参数是否属于当前模式
                if (self.current_mode == "RECOIL" and param_id == "VIB_START_DATA") or \
                   (self.current_mode == "SNIPER" and param_id == "BREAK_START_DATA"):
                    # 默认值为False
                    if toggle_var.get():
                        toggle_var.set(False)
                        toggle_bg, toggle_button = self.toggle_widgets[param_id]
                        toggle_bg.coords(toggle_button, 2, 2, 24, 22)
                        toggle_bg.itemconfig(toggle_button, fill="#666666")
                        self._actually_send_parameter(param_id, 0)
        
        # 发送当前模式到设备
        self.send_mode(self.current_mode)
        
        # 发送所有参数到设备
        self.send_all_parameters()
        
        self.log_message("参数已重置为默认值并发送到设备")

    def __del__(self):
        """清理资源，当对象被销毁时"""
        self.stop_monitor = True
        self.stop_udp_server = True
        
        if self.device:
            try:
                self.device.close()
            except:
                pass
        
        if hasattr(self, "udp_socket"):
            try:
                self.udp_socket.close()
            except:
                pass

    def load_weapon_config(self, file_path):
        """加载武器配置JSON文件"""
        import json
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.log_message(f"已加载配置文件: {file_path}")
                return config_data
        except Exception as e:
            self.log_message(f"加载配置文件失败: {str(e)}")
            return None

    def get_weapon_trigger_config(self, config_data, weapon_name):
        """根据武器名称获取模式和触发器参数
        
        Args:
            config_data: 加载的JSON配置数据
            weapon_name: 武器名称
            
        Returns:
            tuple: (mode_name, mode_value, trigger_params) 或者 None如果未找到
        """
        if not config_data or not weapon_name:
            return None
            
        # 检查是否在vFilters中找到匹配的武器名称
        for weapon_filter in config_data.get("vFilters", []):
            if weapon_filter.get("name") == weapon_name:
                # 获取右触发器配置
                right_trigger = weapon_filter.get("trigger", {}).get("right", {})
                mode_value = right_trigger.get("mode", 0)
                trigger_params = right_trigger.get("param", [0, 0, 0, 0])
                
                # 获取模式名称
                mode_name = "GENERAL"
                if mode_value == 0:
                    mode_name = "GENERAL"
                elif mode_value == 1:
                    mode_name = "RACING"
                elif mode_value == 2:
                    mode_name = "RECOIL"
                elif mode_value == 3:
                    mode_name = "SNIPER"
                elif mode_value == 4:
                    mode_name = "LOCK"
                
                # 检查参数是否有效（非零）
                has_valid_params = any(param != 0 for param in trigger_params)
                
                self.log_message(f"找到武器 '{weapon_name}' 配置: 模式={mode_name}, 参数={trigger_params}")
                if not has_valid_params:
                    self.log_message(f"警告: 武器 '{weapon_name}' 在 {mode_name} 模式下没有有效参数")
                
                return (mode_name, mode_value, trigger_params)
                
        # 如果没有找到，尝试使用默认配置
        default_config = config_data.get("trigger_default", {})
        if default_config:
            right_trigger = default_config.get("right", {})
            mode_value = right_trigger.get("mode", 0)
            trigger_params = right_trigger.get("param", [0, 0, 0, 0])
            
            # 获取模式名称
            mode_name = "GENERAL"
            if mode_value == 0:
                mode_name = "GENERAL"
            elif mode_value == 1:
                mode_name = "RACING"
            elif mode_value == 2:
                mode_name = "RECOIL"
            elif mode_value == 3:
                mode_name = "SNIPER"
            elif mode_value == 4:
                mode_name = "LOCK"
            
            self.log_message(f"未找到武器 '{weapon_name}'，使用默认配置: 模式={mode_name}, 参数={trigger_params}")
            return (mode_name, mode_value, trigger_params)
        
        self.log_message(f"未找到武器 '{weapon_name}' 配置，且无默认配置")
        return None

    def apply_weapon_config(self, weapon_name, config_file_path=None):
        """应用武器配置到当前设置
        
        Args:
            weapon_name: 武器名称
            config_file_path: 配置文件路径，如果为None则使用上次加载的配置
        """
        # 如果提供了配置文件路径，则加载配置
        config_data = None
        if config_file_path:
            config_data = self.load_weapon_config(config_file_path)
            self.current_config_data = config_data
        else:
            # 使用上次加载的配置
            if hasattr(self, 'current_config_data'):
                config_data = self.current_config_data
            else:
                self.log_message("错误: 未加载配置文件")
                return False
        
        if not config_data:
            return False
            
        # 获取武器配置
        weapon_config = self.get_weapon_trigger_config(config_data, weapon_name)
        if not weapon_config:
            return False
            
        mode_name, mode_value, trigger_params = weapon_config
        
        # 切换到对应的模式
        self.select_mode(mode_name)
        
        # 应用参数值
        if mode_name == "RACING" and len(trigger_params) >= 2:
            # 赛车模式参数 [DAMPING_START, DAMPING_STRENGTH]
            if trigger_params[0] != 0:
                self.update_slider_value("DAMPING_START", trigger_params[0], False)
            if trigger_params[1] != 0:
                self.update_slider_value("DAMPING_STRENGTH", trigger_params[1], False)
                
        elif mode_name == "RECOIL" and len(trigger_params) >= 4:
            # 后座力模式参数 [VIB_START_POS, VIB_START_STRENGTH, VIB_INTENSITY, VIB_FREQUENCY]
            if trigger_params[0] != 0:
                self.update_slider_value("VIB_START_POS", trigger_params[0], False)
            if trigger_params[1] != 0:
                self.update_slider_value("VIB_START_STRENGTH", trigger_params[1], False)
            if trigger_params[2] != 0:
                self.update_slider_value("VIB_INTENSITY", trigger_params[2], False)
            if trigger_params[3] != 0:
                self.update_slider_value("VIB_FREQUENCY", trigger_params[3], False)
                
        elif mode_name == "SNIPER" and len(trigger_params) >= 3:
            # 狙击模式参数 [START_POS, TRIGGER_STROKE, RESISTANCE]
            if trigger_params[0] != 0:
                self.update_slider_value("START_POS", trigger_params[0], False)
            if trigger_params[1] != 0:
                self.update_slider_value("TRIGGER_STROKE", trigger_params[1], False)
            if trigger_params[2] != 0:
                self.update_slider_value("RESISTANCE", trigger_params[2], False)
                
        elif mode_name == "LOCK" and len(trigger_params) >= 1:
            # 锁定模式参数 [LOCK_DAMPING_START]
            if trigger_params[0] != 0:
                self.update_slider_value("LOCK_DAMPING_START", trigger_params[0], False)
        
        # 发送所有参数到设备
        self.send_all_parameters()
        
        self.log_message(f"已应用武器 '{weapon_name}' 的配置并发送到设备")
        return True

    def create_weapon_config_frame(self):
        """创建武器配置框架"""
        import tkinter.filedialog as filedialog
        
        # 创建武器配置框架
        weapon_frame = ttk.LabelFrame(self.main_frame, text="武器配置", style="Dark.TLabelframe")
        weapon_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        # 创建按钮框架
        button_frame = ttk.Frame(weapon_frame, style="Dark.TFrame")
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 创建加载配置按钮
        load_button = ttk.Button(button_frame, text="加载配置文件", style="Accent.TButton",
                               command=lambda: self.load_config_file())
        load_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # 创建武器选择下拉框
        self.weapon_var = tk.StringVar()
        self.weapon_combo = ttk.Combobox(button_frame, textvariable=self.weapon_var, 
                                      state="readonly", style="Dark.TCombobox")
        self.weapon_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 创建应用配置按钮
        apply_button = ttk.Button(button_frame, text="应用配置", style="Accent.TButton",
                                command=lambda: self.apply_weapon_config(self.weapon_var.get()))
        apply_button.pack(side=tk.LEFT, padx=(5, 0))
        
        # 绑定武器选择事件
        self.weapon_combo.bind("<<ComboboxSelected>>", 
                             lambda e: self.apply_weapon_config(self.weapon_var.get()))
    
    def load_config_file(self):
        """加载配置文件对话框"""
        import tkinter.filedialog as filedialog
        
        file_path = filedialog.askopenfilename(
            title="选择配置文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
            
        # 加载配置文件
        config_data = self.load_weapon_config(file_path)
        if not config_data:
            return
            
        self.current_config_data = config_data
        
        # 更新武器下拉框
        weapon_names = []
        for weapon_filter in config_data.get("vFilters", []):
            if "name" in weapon_filter:
                weapon_names.append(weapon_filter["name"])
                
        if weapon_names:
            self.weapon_combo["values"] = weapon_names
            self.weapon_combo.current(0)
            # 自动应用第一个武器的配置
            self.apply_weapon_config(weapon_names[0])
        else:
            self.weapon_combo["values"] = []
            self.log_message("警告: 配置文件中没有找到武器")

    def run_udp_server(self):
        """运行UDP服务器线程"""
        self.log_message("启动UDP服务器...")
        try:
            # 创建UDP套接字
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind((self.udp_host, self.udp_port))
            self.log_message(f"UDP服务器已启动，监听 {self.udp_host}:{self.udp_port}")
            
            while not self.stop_udp_server:
                # 接收数据
                data, addr = self.udp_socket.recvfrom(1024)
                self.log_message(f"收到UDP数据: {data} ({addr[0]}:{addr[1]})")
                
                # 处理数据
                self.handle_udp_data(data)
                
        except Exception as e:
            self.log_message(f"UDP服务器错误: {e}")
            traceback.print_exc()
        
        finally:
            # 关闭UDP套接字
            if hasattr(self, "udp_socket"):
                self.udp_socket.close()
                self.log_message("UDP服务器已关闭")

    def handle_udp_data(self, data):
        """处理UDP数据"""
        try:
            # 解码数据
            weapon_name = data.decode('utf-8').strip()
            self.log_message(f"收到武器名称: {weapon_name}")
            
            # 武器名称映射表（中文名称到下拉菜单值的映射）
            weapon_name_map = {
                "手枪": "手枪",
                "主武器": "主武器",
                "副武器": "副武器"
            }
            
            # 检查当前是否已加载配置
            if not hasattr(self, 'current_config_data') or not self.current_config_data:
                self.log_message("错误: 未加载配置文件，无法应用武器配置")
                return
            
            # 获取当前下拉菜单中的武器列表
            weapon_values = list(self.weapon_combo["values"])
            if not weapon_values:
                self.log_message("错误: 下拉菜单中没有武器选项")
                return
            
            # 查找对应的武器
            target_weapon = weapon_name_map.get(weapon_name)
            if not target_weapon:
                self.log_message(f"错误: 未知的武器名称 '{weapon_name}'")
                return
            
            # 在下拉菜单中查找匹配的武器
            found_weapon = None
            for weapon in weapon_values:
                if target_weapon in weapon:
                    found_weapon = weapon
                    break
            
            if not found_weapon:
                self.log_message(f"错误: 在配置中未找到匹配的武器 '{target_weapon}'")
                return
            
            # 在主线程中执行UI更新
            self.root.after(0, lambda: self._apply_weapon_from_udp(found_weapon))
            
        except Exception as e:
            self.log_message(f"处理UDP数据错误: {e}")
            traceback.print_exc()
    
    def _apply_weapon_from_udp(self, weapon_name):
        """在主线程中应用武器配置（从UDP接收）"""
        try:
            # 设置下拉菜单选择
            self.weapon_var.set(weapon_name)
            
            # 应用配置
            self.log_message(f"通过UDP应用武器配置: {weapon_name}")
            self.apply_weapon_config(weapon_name)
            
        except Exception as e:
            self.log_message(f"应用武器配置错误: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    print("启动触发器配置程序")
    root = tk.Tk()
    app = TriggerConfigApp(root)
    root.mainloop()
    print("触发器配置程序关闭")