#!/usr/bin/python3

import sys, os, signal, time, traceback

import time
import signal

import logging

import RPi.GPIO as GPIO
from signal import pause

from mplayer.core import Player

hall_pin = 17
play_pin = 25
prev_pin = 23
next_pin = 12

class SpeedoPlayer(object):

    def __init__(self):
        self.pulse = 0
        self.rpm = 0.00
        self.multiplier = 2.0
        self.elapse = 0.00
        self.starttime = time.time()
        self.speed_refresh_delay = 0.25
        self.player = Player()

    def display(self):
        print("{0}\t{1: 5.0f}\t{2:05.2f}".format(self.player.filename, self.rpm, self.multiplier*100), end='\r')

    def get_pulse(self, number):
        self.pulse+=1
        if self.pulse > 0:
            self.elapse = time.time() - self.starttime
            self.pulse -=1

        self.rpm = 1/self.elapse * 60
        self.multiplier = self.rpm/1000

        self.starttime = time.time()

    def start(self, args):
        # The script expects MP3 files to be given as arguments
        if len(args) < 2:
            sys.stderr.write("usage: %s <media file or uri>\n" % args[0])
            sys.exit(1)
        else:
            for arg in args[1:]:
                if os.path.isfile(arg):
                    self.player.loadfile(arg, 1)

        # Need to wait for the first track to load
        while self.player.paused is True:
            time.sleep(0.1)

        while self.player.paused is False:
            try:
                self.display()
                self.player.speed = self.multiplier + 0.25
                time.sleep(self.speed_refresh_delay)
            except:
                print('Exception in user code:')
                print('-'*60)
                traceback.print_exc(file=sys.stdout)
                print('-'*60)

        self.player.stop();

    def playpause(self, number):
        print("Play / pause pressed")
        self.player.pause()
        self.player.speed = self.multiplier

    def skipnext(self, number):
        print("Skipping to next track")
        self.player.pt_step(1)
        self.player.speed = self.multiplier

    def skipprev(self, number):
        print("Skipping to previous track")
        self.player.pt_step(-1)
        self.player.speed = self.multiplier

    def cleanup(self):
        print("Cleaup called")
        self.player.quit()

    def signal_handler(self, signalNumber, frame):
        print('received:', signalNumber)
        self.cleanup()
        sys.exit(0)

    def log(data):
        logging.info(data)

    def error(data):
        logging.error(data)

if __name__ == '__main__':

    app = SpeedoPlayer()

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

    GPIO.cleanup()
