from periphery import GPIO
import time

Write_Pin = 54

Write_GPIO = GPIO(Write_Pin, "out")

try:
    while True:
        try:
            Write_GPIO.write(True)
            time.sleep(1)
            Write_GPIO.write(False)
            time.sleep(1)

        except KeyboardInterrupt:
            break

except IOError:
    print("Error")

finally:
    Write_GPIO.close()
