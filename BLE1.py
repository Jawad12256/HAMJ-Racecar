##############################################################################
#
# This code allows you to easily control your ESP32 from the Bluefruit LE
# Connect app!
#
# You can find the download links for Apple or Google App stores here: 
# https://learn.adafruit.com/bluefruit-le-connect/ios-setup  
#
# Tested with uPy version 1.18 
#
# Ensure that you change the name of your ESP32 below in line 102 from 'David's
# ESP32' to something else!  
# 
# Once you open the app, connect to your device. The code below allows you to
# send the message 'led' to the ESP32, which will toggle the on-board LED and
# reply to the app with current state.
#
# Experiment with the Controller in the app to understand the message formats
# sent (keep an eye on REPL in Mu and think about how to use these as
# control inputs!
# 
# Read the ubluetooth docs here: 
# https://docs.micropython.org/en/v1.15/library/ubluetooth.html 
#
# DBoyle 08/06/2023
#
#############################################################################

from machine import Pin, Timer
from time import sleep_ms
import ubluetooth


class BLE:
    def __init__(self, name):
        self.name = name
        self.ble = ubluetooth.BLE()
        self.ble.active(True)

        # onboard LED (change pin if needed)
        self.led = Pin(25, Pin.OUT)

        self.timer1 = Timer(0)
        self.timer2 = Timer(1)

        # track connections (IMPORTANT for newer MicroPython)
        self.connections = set()

        self.ble.irq(self.ble_irq)

        self.register()
        self.advertiser()
        self.disconnected()

    # ------------------------
    # Connection state helpers
    # ------------------------
    def connected(self):
        self.timer1.deinit()
        self.timer2.deinit()

    def disconnected(self):
        self.timer1.init(
            period=1000,
            mode=Timer.PERIODIC,
            callback=lambda t: self.led.value(1)
        )
        sleep_ms(100)
        self.timer2.init(
            period=1000,
            mode=Timer.PERIODIC,
            callback=lambda t: self.led.value(0)
        )

    # ------------------------
    # IRQ handler
    # ------------------------
    def ble_irq(self, event, data):

        # Central connected
        if event == 1:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)
            self.connected()
            self.led.value(1)

        # Central disconnected
        elif event == 2:
            conn_handle, _, _ = data
            self.connections.discard(conn_handle)
            self.disconnected()
            self.advertiser()

        # Data received
        elif event == 3:
            conn_handle, value_handle = data

            message = self.ble.gatts_read(self.rx).decode().strip()
            print("RX:", message)

            if message == "led":
                self.led.value(not self.led.value())
                print("LED:", self.led.value())
                self.send("led" + str(self.led.value()))

    # ------------------------
    # BLE service registration
    # ------------------------
    def register(self):
        NUS_UUID = ubluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        RX_UUID  = ubluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
        TX_UUID  = ubluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

        BLE_UART = (
            NUS_UUID,
            (
                (TX_UUID, ubluetooth.FLAG_NOTIFY),
                (RX_UUID, ubluetooth.FLAG_WRITE),
            ),
        )

        ((self.tx, self.rx),) = self.ble.gatts_register_services((BLE_UART,))

        # allow larger messages
        self.ble.gatts_set_buffer(self.rx, 100, True)

    # ------------------------
    # Send data to central
    # ------------------------
    def send(self, data):
        if isinstance(data, str):
            data = (data + "\n").encode()

        for conn_handle in self.connections:
            self.ble.gatts_notify(conn_handle, self.tx, data)

    # ------------------------
    # Advertising
    # ------------------------
    def advertiser(self):
        name = self.name.encode()

        payload = bytearray(b"\x02\x01\x06")
        payload += bytearray((len(name) + 1, 0x09))
        payload += name

        self.ble.gap_advertise(100, payload)
S

# ------------------------
# STARTUP
# ------------------------

ble = BLE("HAMJ's ESP32")
