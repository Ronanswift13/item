#cd ~/Desktop/item/laser_camera/pic_compare/PythonCode

#usr/bin/python3 - << 'EOF'
import cv2

# TODO:
url = "rtsp://admin:admin123@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0"

print("Try open:", url)
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Open failed!")
    exit(1)

print("Open OK, start showing frames. Press 'q' to quit.")

while True:
    ok, frame = cap.read()
    if not ok:
        print("Read frame failed.")
        break

    cv2.imshow("rtsp_test", frame)
    # 1ms 轮询键盘，按 q 退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
