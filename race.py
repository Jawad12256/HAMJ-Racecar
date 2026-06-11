#race.py
from machine import Pin, PWM
import time

#PINS
servo_pin = 23
motor_pin1 = 16
motor_pin2 = 17

#PWM setup
servo = PWM(Pin(servo_pin), freq=50)
fmotor = PWM(Pin(motor_pin1), freq=10000)
bmotor = PWM(Pin(motor_pin2), freq=10000)

def turn_default():
    servo.duty(70)

def turn_right():
    servo.duty(120)

def turn_left():
    servo.duty(20)