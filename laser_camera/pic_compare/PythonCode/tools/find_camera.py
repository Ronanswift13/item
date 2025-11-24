import cv2

def list_cameras(max_check=5):
    print("正在扫描可用摄像头...")
    available = []
    for i in range(max_check):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"发现摄像头 ID: {i} (分辨率: {int(cap.get(3))}x{int(cap.get(4))})")
                available.append(i)
            else:
                print(f"摄像头 ID: {i} 无法读取画面")
            cap.release()
        else:
            print(f"摄像头 ID: {i} 无法打开")
    return available

if __name__ == "__main__":
    list_cameras()