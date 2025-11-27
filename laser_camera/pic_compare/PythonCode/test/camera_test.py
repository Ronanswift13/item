import cv2

cap = cv2.VideoCapture(0)  # 如果你现在用的是 USB 摄像头

if not cap.isOpened():
    print("Failed to open camera")
    raise SystemExit

while True:
    ok, frame = cap.read()
    if not ok:
        print("Failed to read frame")
        break

    # 可选：降低分辨率，看是否更流畅
    # frame = cv2.resize(frame, (960, 540))

    cv2.imshow("camera_test", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()