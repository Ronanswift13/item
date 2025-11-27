import socket
import struct
import time

def check_hikvision_broadcast():
    print("--- 正在侦听海康设备广播 (SADP协议) ---")
    # 海康 SADP 协议使用 UDP 广播
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(5)
    
    # 绑定到本地所有 IP
    try:
        sock.bind(("", 37020))
    except:
        print("端口 37020 被占用，可能已有 SADP 软件在运行。")
        return

    print("正在等待设备心跳包 (请等待 5-10 秒)...")
    
    try:
        start_time = time.time()
        while time.time() - start_time < 10:
            data, addr = sock.recvfrom(4096)
            # 过滤目标 IP
            if addr[0] == "192.168.1.64":
                print(f"\n✅ 捕获到设备信号! IP: {addr[0]}")
                
                # 尝试解析 XML 数据 (海康协议通常包含 XML)
                try:
                    payload = data.decode('utf-8', errors='ignore')
                    if "<ProbeMatch>" in payload or "<Uuid>" in payload:
                        print("确认是海康系设备！")
                        
                        # 寻找激活状态
                        if "<Activated>false</Activated>" in payload or "<Activated>0</Activated>" in payload:
                            print("\n🚨 状态：【未激活】(Inactive)")
                            print("👉 原因找到！因为未激活，所以 554/80 端口都被锁死了。")
                            print("👉 解决方法：必须使用 SADP 工具设置密码。")
                        elif "<Activated>true</Activated>" in payload:
                            print("\n✅ 状态：【已激活】")
                            print(f"👉 既然已激活但端口554关闭，可能是端口被改到了: {payload}")
                        else:
                            print("❓ 状态未知，原始数据片段:", payload[:100])
                        return
                except:
                    pass
    except socket.timeout:
        print("❌ 未收到广播，可能是防火墙拦截或非海康设备。")
    finally:
        sock.close()

def check_port_5000_http():
    print("\n--- 尝试 HTTP 访问端口 5000 ---")
    target = ("192.168.1.64", 5000)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(target)
        # 发送简单的 HTTP 请求看看它是谁
        s.sendall(b"GET / HTTP/1.1\r\nHost: 192.168.1.64\r\n\r\n")
        data = s.recv(1024)
        print(f"收到响应:\n{data.decode('utf-8', errors='ignore')}")
        s.close()
    except Exception as e:
        print(f"HTTP 请求失败: {e}")
        print("👉 端口 5000 可能不是 Web 服务，而是 UPnP 或私有协议。")

if __name__ == "__main__":
    check_port_5000_http()
    check_hikvision_broadcast()