from machine import Pin, PWM, Timer
from time import sleep_ms, sleep, ticks_ms, ticks_diff
import ubluetooth
from neopixel import NeoPixel
import random

print("Systems online. Code is running!")

# --- HARDWARE SETUP ---
motor_fwd = PWM(Pin(16), freq=1000)
motor_rev = PWM(Pin(17), freq=1000)
servo = PWM(Pin(23), freq=50)

LED = Pin(25, Pin.OUT)
NUM_LEDS = 8
ledstrip = NeoPixel(Pin(4), NUM_LEDS)

# BUZZER SETUP
buzzer = PWM(Pin(13), freq=440, duty=0)

# Note frequencies (Hz)
NOTES = {
    'C4': 262, 'D4': 294, 'E4': 330, 'F4': 349, 'G4': 392, 'A4': 440, 'B4': 494,
    'C5': 523, 'D5': 587, 'E5': 659, 'F5': 698, 'G5': 784, 'A5': 880, 'B5': 988,
    'C6': 1047,
    'Gs4': 415, 'As4': 466, 'Cs5': 554, 'Ds5': 622, 'Fs5': 740, 'Gs5': 831,
    'REST': 0,
}

# --- MELODIES ---
mario_theme = [
    ('E5', 0.12), ('E5', 0.12), ('REST', 0.12), ('E5', 0.12),
    ('REST', 0.12), ('C5', 0.12), ('E5', 0.12),
    ('G5', 0.12), ('REST', 0.36), ('G4', 0.12), ('REST', 0.36),
    ('C5', 0.18), ('REST', 0.12), ('G4', 0.18), ('REST', 0.12),
    ('E4', 0.18), ('REST', 0.12), ('A4', 0.15), ('B4', 0.15),
    ('As4', 0.10), ('A4', 0.18), ('G4', 0.12), ('E5', 0.12),
    ('G5', 0.12), ('A5', 0.18), ('F5', 0.10), ('G5', 0.12),
    ('REST', 0.12), ('E5', 0.15), ('C5', 0.10), ('D5', 0.10),
    ('B4', 0.18), ('REST', 0.18)
]


champions_theme = [
    # Intro: "Daah, Daaaaaaah"
    ('A4', 0.4), ('E4', 0.8), ('REST', 0.1),

    # "Da, da-da-da-da DAAAAAA"
    ('A4', 0.2), ('A4', 0.1), ('B4', 0.1), ('Cs5', 0.1), ('D5', 0.1), ('E5', 0.8), ('REST', 0.1),

    # "Da, da-da-da-da DAAAAAA" (steps up higher)
    ('E5', 0.2), ('E5', 0.1), ('F5', 0.1), ('G5', 0.1), ('A5', 0.1), ('B5', 0.8), ('REST', 0.1),

    # The iconic descending run
    ('B5', 0.15), ('B5', 0.15), ('A5', 0.15), ('G5', 0.15), ('A5', 0.3), ('G5', 0.15), ('F5', 0.8), ('REST', 0.1),

    # The final steps down
    ('E5', 0.15), ('D5', 0.15), ('D5', 0.1), ('E5', 0.1), ('F5', 0.5), ('REST', 0.1),
    ('E5', 0.15), ('C5', 0.15), ('C5', 0.1), ('D5', 0.1), ('E5', 0.5), ('REST', 0.1),
    ('D5', 0.15), ('B4', 0.15), ('B4', 0.1), ('C5', 0.1), ('D5', 0.5), ('REST', 0.1),

    # Resolution!
    ('C5', 0.3), ('A4', 0.8)
]

# --- MANUAL TESTING FUNCTIONS ---
def move_forwards():
    motor_fwd.duty(1023)
    motor_rev.duty(0)

def move_backwards():
    motor_fwd.duty(0)
    motor_rev.duty(1023)

def stop():
    motor_fwd.duty(0)
    motor_rev.duty(0)

def turn_left():
    servo.duty(90)

def turn_right():
    servo.duty(60)

def turn_centre():
    servo.duty(75)

# --- GLOBAL STATE TRACKERS ---
drive_state = "S"
steer_state = "C"
win_state = ""
ble_status = 0


class BLE:
    def __init__(self, name):
        self.name = name
        self.ble = ubluetooth.BLE()
        self.ble.active(True)
        self.ble.config(gap_name=name)

        self.led = Pin(25, Pin.OUT)
        self.timer1 = Timer(0)
        self.timer2 = Timer(1)
        self.connections = set()
        self.ble.irq(self.ble_irq)

        self.register()
        self.advertiser()
        self.disconnected()

    def connected(self):
        global ble_status
        self.timer1.deinit()
        self.timer2.deinit()
        ble_status = 1

    def disconnected(self):
        global ble_status, drive_state, steer_state, win_state
        ble_status = 0
        drive_state = "S"
        steer_state = "C"
        win_state = ""

        motor_fwd.duty(0)
        motor_rev.duty(0)
        servo.duty(75)
        buzzer.duty(0) # Silence buzzer on disconnect

        self.timer1.init(period=1000, mode=Timer.PERIODIC, callback=lambda t: self.led.value(1))
        sleep_ms(100)
        self.timer2.init(period=1000, mode=Timer.PERIODIC, callback=lambda t: self.led.value(0))

    def ble_irq(self, event, data):
        global drive_state, steer_state, win_state

        if event == 1:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)
            self.connected()
            self.led.value(1)

        elif event == 2:
            conn_handle, _, _ = data
            self.connections.discard(conn_handle)
            self.disconnected()
            self.advertiser()

        elif event == 3:
            conn_handle, value_handle = data
            message = self.ble.gatts_read(self.rx).decode().strip()

            if message == "led":
                self.led.value(not self.led.value())
                self.send("led" + str(self.led.value()))
            else:
                if "W" in message:
                    win_state = "W"
                else:
                    win_state = ""

                if "F" in message:
                    motor_fwd.duty(1023)
                    motor_rev.duty(0)
                    drive_state = "F"
                elif "B" in message:
                    motor_fwd.duty(0)
                    motor_rev.duty(1023)
                    drive_state = "B"
                else:
                    motor_fwd.duty(0)
                    motor_rev.duty(0)
                    drive_state = "S"

                if "L" in message:
                    servo.duty(90)
                    steer_state = "L"
                elif "R" in message:
                    servo.duty(60)
                    steer_state = "R"
                else:
                    servo.duty(75)
                    steer_state = "C"


    def register(self):
        NUS_UUID = ubluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        RX_UUID  = ubluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
        TX_UUID  = ubluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

        BLE_UART = (NUS_UUID, ((TX_UUID, ubluetooth.FLAG_NOTIFY), (RX_UUID, ubluetooth.FLAG_WRITE)))
        ((self.tx, self.rx),) = self.ble.gatts_register_services((BLE_UART,))
        self.ble.gatts_set_buffer(self.rx, 100, True)

    def send(self, data):
        if isinstance(data, str):
            data = (data + "\n").encode()
        for conn_handle in self.connections:
            self.ble.gatts_notify(conn_handle, self.tx, data)

    def advertiser(self):
        name = self.name.encode()
        payload = bytearray(b"\x02\x01\x06")
        payload += bytearray((len(name) + 1, 0x09))
        payload += name
        self.ble.gap_advertise(500000, payload)


# --- STARTUP ---
ble = BLE("HANSEL LOOK AT THIS")

# Animation Trackers
last_update = ticks_ms()
anim_frame = 0
conn_flash_count = 0

# Audio Trackers
current_song = None
song_index = 0
buzzer_last_update = ticks_ms()
buzzer_wait_time = 0
buzzer_phase = "GAP" # "PLAYING" or "GAP"

running = True
while running:
    current_time = ticks_ms()

    # ==========================================
    # 1. THE NON-BLOCKING AUDIO ENGINE
    # ==========================================
    target_song = None
    if win_state == "W":
        target_song = champions_theme
    elif drive_state == "F":
        target_song = mario_theme

    if target_song != current_song:
        current_song = target_song
        song_index = 0
        buzzer_phase = "GAP"
        buzzer_wait_time = 0
        buzzer.duty(0)

    if current_song is not None:
        if ticks_diff(current_time, buzzer_last_update) >= buzzer_wait_time:
            if buzzer_phase == "GAP":
                if song_index >= len(current_song):
                    song_index = 0

                note, dur = current_song[song_index]
                buzzer_wait_time = int(dur * 1000)

                if note == 'REST' or NOTES[note] == 0:
                    buzzer.duty(0)
                else:
                    buzzer.freq(NOTES[note])
                    buzzer.duty(512)

                buzzer_phase = "PLAYING"
                buzzer_last_update = current_time

            elif buzzer_phase == "PLAYING":
                buzzer.duty(0)
                buzzer_wait_time = 30
                buzzer_phase = "GAP"
                song_index += 1
                buzzer_last_update = current_time

    # ==========================================
    # 2. THE NON-BLOCKING ANIMATION ENGINE
    # ==========================================
    if ticks_diff(current_time, last_update) >= 150:
        last_update = current_time

        if ble_status == 0:
            anim_frame = (anim_frame + 1) % 2
            color = (0, 0, 25) if anim_frame == 0 else (0, 0, 0)
            for i in range(NUM_LEDS): ledstrip[i] = color
            ledstrip.write()

        elif ble_status == 1:
            conn_flash_count += 1
            color = (0, 25, 0) if conn_flash_count % 2 != 0 else (0, 0, 0)
            for i in range(NUM_LEDS): ledstrip[i] = color
            ledstrip.write()

            if conn_flash_count >= 6:
                ble_status = 2
                conn_flash_count = 0

        elif ble_status == 2:
            if win_state == "W":
                for i in range(NUM_LEDS):
                    colour = random.randint(1, 4)
                    if colour == 1:
                        ledstrip[i] = (random.randint(100,200), random.randint(0,75), random.randint(0,75))
                    elif colour == 2:
                        ledstrip[i] = (random.randint(0,75), random.randint(100,200), random.randint(0,75))
                    elif colour == 3:
                        ledstrip[i] = (random.randint(0,75), random.randint(0,75), random.randint(100,200))
                    elif colour == 4:
                        ledstrip[i] = (0, 0, 0) # Added safety fallback to prevent errors
            else:
                if drive_state == "B":
                    for i in range(NUM_LEDS): ledstrip[i] = (25, 0, 0)
                else:
                    for i in range(NUM_LEDS): ledstrip[i] = (0, 0, 0)

                if steer_state == "L":
                    anim_frame = (anim_frame + 1) % 5
                    if anim_frame < 4:
                        for j in range(anim_frame + 1): ledstrip[3 - j] = (25, 25, 0)
                elif steer_state == "R":
                    anim_frame = (anim_frame + 1) % 5
                    if anim_frame < 4:
                        for j in range(anim_frame + 1): ledstrip[4 + j] = (25, 25, 0)

            ledstrip.write()

    sleep_ms(10)
