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
  parser.add_argument('--print_percentiles', default=False, action='store_true',
                      help='Print latency percentiles.')
  parser.add_argument('--plot_timeline', default=False, action='store_true',
                      help=('Plot the conditions in a timeline.'))
  parser.add_argument('--latency_threshold', type=float, default=0.02,
                      help=('Latencies equal or greater than this threshold '
                            'are considered excessive.'))
  return parser.parse_args(args)


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
    latency_threshold_secs=0.02):
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
    percentiles = CalculatePercentiles(latencies)
    max_latency = percentiles[-1][1]

    if args.parsable_output:
      _Print(json.dumps({'latencies': latencies, 'dropouts': dropouts}))
    else:
      if args.plot_timeline:
        duration_secs = _GetWaveDurationSecs(args.ref_wav_path)
        _PlotResults(duration_secs, latencies, dropouts,
                     latency_threshold_secs=args.latency_threshold)
      if args.print_percentiles:
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
