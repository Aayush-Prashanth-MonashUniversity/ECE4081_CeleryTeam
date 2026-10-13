# ==============================================================
# REAL-TIME EMG REHABILITATION MONITOR
#
# Current project scope:
#
#   raw ADC
#      ↓
#   resting baseline removal
#      ↓
#   moving RMS
#      ↓
#   %MVC
#      ↓
#   display smoothing
#      ↓
#   real-time biofeedback
#
# The present prototype uses a lower-rail-clipped EMG signal.
# Therefore %MVC is interpreted as a relative within-session
# activation metric.
# ==============================================================


import serial
import pygame
import numpy as np
import json
import time

from collections import deque


# ==============================================================
# 1. SETTINGS
# ==============================================================

SERIAL_PORT = "COM16"

BAUD_RATE = 115200


WIDTH = 1050
HEIGHT = 600


# How quickly RMS reacts.
RMS_WINDOW_SECONDS = 0.25


# EMA controls how smooth the displayed %MVC is.
#
# Higher = faster response but more movement.
# Lower = smoother but slower.
EMA_ALPHA = 0.20


# Optional biofeedback target
TARGET_LOW = 40.0
TARGET_HIGH = 60.0


# ==============================================================
# 2. LOAD CALIBRATION
# ==============================================================

with open(
    "mvc_calibration.json",
    "r"
) as file:

    calibration = json.load(file)


MUSCLE_NAME = calibration[
    "muscle"
]

BASELINE_ADC = calibration[
    "baseline_adc"
]

MVC_RMS = calibration[
    "mvc_rms_adc"
]

SAMPLE_RATE_HZ = calibration[
    "sample_rate_hz"
]


RMS_WINDOW_SAMPLES = int(
    RMS_WINDOW_SECONDS
    * SAMPLE_RATE_HZ
)


print(
    f"\nMuscle: {MUSCLE_NAME}"
)

print(
    f"Rest baseline: "
    f"{BASELINE_ADC:.2f} ADC"
)

print(
    f"MVC reference: "
    f"{MVC_RMS:.2f} ADC RMS"
)


# ==============================================================
# 3. SERIAL
# ==============================================================

ser = serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=0.001
)

time.sleep(2)

ser.reset_input_buffer()

print(
    f"Connected to STM32 "
    f"on {SERIAL_PORT}"
)


# ==============================================================
# 4. PYGAME
# ==============================================================

pygame.init()

screen = pygame.display.set_mode(
    (WIDTH, HEIGHT)
)

pygame.display.set_caption(
    "EMG Rehabilitation Monitor"
)


font_small = pygame.font.SysFont(
    "Consolas",
    16
)

font_medium = pygame.font.SysFont(
    "Consolas",
    22,
    bold=True
)

font_large = pygame.font.SysFont(
    "Consolas",
    48,
    bold=True
)


clock = pygame.time.Clock()


# ==============================================================
# 5. COLOURS
# ==============================================================

BG = (18, 22, 30)

PANEL = (26, 32, 44)

GRID = (45, 55, 72)

GREEN = (0, 210, 130)

RED = (255, 90, 90)

BLUE = (66, 153, 225)

TEXT = (230, 230, 230)

MUTED = (145, 155, 170)


# ==============================================================
# 6. BUFFERS
# ==============================================================

rms_buffer = deque(
    maxlen=RMS_WINDOW_SAMPLES
)


PLOT_WIDTH = WIDTH - 350


plot_buffer = deque(
    [HEIGHT - 40] * PLOT_WIDTH,
    maxlen=PLOT_WIDTH
)


# ==============================================================
# 7. VARIABLES
# ==============================================================

current_rms = 0.0

raw_percent_mvc = 0.0

displayed_percent_mvc = 0.0


# ==============================================================
# 8. READ ADC
# ==============================================================

def read_adc():

    try:

        line = (
            ser.readline()
            .decode(
                "utf-8",
                errors="ignore"
            )
            .strip()
        )

        if line.isdigit():

            value = int(line)

            if 0 <= value <= 4095:
                return value

    except (
        ValueError,
        UnicodeDecodeError
    ):
        pass

    return None


# ==============================================================
# 9. RMS
# ==============================================================

def calculate_rms(signal):

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
# 10. MAIN LOOP
# ==============================================================

running = True


while running:

    # ----------------------------------------------------------
    # PYGAME EVENTS
    # ----------------------------------------------------------

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False


    # ----------------------------------------------------------
    # READ AVAILABLE ADC VALUES
    # ----------------------------------------------------------

    while ser.in_waiting > 0:

        raw_adc = read_adc()

        if raw_adc is None:
            continue


        # ------------------------------------------------------
        # BASELINE CORRECTION
        # ------------------------------------------------------
        #
        # Example:
        #
        # ADC = 600
        # baseline = 3
        #
        # corrected = 597
        #
        # Any value below baseline is clamped to zero because
        # the current hardware signal is already lower-rail
        # clipped.

        corrected = max(
            0.0,
            raw_adc - BASELINE_ADC
        )


        # Add signal to RMS window
        rms_buffer.append(
            corrected
        )


        # ------------------------------------------------------
        # RAW SIGNAL PLOT
        # ------------------------------------------------------
        #
        # Because our present ADC signal is non-negative, the
        # graph starts near the bottom and rises with activation.

        plot_scale = 0.15

        plot_y = int(
            HEIGHT - 40
            -
            corrected * plot_scale
        )


        plot_y = max(
            20,
            min(
                HEIGHT - 40,
                plot_y
            )
        )


        plot_buffer.append(
            plot_y
        )


    # ==========================================================
    # 11. MOVING RMS
    # ==========================================================

    if (
        len(rms_buffer)
        ==
        RMS_WINDOW_SAMPLES
    ):

        current_rms = calculate_rms(
            rms_buffer
        )


        # ------------------------------------------------------
        # % MVC
        # ------------------------------------------------------

        if MVC_RMS > 0:

            raw_percent_mvc = (
                current_rms
                /
                MVC_RMS
            ) * 100.0

        else:

            raw_percent_mvc = 0.0


        raw_percent_mvc = max(
            0.0,
            raw_percent_mvc
        )


        # ------------------------------------------------------
        # EMA DISPLAY SMOOTHING
        # ------------------------------------------------------

        displayed_percent_mvc = (

            EMA_ALPHA
            * raw_percent_mvc

            +

            (1.0 - EMA_ALPHA)
            * displayed_percent_mvc
        )


    # ==========================================================
    # 12. BIOFEEDBACK STATUS
    # ==========================================================

    if (
        displayed_percent_mvc
        < TARGET_LOW
    ):

        target_status = (
            "INCREASE EFFORT"
        )

        target_color = TEXT


    elif (
        displayed_percent_mvc
        <= TARGET_HIGH
    ):

        target_status = (
            "IN TARGET RANGE"
        )

        target_color = GREEN


    else:

        target_status = (
            "REDUCE EFFORT"
        )

        target_color = RED


    # ==========================================================
    # 13. DRAW
    # ==========================================================

    screen.fill(
        BG
    )


    # ----------------------------------------------------------
    # RAW ADC / EMG WAVEFORM
    # ----------------------------------------------------------

    points = [

        (x, y)

        for x, y
        in enumerate(
            plot_buffer
        )

    ]


    if len(points) > 1:

        pygame.draw.lines(
            screen,
            GREEN,
            False,
            points,
            2
        )


    # ----------------------------------------------------------
    # RIGHT PANEL
    # ----------------------------------------------------------

    panel_x = PLOT_WIDTH


    pygame.draw.rect(
        screen,
        PANEL,
        (
            panel_x,
            0,
            350,
            HEIGHT
        )
    )


    # Muscle
    screen.blit(

        font_medium.render(
            MUSCLE_NAME,
            True,
            BLUE
        ),

        (
            panel_x + 20,
            20
        )
    )


    # ----------------------------------------------------------
    # %MVC
    # ----------------------------------------------------------

    screen.blit(

        font_small.render(
            "MUSCLE ACTIVATION",
            True,
            MUTED
        ),

        (
            panel_x + 20,
            80
        )
    )


    activation_text = (
        f"{displayed_percent_mvc:.1f}% MVC"
    )


    screen.blit(

        font_large.render(
            activation_text,
            True,
            TEXT
        ),

        (
            panel_x + 20,
            105
        )
    )


    # ----------------------------------------------------------
    # ACTIVATION BAR
    # ----------------------------------------------------------

    bar_x = panel_x + 20

    bar_y = 180

    bar_width = 300

    bar_height = 22


    pygame.draw.rect(
        screen,
        GRID,
        (
            bar_x,
            bar_y,
            bar_width,
            bar_height
        ),
        border_radius=5
    )


    displayed_bar_percent = min(
        100.0,
        displayed_percent_mvc
    )


    fill_width = int(

        (
            displayed_bar_percent
            / 100.0
        )

        * bar_width
    )


    if fill_width > 0:

        pygame.draw.rect(
            screen,
            BLUE,
            (
                bar_x,
                bar_y,
                fill_width,
                bar_height
            ),
            border_radius=5
        )


    # ----------------------------------------------------------
    # RMS
    # ----------------------------------------------------------

    screen.blit(

        font_small.render(
            (
                f"RMS EMG: "
                f"{current_rms:.1f} ADC RMS"
            ),
            True,
            TEXT
        ),

        (
            panel_x + 20,
            240
        )
    )


    # ----------------------------------------------------------
    # UNSMOOTHED %MVC
    # ----------------------------------------------------------

    screen.blit(

        font_small.render(
            (
                f"Raw %MVC: "
                f"{raw_percent_mvc:.1f}%"
            ),
            True,
            MUTED
        ),

        (
            panel_x + 20,
            270
        )
    )


    # ----------------------------------------------------------
    # TARGET RANGE
    # ----------------------------------------------------------

    screen.blit(

        font_small.render(
            (
                f"Target: "
                f"{TARGET_LOW:.0f}-"
                f"{TARGET_HIGH:.0f}% MVC"
            ),
            True,
            MUTED
        ),

        (
            panel_x + 20,
            330
        )
    )


    screen.blit(

        font_medium.render(
            target_status,
            True,
            target_color
        ),

        (
            panel_x + 20,
            365
        )
    )


    # ----------------------------------------------------------
    # HARDWARE NOTE
    # ----------------------------------------------------------

    screen.blit(

        font_small.render(
            "Relative within-session metric",
            True,
            MUTED
        ),

        (
            panel_x + 20,
            500
        )
    )


    screen.blit(

        font_small.render(
            "Prototype - not diagnostic",
            True,
            MUTED
        ),

        (
            panel_x + 20,
            530
        )
    )


    pygame.display.flip()


    # Only UI refresh rate.
    # STM32 still samples at ~1000 Hz.
    clock.tick(
        60
    )


# ==============================================================
# CLEANUP
# ==============================================================

if ser.is_open:
    ser.close()

pygame.quit()