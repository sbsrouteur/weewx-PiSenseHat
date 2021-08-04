# installer for PiSenseHat data acquisition service
# Copyright 2021- 
# Distributed under the terms of the MIT License

from bin.user.PiSense import PiSensewx
from weecfg.extension import ExtensionInstaller

def loader():
    return PiSenseHatInstaller()

class PiSenseHatInstaller(ExtensionInstaller):
    def __init__(self):
        super(PiSenseHatInstaller, self).__init__(
            version="0.1",
            name='Pi Sense Hat Service',
            description='Service to include PiSense sensor to WeeWx loop.',
            author="sbsrouteur",
            author_email="sbsrouteur@free.fr",
            data_services='user.PiSense.PiSensewx',
            config={
                'PiSensewx': {
                    'i2c_port' : '1',
                    'i2c_address' : '0x5c',
                    'temperatureKeys' : 'extraTemp1',
                    'pressureKeys' : 'pressure',
                    'humidityKeys' : 'outHumidity'
                    }
                },
            files=[('bin/user', ['bin/user/TCS34725.py','bin/user/PiSense.py'])]
            )
