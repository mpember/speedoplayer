#!/usr/bin/python3 -d

import sys, os, signal, time, traceback

import time
import gi
import signal

import logging

import RPi.GPIO as GPIO
from signal import pause

gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst

hall_pin = 17
play_pin = 25
prev_pin = 23
next_pin = 12

class MalvernStar_Player(object):

    def __init__(self):

        self.pulse = 0
        self.rpm = 0.00
        self.multiplier = 0.25
        self.elapse = 0.00
        self.starttime = time.time()

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

        # create an event loop and feed gstreamer bus mesages to it
        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect ("message", self.bus_call, loop)

    def display(self):
        # os.system('clear')
        # print(self.playlist[self.playnumber])
        # print("RPM: %d" % self.rpm)
        # print("Multiplier: %.2f" % self.multiplier)
        print("{0}\t{1:05.0f}\t{2:05.2f}".format(self.playlist[self.playnumber], self.rpm, self.multiplier*100))

    def get_pulse(self, number):
        self.pulse+=1
        if self.pulse > 0:
            self.elapse = time.time() - self.starttime
            self.pulse -=1

        self.rpm = 1/self.elapse * 60
        self.multiplier = self.rpm/1000

        self.starttime = time.time()

    def bus_call(self, bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            sys.stdout.write("End-of-stream\n")
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            sys.stderr.write("Error: %s: %s\n" % (err, debug))
            loop.quit()
        return True

    def start(self, args):
        self.speed_refresh_delay = 0.25
        self.playnumber = 0;
        self.playlist = []

        if len(args) < 2:
            sys.stderr.write("usage: %s <media file or uri>\n" % args[0])
            sys.exit(1)
        else:
            for arg in args[1:]:
                if os.path.isfile(arg):
                    self.playlist.append(os.path.realpath(arg))

        print(self.playlist[0])

        # take the commandline argument and ensure that it is a uri
        self.source.set_property("location", self.playlist[0])

        # start play back and listen to events
        self.player.set_state(Gst.State.PLAYING)

        while self.player.get_state(Gst.CLOCK_TIME_NONE)[1] in [Gst.State.PLAYING, Gst.State.PAUSED]:
            try:
                self.display()
                self.speed.set_property("speed", self.multiplier + 0.25)
                time.sleep(self.speed_refresh_delay)
            except:
                print('Exception in user code:')
                print('-'*60)
                traceback.print_exc(file=sys.stdout)
                print('-'*60)

        self.player.set_state (Gst.State.NULL);

    #def playpause_held(self):
    #    self.was_playpause_held = True
    #    self.player.set_state (Gst.State.NULL);

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

    def cleanup(self):
        sys.stderr.write("cleaup called\n")
        self.player.set_state(Gst.State.NULL)

    def signal_handler(self, signalNumber, frame):
        print('received:', signalNumber)
        self.cleanup()
        sys.exit(0)

    def on_overrun(self, element):
        logging.debug('on_overrun')

    def on_underrun(self, element):
        logging.debug('on_underrun')

    def on_running(self, element):
        logging.debug('on_running')

    def on_pushing(self, element):
        logging.debug('on_pushing')

if __name__ == '__main__':

    GObject.threads_init()
    Gst.init(None)
    loop = GObject.MainLoop()

    app = MalvernStar_Player()

    # register the signals to be caught
    signal.signal(signal.SIGINT, app.signal_handler)
    signal.signal(signal.SIGTERM, app.signal_handler)

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup(hall_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(hall_pin, GPIO.FALLING, callback = app.get_pulse, bouncetime=20)

    GPIO.setup(play_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(play_pin, GPIO.FALLING, callback = app.playpause, bouncetime=500)

    GPIO.setup(prev_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(prev_pin, GPIO.FALLING, callback = app.skipprev, bouncetime=500)

    GPIO.setup(next_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
    GPIO.add_event_detect(next_pin, GPIO.FALLING, callback = app.skipnext, bouncetime=500)

    try:
        app.start(sys.argv)
    except:
        print('Exception in user code:')
        print('-'*60)
        traceback.print_exc(file=sys.stdout)
        print('-'*60)

    try:
    # Loop until users quits with CTRL-C
        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        # Reset GPIO settings
        GPIO.cleanup()
