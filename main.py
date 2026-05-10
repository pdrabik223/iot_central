import json
import time

from pi_pico_neopixel_tools.color import Color
from pi_pico_w_server_tools.app import App, compose_response, format_dict, load_html
import socket
from pi_pico_neopixel_tools.led_strip import LedStrip
import utime

import ntptime
from machine import RTC
import _thread

led_strip = LedStrip(1, 16)
app = App(hostname="iot_central.local")
rtc = RTC()


def animation():
    # global uptime_minutes
    brightness = 1
    up = True
    while 1 < 2:
        for _ in range(24 * 60):
            for _ in range(60):
                for _ in range(10):
                    time.sleep(0.1)

                    led_strip.set_pixel(0, Color.pink(), 100 * brightness)

                    if up:
                        brightness += 0.02
                    else:
                        brightness -= 0.02

                    if brightness >= 1:
                        up = False
                    elif brightness <= 0.05:
                        up = True

        synch_time(rtc)


def synch_time(rtc, timezone_offset=1):
    ntptime.settime()

    t = time.time() + (60 * (60 * timezone_offset))
    tm = time.localtime(t)

    rtc.datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], 0))


def home_page(cl: socket.socket, parameters: dict):
    cl.sendall(compose_response(response=load_html("static/index.html")))


def connect(cl: socket.socket, parameters: dict):

    is_new_connection = True
    requires_save = False
    
    for id, config in enumerate(endpoint_config):
        if parameters["host_name"] == config.host_name:

            if config.ip != parameters.get("ip", "Unknown"):
                requires_save = True

            config.ip = parameters.get("ip", "Unknown")
            config.last_connection_time = utime.localtime()
            is_new_connection = False
            break

    if is_new_connection:
        endpoint_config.append(
            Endpoint(
                parameters["host_name"],
                utime.localtime(),
                parameters.get("ip", "Unknown"),
            )
        )

    if is_new_connection or requires_save:
        # save config to file
        pass
    cl.sendall(compose_response())


def get_endpoint_config(cl: socket.socket, parameters: dict):
    data = [endpoint.to_dict() for endpoint in endpoint_config]
    cl.sendall(compose_response(response=json.dumps(data)))

def timestamp_to_str(t: tuple) -> str:
    def add_zero(val: int):
        return f"{val if val >= 10 else "0" + str(val)}"
    
    return f"{add_zero(t[2])}/{add_zero(t[1])}/{add_zero(t[0])} {add_zero(t[3])}:{add_zero(t[4])}"


class Endpoint:
    host_name: str
    ip: str
    last_connection_time: tuple
    redirects_to: list[str]

    def __init__(self, host_name, last_connection_time, ip, redirects_to=[]):
        self.host_name = host_name
        self.ip = ip
        self.last_connection_time = last_connection_time
        self.redirects_to = redirects_to

    def to_dict(self):
        return {
            "host_name": self.host_name,
            "ip": self.ip,
            "last_connection_time": timestamp_to_str(self.last_connection_time),
            "redirects_to": self.redirects_to,
        }


endpoint_config: list[Endpoint] = [
    Endpoint("SENSOR_ROOM", utime.localtime(), app.ip, []),
    Endpoint("MOON_CALENDAR", utime.localtime(), app.ip, []),
    Endpoint("SENSOR_ROOM", utime.localtime(), app.ip, []),
]


if __name__ == "__main__":

    synch_time(rtc)

    _thread.start_new_thread(animation, ())

    app.register_endpoint("/v1/", home_page)
    app.register_endpoint("/v1/get_endpoint_config", get_endpoint_config)
    app.register_endpoint("/v1/connect", connect)

    try:
        app.main_loop()
    except (KeyboardInterrupt, Exception) as ex:
        print(f"Server error type: {type(ex)}\tmessage: {ex}\texiting")
