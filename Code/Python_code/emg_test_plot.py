import serial
import time
import csv
import matplotlib.pyplot as plt


# ============================================================
# SETTINGS
# ============================================================

PORT = "COM16"          # Change this to your STM32 COM port
BAUD = 115200

# How long to record for
TEST_DURATION_SECONDS = 20

CSV_FILE = "emg_adc_test2.csv"
PLOT_FILE = "emg_adc_plot2.png"


# ============================================================
# CONNECT TO STM32
# ============================================================

print("Connecting to STM32...")

ser = serial.Serial(
    PORT,
    BAUD,
    timeout=0.01
)

time.sleep(2)

# Remove old samples already sitting in the serial buffer
ser.reset_input_buffer()

print(f"Connected to {PORT}")
print(f"Recording for {TEST_DURATION_SECONDS} seconds...")
print("Contract and relax your muscle during the test.\n")


# ============================================================
# STORAGE
# ============================================================

sample_numbers = []
times = []
adc_values = []


# ============================================================
# RECORDING
# ============================================================

start_time = time.time()

sample_number = 0


try:

    while (
        time.time() - start_time
        < TEST_DURATION_SECONDS
    ):

        line = (
            ser.readline()
            .decode(
                "utf-8",
                errors="ignore"
            )
            .strip()
        )

        # STM32 sends one integer per line
        if line.isdigit():

            adc = int(line)

            # Only accept valid 12-bit ADC values
            if 0 <= adc <= 4095:

                current_time = (
                    time.time()
                    - start_time
                )

                sample_numbers.append(
                    sample_number
                )

                times.append(
                    current_time
                )

                adc_values.append(
                    adc
                )

                sample_number += 1


except KeyboardInterrupt:

    print(
        "\nRecording stopped manually."
    )


finally:

    ser.close()


# ============================================================
# CHECK DATA
# ============================================================

if len(adc_values) == 0:

    raise RuntimeError(
        "No ADC data received."
    )


# ============================================================
# SAVE EVERY SAMPLE TO CSV
# ============================================================

with open(
    CSV_FILE,
    "w",
    newline=""
) as file:

    writer = csv.writer(file)

    # Column headings
    writer.writerow(
        [
            "Sample Number",
            "Time (s)",
            "ADC Value"
        ]
    )

    # Write every individual sample
    for sample, t, adc in zip(
        sample_numbers,
        times,
        adc_values
    ):

        writer.writerow(
            [
                sample,
                f"{t:.6f}",
                adc
            ]
        )


# ============================================================
# BASIC RESULTS
# ============================================================

total_time = (
    times[-1]
    - times[0]
)

sample_rate = (
    len(adc_values)
    /
    total_time
)


print("\n====================================")
print("TEST COMPLETE")
print("====================================")

print(
    f"Total samples: "
    f"{len(adc_values)}"
)

print(
    f"Recording time: "
    f"{total_time:.2f} s"
)

print(
    f"Measured sample rate: "
    f"{sample_rate:.1f} samples/s"
)

print(
    f"Minimum ADC: "
    f"{min(adc_values)}"
)

print(
    f"Maximum ADC: "
    f"{max(adc_values)}"
)

print(
    f"Average ADC: "
    f"{sum(adc_values) / len(adc_values):.2f}"
)

print(
    f"\nData saved to: "
    f"{CSV_FILE}"
)


# ============================================================
# PLOT ADC DATA
# ============================================================

plt.figure(
    figsize=(12, 6)
)

plt.plot(
    times,
    adc_values,
    linewidth=0.8
)

plt.xlabel(
    "Time (s)"
)

plt.ylabel(
    "ADC Value"
)

plt.title(
    "Raw EMG ADC Signal"
)

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


# Save graph
plt.savefig(
    PLOT_FILE,
    dpi=300
)

print(
    f"Plot saved to: "
    f"{PLOT_FILE}"
)


# Show graph
plt.show()