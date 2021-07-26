# installer for PiSenseHat data acquisition service
# Copyright 2021- 
# Distributed under the terms of the MIT License

from bin.user.PiSense import PiSensewx
from weecfg.extension import ExtensionInstaller

def loader():
    return PiSenseHayInstaller()

class PiSenseHayInstaller(ExtensionInstaller):
    def __init__(self):
        super(PiSenseHayInstaller, self).__init__(
            version="0.1",
            name='Pi Sense Hat Service',
            description='Service to include PiSense sensor to WeeWx loop.',
            author="sbsrouteur",
            author_email="sbsrouteur@free.fr",
            restful_services='user.PiSense.PiSensewx',
            config={
                'PiSensewx': {
                    'i2c_port' : '1'
                    'i2c_address' : '0x5c'
                    'temperatureKeys' : 'extraTemp1'
                    'pressureKeys' : 'pressure'
                    'humidityKeys' : 'outHumidty'}
                },
            files=[('bin/user', ['bin/user/PiSense.py','bin/users/TCS34725.py'])]
            )
