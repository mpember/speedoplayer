#!/usr/bin/python3

import sys, os, signal, time
import termios, tty
import gi

import RPi.GPIO as GPIO
from signal import pause

from ADS1115 import ADS1115

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
		self.sink = Gst.ElementFactory.make("alsasink", "alsa-output")

		self.player.add(self.source)
		self.player.add(self.decoder)
		self.player.add(self.speed)
		self.player.add(self.conv)
		self.player.add(self.sink)

		self.source.link(self.decoder)
		self.decoder.link(self.conv)
		self.conv.link(self.speed)
		self.speed.link(self.sink)

		# create an event loop and feed gstreamer bus mesages to it
		self.bus = self.player.get_bus()
		self.bus.add_signal_watch()
		self.bus.connect ("message", self.bus_call, loop)

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

		speed_refresh_delay = 0.15
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

		ads1115 = ADS1115()

		# start play back and listed to events
		self.player.set_state(Gst.State.PLAYING)

		while self.player.get_state(Gst.CLOCK_TIME_NONE)[1] in [Gst.State.PLAYING, Gst.State.PAUSED]:
			adc = ads1115.readADCSingleEnded()
			playspeed = (adc / 3320) + 0.5
			self.speed.set_property("speed", playspeed)
			time.sleep(speed_refresh_delay)

		self.player.set_state (Gst.State.NULL);

	#def playpause_held(self):
	#	self.was_playpause_held = True
	#	self.player.set_state (Gst.State.NULL);

	#def playpause_released(self):
	#	if not self.was_playpause_held:
	#		self.playpause()
	#	self.was_playpause_held = False

	def playpause(self):
		if self.player.get_state(0)[1] == Gst.State.PAUSED:
			self.player.set_state(Gst.State.PLAYING)
		else:
			self.player.set_state(Gst.State.PAUSED)
		print("play / pause music playback")

	def skipnext(self):
		if (self.playnumber<(len(self.playlist)-1)):
			self.player.set_state(Gst.State.NULL)
			self.playnumber=self.playnumber+1
			self.source.set_property("location", self.playlist[self.playnumber])
			self.player.set_state(Gst.State.PLAYING)
		else:
			print("no next track")

	def skipprev(self):
		if (self.playnumber>0):
			self.player.set_state(Gst.State.NULL)
			self.playnumber=self.playnumber-1
			self.source.set_property("location", self.playlist[self.playnumber])
			self.player.set_state(Gst.State.PLAYING)
		else:
			print("no prev track")

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
	# GPIO.add_event_detect(hall_pin,GPIO.FALLING,callback = app.get_pulse, bouncetime=20)

	GPIO.setup(play_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
	GPIO.add_event_detect(play_pin,GPIO.FALLING,callback = app.playpause, bouncetime=200)

	GPIO.setup(prev_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
	GPIO.add_event_detect(prev_pin,GPIO.FALLING,callback = app.skipprev, bouncetime=200)

	GPIO.setup(next_pin, GPIO.IN, pull_up_down = GPIO.PUD_UP)
	GPIO.add_event_detect(next_pin,GPIO.FALLING,callback = app.skipnext, bouncetime=200)

	# register the signals to be caught
	signal.signal(signal.SIGINT, app.signal_handler)
	signal.signal(signal.SIGTERM, app.signal_handler)

	app.start(sys.argv)