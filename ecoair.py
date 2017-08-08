#!/usr/bin/python

from __future__ import print_function

import datetime
import os
import sys
import time
from urllib import urlencode

import urllib2
from sense_hat import SenseHat, ACTION_RELEASED, ACTION_HELD, ACTION_PRESSED

from config import Config

import contextlib
import six
import sys
import unicodedata
import dropbox
from dropbox.files import FileMetadata, FolderMetadata

# ============================================================================
# Constants
# ============================================================================
# specifies how often to measure values from the Sense HAT (in minutes)
MEASUREMENT_INTERVAL = 10  # minutes
# Set to False when testing the code and/or hardware
# Set to True to enable upload of weather data to Weather Underground
WEATHER_UPLOAD = True
# the weather underground URL used to upload weather data
WU_URL = "http://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
# some string constants
SINGLE_HASH = "#"
HASHES = "########################################"
SLASH_N = "\n"

#fix stdout immediate flush in python2
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)


# constants used to display an up and down arrows plus bars
# modified from https://www.raspberrypi.org/learning/getting-started-with-the-sense-hat/worksheet/
# set up the colours (blue, red, empty)
b = [0, 0, 255]  # blue
r = [255, 0, 0]  # red
e = [0, 0, 0]  # empty
# create images for up and down arrows
arrow_up = [
    e, e, e, r, r, e, e, e,
    e, e, r, r, r, r, e, e,
    e, r, e, r, r, e, r, e,
    r, e, e, r, r, e, e, r,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e,
    e, e, e, r, r, e, e, e
]
arrow_down = [
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    e, e, e, b, b, e, e, e,
    b, e, e, b, b, e, e, b,
    e, b, e, b, b, e, b, e,
    e, e, b, b, b, b, e, e,
    e, e, e, b, b, e, e, e
]
bars = [
    e, e, e, e, e, e, e, e,
    e, e, e, e, e, e, e, e,
    r, r, r, r, r, r, r, r,
    r, r, r, r, r, r, r, r,
    b, b, b, b, b, b, b, b,
    b, b, b, b, b, b, b, b,
    e, e, e, e, e, e, e, e,
    e, e, e, e, e, e, e, e
]
"""
def dropbox():
    dbx = dropbox.Dropbox('i2Bc9DL9WJ0AAAAAAAAfqGd2NdHU1-7uhNeuM41-H3hNE9B11H5q2wN22vAjcNKX')
    with open(fullname, 'rb') as f:
        data = f.read()
    res = dbx.files_upload(
                data, '/' + fullname, dropbox.files.WriteMode.overwrite,
                autorename=False,
                mute=True)
       
    print('Dropbox uploaded as', res.name.encode('utf8'))
    return res
"""

def c_to_f(input_temp):
    # convert input_temp from Celsius to Fahrenheit
    return (input_temp * 1.8) + 32


def get_cpu_temp():
    # 'borrowed' from https://www.raspberrypi.org/forums/viewtopic.php?f=104&t=111457
    # executes a command at the OS to pull in the CPU temperature
    res = os.popen('vcgencmd measure_temp').readline()
    return float(res.replace("temp=", "").replace("'C\n", ""))


# use moving average to smooth readings
def get_smooth(x):
    # do we have the t object?
    if not hasattr(get_smooth, "t"):
        # then create it
        get_smooth.t = [x, x, x]
    # manage the rolling previous values
    get_smooth.t[2] = get_smooth.t[1]
    get_smooth.t[1] = get_smooth.t[0]
    get_smooth.t[0] = x
    # average the three last temperatures
    xs = (get_smooth.t[0] + get_smooth.t[1] + get_smooth.t[2]) / 3
    return xs


def get_temp():
    # ====================================================================
    # Unfortunately, getting an accurate temperature reading from the
    # Sense HAT is improbable, see here:
    # https://www.raspberrypi.org/forums/viewtopic.php?f=104&t=111457
    # so we'll have to do some approximation of the actual temp
    # taking CPU temp into account. The Pi foundation recommended
    # using the following:
    # http://yaab-arduino.blogspot.co.uk/2016/08/accurate-temperature-reading-sensehat.html
    # ====================================================================
    # First, get temp readings from both sensors
    t1 = sense.get_temperature_from_humidity()
    t2 = sense.get_temperature_from_pressure()
    # t becomes the average of the temperatures from both sensors
    t = (t1 + t2) / 2
    # Now, grab the CPU temperature
    t_cpu = get_cpu_temp()
    # Calculate the 'real' temperature compensating for CPU heating
    t_corr = t - ((t_cpu - t) / 1.5)
    # Finally, average out that value across the last three readings
    t_corr = get_smooth(t_corr)
    # convoluted, right?
    # Return the calculated temperature
    return t_corr

def get_temperature_from_humidity():
    t = sense.get_temperature_from_humidity()
    temp = t - ((get_cpu_temp() - t) / 1.5)
    return round(temp, 1)

def get_temperature_from_pressure():
    t = sense.get_temperature_from_pressure()
    temp = t - ((get_cpu_temp() - t) / 1.5)
    return round(temp, 1)


def pushed_right(event):
    if event.action != ACTION_RELEASED:
        sense.show_message("BYE!")
        print("\nExiting application\n")
        sense.clear()
        os._exit(1)
        #sys.exit(0) 

def pushed_up(event):
    global counter
    if event.action != ACTION_RELEASED:
        counter = counter + 1
        sense.clear() 
        show_number(counter, 200, 0, 0) #Place number
        #time.sleep(1)

def pushed_down(event):
    global counter
    if event.action != ACTION_RELEASED:
        counter = counter - 1
        sense.clear() 
        show_number(counter, 200, 0, 0) #Place number
        #time.sleep(1)

def pushed_pause(event):
    global paused
    if event.action != ACTION_RELEASED:
        sense.clear()
        if paused:
            paused = False
            sense.show_message("ON")
        else:
            paused = True
            sense.show_message("OFF")

def capture():
    dt = datetime.datetime.now()
    dtime = dt[0:4]+dt[5:7]+dt[8:10]+dt[11:13]+dt[14:16]+dt[17:19]
    call(["fswebcam", "-d","/dev/video0", "-r", "640x480", "--no-banner", "./data/%d.jpg" % int(dtime)])

#######################################################
#Display short format

OFFSET_LEFT = 1
OFFSET_TOP = 3

NUMS =[1,1,1,1,0,1,1,0,1,1,0,1,1,1,1,  # 0
       0,1,0,0,1,0,0,1,0,0,1,0,0,1,0,  # 1
       1,1,1,0,0,1,0,1,0,1,0,0,1,1,1,  # 2
       1,1,1,0,0,1,1,1,1,0,0,1,1,1,1,  # 3
       1,0,0,1,0,1,1,1,1,0,0,1,0,0,1,  # 4
       1,1,1,1,0,0,1,1,1,0,0,1,1,1,1,  # 5
       1,1,1,1,0,0,1,1,1,1,0,1,1,1,1,  # 6
       1,1,1,0,0,1,0,1,0,1,0,0,1,0,0,  # 7
       1,1,1,1,0,1,1,1,1,1,0,1,1,1,1,  # 8
       1,1,1,1,0,1,1,1,1,0,0,1,0,0,1]  # 9

# Displays a single digit (0-9)
def show_digit(val, xd, yd, r, g, b):
  offset = val * 15
  for p in range(offset, offset + 15):
    xt = p % 3
    yt = (p-offset) // 3
    sense.set_pixel(xt+xd, yt+yd, r*NUMS[p], g*NUMS[p], b*NUMS[p])

# Displays a two-digits positive number (0-99)
def show_number(val, r, g, b):
  abs_val = int(round(abs(val),0))
  tens = abs_val // 10
  units = abs_val % 10
  if (abs_val > 9): show_digit(tens, OFFSET_LEFT, OFFSET_TOP, r, g, b)
  show_digit(units, OFFSET_LEFT+4, OFFSET_TOP, r, g, b)
  time.sleep(0.3)

def show_chart(val, r, g, b):
  val = int(round(abs(val),0))
  tens = val // 10
  j=0
  for j in range(0, tens ):
       sense.set_pixel(j % 8, j // 8, 250, 0, 0)
  digits  = val % 10
  for i in range(j + 1 , j + digits + 1):
       sense.set_pixel(i % 8, i // 8, r, g, b)

def show_line(val):
  val = int(round(abs(val),0))
  base5 = val // 5
  for j in range(0, base5 ):
       sense.set_pixel(0, 7 - j % 5, 250, 250, 0)
  digits  = val % 5
  #if base5 > 0 : base5 = base5 + 1
  for i in range(base5 , base5 + digits ):
       sense.set_pixel(0, 7 - i % 5, 250, 250, 250)

#######################################################
def display(mode, counter, temp_c, humidity):
  sense.clear()       
  if mode:
    sense.show_message("%s" % counter , text_colour=[0,255,0] , back_colour=[64,0,0], scroll_speed=0.15)
    sense.show_message("%sC" % temp_c , text_colour=[255,0,0] , back_colour=[0,0,64], scroll_speed=0.15)
    sense.show_message("%s%%" % humidity , text_colour=[0,255,255] , back_colour=[64,64,64], scroll_speed=0.15)
    sense.show_message(" " , back_colour=[0,0,0])
  else:
    show_line(counter) #Place number
    show_chart(temp_c, 0, 0, 200) #Tempature
    show_number(humidity, 0, 200, 0) #Humidity

def main():  
    global last_temp, counter, paused, filedata

    # initialize the lastMinute variable to the current time to start
    last_minute = datetime.datetime.now().minute
    # on startup, just use the previous minute as lastMinute
    last_minute -= 1
    if last_minute == 0:
        last_minute = 59

    fullname = '/home/pi/ecoair/data/ecoair-data ' + time.strftime("%Y-%m-%d_%H-%M-%S") + '.xls'
    filedata = open(fullname ,'w', 0 )

    filedata.write("Time, AVG Centigrade, Centigrade from Pressure, Centigrade from Humidity, Humidity, Place\n")

    counter = 1
    paused = False

    # infinite loop to continuously check weather values
    while 1:
        # The temp measurement smoothing algorithm's accuracy is based
        # on frequent measurements, so we'll take measurements every 5 seconds
        # but only upload on measurement_interval
        while paused:
            sense.clear()
            sense.stick.wait_for_event(True) #wait for click down and then start again, this allows us to pause the program (coffe break!!)


        current_second = datetime.datetime.now().second
        # are we at the top of the minute or at a 5 second interval?
        if (current_second == 0) or ((current_second % 5) == 0):
            # ========================================================
            # read values from the Sense HAT
            # ========================================================
            # calculate the temperature
            calc_temp = get_temp()
            # now use it for our purposes
            temp_c = round(calc_temp, 1)
            temp_f = round(c_to_f(calc_temp), 1)
            humidity = round(sense.get_humidity(), 0)
            # convert pressure from millibars to inHg before posting
            pressure = round(sense.get_pressure() * 0.0295300, 1)

            #time now
            now = datetime.datetime.now()
            #log the data to the stadnard output (screen or file)
            print("Temp: %sC, Pressure: %s inHg, Humidity: %s%% [place %s @ %s ]" % (temp_c, pressure, humidity, counter, now))
            # save the data to an excel file
            filedata.write("%s, %s, %s, %s, %s, %s\n" % (now , temp_c, get_temperature_from_pressure(), get_temperature_from_humidity(), humidity, counter))            

            # Show results on dot matrix display
            display(False, counter, temp_c, humidity)

            # get the current minute
            current_minute = datetime.datetime.now().minute
            # is it the same minute as the last time we checked?
            if current_minute != last_minute:
                # reset last_minute to the current_minute
                last_minute = current_minute
                # is minute zero, or divisible by 10?
                # we're only going to take measurements every MEASUREMENT_INTERVAL minutes
                if (current_minute == 0) or ((current_minute % MEASUREMENT_INTERVAL) == 0):
                    # get the reading timestamp
                    now = datetime.datetime.now()
                    print("\n%d minute mark (%d @ %s)" % (MEASUREMENT_INTERVAL, current_minute, str(now)))
                    # did the temperature go up or down?
                    if last_temp != temp_f:
                        if last_temp > temp_f:
                            # display a blue, down arrow
                            sense.set_pixels(arrow_down)
                        else:
                            # display a red, up arrow
                            sense.set_pixels(arrow_up)
                    else:
                        # temperature stayed the same
                        # display red and blue bars
                        sense.set_pixels(bars)
                    # set last_temp to the current temperature before we measure again
                    last_temp = temp_f

                    # ========================================================
                    # Upload the weather data to Weather Underground
                    # ========================================================
                    # is weather upload enabled (True)?
                    if WEATHER_UPLOAD:
                        # From http://wiki.wunderground.com/index.php/PWS_-_Upload_Protocol
                        print("Uploading data to Weather Underground")
                        # build a weather data object
                        weather_data = {
                            "action": "updateraw",
                            "ID": wu_station_id,
                            "PASSWORD": wu_station_key,
                            "dateutc": "now",
                            "tempf": str(temp_f),
                            "humidity": str(humidity),
                            "baromin": str(pressure),
                        }
                        try:
                            upload_url = WU_URL + "?" + urlencode(weather_data)
                            response = urllib2.urlopen(upload_url)
                            html = response.read()
                            print("Server response:", html)
                            # do something
                            response.close()  # best practice to close the file
                        except:
                            print("Exception:", sys.exc_info()[0], SLASH_N)
                    else:
                        print("Skipping Weather Underground upload")

        # wait a second then check again
        # You can always increase the sleep value below to check less often
        #time.sleep(0.25)  # this should never happen since the above is an infinite loop

    print("Leaving main()")


# ============================================================================
# here's where we start doing stuff
# ============================================================================
#print(SLASH_N + HASHES)
#print(SINGLE_HASH, "EcoAir  Station                     ", SINGLE_HASH)
#print(SINGLE_HASH, "By Sofia O'Donnell Arceo            ", SINGLE_HASH)
#print(HASHES)

# make sure we don't have a MEASUREMENT_INTERVAL > 60
if (MEASUREMENT_INTERVAL is None) or (MEASUREMENT_INTERVAL > 60):
    print("The application's 'MEASUREMENT_INTERVAL' cannot be empty or greater than 60")
    sys.exit(1)

# ============================================================================
#  Read Weather Underground Configuration Parameters
# ============================================================================
print("\nInitializing Weather Underground configuration")
wu_station_id = Config.STATION_ID
wu_station_key = Config.STATION_KEY
if (wu_station_id is None) or (wu_station_key is None):
    print("Missing values from the Weather Underground configuration file\n")
    sys.exit(1)

# we made it this far, so it must have worked...
print("Successfully read Weather Underground configuration values")
print("Station ID:", wu_station_id)
# print("Station key:", wu_station_key)

# ============================================================================
# initialize the Sense HAT object
# ============================================================================
try:
    print("Initializing the Sense HAT client")
    sense = SenseHat()
    # sense.set_rotation(180)
    # then write some text to the Sense HAT's 'screen'
    sense.show_message("EcoAir", text_colour=[255, 255, 0], back_colour=[0, 0, 255])

    sense.stick.direction_up = pushed_up
    sense.stick.direction_down = pushed_down
    sense.stick.direction_middle = pushed_pause
    sense.stick.direction_right = pushed_right
    sense.stick.direction_left = pushed_right

    # clear the screen
    sense.clear()
    # get the current temp to use when checking the previous measurement
    last_temp = round(c_to_f(get_temp()), 1)
    print("Current temperature reading:", last_temp)
except:
    print("Unable to initialize the Sense HAT library:", sys.exc_info()[0])
    sys.exit(1)

print("Initialization complete!")

# Now see what we're supposed to do next
if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        sense.clear()
        print("\nExiting application\n")
        sys.exit(0)
