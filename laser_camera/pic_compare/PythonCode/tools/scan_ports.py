import socket
import time

IP = "192.168.1.108"  # 你的摄像头 IP

# 工业相机常用端口列表
PORTS_TO_SCAN = [
    554,   # RTSP 标准端口 (最重要)
    80,    # Web HTTP
    8080,  # Web / ONVIF
    8000,  # 海康 SDK / HTTP
    8554,  # RTSP 备用
    1935,  # RTMP
    10554, # 特殊 RTSP
    5000,  # UPnP
    37777, # 大华私有
    34567, # 雄迈私有
    52381, # Visca (云台控制)
    23,    # Telnet (调试)
]

print(f"--- 开始扫描设备 {IP} ---")
open_ports = []

for port in PORTS_TO_SCAN:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)  # 1秒超时
    result = sock.connect_ex((IP, port))
    
    if result == 0:
        print(f"✅ 端口 {port} [OPEN] -> 居然是开着的！")
        open_ports.append(port)
    elif result == 61: # Connection refused
        print(f"❌ 端口 {port} [Refused] -> 设备主动拒绝 (服务未开)")
    else:
        print(f"⏳ 端口 {port} [Timeout] -> 无响应")
    
    sock.close()

print("-" * 30)
if open_ports:
    print(f"🎉 发现开放端口: {open_ports}")
    if 554 in open_ports:
        print("👉 建议：RTSP 服务已开启，请继续尝试爆破密码/路径。")
    elif 8000 in open_ports or 8080 in open_ports:
        print(f"👉 建议：尝试使用 rtsp://{IP}:{open_ports[0]}/... 连接")
else:
    print("😱 没有发现任何开放端口！")
    print("可能原因：")
    print("1. 摄像头的 RTSP 功能默认是关闭的（需要专用工具开启）。")
    print("2. 这是一台需要专用客户端（如海康 iVMS-4200）配置的设备。")