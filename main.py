import gc
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


def add_redirect(cl: socket.socket, parameters: dict):
    global endpoint_config
    host_name = parameters.get("host_name", None)
    target = parameters.get("target", None)

    if host_name is None:
        return cl.sendall(compose_response(status_code=400))

    if target is None:
        return cl.sendall(compose_response(status_code=400))

    for id, config in enumerate(endpoint_config):

        if config.host_name == host_name:
            endpoint_config[id].redirects_to.append(target)
            break

    print([data.to_dict() for data in endpoint_config])

    safe_config()

    cl.sendall(compose_response())


def remove_redirect(cl: socket.socket, parameters: dict):
    global endpoint_config
    host_name = parameters.get("host_name", None)
    target = parameters.get("target", None)

    if host_name is None:
        return cl.sendall(compose_response(status_code=400))

    if target is None:
        return cl.sendall(compose_response(status_code=400))

    for id, config in enumerate(endpoint_config):

        if config.host_name == host_name:
            endpoint_config[id].redirects_to.remove(target)

    safe_config()
    cl.sendall(compose_response())


def delete_host(cl: socket.socket, parameters: dict):
    global endpoint_config
    param = "host_name"
    val = parameters.get(param, None)

    if val is None:
        return cl.sendall(
            compose_response(
                status_code=400, response=f"Missing param '{param}', of type: '{type}'"
            )
        )

    if type(val) is not str:
        return cl.sendall(
            compose_response(
                status_code=400,
                response=f"Invalid '{param}' type, expected: '{type}', got: '{type(val)}'",
            )
        )

    endpoint_config = [config for config in endpoint_config if config.host_name != val]

    safe_config()
    cl.sendall(compose_response())


def get_redirect_url(host_name: str) -> str | None:
    for config in endpoint_config:
        if config.host_name == host_name:
            if config.redirect_endpoint != None:
                endpoint = config.redirect_endpoint

                while endpoint[0] == "/":
                    endpoint = endpoint[1:]

                ip = config.ip

                while ip[-1] == "/":
                    ip = ip[:-1]

                return f"http://{ip}/{endpoint}"

    return None


def validate_required(cl: socket.socket, parameters: dict, param: str) -> any:
    val = parameters.get(param)

    # if type(val) is not param_type:
    #     return cl.sendall(
    #         compose_response(
    #             status_code=400,
    #             response=f"Invalid '{param}' type, expected: '{param_type}', got: '{type(val)}'",
    #         )
    #     )

    return val


def connect(cl: socket.socket, parameters: dict):

    host_name = parameters.get("host_name")

    if host_name is None:
        cl.sendall(
            compose_response(status_code=400, response=f"Missing param 'host_name'")
        )
        return 
        
    ip = parameters.get("ip")
    
    if ip is None:
        cl.sendall(
            compose_response(status_code=400, response=f"Missing param 'host_name'")
        )
        return 
    
    redirect_endpoint = parameters.get("redirect_endpoint")

    is_new_connection = True
    requires_save = False
    redirects = []
    for id, config in enumerate(endpoint_config):
        if host_name != config.host_name:
            continue

        is_new_connection = False

        if config.ip != ip or config.redirect_endpoint != redirect_endpoint:
            requires_save = True

        config.ip = ip
        config.redirect_endpoint = redirect_endpoint
        config.last_connection_time = utime.localtime()
        redirects = config.redirects_to

    if is_new_connection:
        endpoint_config.append(
            Endpoint(
                host_name,
                utime.localtime(),
                ip,
                redirect_endpoint,
            )
        )

    if is_new_connection or requires_save:
        safe_config()

    cl.sendall(compose_response())

    for target in redirects:
        url = get_redirect_url(target)
        print(url)
        if url is not None:
            try:
                # res = requests.get(url=url, timeout=3)
                # res.close()
                gc.collect()
            except Exception as err:
                print(err)


def get_endpoint_config(cl: socket.socket, parameters: dict):
    data = [endpoint.to_dict() for endpoint in endpoint_config]
    cl.sendall(compose_response(response=json.dumps(data)))


def timestamp_to_str(t: tuple) -> str:
    def add_zero(val: int):
        return f"{val if val >= 10 else '0' + str(val)}"

    return f"{add_zero(t[2])}/{add_zero(t[1])}/{add_zero(t[0])} {add_zero(t[3])}:{add_zero(t[4])}"


def str_to_timestamp(timestamp: str) -> tuple | None:
    try:
        date_part, time_part = timestamp.split(" ")
        day, month, year = (int(value) for value in date_part.split("/"))
        hour, minute = (int(value) for value in time_part.split(":"))
        return year, month, day, hour, minute
    except Exception:
        return None


class Endpoint:
    host_name: str
    ip: str
    redirect_endpoint: str | None
    last_connection_time: tuple
    redirects_to: list[str]

    def __init__(
        self, host_name, last_connection_time, ip, redirect_endpoint, redirects_to=[]
    ):
        if host_name == None or ip == None:
            raise ValueError("incorrect params")
        self.host_name = host_name
        self.ip = ip
        self.redirect_endpoint = redirect_endpoint
        self.last_connection_time = last_connection_time
        self.redirects_to = redirects_to

    def to_dict(self):
        return {
            "host_name": self.host_name,
            "ip": self.ip,
            "redirect_endpoint": self.redirect_endpoint,
            "last_connection_time": timestamp_to_str(self.last_connection_time),
            "redirects_to": self.redirects_to,
        }

    @staticmethod
    def from_dict(data: dict):
        last_connection_time = data.get("last_connection_time")

        if isinstance(last_connection_time, str):
            parsed = str_to_timestamp(last_connection_time)
            if parsed is not None:
                last_connection_time = parsed

        return Endpoint(
            host_name=data.get("host_name"),
            ip=data.get("ip"),
            redirect_endpoint=data.get("redirect_endpoint"),
            last_connection_time=last_connection_time,
            redirects_to=data.get("redirects_to"),
        )


def safe_config():
    global endpoint_config
    path = "endpoint_config.json"
    data = []

    for config in endpoint_config:
        data.append(config.to_dict())

    write_json_file(path, data)


def load_config():
    global endpoint_config
    path = "endpoint_config.json"
    file = load_json_file(path)

    if file is None:
        file = []

    config = [Endpoint.from_dict(data) for data in file]

    if config is not None:
        endpoint_config = config


def load_json_file(path: str) -> dict | None:
    try:
        with open(path, "r") as file:
            return json.loads(file.read())
    except Exception:
        return None


def write_json_file(path: str, data: dict) -> None:
    try:
        with open(path, "w") as file:
            file.write(json.dumps(data))
            file.flush()
    except Exception:
        return None


import urequests as requests

endpoint_config: list[Endpoint] = []


if __name__ == "__main__":

    synch_time(rtc)

    _thread.start_new_thread(animation, ())

    load_config()

    app.register_endpoint("/v1/", home_page)
    app.register_endpoint("/v1/get_endpoint_config", get_endpoint_config)
    app.register_endpoint("/v1/connect", connect)
    app.register_endpoint("/v1/delete_host", delete_host)
    app.register_endpoint("/v1/add_redirect", add_redirect)
    app.register_endpoint("/v1/remove_redirect", remove_redirect)

    try:
        app.main_loop()
    except (KeyboardInterrupt, Exception) as ex:
        print(f"Server error type: {type(ex)}\tmessage: {ex}\texiting")
