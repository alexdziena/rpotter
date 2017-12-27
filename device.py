import requests
import json
import yaml
from abc import ABCMeta, abstractmethod
from config import _CONFIG_FILE

_METHODS = {
    'passthrough': 'passthrough'
}

class Device:
    __metaclass__ = ABCMeta

    def __init__(self, deviceId, alias, token=None, endpoint=None):
        self.deviceId = deviceId
        self.alias = alias
        self.token = token
        self.endpoint = endpoint
        self.session = requests.Session()

    @property
    def alias(self):
        return self._alias

    @alias.setter
    def alias(self,alias):
        self._alias = alias

    @property
    def deviceId(self):
        return self._deviceId

    @deviceId.setter
    def deviceId(self, deviceId):
        self._deviceId = deviceId

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, token):
        self._token = token

    @property
    def endpoint(self):
        return self._endpoint

    @endpoint.setter
    def endpoint(self, endpoint):
        self._endpoint = endpoint
        
    def _tplink_request(self, method, requestData):
        self.session.params = {
            # 'appName': 'Kasa_Android',
            # 'termID': self.uuid,
            # 'appVer': '1.4.4.607',
            # 'ospf': 'Android+6.0.1',
            # 'netType': 'wifi',
            # 'locale': 'es_ES',
            'token': self.token
        }
        data = {
            "method": method,
            "params": {
                'deviceId': self.deviceId,
                'requestData': json.dumps(requestData)
            }
        }
        try:
            return self.session.post(url=self.endpoint, json=data).json()
        except Exception as e:
            print e
            raise e

    @abstractmethod
    def on(self):
        pass

    @abstractmethod
    def off(self):
        pass


class Plug(Device):

    def _set_relay_state(self, value):
        requestData = {"system":{"set_relay_state":{"state": value }}}
        return self._tplink_request(_METHODS.get('passthrough'), requestData)

    def on(self):
        return self._set_relay_state(1)

    def off(self):
        return self._set_relay_state(0)

class Bulb(Device):

    def _transition_light_state(self, **kwargs):
         # on_off: 1 on, 0 on_off
         # hue: 0-360, saturation: 0-100, brightness: 0-100, color_temp:4000
         # See HSB in http://colorizer.org/
        requestData = {"smartlife.iot.smartbulb.lightingservice": { "transition_light_state": kwargs } }
        return self._tplink_request(_METHODS.get('passthrough'), requestData)

    def on(self):
        return self._transition_light_state(on_off=1)

    def off(self):
        return self._transition_light_state(on_off=0)

    def hue(self,hue):
        return self._transition_light_state(hue=hue)

    def saturation(self,saturation):
        return self._transition_light_state(saturation=saturation)

    def color(self):
        return self._transition_light_state(color_temp=0)

    def white(self):
        return self._transition_light_state(color_temp=4000)

DEVICE_TYPES ={
    u'IOT.SMARTPLUGSWITCH': Plug,
    u'IOT.SMARTBULB': Bulb
}

class DeviceFactory:
    class __DeviceFactory:

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

        def __init__(self, endpoint):
            self.endpoint = endpoint or self.config['tplink']['endpoint']

        def __str__(self):
            return repr(self) + self.val

        def buildDevice(self, deviceSpec):
            type = deviceSpec.get('deviceType', None)
            if not type: raise ValueError('No deviceType was specified.')
            device = DEVICE_TYPES.get(type, None)(
                deviceSpec.get('deviceId'),
                deviceSpec.get('alias'),
                endpoint=self.endpoint)
            if not device: raise KeyError('No known deviceType: {}'.format(type))

            return device

    instance = None

    def __init__(self, endpoint):
        if not DeviceFactory.instance:
            DeviceFactory.instance = DeviceFactory.__DeviceFactory(endpoint)
        else:
            DeviceFactory.instance.endpoint = endpoint

    def __getattr__(self, name):
        return getattr(self.instance, name)

    def __setattr__(self, name, value):
        return setattr(self.instance, name, value)