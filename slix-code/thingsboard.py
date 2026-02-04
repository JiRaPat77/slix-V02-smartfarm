from tb_device_mqtt import TBDeviceMqttClient, TBPublishInfo
import threading
import time
import requests
import pandas as pd
import json
from datetime import datetime, timedelta


class ThingsBoard:

    def __init__(self, host: str = "thingsboard.weaverbase.com", user: str = None, password=None) -> None:
        self.host = host
        url = f"https://{host}/api/auth/login"
        payload = json.dumps({"username": user, "password": password})
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            self.token = json.loads(response.content.decode())["token"]
        else:
            raise ValueError("response code", response.status_code)

    def get_data(self, para=list[str], limit=24, startTS="", endTS="", device_ID="", time=None):
        start = int(datetime.strptime(startTS, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
        end = int(datetime.strptime(endTS, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)

        url = f'https://{self.host}:443/api/plugins/telemetry/DEVICE/{device_ID}/values/timeseries'
        params = {'keys': para, 'startTs': start, 'endTs': end, 'limit': f"{limit}"}
        headers = {'accept': 'application/json', 'X-Authorization': f'Bearer {self.token}'}

        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            formatted_data = {}
            for key, values in json.loads(response.content.decode("utf-8")).items():
                formatted_data[key] = []
                ts = []
                for item in values:
                    formatted_data[key].append(item["value"])
                    ts.append(item["ts"])
            formatted_data["ts"] = ts

            max_key = min(formatted_data, key=lambda k: len(formatted_data[k]))
            for i in formatted_data.keys():
                formatted_data[i] = formatted_data[i][:len(formatted_data[max_key])]

            df = pd.DataFrame(formatted_data)
            df["ts"] = df["ts"].apply(lambda value: datetime.fromtimestamp(value / 1000))
            df['ts'] = pd.to_datetime(df['ts'], dayfirst=True)
            df = df.sort_values("ts").reset_index().drop(columns="index")[["ts"] + para]
            if time is not None:
                df.set_index('ts', inplace=True)
                df = df.resample(time).nearest()
                df = df.reset_index()

            df = df.set_index("ts")
            df = df.apply(pd.to_numeric)
            return df.reset_index()
        else:
            return f"Error {response.status_code}"


class TBClientWrapper:

    def __init__(self, host: str, token: str):
        self.client = TBDeviceMqttClient(host, token=token)
        self.client.connect()
        self.rpc_callback = None

    def send_data(self, telemetry: dict, ts: int = None):
        """
        telemetry: dict, ex. {"temp": 30}
        ts: int | None, ex. 1721770740000 (timestamp in ms)
        """
        if ts is not None:
            payload = {
                "ts": ts,
                "values": telemetry
            }
        else:
            payload = telemetry

        result = self.client.send_telemetry(payload)
        return result.get() == TBPublishInfo.TB_ERR_SUCCESS

    def set_rpc_callback(self, callback_function):
        """Register a callback function for RPC from server."""
        self.rpc_callback = callback_function
        self.client.set_server_side_rpc_request_handler(callback_function)

    def disconnect(self):
        self.client.disconnect()

    def loop_forever(self):
        """Start a thread to listen for RPCs (non-blocking)."""
        t = threading.Thread(target=self.client.loop_forever)
        t.daemon = True
        t.start()

