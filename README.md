Audio sync analysis library
===========================

Notices
-------

This is not an official Google product.

The code of this project is released under the terms of the
Apache 2 license. See LICENSE for details.

Overview
--------

`audio_sync` is a Python library that compares two audio signals and
obtains the latency (or delay) of one of the signals vs the other.
The library was developed originally to test multiroom for Chromecast Audio.

For the library to be able to determine the latency, the audio signals
output by the audio sources under test (e.g., loudspeakers)
need to have certain characteristics (described in the
[How is latency measured](#How-is-latency-measured) section).
This limits the applicability of the library to cases where it's possible
to control the audio played by the sources. If that's not the case, then
cross-correlation may be a better technique to consider.

The high-level flow for checking audio sync is:

1. Generate the audio to be played by the audio sources.
2. Have the sources play the audio and record it.
3. Measure the latency between pairs of audios.

The first step is described in detail in the
[Test audio generation](#Test-audio-generation).

The second step is highly dependent on the sources of the audio. For
example, if they are devices with analog outputs, the audio could be
recorded using a multichannel audio capture device (like
[this](http://tascam.com/product/dr-680mkii/) or
[this](http://www.m-audio.com/products/view/delta-1010lt)). If one of
the sources doesn't feature a line out, it may be necessary to record
the audio using a mic. Or maybe the audio is streamed via the network.
The recording process may be manual or can be automated, but again this
is dependent on the nature of the audio sources under test. A method
to capture audio from devices with a line output is described in
[Recording audio](#Recording-audio).

The third step is an analysis performed in the recordings from the
sources. The library described here provides an automated way to
perform this analysis.
[Measuring sync from your program](#Measuring-sync-from-your-program)
details the steps to use the library in your project.

Requirements
------------

The library depends on the following python packages (aside from some
others in the standard library):
- numpy (tested with 1.10.2)

Audio generation is done via [SoX](http://sox.sourceforge.net/), which
is available in most Linux distributions as well as on MacOS X and
Windows.

Test audio generation
---------------------

This section describes how to generate the audio to be played by
the audio sources. There are many methods to craft the audio; the
one detailed here uses the [SoX](http://sox.sourceforge.net/)
utility and has the advantage that can be done from the command line
or from a script (in contrast, using Audacity, for example, requires
manual interaction with the GUI).

The following SoX commands generate a test audio file with the
properties

- Duration: 1 min
- Period: 100 msecs
- Max sine pulse amplitud: 0.8
- Max noise amplitud: 0.2
- Sampling rate: 48 kHz
- Encoding: signed int, low-endian

```
sox -n -r 48k sine.wav synth 0.002 sine 500 gain -n vol 0.8
sox -n -r 48k noise.wav synth 0.098 pinknoise gain -n vol 0.2
sox sine.wav noise.wav sine_noise_f48k_p100msecs_d60sec.wav repeat 599
```

The following options can be added to the above commands to
control audio encoding:
- `-e`: selects the encoding. `signed-integer`, `unsigned-integer`, and
        `floating-point` are common options..
- `-b`: sets the sample width. 8, 16, 24, and 32 are common options.
- `-r`: sets the sampling rate. `16k`, `44.1k`, and `48k` are common
        options.
- `-L`, `-B`: use little-endian or big-endian.

If silence is needed instead of noise, this can be done in a single
command using the `pad` effect:

```
sox -n -r 48k sine_silence_f48k_p100msecs_d60sec.wav \
    synth 0.002 sine 500 gain -n vol 0.8 pad 0 0.098 repeat 599
```

Recording audio
---------------

This section describes how to record audio from multiple channels using the
`arecord` utility. This method is suitable for cases when the audio sources
are devices that have a line out.

Since `arecord` uses the standard ALSA sound interface, this process can be
done in any Linux system with a 2.6 or later kernel (including embedded
systems such as the Raspberry Pi).

### Recording hardware

The instructions apply to any ALSA-compatible multi-channel audio recorder.
The examples below use the Behringer U-Phono UFO202, a USB device with
two input ports.

The U-Phono is connected to a Linux system from where the recording commands
will be issued.

### Determining the ALSA device name

The first step is determining the name of the ALSA device corresponding to
the multi-channel recorder. Many systems have an embedded recording port
(e.g., the mic in most PCs), so it's important to determine the right device.

The most straightforward way to identify the name is by running `arecord -L`
when the card is disconnected, then connecting the card and running again
`arecord -L`; the additional entries will correspond to the card in question.

For the U-Phono, the entries are those with `CARD=CODEC,DEV=0`:

```
sysdefault:CARD=CODEC
    USB Audio CODEC, USB Audio
    Default Audio Device
...
hw:CARD=CODEC,DEV=0
    USB Audio CODEC, USB Audio
    Direct hardware device without any conversions
plughw:CARD=CODEC,DEV=0
    USB Audio CODEC, USB Audio
    Hardware device with all software conversions
```

For latency measurement, it's preferable to use `hw:CARD=CODEC,DEV=0` because
it provides the most direct path to the hardware and reduces the chances
of breaking the simultaneity of the recording.

### Recording command

Once the proper device name has been identified, the next step is actually
recording the audio. The following command line does it for the U-Phono:

```
arecord -D hw:CARD=CODEC,DEV=0 -c 2 -f S16_LE -r 16k -d 0 recording.wav
```

Here's the meaning of each option:
* `-D` specifies the recording device.
* `-c` specifies the number of channels in the output audio file. The example
  uses `2` because that's the number of capture ports in the U-Phono.
* `-f` specifies the sample format (signed int 16-bit little-endian in the
  example).
* `-r` specifies the sampling rate.
* `-d` specifies the recording time, in seconds (if 0, records until
  it receives SIGINT).
* `recording.wav` is the name of the file containing the recorded audio.

Since we're using the direct hardware device, it's mandatory to specify
parameters that are supported natively by the card. (In contrast, if
`plughw` were used, it would possible to specify a non-native format and
the conversion would be done by the `plug` software layer.) The card manual
should list the valid values or they can be dumped by providing the
`--dump-hw-params` switch:

```
$ arecord -D hw:CARD=CODEC,DEV=0 --dump-hw-params
Recording WAVE 'stdin' : Unsigned 8 bit, Rate 8000 Hz, Mono
HW Params of device "hw:CARD=CODEC,DEV=0":
--------------------
ACCESS:  MMAP_INTERLEAVED RW_INTERLEAVED
FORMAT:  S8 S16_LE
SUBFORMAT:  STD
SAMPLE_BITS: [8 16]
FRAME_BITS: [8 32]
CHANNELS: [1 2]
RATE: [8000 48000]
PERIOD_TIME: [1000 65536000]
PERIOD_SIZE: [16 524288]
PERIOD_BYTES: [64 524288]
PERIODS: [2 1024]
BUFFER_TIME: (666 131072000]
BUFFER_SIZE: [32 1048576]
BUFFER_BYTES: [64 1048576]
TICK_TIME: ALL
--------------------
...
```

Once the recording is finished, `soxi` can be used to verify that the
parameters in the audio file correspond to the arguments passed to `arecord`:

```
$ soxi recording.wav

Input File     : 'recording.wav'
Channels       : 2
Sample Rate    : 16000
Precision      : 16-bit
Duration       : 00:00:03.75 = 60000 samples ~ 281.25 CDDA sectors
File Size      : 240k
Bit Rate       : 512k
Sample Encoding: 16-bit Signed Integer PCM
```

### Splitting into mono files

Since the sync analyzer requires the audio signals to be in separate
files, the following commands can be used to split the multichannel
audio:

```
sox recording.wav recording_ch1.wav remix 1
sox recording.wav recording_ch2.wav remix 2
```

[//]: # (TODO: add description of canonical setup)

Measuring sync from your program
--------------------------------

The following steps were tested in Goobuntu 14.04, but should be
applicable to any Debian-based distribution.

1. Create and start a virtualenv for the project.

```
sudo apt-get install virtualenv
virtualenv python-sandbox
. python-sandbox/bin/activate
```

2. Install the required libraries.

```
pip install numpy==1.10.2
```

3. Configure the PYTHONPATH to include the main repo directory:

```
PYTHONPATH=$PYTHONPATH:path/to/audio_sync_test
```

4. Use `audio_sync.AnalyzeAudios()` to determine the latency:

```python
import audio_sync

# This assumes the test audio played by the devices under
# test is audio_sync.DEFAULT_TEST_AUDIO, whose properties
# are given in audio_sync.DEFAULT_TEST_AUDIO_PROPERTIES.
latencies, dropouts  = audio_sync.AnalyzeAudios(ref_wav_path, act_wav_path)

# Verify there are no dropouts and the latency is below the threshold.
assert [] == [x for x in latencies if x[1] >= LATENCY_THRESHOLD]
assert [] == dropouts
```

`latencies` has the form `[(t0, latency0), (t1, latency1), ...]`,
where `tx` is the time, in seconds, from the start of the audio
to a cliff in the reference audio and `latencyx` is the latency,
in seconds, of the corresponding cliff in the actual signal.

`dropouts` is a list of the form `[(s0, e0), (s1, e1), ...]`
with the start and the end of each dropout in the actual signal.

How is latency measured
-----------------------

Latency measurements depend on the audio signals being made of pulsed
sine waves of the following form:

```
            period
      |----------------|
      _                _                _
     / \              / \              / \
~~~~~   \   ~~~~~~~~~~   \   ~~~~~~~~~~   \   ~~~~~~ ...
         \_/              \_/              \_/
            |--------|                  |---|
         low volume noise                sine
            or silence                   pulse
```

These audio signals are played by the sources under test and recorded
_simultaneously_, for example, using a multichannel audio card.
(Notice that the requirement of simultaneity is a fundamental one;
otherwise it's impossible to ensure that two corresponding data
samples had occurred at the same time.)
By knowing the sampling frequency of the recordings the latency
between the signals can be calculated by comparing the distance
between two corresponding peaks in each audio signal using the formula

```
                location_max_ref - location_max_act
latency[sec] = -------------------------------------
                           sampling_rate
```

There are two reasons for using a special crafted audio instead of using
arbitrary media like a song:

1. The first is that it allows to determine the sync of the audios as
   time progresses, which is important to, for example, determine how
   long it takes for two devices to play below a given latency threshold
   and if some event (e.g., unplugging and re-plugging the device from
   the network) has any effect in the sync.

2. The second is that since the audio is well characterized, it's
   possible to know that a phenomenon is caused by a bug (e.g., if
   a silence is found when no part of the audio has some).

### Limitations

1. The algorithm can detect latencies in the range
   [-0.45\*period, 0.45\*period] to avoid any corner cases where there
   are two cliffs in the same comparison window (e.g., if the sine
   pulses move closer together due to drops of samples or PLL effects).
   A longer period allows to detect greater latencies at the cost of
   lower resolution. In turn, a lower resolution may yield to undetected
   out-of-sync playback if the audio is resynced within the period.

2. The algorithm doesn't detect dropouts in the reference signal.
   Swapping the signals is a workaround to find dropouts in the
   reference signal.

Command line interface
----------------------

The library also provides a command line interface (CLI) to analyze
the audios. This is useful for exploratory testing and experimentation.

### Requirements

The CLI depends on numpy (tested with 1.10.2, but other versions may
also work).

```
pip install numpy==1.10.2
```

### Usage

Running the program without parameters shows the available options.
The most relevant ones are:

* `--parsable_output`: prints latencies and dropouts as a JSON of the form
  ```
  {
    "latencies": [[<time>, <delay_secs>], ...],
    "dropouts": [[<dropout_start>, <dropout_end>], ...]
  }
  ```

* `--plot_timeline: plots the conditions in a text timeline, like
  ```
                              -                         +
  ............oooooooo........<.........................................
               |             |             |             |             |
           0.66s         1.32s         1.98s         2.64s         3.30s
  ```

* `--print_percentiles`: prints the latencies percentiles.

* `--latency_threshold`: latencies equal or greater than this threshold (secs)
  are considered excessive.

* `--help`: displays a help message listing all the available options.

* `--plot_ascii_graph: plots the latencies in a ASCII art type of flow, like
  ```
  10:17:35 34:13 > +0839 ......... |
  10:17:36 34:14 > +0929 ..........|
  10:17:36 34:14 > +1111 ..........|**
  10:17:36 34:14 > +0884 ......... |
  10:17:37 34:15 > +0907 ..........|
  10:17:37 34:15 > +1043 ..........|*
  10:17:37 34:15 > +0816 ......... |
  10:17:37 34:15 > +0884 ......... |
     |       |       |     |
     |       |       |     + dots proportional to abs(latency)
     |       |       |       '.' used below threshold
     |       |       |       ' ' used as filler until threshold
     |       |       |       '|' is the threshold
     |       |       |       '*' is used after the threshold
     |       |       |           this typically means failure
     |       |       + latency value
     |       + relative time since start
     + wallclock time (requires '--start_time')
  ```
* `--start_time`: time (format: <hh:mm:ss>) when playback started. This is used
  in the ASCII plot to timestamp each latency. It can be used to correlate
  specific latencies to occurances in the device log.

* `--dots_per_usec`: how many ASCII dots are used per usec of latency.

The program exits with code:

* 0, if all the latencies are below 20 ms and no dropouts were detected,
* 1, if any latency is greater or equal 20 ms,
* 2, if any dropout is detected.

### Example 1

```
$ python ref.wav act.wav --print_percentiles

Percentiles (secs):
0%: 0.000000
50%: 0.000000
75%: 0.000000
90%: 0.004000
95%: 0.007000
99%: 0.009400
100%: 0.010000

$ echo $?
1
```

The latencies printed are the max absolute value of the delay, so a delay
of -0.1 seconds would be displayed as 0.1.

Naturally:

```
python ref.wav act.wav --print_percentiles

Percentiles (secs):
0%: 0.000000
50%: 0.000000
75%: 0.000000
90%: 0.000000
95%: 0.000000
99%: 0.000000
100%: 0.000000

$ echo $?
0
```

### Example 2

```
$ python audio_sync/cli.py ref.wav act.wav --parsable_output
{"dropouts": [[0.125125, 0.13075], [0.1385, 0.1445], [0.435125, 0.44075],
[0.4485, 0.4545], [0.5095000000000001, 0.9995], [1.025125, 1.03075], [1.0385,
1.0445], [1.0995000000000001, 1.5995], [1.625125, 1.63075], [1.6385, 1.6445],
[2.525125, 2.53075], [2.5385, 2.5445], [2.825125, 2.83075], [2.8385, 2.8445],
[3.125125, 3.13075], [3.1385, 3.1445]], "latencies": [[0.1495, 0.0], [0.4495,
-0.01], [0.7495, NaN], [1.0495, 0.0], [1.3495, NaN], [1.6495, 0.0], [2.5495,
0.0], [2.8495, 0.0], [3.1495, 0.0]]}
```

Dropouts and latencies are printed as a JSON object.

For latencies, the first element on each sub-list is the time in seconds
from the start of the recording and the second element is the latency measured.
For dropouts, the first element on each sub-list is the start time of the
dropout (in seconds from the start of the recording) and the second element
end time of the dropout.

### Example 3

```
$ python audio_sync/cli.py ref.wav act.wav --plot_timeline
Timeline:


........<.......<.......<.......<........<.......<.......<.......<....
             |             |             |             |             |
         0.51s         1.02s         1.53s         2.04s         2.55s

< = Act more than 0.020 secs behind ref
> = Act more than 0.020 secs ahead of ref
o = Dropout
. = 0.036 secs
```

The output shows a comparison over the time of the two audios:
- If latencies are below the specified threshold, a `.` is displayed.
- If the _actual_ signal is *behind* the reference signal by more than
  the specified threshold, a `<` will be displayed.
- If the _actual_ signal is *ahead* of the reference signal by more
  than the specified threshold, a `>` will be displayed.
- If there's a dropout, a `o` is displayed.

In the above example, the actual audio was behind at several
points. If the files are inverted

```
$ python audio_sync/cli.py act.wav ref.wav --plot_timeline
Timeline:

.....>.......>.......>........>.......>.......>.......>.......>.......
             |             |             |             |             |
         0.51s         1.02s         1.53s         2.04s         2.55s

< = Act more than 0.020 secs behind ref
> = Act more than 0.020 secs ahead of ref
o = Dropout
. = 0.035 secs
```

we can see an expected reversal of the latencies.

Unittests
---------

Unittests for all the modules can be run via the `audio_sync/run_unittests`
script.
