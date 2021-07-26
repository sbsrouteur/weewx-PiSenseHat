# PiSenseHat WeeWX Service

This service allows including in WeeWx acquisition loop data from a PiSense Hat b (from waweshare).

Since this devices uses common component, there are good chances another hat with the same component may work with this service.

# Installation

## Prerequisites

- You need a Pi Sense Hat (https://www.waveshare.com/wiki/Sense_HAT_(B))
- Install the required libs and programs as per wiki instructions:
  - BCM2835 libraries
  - Pyhton Libraries

## WeeWx extension
### Installation
To install the extension, just download the last release file, and run the weewx installation command:
```
wee_extension --install PiSenseHatVxxxx.zip
```

copy the sdhtc3 lib from ... to WEEWX_HOME/bin/user

Update configuration and restart Weewx.

### Configuration
The configuration entries are in the \[\[PiSensewx\]\] section.
Entries are : 

Entry | Default Value | Comment
------|---------------|----------
i2c_port | 1 |  I2C Address of the device
i2c_address | 0x5C | I2C address of LPS22HB (Pressure sensor)
temperatureKeys | extraTemp1 | Temperature key to store the temperature read from SHTC3
pressureKeys | pressure | Pressure keys to store read from LPS22HB
humidityKeys | outHumidity | Humidity keys to store the humidity read from SHTC3

radiation level is read from TCS34725 and stored in WeeWx radiation key. No configuration key for this one at the moment.

