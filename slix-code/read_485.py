import serial


ser = serial.Serial(
    port='/dev/ttyS2',   
    baudrate=4800,      
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1      
)

print("Starting RS485 read loop...")

try:
    while True:
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)  
            print(f"Received raw bytes: {data}")
            print("Hex:", data.hex())
except KeyboardInterrupt:
    print("Stopping RS485 read loop.")
finally:
    ser.close()
