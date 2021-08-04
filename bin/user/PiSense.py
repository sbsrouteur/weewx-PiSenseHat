#!/usr/bin/env python
"""
PiSensewx
"""
import smbus
import syslog
import weewx
from weewx.engine import StdService
import weeutil
import ctypes
import os
from datetime import datetime
from datetime import timedelta
import RPi.GPIO as GPIO
from user.TCS34725 import TCS34725


def logmsg(level, msg):
    syslog.syslog(level, 'PiSense: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def surely_a_list(innie):
    if isinstance(innie, list):
        return innie
    if innie is None or innie is "":
        return []
    return [innie] # cross fingers
    
#

LPS_ID                =  0xB1
#Register 
LPS_INT_CFG           =  0x0B        #Interrupt register
LPS_THS_P_L           =  0x0C        #Pressure threshold registers 
LPS_THS_P_H           =  0x0D        
LPS_WHO_AM_I          =  0x0F        #Who am I        
LPS_CTRL_REG1         =  0x10        #Control registers
LPS_CTRL_REG2         =  0x11
LPS_CTRL_REG3         =  0x12
LPS_FIFO_CTRL         =  0x14        #FIFO configuration register 
LPS_REF_P_XL          =  0x15        #Reference pressure registers
LPS_REF_P_L           =  0x16
LPS_REF_P_H           =  0x17
LPS_RPDS_L            =  0x18        #Pressure offset registers
LPS_RPDS_H            =  0x19        
LPS_RES_CONF          =  0x1A        #Resolution register
LPS_INT_SOURCE        =  0x25        #Interrupt register
LPS_FIFO_STATUS       =  0x26        #FIFO status register
LPS_STATUS            =  0x27        #Status register
LPS_PRESS_OUT_XL      =  0x28        #Pressure output registers
LPS_PRESS_OUT_L       =  0x29
LPS_PRESS_OUT_H       =  0x2A
LPS_TEMP_OUT_L        =  0x2B        #Temperature output registers
LPS_TEMP_OUT_H        =  0x2C
LPS_RES               =  0x33        #Filter reset register

BUFFER_SIZE = 10

class PiSensewx(StdService):

    def __init__(self, engine, config_dict):

        # Initialize my superclass first:
        super(PiSensewx, self).__init__(engine, config_dict)
        self.PiSense_dict = config_dict.get('PiSensewx', {})
        loginf('PiSensewx configuration %s' % self.PiSense_dict)

        self.port = int(self.PiSense_dict.get('i2c_port', '1'))
        self.address = int(self.PiSense_dict.get('i2c_address', '0x5c'), base=16)

        self.default_units = self.PiSense_dict.get('usUnits', 'US').upper()
        self.default_units = weewx.units.unit_constants[self.default_units]

        self.temperatureKeys = surely_a_list(self.PiSense_dict.get('temperatureKeys', 'extraTemp1'))
        self.temperature_must_have = surely_a_list(self.PiSense_dict.get('temperature_must_have', []))

        # The conversion from station pressure to MSL barometric pressure depends on the
        # temperature. So, the default is to only provide the pressure value when there
        # is already an outdoor temperature value
        self.pressureKeys = surely_a_list(self.PiSense_dict.get('pressureKeys', 'pressure'))
        self.pressure_must_have = surely_a_list(self.PiSense_dict.get('pressure_must_have', []))

        self.humidityKeys = surely_a_list(self.PiSense_dict.get('humidityKeys', 'outHumidity'))
        self.humidity_must_have = surely_a_list(self.PiSense_dict.get('humidity_must_have', []))

        self.bus = smbus.SMBus(self.port)

        self.LPS22HB_RESET()                         #Wait for reset to complete

        self._write_byte(LPS_CTRL_REG1 ,0x02) 
        
        loginf('I2C port: %s' % self.port)
        loginf('I2C address: %s' % hex(self.address))
        loginf('fallback default units: %s' % weewx.units.unit_nicknames[self.default_units])
        loginf('keys: %s %s %s' % (self.pressureKeys,self.temperatureKeys, self.humidityKeys))
        
        #init SHTC3 dll
        self.dll = ctypes.CDLL("./bin/user/SHTC3.so")
        init = self.dll.init
        init.restype = ctypes.c_int
        init.argtypes = [ctypes.c_void_p]
        
        init(None)
        
        self.temperature = self.dll.SHTC3_Read_TH
        self.temperature.restype = ctypes.c_float
        self.temperature.argtypes = [ctypes.c_void_p]
        self.humidity = self.dll.SHTC3_Read_RH
        self.humidity.restype = ctypes.c_float
        self.humidity.argtypes = [ctypes.c_void_p]
        self.LastRead=0
        self.PrevTime=datetime.now()
        
        self.Light=TCS34725(0X29, debug=False)
        self.LightGain=1
        if(self.Light.TCS34725_init() == 1):
            self.LightInit=False
            loginf('TCS34725 initialization error!!')
        else:
            print("Lux Init success")
            self.LightInit=True
            loginf('TCS34725 initialization success!!')
        
        self.LPS22HB_START_CONTINUOUS()
        self.PressBuffer=[]
        self.PressCount=0
        self.PressIndex=0
        self.SkipPressures=0
        
        # This is last to make sure all the other stuff is ready to go
        # (avoid race condition)
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        
    def LPS22HB_RESET(self):
        Buf=self._read_u16(LPS_CTRL_REG2)
        Buf|=0x04                                         
        self._write_byte(LPS_CTRL_REG2,Buf)               #SWRESET Set 1
        while Buf:
            Buf=self._read_u16(LPS_CTRL_REG2)
            Buf&=0x04
        
    def LPS22HB_START_ONESHOT(self):
        Buf=self._read_u16(LPS_CTRL_REG2)
        Buf|=0x01                                         #ONE_SHOT Set 1
        self._write_byte(LPS_CTRL_REG2,Buf)

    def LPS22HB_START_CONTINUOUS(self):
        Buf=self._read_u16(LPS_CTRL_REG1)
        Buf|=0x18                                         #Continuous 1Hz, LowPass On default
        self._write_byte(LPS_CTRL_REG1,Buf)
        Buf=self._read_u16(LPS_CTRL_REG2)
        Buf|=0x40                                         #FIFO Enable
        self._write_byte(LPS_CTRL_REG2,Buf)

    def _read_u16(self,cmd):
        LSB = self.bus.read_byte_data(self.address,cmd)
        MSB = self.bus.read_byte_data(self.address,cmd+1)
        return (MSB	<< 8) + LSB

    def _write_byte(self,cmd,val):
        self.bus.write_byte_data(self.address,cmd,val)
        
    def _read_byte(self,cmd):
        return self.bus.read_byte_data(self.address,cmd)

    
      
    def new_loop_packet(self, event):

        packet = event.packet
        
        CurTime = datetime.now()
        
        print (CurTime - self.PrevTime)
        if (CurTime - self.PrevTime < timedelta(seconds=1)):
            return
        self.PrevTime=CurTime

        # the sample method will take a single reading and return a
        # compensated_reading object
        
        PRESS_DATA = 0.0

        TEMP_DATA = 0.0

        u8Buf=[0,0,0]

        #print("\nPressure Sensor Test Program ...\n")

        #lps22hb=LPS22HB()
        
        ReadCount=0
        
        while ReadCount < 1:
            #self.LPS22HB_START_ONESHOT()

            if (self._read_byte(LPS_STATUS)&0x01)==0x01:  # a new pressure data is generated
                u8Buf[0]=self._read_byte(LPS_PRESS_OUT_XL)
                u8Buf[1]=self._read_byte(LPS_PRESS_OUT_L)
                u8Buf[2]=self._read_byte(LPS_PRESS_OUT_H)
                PRESS_DATA=((u8Buf[2]<<16)+(u8Buf[1]<<8)+u8Buf[0])/4096.0
                ReadCount+=1

            if (self._read_byte(LPS_STATUS)&0x02)==0x02:   # a new pressure data is generated

                u8Buf[0]=self._read_byte(LPS_TEMP_OUT_L)

                u8Buf[1]=self._read_byte(LPS_TEMP_OUT_H)

                TEMP_DATA=((u8Buf[1]<<8)+u8Buf[0])/100.0

        #print('Pressure = %6.2f hPa , Temperature = %6.2f °C\r\n'%(PRESS_DATA,TEMP_DATA))
        if (PRESS_DATA==0 and TEMP_DATA==0) or self.SkipPressures < 10:
            self.SkipPressures+=1
            return
        
        #print(self.LastRead) 
        
        if self.PressCount < BUFFER_SIZE:
            self.PressBuffer.append(PRESS_DATA)
            self.PressCount+=1
        else:
            if (self.LastRead!=0 and abs(self.LastRead-PRESS_DATA)>5):
                loginf("Ignored Pressure :" + str(PRESS_DATA))
                return
            self.PressBuffer[self.PressIndex]=PRESS_DATA   
            self.PressIndex=(self.PressIndex+1) % BUFFER_SIZE
        CumPress=0
        for i in self.PressBuffer:
            CumPress+=i;
            
        PRESS_DATA=CumPress/self.PressCount
        self.LastRead=PRESS_DATA
        #print(self.PressBuffer)
        loginf("Pressure :" + str(PRESS_DATA))
       #read Pi Temp & humidity
        PiTemp= self.temperature(None)        
        Humid= self.humidity(None)
        
        if self.LightInit:
            self.Light.Get_RGBData()
            self.Light.GetRGB888()
            RawLux = self.Light.Get_Lux()
            Lux = RawLux/3
            loginf('Lux:'+str(Lux)+ " Clear:"+ str(self.Light.C) + " Gain : " + str(self.LightGain) + " RGB : " + hex(self.Light.RGB888))
             
            if self.Light.C < 2000 and self.LightGain < 60:
                #loginf("Autogain stepping up")
                self.LightGain=self.Light.ChangeGain(1)
                loginf("changed gain to " + str(self.LightGain)) 
            elif self.Light.C >= 50000:
                #print("Autogain setting down")
                self.LightGain=self.Light.ChangeGain(-1)
                loginf("changed gain to " + str(self.LightGain)) 
            else:
                packet['radiation']=Lux
                
        #print('Temperature = %6.2f°C , Humidity = %6.2f%%' % (PiTemp, Humid))
         # If there is a declared set of units already, we'll convert to that.
        # If there isn't, we'll accept the configured wisdom.
        if 'usUnits' in packet:
            converter = weewx.units.StdUnitConverters[packet['usUnits']]
        else:
            converter = weewx.units.StdUnitConverters[self.default_units]
            
        #temperatureC = (TEMP_DATA, 'degree_C', 'group_temperature')
        #converted = converter.convert(temperatureC)
        #packet['extraTemp2']=converted[0]
       
        pressurePA = (PRESS_DATA, 'mbar', 'group_pressure')
        converted = converter.convert(pressurePA)
        for key in self.pressureKeys:
            logdbg("pressure to key "+key+" value"+str(converted[0]))
            packet[key] = converted[0]

        temperatureC = (TEMP_DATA, 'degree_C', 'group_temperature')
        converted = converter.convert(temperatureC)
        for key in self.temperatureKeys:
            packet[key] = converted[0]

        humidityPCT = (Humid, 'percent', 'group_percent')
        converted = converter.convert(humidityPCT)
        for key in self.humidityKeys:
            packet[key] = converted[0]

        logdbg(packet)
