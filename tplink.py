import yaml
import json
import requests
import time
from config import _CONFIG_FILE
from device import DeviceFactory, Bulb, Plug
from collections import defaultdict
import logging

# logging.basicConfig(level=logging.DEBUG)

_METHODS = {
    'login': 'login',
    'getDeviceList': 'getDeviceList'
}

class TPLink(object):

    def _get_config(self, config=_CONFIG_FILE):
        with open(config) as f:
            return yaml.safe_load(f)

    @property
    def config(self, config=_CONFIG_FILE):
        if not hasattr(self, '_config') or not self._config:
            self._config = self._get_config(config)
        return self._config

    @config.setter
    def config(self, value):
        self._config = value


    @property
    def token(self):
        if not hasattr(self, '_token') or not self._token:
            raise Exception('Not logged in')
        return self._token

    @token.setter
    def token(self, value):
        self._token = value

    def __init__(self, endpoint=None, uuid=None):
        self.endpoint = endpoint or self.config['tplink']['endpoint']
        self.uuid = uuid or self.config['tplink']['clientDeviceUuid']
        self.methods = _METHODS

    def login(self, username=None, password=None, uuid=None):
        uuid = uuid or self.uuid
        data = {
            "method": self.methods.get('login'),
            "params": {
                "appType": self.config['tplink']['appType'],
                "cloudUserName": self.config['tplink']['username'],
                "cloudPassword": self.config['tplink']['password'],
                "terminalUUID": uuid
            }
        }
        resp = requests.post(self.endpoint, json=data).json()
        self.token = resp['result']['token']
        return resp

    def getDeviceList(self):
        data = {
            "method": self.methods.get('getDeviceList'),
            "params": {
                "token": self.token
            }
        }
        try:
            resp = requests.post(self.endpoint, json=data).json()
            self.devicesById = self.devicesById if hasattr(self,'devicesById') else {}
            self.devicesByAlias = self.devicesByAlias if hasattr(self,'devicesByAlias') else {}
            for device in resp['result']['deviceList']:
                self.devicesById[device['deviceId']] = device
                self.devicesByAlias[device['alias']] = device
            return resp
        except Exception as e:
            logging.error(e)
            raise e

    def getDeviceByAlias(self, alias):
        return self.devicesByAlias[alias]

    def getDeviceById(self, deviceId):
        return self.devicesById[deviceId]


def allOff():
    l = TPLink()
    logging.info(l.login('alexdziena@gmail.com','bg0*ls6C)ny1'))
    factory = DeviceFactory(l.endpoint)
    for device in l.getDeviceList()['result']['deviceList']:
        device = factory.buildDevice(device)
        device.token = l.token
        device.off()

def allOn():
    l = TPLink()
    logging.info(l.login('alexdziena@gmail.com','bg0*ls6C)ny1'))
    factory = DeviceFactory(l.endpoint)
    for device in l.getDeviceList()['result']['deviceList']:
        device = factory.buildDevice(device)
        device.token = l.token
        device.on()

def test():
    l = TPLink()
    logging.info(l.login('alexdziena@gmail.com','bg0*ls6C)ny1'))
    factory = DeviceFactory(l.endpoint)
    devices = defaultdict(list)
    for device in l.getDeviceList()['result']['deviceList']:
        logging.info('{}: {}'.format(device['alias'],device['deviceId']))
        device = factory.buildDevice(device)
        devices[device.__class__].append(device)
        device.token=l.token
        # logging.info(device.on())
        # time.sleep(.5)
        # logging.info(device.off())
    for bulb in devices[Bulb]:
        logging.info(bulb.on())
        logging.info(bulb.color())
        logging.info(bulb.saturation(100))
        for hue in range(361):
            logging.info(bulb.hue(hue))
            time.sleep(20/1000.0)
        logging.info(bulb.white())
