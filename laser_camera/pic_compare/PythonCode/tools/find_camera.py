import subprocess
import threading
import socket
from queue import Queue

# 这一步非常重要：确保你的 Wi-Fi 已关闭，且 USB 网卡设为了 192.168.1.x
NETWORK_PREFIX = "192.168.1." 

def ping_ip(ip, result_queue):
    try:
        # Mac 下的 ping 命令，-c 1 次数，-W 500 毫秒超时
        res = subprocess.run(
            ["ping", "-c", "1", "-W", "500", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if res.returncode == 0:
            # 再次确认不是本机
            # 获取本机 IP 比较繁琐，这里简单过滤 .200 (你设置的本机IP)
            if not ip.endswith(".200"): 
                result_queue.put(ip)
    except:
        pass

def scan_network():
    print(f"--- 开始扫描网段 {NETWORK_PREFIX}0/24 ---")
    print("请确保 Wi-Fi 已关闭！")
    
    queue = Queue()
    threads = []

    # 启动 254 个线程并发扫描，速度很快
    for i in range(1, 255):
        ip = f"{NETWORK_PREFIX}{i}"
        t = threading.Thread(target=ping_ip, args=(ip, queue))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    found_ips = []
    while not queue.empty():
        found_ips.append(queue.get())

    found_ips.sort(key=lambda x: int(x.split('.')[-1]))
    
    if found_ips:
        print(f"\n✅ 发现活跃设备 IP: {found_ips}")
        print("请尝试用浏览器或 RTSP 扫描这些 IP。")
    else:
        print("\n❌ 未发现任何设备。")
        print("可能原因：")
        print("1. 摄像头的默认 IP 不是 192.168.1.x (可能是 192.168.0.x)")
        print("2. 建议修改电脑 IP 为 192.168.0.200，然后修改脚本 NETWORK_PREFIX='192.168.0.' 再试一次。")

if __name__ == "__main__":
    scan_network()