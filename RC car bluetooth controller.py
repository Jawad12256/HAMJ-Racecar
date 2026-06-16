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
                # 1. Win State Tracking (Requires the 'else' so it stops when you let go)
                if "W" in message:
                    win_state = "W"
                else:
                    win_state = ""

                # 2. Throttle Control
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

                # 3. Steering Control
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

last_update = ticks_ms()
anim_frame = 0
conn_flash_count = 0

running = True
while running:
    current_time = ticks_ms()

    # Tick the animation forward every 150 milliseconds
    if ticks_diff(current_time, last_update) >= 150:
        last_update = current_time

        # SCENARIO A: Disconnected (Pulse Blue)
        if ble_status == 0:
            anim_frame = (anim_frame + 1) % 2
            color = (0, 0, 25) if anim_frame == 0 else (0, 0, 0)
            for i in range(NUM_LEDS):
                ledstrip[i] = color
            ledstrip.write()

        # SCENARIO B: Just Connected (Flash Green 3 Times)
        elif ble_status == 1:
            conn_flash_count += 1
            color = (0, 25, 0) if conn_flash_count % 2 != 0 else (0, 0, 0)
            for i in range(NUM_LEDS):
                ledstrip[i] = color
            ledstrip.write()

            if conn_flash_count >= 6:
                ble_status = 2
                conn_flash_count = 0

        # SCENARIO C: Normal Driving Operations
        elif ble_status == 2:

            # --- THE WINNING OVERRIDE ---
            if win_state == "W":
                # Instantly generates a new random color frame every 150ms!
                for i in range(NUM_LEDS):
                    colour = random.randint(1,4)
                    if colour == 1: # RED
                        ledstrip[i] = (random.randint(100,200),random.randint(0,75),random.randint(0,75))
                    elif colour == 2: # GREEN
                        ledstrip[i] = (random.randint(0,75),random.randint(100,200),random.randint(0,75))
                    elif colour == 3: # BLUE
                        ledstrip[i] = (random.randint(0,75),random.randint(0,75),random.randint(100,200))


            # --- NORMAL DRIVING LIGHTS ---
            else:
                # Layer 1: Throttle Base Lights
                if drive_state == "B":
                    for i in range(NUM_LEDS): ledstrip[i] = (25, 0, 0)
                else:
                    for i in range(NUM_LEDS): ledstrip[i] = (0, 0, 0)

                # Layer 2: Animated Turn Signals
                if steer_state == "L":
                    anim_frame = (anim_frame + 1) % 5
                    if anim_frame < 4:
                        for j in range(anim_frame + 1):
                            ledstrip[3 - j] = (25, 25, 0)

                elif steer_state == "R":
                    anim_frame = (anim_frame + 1) % 5
                    if anim_frame < 4:
                        for j in range(anim_frame + 1):
                            ledstrip[4 + j] = (25, 25, 0)

            # Write whatever colors were chosen to the strip
            ledstrip.write()

    sleep_ms(10)
