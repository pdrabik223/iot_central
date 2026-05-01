import time
import utime
from pi_pico_neopixel_tools.color import Color
from pi_pico_w_server_tools.app import App, compose_response, format_dict, load_html
import socket
from pi_pico_neopixel_tools.led_strip import LedStrip

# import ephem
import ntptime
from machine import RTC
import _thread

led_strip = LedStrip(1, 16)
app = App(hostname="iot_central.local")
rtc = RTC()

uptime_minutes = 0
animation_timer = 0


def home_page(cl: socket.socket, parameters: dict):

    cl.sendall(
        compose_response(response=format_dict(load_html("static/index.html"), {}))
    )


def animation():
    global uptime_minutes
    brightness = 1
    up = True
    while 1 < 2:
        for _ in range(24 * 60):
            for _ in range(60):
                for _ in range(10):
                    time.sleep(0.1)

                    led_strip.set_pixel(0, Color.white(), 100 * brightness)
                    
                    if up:
                        brightness += 0.02
                    else:
                        brightness -= 0.02

                    if brightness >= 1:
                        up = False
                    elif brightness <= 0.05:
                        up = True

            uptime_minutes += 1

        synch_time(rtc)


def synch_time(rtc, timezone_offset=1):
    ntptime.settime()

    t = time.time() + (60 * (60 * timezone_offset))
    tm = time.localtime(t)

    rtc.datetime(
        (tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0)  # weekday (1–7)
    )


if __name__ == "__main__":

    synch_time(rtc)
    _thread.start_new_thread(animation, ())

    app.register_endpoint("/v1", home_page)

    try:
        app.main_loop()
    except (KeyboardInterrupt, Exception) as ex:
        print(f"Server error type: {type(ex)}\tmessage: {ex}\texiting")
