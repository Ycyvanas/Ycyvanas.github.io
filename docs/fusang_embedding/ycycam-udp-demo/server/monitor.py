import serial
import time

ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=2)
time.sleep(2)
start = time.time()
while time.time() - start < 15:
    try:
        line = ser.readline().decode('utf-8', errors='ignore')
        print(line.rstrip())
    except:
        break
ser.close()
