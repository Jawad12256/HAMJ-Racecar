import asyncio
import sys
import threading
import queue
import time
import pygame
from bleak import BleakScanner, BleakClient

RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
DEVICE_NAME = "HANSEL LOOK AT THIS" 

# --- SWITCH 2 PRO CONTROLLER MAPPING ---
AXIS_LEFT_STICK_X = 0  
AXIS_ZR_FORWARD = 5   
AXIS_ZL_BACKWARD = 4   
BTN_MINUS_QUIT = 4
BTN_PLUS_WIN = 6

command_queue = queue.Queue()

async def bluetooth_worker():
    """Background thread with Auto-Reconnect capabilities"""
    print(f"\n📡 Bluetooth system active. Searching for '{DEVICE_NAME}'...")
    
    # Outer loop: Keeps trying to scan and connect forever
    while True:
        try:
            device = await BleakScanner.find_device_by_filter(
                lambda d, a: d.name == DEVICE_NAME, timeout=5.0
            )
            
            if not device:
                print("   ⏳ Still searching for car... (Ensure ESP32 is powered on)")
                await asyncio.sleep(2)
                continue # Loop back up and scan again

            print(f"✅ Found car at hardware address: {device.address}")
            print("🏎️ Establishing connection...")

            async with BleakClient(device) as client:
                print("\n⚡ CONNECTED! You are clear to drive.")
                print(f"🎮 MAP: ZR = Forward | ZL = Backward | Left Stick = Steer | Minus Btn = Quit")
                
                # Clear out any old commands that piled up while disconnected
                while not command_queue.empty():
                    command_queue.get_nowait()
                
                last_sent = ""
                
                # Inner loop: Active driving connection
                while True:
                    cmd = None
                    while not command_queue.empty():
                        cmd = command_queue.get_nowait()
                    
                    if cmd == "QUIT":
                        print("\nDisconnecting Bluetooth safely...")
                        try:
                            await client.write_gatt_char(RX_UUID, b"S\n") 
                        except: pass
                        return # Exits the entire thread
                    
                    if cmd and cmd != last_sent:
                        await client.write_gatt_char(RX_UUID, (cmd + "\n").encode())
                        print(f"Beamed -> {cmd}")
                        last_sent = cmd
                        
                    await asyncio.sleep(0.05)
                    
        except Exception as e:
            # If the car drives out of range or loses power, it triggers this error block
            print(f"\n❌ Connection lost or failed: {e}")
            print("🔄 Attempting to reconnect in 3 seconds...")
            await asyncio.sleep(3)


def start_bluetooth_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(bluetooth_worker())


def main():
    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        print("❌ No controller detected! Please pair your Switch Pro Controller to Windows first.")
        return
        
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    print(f"🎮 Initialized: {joystick.get_name()}")
    
    print("⏱️ Skipping Test Bench. Launching resilient Bluetooth systems...")

    bl_loop = asyncio.new_event_loop()
    bt_thread = threading.Thread(target=start_bluetooth_loop, args=(bl_loop,), daemon=True)
    bt_thread.start()
    
    last_calculated_cmd = "S"
    command_queue.put("S") 

    try:
        while True:
            pygame.event.pump()
            
            # Safe Exit
            if joystick.get_button(BTN_MINUS_QUIT):
                print("\n🏁 Exit button pressed on controller!")
                command_queue.put("QUIT")
                break
            
            win = ""
            if joystick.get_button(BTN_PLUS_WIN):
                print("YAY WE WON!")
                win = "W"


            # Read analog data
            x_steering = joystick.get_axis(AXIS_LEFT_STICK_X) 
            zr_val = joystick.get_axis(AXIS_ZR_FORWARD)
            zl_val = joystick.get_axis(AXIS_ZL_BACKWARD)
            
            zr_pulled = zr_val > 0.2
            zl_pulled = zl_val > 0.2
            
            # Compound Drive Logic
            throttle = ""
            if zr_pulled:
                throttle = "F"
            elif zl_pulled:
                throttle = "B"
                
            steering = ""
            if x_steering < -0.5: 
                steering = "L"
            elif x_steering > 0.5:  
                steering = "R"
                
            current_cmd = throttle + steering + win
            if current_cmd == "":
                current_cmd = "S"
            
            # Push changes to the Bluetooth worker
            if current_cmd != last_calculated_cmd:
                last_calculated_cmd = current_cmd
                command_queue.put(current_cmd)
                
            time.sleep(0.05) 
            
    except KeyboardInterrupt:
        print("\n🏁 Script closing down...")
        command_queue.put("QUIT")
        
    time.sleep(0.5) 

if __name__ == "__main__":
    main()