# ==============================================================
# MVC CALIBRATION
#
# For the current hardware:
# - EMG is clipped at the STM32 lower ADC rail.
# - We therefore treat the received signal as a non-negative
#   amplitude signal.
#
# Processing:
# ADC -> subtract resting baseline -> clamp >= 0
#     -> moving RMS -> MVC reference
# ==============================================================

import serial
import time
import json
import numpy as np


# ==============================================================
# 1. SETTINGS
# ==============================================================

SERIAL_PORT = "COM16"      
BAUD_RATE = 115200

SAMPLE_RATE_HZ = 1000

REST_BASELINE_SECONDS = 3.0

MVC_TRIALS = 3
MVC_DURATION_SECONDS = 3.0

MVC_STABLE_START_SECONDS = 0.5
MVC_STABLE_END_SECONDS = 2.5

# Longer rest is preferable after a true MVC.
MVC_REST_SECONDS = 30

# RMS window
RMS_WINDOW_SECONDS = 0.25

RMS_WINDOW_SAMPLES = int(
    SAMPLE_RATE_HZ * RMS_WINDOW_SECONDS
)


# ==============================================================
# 2. MUSCLE OPTIONS
# ==============================================================

MUSCLE_PROFILES = {

    "1": {
        "name": "Biceps",
        "instruction":
            "Keep the elbow near 90 degrees and flex maximally "
            "against an immovable resistance."
    },

    "2": {
        "name": "Triceps",
        "instruction":
            "Keep the elbow fixed and extend maximally "
            "against an immovable resistance."
    },

    "3": {
        "name": "Deltoid",
        "instruction":
            "Attempt maximum shoulder abduction against "
            "an immovable resistance."
    },

    "4": {
        "name": "Quadriceps",
        "instruction":
            "Keep the knee fixed and attempt maximum "
            "knee extension."
    },

    "5": {
        "name": "Hamstrings",
        "instruction":
            "Keep the knee fixed and attempt maximum "
            "knee flexion."
    }
}


# ==============================================================
# 3. CONNECT TO STM32
# ==============================================================

print("Connecting to STM32...")

ser = serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=0.02
)

time.sleep(2)

ser.reset_input_buffer()

print(f"Connected on {SERIAL_PORT}")


# ==============================================================
# 4. READ ONE ADC SAMPLE
# ==============================================================

def read_adc():

    try:

        line = (
            ser.readline()
            .decode("utf-8", errors="ignore")
            .strip()
        )

        if line.isdigit():

            value = int(line)

            # STM32 12-bit ADC safety check
            if 0 <= value <= 4095:
                return value

    except (ValueError, UnicodeDecodeError):
        pass

    return None


# ==============================================================
# 5. COLLECT SAMPLES
# ==============================================================

def collect_samples(duration):

    samples = []

    start = time.time()

    while time.time() - start < duration:

        value = read_adc()

        if value is not None:
            samples.append(value)

    return np.asarray(
        samples,
        dtype=float
    )


# ==============================================================
# 6. CORRECT SIGNAL
# ==============================================================

def correct_signal(samples, baseline):
    """
    Remove resting ADC offset.

    Because the current analogue signal is already clipped at
    the STM32 lower rail, negative corrected values are set to 0.

    Example:

        raw ADC = 5
        baseline = 3

        corrected = 2

        raw ADC = 1
        baseline = 3

        corrected would be -2,
        but we store 0 instead.
    """

    corrected = (
        np.asarray(samples, dtype=float)
        - baseline
    )

    corrected = np.maximum(
        corrected,
        0
    )

    return corrected


# ==============================================================
# 7. RMS
# ==============================================================

def calculate_rms(signal):
    """
    Calculate the RMS amplitude of a signal.

    RMS = sqrt(mean(x^2))
    """

    signal = np.asarray(
        signal,
        dtype=float
    )

    if len(signal) == 0:
        return 0.0

    return float(
        np.sqrt(
            np.mean(
                signal ** 2
            )
        )
    )


# ==============================================================
# 8. SELECT MUSCLE
# ==============================================================

print("\nSELECT TARGET MUSCLE")

for key, profile in MUSCLE_PROFILES.items():
    print(f"{key}. {profile['name']}")

choice = input(
    "\nSelect muscle: "
).strip()

if choice not in MUSCLE_PROFILES:

    ser.close()
    raise SystemExit("Invalid muscle selection.")


muscle = MUSCLE_PROFILES[choice]

print(
    f"\nSelected: {muscle['name']}"
)

print(
    muscle["instruction"]
)


# ==============================================================
# 9. RESTING BASELINE
# ==============================================================

print("\nRESTING BASELINE")

print(
    "Relax the target muscle completely."
)

input(
    "Press ENTER when ready..."
)

ser.reset_input_buffer()

print(
    f"Recording for "
    f"{REST_BASELINE_SECONDS:.1f} s..."
)

rest_samples = collect_samples(
    REST_BASELINE_SECONDS
)

if len(rest_samples) == 0:

    ser.close()

    raise RuntimeError(
        "No ADC samples received."
    )


baseline_adc = float(
    np.mean(rest_samples)
)

rest_rms = float(
    np.sqrt(
        np.mean(
            np.maximum(
                rest_samples - baseline_adc,
                0
            ) ** 2
        )
    )
)


print(
    f"\nBaseline ADC = "
    f"{baseline_adc:.2f}"
)

print(
    f"Rest RMS = "
    f"{rest_rms:.2f} ADC RMS"
)


# ==============================================================
# 10. MVC TRIALS
# ==============================================================

mvc_results = []


for trial in range(
    1,
    MVC_TRIALS + 1
):

    print(
        f"\n=============================="
    )

    print(
        f"MVC TRIAL {trial}/{MVC_TRIALS}"
    )

    print(
        muscle["instruction"]
    )

    input(
        "\nPress ENTER when ready..."
    )

    print("3")
    time.sleep(1)

    print("2")
    time.sleep(1)

    print("1")
    time.sleep(1)

    print("CONTRACT NOW!")

    ser.reset_input_buffer()

    raw_samples = collect_samples(
        MVC_DURATION_SECONDS
    )

    if len(raw_samples) == 0:

        print(
            "No data received."
        )

        continue


    # ----------------------------------------------------------
    # Remove resting baseline
    # ----------------------------------------------------------

    corrected = correct_signal(
        raw_samples,
        baseline_adc
    )


    # ----------------------------------------------------------
    # Select stable portion of MVC
    # ----------------------------------------------------------

    stable_start_sample = int(
    MVC_STABLE_START_SECONDS
    * SAMPLE_RATE_HZ
    )

    stable_end_sample = int(
    MVC_STABLE_END_SECONDS
    * SAMPLE_RATE_HZ
    )


    # Make sure enough samples were actually received
    if len(corrected) < stable_end_sample:

        print(
        "Not enough samples received "
        "for stable MVC calculation."
        )

        continue


    stable_signal = corrected[
        stable_start_sample:
        stable_end_sample
    ]


    # ----------------------------------------------------------
    # RMS of stable MVC period
    # ----------------------------------------------------------
    #
   

    trial_mvc = calculate_rms(
    stable_signal
)   


    mvc_results.append(
        trial_mvc
    )


    print(
        f"\nStable MVC RMS = "
        f"{trial_mvc:.2f} ADC RMS"
    )   


    if trial < MVC_TRIALS:

        print(
            f"\nRest for "
            f"{MVC_REST_SECONDS} seconds..."
        )

        time.sleep(
            MVC_REST_SECONDS
        )

        print(
            "\nRest complete."
        )


# ==============================================================
# 11. FINAL MVC REFERENCE
# ==============================================================

if len(mvc_results) == 0:

    ser.close()

    raise RuntimeError(
        "No successful MVC measurements."
    )


print(
    "\n=============================="
)

print(
    "MVC RESULTS"
)

for i, result in enumerate(
    mvc_results,
    start=1
):

    print(
        f"Trial {i}: "
        f"{result:.2f} ADC RMS"
    )

# The final MVC reference is the mean RMS amplitude
# of the three valid MVC trials.
#
# Averaging repeated trials reduces trial-to-trial
# variability while each trial is calculated only from
# the stable middle portion of the contraction.

mvc_reference = float(
    np.mean(
        mvc_results
    )
)


print(
    f"\n100% MVC reference = "
    f"{mvc_reference:.2f} ADC RMS"
)


# ==============================================================
# 12. SAVE CALIBRATION
# ==============================================================

calibration = {

    "muscle":
        muscle["name"],

    "baseline_adc":
        baseline_adc,

    "rest_rms_adc":
        rest_rms,

    "mvc_rms_adc":
        mvc_reference,

    "sample_rate_hz":
        SAMPLE_RATE_HZ,

    "rms_window_seconds":
        RMS_WINDOW_SECONDS,

    "mvc_trials":
        mvc_results,

    "signal_note":
        "ADC signal is lower-rail clipped; "
        "MVC is a relative within-session metric."
}


with open(
    "mvc_calibration.json",
    "w"
) as file:

    json.dump(
        calibration,
        file,
        indent=4
    )


print(
    "\nCalibration saved to "
    "mvc_calibration.json"
)


ser.close()