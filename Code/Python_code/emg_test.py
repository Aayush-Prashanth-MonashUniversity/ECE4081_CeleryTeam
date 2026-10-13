import serial
import time

PORT = "COM16"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=0.01)

samples = []
start = time.time()

while True:

    line = ser.readline().decode(
        "utf-8",
        errors="ignore"
    ).strip()

    if line.isdigit():
        samples.append(int(line))

    if time.time() - start >= 1.0:

        if samples:

            ##print(
               # f"Samples: {len(samples)} | "
                #f"Min: {min(samples)} | "
               # f"Max: {max(samples)} | "
               # f"Average: {sum(samples)/len(samples):.1f}"
           # )
           print(samples)

        samples = []
        start = time.time()