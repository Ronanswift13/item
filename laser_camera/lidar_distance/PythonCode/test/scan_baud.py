import time
import serial

PORT = "/dev/tty.usbserial-1120"   # 你现在这个端口
BAUDS = [9600, 19200, 38400, 57600, 115200]

def try_baud(baud):
    print(f"\n=== Try baud {baud} on {PORT} ===")
    try:
        ser = serial.Serial(PORT, baud, timeout=0.5)
    except Exception as e:
        print(f"  [ERROR] open failed: {e}")
        return

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    got_data = False
    start = time.time()
    while time.time() - start < 3.0:  # 每个波特率试 3 秒
        data = ser.read(64)
        if data:
            print(f"  [DATA] {len(data)} bytes:", data)
            got_data = True
            # 多打印几次看看
        else:
            print("  [TIMEOUT] no data")
        time.sleep(0.2)

    ser.close()
    if not got_data:
        print(f"  >>> No data at {baud} bps")
    else:
        print(f"  >>> GOT DATA at {baud} bps !!!")

def main():
    print(f"Start scanning {PORT} ... (Ctrl+C to stop)")
    for b in BAUDS:
        try_baud(b)

if __name__ == "__main__":
    main()