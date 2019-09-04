#!/usr/bin/python3

import sys, os, signal, time, traceback
import termios, tty
import gi

import RPi.GPIO as GPIO
from signal import pause

import logging

import board
import busio
from digitalio import DigitalInOut, Direction, Pull
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

from helper import format_ns

gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

play_pin = 25
prev_pin = 23
next_pin = 12

class MalvernStar_Player(object):

    def __init__(self):

        self.was_playpause_held = False

        self.player = Gst.Pipeline.new("player")
        self.player.set_auto_flush_bus(True)

        self.source = Gst.ElementFactory.make("filesrc", "source")
        self.decoder = Gst.ElementFactory.make("mad", "mp3-decoder")
        self.speed = Gst.ElementFactory.make("speed", "speed")
        self.conv = Gst.ElementFactory.make("audioconvert", "converter")
        self.queue = Gst.ElementFactory.make("queue", "queue")
        self.sink = Gst.ElementFactory.make("alsasink", "alsa-output")

        self.queue.set_property('max-size-buffers', 0)
        self.queue.set_property('max-size-bytes', 0)
        self.queue.set_property('max-size-time', 1000000000)
        self.queue.connect('overrun', self.on_overrun)
        self.queue.connect('underrun', self.on_underrun)
        self.queue.connect('pushing', self.on_pushing)
        self.queue.connect('running', self.on_running)
        
        self.player.add(self.source)
        self.player.add(self.decoder)
        self.player.add(self.speed)
        self.player.add(self.conv)
        self.player.add(self.queue)
        self.player.add(self.sink)

        self.source.link(self.decoder)
        self.decoder.link(self.conv)
        self.conv.link(self.queue)
        self.queue.link(self.speed)
        self.speed.link(self.sink)

        self.duration = Gst.CLOCK_TIME_NONE

        # create an event loop and feed gstreamer bus mesages to it
        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect ("message", self.bus_call, loop)

    def bus_call(self, bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stdout.write("End-of-stream\n")
            loop.quit()
        elif t == Gst.MessageType.DURATION_CHANGED:
            # the duration has changed, invalidate the current one
            self.duration = Gst.CLOCK_TIME_NONE
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write("Error: %s: %s\n" % (err, debug))
            loop.quit()
        return True

    def start(self, args):

        speed_refresh_delay = 0.25
        self.playnumber = 0;
        self.playlist = []

        if len(args) < 2:
            sys.stderr.write("usage: %s <media file or uri>\n" % args[0])
            sys.exit(1)
        else:
            for arg in args[1:]:
                if os.path.isfile(arg):
                    self.playlist.append(os.path.realpath(arg))

        # take the commandline argument and ensure that it is a uri
        self.source.set_property("location", self.playlist[0])

        # Create the I2C bus
        i2c = busio.I2C(board.SCL, board.SDA)

        # Create the ADC object using the I2C bus
        ads = ADS.ADS1015(i2c)

        # Create single-ended input on channel 0
        chan = AnalogIn(ads, ADS.P0)

        # start play back and listed to events
        self.player.set_state(Gst.State.PLAYING)

        while self.player.get_state(Gst.CLOCK_TIME_NONE)[1] in [Gst.State.PLAYING, Gst.State.PAUSED]:
            playspeed = (chan.voltage / 4.09) + 0.5
            ret, current = self.decoder.query_position(Gst.Format.TIME)
            # print current position and total duration
            if self.duration == Gst.CLOCK_TIME_NONE:
                (ret, duration) = self.player.query_duration(Gst.Format.TIME)
                if not ret:
                    print("ERROR: Could not query stream duration")
                self.duration = duration
            print("{0}\t{1}\t{2:05.2f}".format(self.playlist[self.playnumber], chan.voltage, playspeed*100))
            self.speed.set_property("speed", playspeed)
            time.sleep(speed_refresh_delay)

        self.player.set_state(Gst.State.NULL);

    #def playpause_held(self):
    #    self.was_playpause_held = True
    #    self.player.set_state(Gst.State.NULL);

    #def playpause_released(self):
    #    if not self.was_playpause_held:
    #        self.playpause()
    #    self.was_playpause_held = False

    def playpause(self, number):
        if self.player.get_state(0)[1] == Gst.State.PAUSED:
            self.player.set_state(Gst.State.PLAYING)
        else:
            self.player.set_state(Gst.State.PAUSED)
        print("play / pause music playback")

    def skipnext(self, number):
        if (self.playnumber<(len(self.playlist)-1)):
            self.player.set_state(Gst.State.NULL)
            self.playnumber=self.playnumber+1
            self.source.set_property("location", self.playlist[self.playnumber])
            self.player.set_state(Gst.State.PLAYING)
            print(self.playlist[self.playnumber])
        else:
            print("no next track")

    def skipprev(self, number):
        if (self.playnumber>0):
            self.player.set_state(Gst.State.NULL)
            self.playnumber=self.playnumber-1
            self.source.set_property("location", self.playlist[self.playnumber])
            self.player.set_state(Gst.State.PLAYING)
            print(self.playlist[self.playnumber])
        else:
            print("no prev track")

    def on_overrun(self, element):
        logging.debug('on_overrun')

    def on_underrun(self, element):
        logging.debug('on_underrun')

    def on_running(self, element):
        logging.debug('on_running')

    def on_pushing(self, element):
        logging.debug('on_pushing')

    def cleanup(self):
        sys.stderr.write("cleaup called\n")
        self.player.set_state(Gst.State.NULL)

    def signal_handler(self, signalNumber, frame):
        print('received:', signalNumber)
        self.cleanup()
        sys.exit(0)


if __name__ == '__main__':

    GObject.threads_init()
    Gst.init(None)
    loop = GObject.MainLoop()

    app = MalvernStar_Player()

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # GPIO.setup(hall_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    # GPIO.add_event_detect(hall_pin, GPIO.FALLING, callback = app.get_pulse, bouncetime=20)

    GPIO.setup(play_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(play_pin, GPIO.FALLING, callback = app.playpause, bouncetime=500)

    GPIO.setup(prev_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(prev_pin, GPIO.FALLING, callback = app.skipprev, bouncetime=500)

    GPIO.setup(next_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(next_pin, GPIO.FALLING, callback = app.skipnext, bouncetime=500)

    # register the signals to be caught
    signal.signal(signal.SIGINT, app.signal_handler)
    signal.signal(signal.SIGTERM, app.signal_handler)

    try:
        app.start(sys.argv)
    except:
        print('Exception in user code:')
        print('-'*60)
        traceback.print_exc(file=sys.stdout)
        print('-'*60)

