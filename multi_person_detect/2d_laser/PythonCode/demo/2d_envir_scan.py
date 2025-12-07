import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Wedge, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.widgets import CheckButtons

# ================= 现场参数配置 =================
CORRIDOR_LENGTH = 10.0    # 过道长度
CORRIDOR_WIDTH = 3.5      # 过道宽度
CABINET_DEPTH = 0.8       # 机柜深度
YELLOW_LINE_Y = 1.2       # 黄线Y坐标
BUFFER_ZONE = 0.3         # 缓冲区
SENSOR_POS = (0, YELLOW_LINE_Y) # 传感器安装在过道起始端，正对黄线

class SafetyMonitorSimulation:
    def __init__(self):
        # 1. 界面布局 (留出底部给控制台)
        self.fig, self.ax = plt.subplots(figsize=(14, 8))
        self.fig.subplots_adjust(bottom=0.2) 
        
        # 兼容macOS的窗口标题设置
        try:
            if self.fig.canvas.manager:
                self.fig.canvas.manager.set_window_title('Digital Twin: Authorized Operation Monitor')
        except: pass

        # 2. 状态变量
        self.people_pos = [
            [1.5, 1.5], # P1 (Zone 1)
            [3.5, 2.0], # P2 (Zone 2)
            [5.5, 1.8], # P3 (Zone 3)
            [7.5, 1.0], # P4 (Zone 4 - 越线)
            [9.0, 2.5]  # P5 (Zone 5)
        ]
        self.authorized_zones = [True, False, False, False, False] # 默认只授权1号柜
        self.dragging_idx = None

        # 3. 初始化场景
        self.setup_environment()
        self.init_actors()
        self.init_ui_controls()
        
        # 4. 事件绑定
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_drag)
        self.fig.canvas.mpl_connect('button_release_event', self.on_release)
        
        # 初始刷新
        self.update_logic()
        plt.show()

    def setup_environment(self):
        """绘制静态背景"""
        self.ax.set_xlim(-0.5, CORRIDOR_LENGTH + 0.5)
        self.ax.set_ylim(-0.5, CORRIDOR_WIDTH)
        self.ax.set_facecolor('#f4f6f7')
        self.ax.set_xlabel("Corridor Distance (m)")
        self.ax.set_ylabel("Depth (m)")
        self.ax.set_title("Fusion Monitor: Authorization Logic (Radar) + Line Crossing (Visual)", fontweight='bold')

        # A. 绘制机柜 (Zone 1-5)
        self.zone_width = CORRIDOR_LENGTH / 5
        for i in range(5):
            # 机柜矩形
            rect = Rectangle((i*self.zone_width, 0), self.zone_width, CABINET_DEPTH, 
                             facecolor='#95a5a6', edgecolor='#7f8c8d', lw=2)
            self.ax.add_patch(rect)
            # 地面区域文字
            self.ax.text(i*self.zone_width + self.zone_width/2, CABINET_DEPTH/2, 
                         f"CABINET {i+1}", ha='center', va='center', 
                         color='white', fontweight='bold', fontsize=9)
            # 虚线分隔
            self.ax.vlines(i*self.zone_width, 0, CORRIDOR_WIDTH, colors='gray', linestyles=':', alpha=0.3)

        # B. 绘制黄线
        self.ax.axhline(YELLOW_LINE_Y, color='#f1c40f', lw=4, ls='--')
        self.ax.text(0.2, YELLOW_LINE_Y + 0.1, "SAFETY LINE (Visual Detection)", color='#f39c12', fontweight='bold')

        # C. 绘制危险区
        self.ax.add_patch(Rectangle((0, CABINET_DEPTH), CORRIDOR_LENGTH, YELLOW_LINE_Y - CABINET_DEPTH, color='red', alpha=0.1))

        # D. 传感器图标 (移到黄线位置)
        self.ax.plot(SENSOR_POS[0], SENSOR_POS[1], marker='>', markersize=15, color='#8e44ad', zorder=20)
        self.ax.text(SENSOR_POS[0], SENSOR_POS[1]+0.2, "Fusion Module\n(Cam + LiDAR)", color='#8e44ad', fontsize=8, fontweight='bold')

    def init_actors(self):
        """初始化可拖动的人员和状态框"""
        self.actors = [] # 存 {'body': Circle, 'ray': Line, 'text': Annotation, 'box': Bbox}
        colors = ['#3498db', '#e67e22', '#2ecc71', '#9b59b6', '#34495e']
        
        for i in range(5):
            # 1. 人体圆点
            circle = Circle(self.people_pos[i], radius=0.25, color=colors[i], alpha=0.9, zorder=10)
            self.ax.add_patch(circle)
            
            # 2. 激光射线 (从传感器连向人)
            ray = Line2D([], [], color='#2ecc71', lw=1, alpha=0.6, linestyle='-')
            self.ax.add_line(ray)
            
            # 3. 状态信息框 (FancyBbox)
            # 我们使用 text 的 bbox 属性来实现跟随框
            text = self.ax.text(0, 0, "", fontsize=8, color='white', fontweight='bold',
                                ha='left', va='bottom', zorder=15,
                                bbox=dict(boxstyle="round,pad=0.5", fc="gray", alpha=0.9))
            
            self.actors.append({'body': circle, 'ray': ray, 'text': text})

    def init_ui_controls(self):
        """底部授权控制台"""
        # 在底部创建一个区域放 Checkbox
        ax_check = self.fig.add_axes([0.15, 0.05, 0.7, 0.08], frameon=False)
        ax_check.set_title("AUTHORIZED ZONES CONTROL (Select Allowed Cabinets):", fontsize=10, loc='left')
        
        labels = [f'Cab {i+1}' for i in range(5)]
        # 默认只有 Cab 1 是 True
        visibility = [True, False, False, False, False]
        
        self.check = CheckButtons(ax_check, labels, visibility)
        
        # 绑定点击事件
        def func(label):
            idx = int(label.split(' ')[1]) - 1
            self.authorized_zones[idx] = not self.authorized_zones[idx]
            self.update_logic() # 点击后立即刷新状态
            self.fig.canvas.draw_idle()
            
        self.check.on_clicked(func)

    def update_logic(self):
        """核心业务逻辑：融合判断位置、授权和越线"""
        
        for i, actor in enumerate(self.actors):
            px, py = self.people_pos[i]
            
            # 1. 计算当前所在的 Zone (雷达 X轴定位)
            current_zone_idx = int(px // self.zone_width)
            current_zone_idx = max(0, min(current_zone_idx, 4)) # 限制在0-4
            
            # 2. 计算距离机柜的距离 (雷达 Y轴测距)
            dist_to_cabinet = py - CABINET_DEPTH
            dist_to_line = py - YELLOW_LINE_Y
            
            # 3. 状态判定机 (Status Machine)
            # 优先级：越线 (视觉) > 未授权 (雷达逻辑) > 预警 > 安全
            
            status_text = ""
            box_color = "gray"
            
            is_authorized = self.authorized_zones[current_zone_idx]
            
            # A. 判定越线 (DANGER)
            if py < YELLOW_LINE_Y:
                status_text = "DANGER: LINE CROSSED"
                box_color = "#c0392b" # 红色
                actor['ray'].set_color('red')
                actor['ray'].set_linewidth(2)
            
            # B. 判定未授权 (UNAUTHORIZED)
            elif not is_authorized:
                status_text = "ALERT: UNAUTHORIZED ZONE"
                box_color = "#d35400" # 深橙色
                actor['ray'].set_color('orange')
                actor['ray'].set_linewidth(1.5)
                
            # C. 判定预警 (WARNING)
            elif py < YELLOW_LINE_Y + BUFFER_ZONE:
                status_text = "WARNING: TOO CLOSE"
                box_color = "#f39c12" # 橙色
                actor['ray'].set_color('#f1c40f')
            
            # D. 安全 (SAFE)
            else:
                status_text = "SAFE: AUTHORIZED"
                box_color = "#27ae60" # 绿色
                actor['ray'].set_color('#2ecc71')
                actor['ray'].set_linewidth(1)

            # 4. 更新UI显示
            # 更新圆点位置
            actor['body'].center = (px, py)
            
            # 更新射线 (从传感器到人)
            actor['ray'].set_data([SENSOR_POS[0], px], [SENSOR_POS[1], py])
            
            # 更新文字框内容
            display_str = (f"ID: P{i+1} | Zone: {current_zone_idx+1}\n"
                           f"Dist: {dist_to_cabinet:.2f}m\n"
                           f"[{status_text}]")
            
            actor['text'].set_text(display_str)
            actor['text'].set_position((px + 0.3, py + 0.3)) # 文字显示在人旁边
            actor['text'].set_bbox(dict(boxstyle="round,pad=0.5", fc=box_color, alpha=0.85))

    # ================= 鼠标交互 =================
    def on_click(self, event):
        if event.inaxes != self.ax: return
        for i, pos in enumerate(self.people_pos):
            dist = np.sqrt((pos[0]-event.xdata)**2 + (pos[1]-event.ydata)**2)
            if dist < 0.4:
                self.dragging_idx = i
                break

    def on_drag(self, event):
        if self.dragging_idx is None or event.inaxes != self.ax: return
        
        # 限制拖拽范围
        new_x = max(0.1, min(CORRIDOR_LENGTH-0.1, event.xdata))
        new_y = max(CABINET_DEPTH-0.2, min(CORRIDOR_WIDTH-0.1, event.ydata))
        
        self.people_pos[self.dragging_idx] = [new_x, new_y]
        self.update_logic() # 实时刷新逻辑
        self.fig.canvas.draw_idle()

    def on_release(self, event):
        self.dragging_idx = None

# 启动
sim = SafetyMonitorSimulation()