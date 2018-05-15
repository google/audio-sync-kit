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

r"""Audio sync measurement module.

This module is able to analyze two WAV files coming from a simultaneous
recording and calculate the latency of these two signals. These 2 signals
must have one peak every period and low volume noise or silence between
the peaks. See README.md for a description of how the algorithm works.
"""

import collections
import math

from audio_sync import wave_reader

# One half as named constant
HALF = 0.5
# Bit to Byte conversion
BITS_PER_BYTE = 8
# How many windows shall be evaluated as one chunk
WINDOWS_PER_CHUNK = 120
# Timegap to be seen as no gap
NO_GAP_TIME_SECS = 0.001

# Holder for the latency measurement settings values.
#
# period_secs: (float) distance in secs between two consecutive peaks.
# pulse_duration_secs: (float) Duration of the sine pulse in seconds.
# dropout_threshold: (float) Min peak value. All peak values below that will be
#   interpreted as dropout.
# silence_threshold: (float) Lowest volume level which is not interpreted as
#   silence.
# min_silence_len_secs: (float) minimum length of silence, so that it is
#   interpreted as such.
AnalysisSettings = collections.namedtuple(
    'AnalysisSettings', ['period_secs', 'pulse_duration_secs',
                         'dropout_threshold', 'silence_threshold',
                         'min_silence_len_secs'])


class InputSignalException(Exception):
  """Exception for invalid or not matching input signals."""
  pass


def _GetValueAndIndexForMax(data_array):
  """Helper function to get both max and argmax of a given array.

  Args:
    data_array: (list) array with the values.

  Returns:
    (tuple) containing max(data_array) and argmax(data_array).
  """
  value_max = max(data_array)
  ind_max = data_array.index(value_max)

  return (value_max, ind_max)


def _GetValueAndIndexForMin(data_array):
  """Helper function to get both min and argmin of a given array.

  Args:
    data_array: (list) array with the values.

  Returns:
    (tuple) containing min(data_array) and argmin(data_array).
  """
  value_min = min(data_array)
  ind_min = data_array.index(value_min)

  return (value_min, ind_min)


def _GetNextWinStart(data_array, samples_per_pulse, win_size,
                     dropout_threshold):
  """Helper function to compute the start index of the next valid window.

  The start index will be computed in such way, that the maximum value of the
  window will be at the center of the window. A valid window is a window:
    * containing both a maximum and a minimum which absolute values
      have to be greater then dropout_threshold constant.
    * the gap between maximum and minimum has to be less then
      samples_per_pulse samples.

  Args:
    data_array: (array of float) containing the PCM samples from [-1, 1].
    samples_per_pulse: (int) the max number of samples between min and max peak.
    win_size: (int) number of samples of one period of the reference signal.
    dropout_threshold: (float) Min peak value. All values below that will be
      interpreted as dropout.

  Returns:
    (int) index of the start of the window. There are three scenarios:
    - 0: If no valid pulse is found in |data_array|
    - Negative: If the pulse is located in data_array[0:win_size].
    - Positive: If the pulse is located in data_array[win_size:].
  """
  num_samples = len(data_array)

  ind_win_start = 0
  ind_win_max = None

  while ind_win_start < num_samples:
    ind_win_end = int(min(ind_win_start + win_size, num_samples))

    window = data_array[ind_win_start:ind_win_end]

    (value_win_max, ind_win_max) = _GetValueAndIndexForMax(window)
    (value_win_min, ind_win_min) = _GetValueAndIndexForMin(window)

    dropout_detected = (value_win_max < dropout_threshold or
                        abs(value_win_min) < dropout_threshold)
    pulse_too_long = abs(ind_win_min - ind_win_max) > samples_per_pulse

    if not ind_win_max or dropout_detected or pulse_too_long:
      ind_win_start = int(ind_win_start + math.floor(HALF * win_size))
    else:
      return int(ind_win_start + ind_win_max - math.floor(HALF * win_size))

  return 0


def _LookForDropoutsInWindow(data_array, samp_freq, window_offset,
                             silence_threshold, min_silence_len_secs):
  """Get silence periods inside the current window.

  This function returns a list of periods, for which the wave file contains
  silence. Only silence periods longer then MIN_SILENCE_LENGTH_MS are returned.
  All values in the range of +/- silence_threshold are interpreted as silence.

  Args:
    data_array: the window with the values.
    samp_freq: sampling frequency of the signal in Hz as integer.
    window_offset: the number of samples from start of the wave file until the
      beginning of the current window.
    silence_threshold: (float) Lowest volume level which is not interpreted as
      silence.
    min_silence_len_secs: (float) minimum length of silence, so that it is
      interpreted as such.
  Returns:
    (list of tuple(float, float)) timestamp of beginning and end of silence.
  """
  ret = []
  dropout_counter = -1
  current_dropout = None

  dropout_min_samples = min_silence_len_secs * samp_freq

  for index, value in enumerate(data_array):
    if abs(value) < silence_threshold:
      dropout_counter += 1
      # Dropout detected
      if dropout_counter > dropout_min_samples and not current_dropout:
        timestamp = float(window_offset + index - dropout_counter) / samp_freq
        current_dropout = timestamp
    # Dropout ended
    else:
      dropout_counter = -1
      if current_dropout:
        timestamp = float(window_offset + index) / samp_freq
        ret.append((current_dropout, timestamp))
        dropout_counter = -1
        current_dropout = None

  # Special case: Dropout extends beyond window range
  if current_dropout:
    timestamp = float(window_offset + len(data_array) - 1) / samp_freq
    ret.append((current_dropout, timestamp))

  return ret


def _IsInvalidWindow(latency_value):
  """Readability hepler for finding windows which delay cannot be determined.

  Args:
    latency_value: (tuple (float, float)) containing a timestamp and a delay
      value. Unit is seconds.

  Returns:
    True, if the corresponding window is invalid, False else.
  """
  return math.isnan(latency_value[1])


def _FindPeakOnActual(latency_value):
  """Find a peak on actual stream using timestamp of reference peak and delay.

  Args:
    latency_value: (tuple (float, float)) containing a timestamp and a delay
      value. Unit is seconds.

  Returns:
    (float) timestamp of the peak on the actual stream. Unit is seconds.
  """
  return latency_value[0] - latency_value[1]


def _LookForDropoutsInChunk(act_signal, win_size, samp_freq,
                            chunk_offset, latencies, silence_threshold,
                            min_silence_len_secs):
  """Find dropouts in actual signal.

  By using the knowledge about the testfiles used for latency measurement
  dropouts on the receiver can be found by finding periods of silence present
  in the parts of the actual signal, where the reference signal is playing
  correctly (i.e. a valid window as described in module doc comment is found in
  reference signal). This function is NOT able to detect dropouts in the
  reference signal. Further information about the implementation is available in
  'go/Multizone Test Detailed Design', section 'Dropout detection during sync
   measurement'.

  Args:
    act_signal: (list of float) actual signal normalized to [-1, 1].
    win_size: (int) number of samples of one period of the reference signal.
    samp_freq: (int) the sampling frequency of the audio signal in Hz.
    chunk_offset: (int) offset of the chunk within the WAV file. Used to
      determine the timestamp of each measurement point.
    latencies: (list of float) the latencies for the current chunk as computed
      by _ComputeLatencyInChunk().
    silence_threshold: (float) Lowest volume level which is not interpreted as
      silence.
    min_silence_len_secs: (float) minimum length of silence, so that it is
      interpreted as such.

  Returns:
    (list of tuple(float, float)) timestamp of beginning and end of silence.
  """
  ret = []
  long_dropout_start = None
  half_window_time = win_size * HALF / samp_freq

  # Initialize iterator
  latency_iterator = iter(latencies)
  curr_latency = next(latency_iterator, None)
  prev_latency = None
  end_reached = curr_latency is None

  # Iterate over latency values
  while not end_reached:
    # Type1: Long dropouts causing invalid windows
    if _IsInvalidWindow(curr_latency):
      # Special Case: If follower starts with dropout use reference's playback
      #   start time
      if prev_latency is None:
        long_dropout_start = curr_latency[0] - half_window_time
      # Normal case: For dropout in the middle use last known valid window
      else:
        long_dropout_start = (_FindPeakOnActual(prev_latency) +
                              half_window_time)
      # Move until next not-NaN (i.e. next valid window)
      while not end_reached and _IsInvalidWindow(curr_latency):
        prev_latency = curr_latency
        curr_latency = next(latency_iterator, None)
        end_reached = curr_latency is None

    # Check whether we reached the end or still have something to process
    if end_reached:
      # Special case: Handle long dropout until end of chunk
      if long_dropout_start is not None:
        long_dropout_end = float(chunk_offset + len(act_signal)) / samp_freq
        ret.append((long_dropout_start, long_dropout_end))
      return ret

    # We now have a valid window. Evaluate latency to determine where the
    #   corresponding window is supposed to be on actual
    peak_on_act = _FindPeakOnActual(curr_latency)

    # Handle end of long dropout using the beginning of the valid window
    if long_dropout_start is not None:
      long_dropout_end = peak_on_act - half_window_time
      ret.append((long_dropout_start, long_dropout_end))
      long_dropout_start = None

    # Type2: Short dropouts inside an otherwise valid window
    exp_act_win_start = int(peak_on_act * samp_freq - win_size * HALF)
    exp_act_win_end = min(exp_act_win_start + win_size, len(act_signal))

    # Special case: Handle chunk underflow
    if exp_act_win_start < 0:
      exp_act_win_start = 0

    ret += _LookForDropoutsInWindow(
        act_signal[exp_act_win_start:exp_act_win_end],
        samp_freq, chunk_offset + exp_act_win_start,
        silence_threshold, min_silence_len_secs)

    # Move to next latency value
    prev_latency = curr_latency
    curr_latency = next(latency_iterator, None)
    end_reached = curr_latency is None

  return ret


def _CollapseTimestampList(period_list):
  """Collapses a list of (begin, end) timestamps.

  This method will unify two consecutive items if begin of the first and end
  of the second (begin, end) tuple are similar enough. Similarity threshold is
  determined by NO_GAP_TIME_SECS constant.

  Args:
    period_list: (list of tuple(float, float)) list of timestamp tuples (begin,
      end) as float. Expected unit is seconds. The list has to be sorted
      smallest to biggest (i.e. earliest to latest).

  Returns:
    Nothing

  Sideeffects:
    period_list may change if two timestamp-tuples are united to a single one.
  """
  index = 1

  while index < len(period_list):
    time_diff = period_list[index][0] - period_list[index - 1][1]
    if time_diff < NO_GAP_TIME_SECS:
      unified = (period_list[index - 1][0], period_list[index][1])
      period_list[index - 1] = unified
      del period_list[index]
    else:
      index += 1


def _ComputeLatencyInChunk(ref_signal, act_signal, win_size,
                           samp_freq, chunk_offset, pulse_duration_secs,
                           dropout_threshold):
  """Computes the syncronicity difference of two audio signals.

  These audio signals have to be pulsed sine waves with period length
  (i.e. win_size) greater then 2 times the maximum expected latency.

  Args:
    ref_signal: (list of float) reference signal normalized to [-1, 1]..
    act_signal: (list of float) actual signal normalized to [-1, 1].
    win_size: (int) number of samples of one period of the reference signal.
    samp_freq: (int) the sampling frequency of the audio signal in Hz.
    chunk_offset: (int) offset of the chunk within the WAV file. Used to
      determine the timestamp of each measurement point.
    pulse_duration_secs: (float) Duration of the sine pulse in seconds.
    dropout_threshold: (float) Min peak value. All values below that will be
      interpreted as dropout.

  Returns:
    (list of tuple(float, float)) containing one (timestamp, delay_value)
      tuple per analyzed window (see win_size). timestamp (unit: seconds) gives
      the start time of the current window inside the recording. delay_value
      (unit: seconds) gives the delay (i.e. syncronicity difference) for the
      corresponding window. If a dropout is detected within the act signal a
      NaN value is added for this window. Dropouts within ref signal are
      ignored.
  """
  ret = []
  win_start_neg = False

  samples_per_pulse = pulse_duration_secs * samp_freq
  ind_win_start = _GetNextWinStart(
      ref_signal, samples_per_pulse, win_size, dropout_threshold)

  if ind_win_start < 0:
    win_start_neg = True

  # calculates the latency time per "win_size" samples
  while True:
    ind_win_end = ind_win_start + win_size - 1
    ind_win_start = max(ind_win_start, 0)

    if ind_win_end >= len(ref_signal):
      return ret

    (value_ref_max, ind_ref_max) = _GetValueAndIndexForMax(
        ref_signal[ind_win_start:ind_win_end])
    (value_act_max, ind_act_max) = _GetValueAndIndexForMax(
        act_signal[ind_win_start:ind_win_end])

    timestamp = (float(chunk_offset + ind_win_start + ind_ref_max) /
                 samp_freq)

    # See if we found something to compare with
    if value_ref_max > dropout_threshold:
      current_delay = float(ind_ref_max - ind_act_max) / samp_freq

      if value_act_max > dropout_threshold:
        ret.append((timestamp, current_delay))
      elif not win_start_neg:
        ret.append((timestamp, float('nan')))

    win_start_neg = False
    offset_win_next = _GetNextWinStart(
        ref_signal[ind_win_end:], samples_per_pulse, win_size,
        dropout_threshold)

    if not offset_win_next:
      return ret
    else:
      ind_win_start = int(ind_win_end + offset_win_next)


def DetermineLatenciesAndDropouts(ref_wave_reader, act_wave_reader, settings):
  """Determines the delay between act and ref wave signal and dropouts on act.

  The WAV files are evaluated not as a whole, but in chunks (see
  FRAMES_PER_CHUNK constant) to avoid using to large amounts of RAM for large
  files. Each chunk is passed to the evaluation functions separately.
  Note: Both files need to have the same samplerate!

  Args:
    ref_wave_reader: (WaveReader) reference signal.
    act_wave_reader: (WaveReader) actual signal
    settings: (AnalysisSettings) analysis settings.

  Returns:
    A 2-tuple:
    Element 0: (list of tuple(float, float)) a list of
      (<time_from_start_secs>, <delay_secs_of_act_from_ref>).
      time_from_start_secs is the location in the reference
      audio where a peak occurs and the delay is the time
      of how behind is the corresponding peak in the actual
      audio. Notice that a negative value indicates that
      the peak in the actual audio is *ahead* to the corresponding
      peak in the reference. Notice also that
      time_from_start_secs - delay_secs_of_act_from_ref
      yields the time of the peak in the actual audio.
    Element 1: (list of tuple(float, float)) a list of
      (<start_of_dropout>, <end_of_dropout>) (both values
      being seconds from the start of the reference audio)
      indicating locations where the reference signal has
      audio but not the actual one.

  Raises:
    InputSignalException: if the signals given to the function are not valid.
    This includes:
      * different sampling rate for the two signals.
  """
  # Samplerates must match
  samp_rate = ref_wave_reader.GetSamplingRate()
  if samp_rate != act_wave_reader.GetSamplingRate():
    raise InputSignalException('The samplerates of reference and actual '
                               'have to  be the same!\nCurrently I see '
                               'ref: %i, act: %i' % (
                                   samp_rate,
                                   act_wave_reader.GetSamplingRate()))

  position_frames_start = 0
  latencies = []
  dropouts = []

  samples_per_window = int(samp_rate * settings.period_secs)
  samples_per_chunk = WINDOWS_PER_CHUNK * samples_per_window
  chunk_offset = int(HALF * samples_per_window - 1)
  window_size_latency = int(0.9 * samples_per_window)
  sample_scaler = 2 ** (BITS_PER_BYTE * ref_wave_reader.GetSampleWidth() - 1)

  while position_frames_start < ref_wave_reader.GetNumberOfSamples():
    ref_wave_data = ref_wave_reader.ReadSamples(position_frames_start,
                                                samples_per_chunk)
    act_wave_data = act_wave_reader.ReadSamples(position_frames_start,
                                                samples_per_chunk)

    ref_chunk = wave_reader.Pcm2Float(ref_wave_data, sample_scaler).tolist()
    act_chunk = wave_reader.Pcm2Float(act_wave_data, sample_scaler).tolist()

    chunk_latencies = _ComputeLatencyInChunk(
        ref_chunk, act_chunk, window_size_latency,
        samp_rate, position_frames_start,
        settings.pulse_duration_secs,
        settings.dropout_threshold)

    dropouts += _LookForDropoutsInChunk(
        act_chunk, samples_per_window, samp_rate,
        position_frames_start, chunk_latencies,
        settings.silence_threshold,
        settings.min_silence_len_secs)

    latencies += chunk_latencies

    position_frames_start += samples_per_chunk - chunk_offset

  _CollapseTimestampList(dropouts)
  return latencies, dropouts
