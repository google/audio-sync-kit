# Copyright 2016 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

"""CLI to measure latencies between two audio signals."""
from __future__ import division
from __future__ import print_function

import argparse
import datetime
import json
import logging
import math
import sys
import wave

import audio_sync
from audio_sync import analyzer
from audio_sync import plot
import numpy


EXIT_CODE_UNKNOWN_ERROR = 255
EXIT_CODE_ARGS_PARSE_ERROR = 127
EXIT_CODE_SUCCESS = 0
EXIT_CODE_LATENCIES_ABOVE_THRESHOLD = 1
EXIT_CODE_DROPOUTS_DETECTED = 2

VERY_LARGE_LATENCY_USEC = 10000

SECS_IN_MSEC = 1000
SECS_IN_USEC = 1000000


def ParseArgs(args):
  """Helper function for command line parameter parsing.

  Args:
    args: (list of str) arguments passed to CLI.

  Returns:
    The parsed parameters.
  """
  parser = argparse.ArgumentParser(description='Measure latency.')
  parser.add_argument('--debug', default=False, action='store_true',
                      help='Enable debug output.')
  parser.add_argument('ref_wav_path',
                      help='Path to the reference .wav file.')
  parser.add_argument('act_wav_path',
                      help='Path to the actual .wav file.')
  parser.add_argument('--period', type=float, default=0.1,
                      help='Fundamental period of audio files (secs).')
  parser.add_argument('--pulse_length', type=float, default=0.002,
                      help='Duration of pulse in audio files (secs).')
  parser.add_argument('--dropout_threshold', type=float, default=0.3,
                      help=('Dropout threshold, every peak below will be '
                            'interpreted as dropout. Range: [0.0, 1.0]'))
  parser.add_argument('--silence_threshold', type=float, default=0.05,
                      help=('Silence threshold, every value below will be '
                            'interpreted as silence. Range: [0.0, 1.0]'))
  parser.add_argument('--min_silence_length', type=float, default=0.005,
                      help=('Minimum length of silence (secs). Silences '
                            'below this duration will be ignored.'))
  parser.add_argument('--parsable_output', default=False, action='store_true',
                      help='Print latencies and dropouts as a JSON string.')
  parser.add_argument('--print_stats', default=False, action='store_true',
                      help='Print latencies stats (max, min, and average).')
  parser.add_argument('--print_percentiles', default=False, action='store_true',
                      help='Print latency percentiles.')
  parser.add_argument('--plot_timeline', default=False, action='store_true',
                      help=('Plot the conditions in a timeline.'))
  parser.add_argument('--latency_threshold', type=float, default=0.001,
                      help=('Latencies equal or greater than this threshold '
                            'are considered excessive.'))
  parser.add_argument('--plot_ascii_graph', default=False, action='store_true',
                      help=('Plots all latencies as ASCII art.'))
  parser.add_argument('--start_time', default='00:00:00',
                      help=('hh:mm:ss of when playback started.'))
  parser.add_argument('--dots_per_msec', type=int, default='10',
                      help=('How many ASCII dots are used per msec of '
                        'latency.'))
  return parser.parse_args(args)


def GetStats(latencies):
  """Gets latency stats.

  Args:
    latencies: (list) list of 2-tuples (<time>, <latency>).

  Returns:
    A 3-tuple:
      Element 1: (float) max latency in seconds.
      Element 2: (float) min latency in seconds.
      Element 3: (float) mean latency in seconds.
  """
  values = [d for _, d in latencies if not math.isnan(d)]
  if values:
    # The max, min, and avg should be based on absolute values (otherwise,
    # we could report that -0.1 is greater than -0.2, which is misleading),
    # but we still need to show the signed value so users can tell if the
    # signal was ahead or behind.
    return (max(values, key=abs),
            min(values, key=abs),
            numpy.mean(values))
  else:
    return float('NaN'), float('NaN'), float('NaN')


def CalculatePercentiles(latencies, percentiles=(0, 50, 75, 90, 95, 99, 100)):
  """Calculates the latency percentiles.

  Args:
    latencies: (list) list of 2-tuples (<time>, <latency>).
    percentiles: (tuple) tuple containing the percentiles to calculate.

  Returns:
    A list of the form [(<percentile>, abs(<value>)), ...] for each of
    the percentiles requested.
  """
  values = [d for _, d in latencies if not math.isnan(d)]
  if values:
    vals = numpy.percentile(sorted([abs(v) for v in values]),
                            percentiles).tolist()
    return zip(percentiles, vals)
  else:
    return zip(percentiles, (float('NaN'),) * 7)


def _Print(message):
  """Prints |message| to standard output."""
  print(message)


def _PlotResults(
    duration_secs, latencies, dropouts, num_ticks=5, num_dots=70,
    latency_threshold_secs=0.001):
  """Plots the results in a text timeline."""
  duration_secs = float(duration_secs)

  conditions_timeline = plot.GetConditionsInTimeframe(
      latencies, dropouts, duration_secs, num_dots, latency_threshold_secs)

  output = (
      'Timeline:\n'
      '%s\n\n'
      '< = Act more than %.3f secs behind ref\n'
      '> = Act more than %.3f secs ahead of ref\n'
      'o = Dropout\n'
      '. = %.3f secs\n') % (
          plot.GetPlotString(conditions_timeline, duration_secs, num_ticks),
          latency_threshold_secs,
          latency_threshold_secs,
          duration_secs / num_dots
      )
  print(output)


def _PlotAsciiGraph(
    latencies, start_time, dots_per_msec=10, latency_threshold_secs=0.001):
  """Plots all latencies with timestamp in an ASCII timeline.

  Args:
    latencies: (list) list of 2-tuples (<time>, <latency>).
    start_time: (datetime) time the capture of the .wav files started.
     dots_per_msec: (int) How many ASCII dots to use per msec of latency.
     latency_threshold_secs: (float) latencies equal or greater than this
         threshold are considered excessive and are marked with a '*'.
  """
  if dots_per_msec < 0:
    raise ValueError('Invalid dots_per_msec %d.' % dots_per_msec)

  if latency_threshold_secs < 0:
    raise ValueError('Invalid latency_threshold_secs %d.' % (
      latency_threshold_secs))

  threshold_in_dots = int(latency_threshold_secs * SECS_IN_MSEC * dots_per_msec)
  for latency in latencies:
    if math.isnan(latency[1]):
      usecs = VERY_LARGE_LATENCY_USEC
    else:
      usecs = SECS_IN_USEC * latency[1]
    msecs = usecs / 1000
    dots_total = int(abs(msecs) * dots_per_msec)
    dots_below_threshold = min(dots_total, threshold_in_dots)
    filler_spaces_until_thresh = threshold_in_dots - dots_below_threshold
    out_str = '.'*dots_below_threshold + ' '*filler_spaces_until_thresh + '|'
    if dots_total > threshold_in_dots:
      dots_above_thresh = dots_total - threshold_in_dots
      out_str += '*' * dots_above_thresh
    total_secs = int(latency[0])
    time_h = (int)(total_secs / 60)
    time_m = (int)(total_secs % 60)
    t = datetime.timedelta(seconds=total_secs)
    print((start_time + t).strftime('%H:%M:%S'),
      '%2.2d:%2.2d > %+4.4d %s' % (time_h, time_m, usecs, out_str))

  values = [d for _, d in latencies if not math.isnan(d)]
  if values:
    avg = numpy.mean(values)
    print("\navg[%d]=%.6f\n" % (len(values), avg))


def _PrintPercentiles(percentiles):
  """Prints the percentiles to standard output."""
  output = '\n'.join([
      '%d%%: %.6f' % p for p in percentiles])
  _Print('Percentiles (secs):\n' + output)


def _GetWaveDurationSecs(wav_path):
  """Gets the duration in secs of the WAV file."""
  wav = wave.open(wav_path)
  try:
    return wav.getnframes() / (wav.getnchannels() * wav.getframerate())
  finally:
    wav.close()


def _Main(args):
  """Parses options and shows results."""
  try:
    args = ParseArgs(args)
  except SystemExit:
    sys.exit(EXIT_CODE_ARGS_PARSE_ERROR)

  if args.debug:
    logging.basicConfig(level=logging.DEBUG)

  try:
    settings = analyzer.AnalysisSettings(
        args.period, args.pulse_length, args.dropout_threshold,
        args.silence_threshold, args.min_silence_length)
    latencies, dropouts = audio_sync.AnalyzeAudios(
        args.ref_wav_path, args.act_wav_path, settings)
    max_latency, min_latency, avg_latency = GetStats(latencies)

    if args.parsable_output:
      _Print(json.dumps({'latencies': latencies, 'dropouts': dropouts}))
    else:
      if args.plot_ascii_graph:
        try:
          start_time = datetime.datetime.strptime(args.start_time, "%H:%M:%S")
        except ValueError:
          sys.exit(EXIT_CODE_ARGS_PARSE_ERROR)
        _PlotAsciiGraph(latencies, start_time, dots_per_msec=args.dots_per_msec,
                        latency_threshold_secs=args.latency_threshold)
      duration_secs = _GetWaveDurationSecs(args.ref_wav_path)
      if args.plot_timeline:
        _PlotResults(duration_secs, latencies, dropouts,
                     latency_threshold_secs=args.latency_threshold)
      if args.print_stats:
        _Print('Max latency: %f secs' % max_latency)
        _Print('Min latency: %f secs' % min_latency)
        _Print('Mean latency: %f secs\n' % avg_latency)
      if args.print_percentiles:
        percentiles = CalculatePercentiles(latencies)
        _PrintPercentiles(percentiles)

    if abs(max_latency) >= args.latency_threshold:
      sys.exit(EXIT_CODE_LATENCIES_ABOVE_THRESHOLD)
    elif dropouts:
      sys.exit(EXIT_CODE_DROPOUTS_DETECTED)
    else:
      sys.exit(EXIT_CODE_SUCCESS)
  except Exception:  # pylint: disable=broad-except
    logging.exception('')
    sys.exit(EXIT_CODE_UNKNOWN_ERROR)


def main():
  _Main(sys.argv[1:])


if __name__ == '__main__':
  main()
