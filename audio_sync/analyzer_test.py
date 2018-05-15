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

"""Test module for latency_measurement."""

import math
import os
import unittest
import wave

from audio_sync import analyzer
from audio_sync import wave_reader
import numpy

# Absolute path to the folder containing the handcrafted (ref, act) filepairs
TEST_DATA_DIR_ABS_PATH = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), 'test_data')

# Handcrafted unittest files
REF_WAV_0 = 'latency_ref_0.wav'
REF_WAV_1 = 'latency_ref_1.wav'
REF_WAV_2 = 'dropout_ref_0.wav'
REF_WAV_3 = REF_WAV_2
REF_WAV_4 = 'dropout_ref_1.wav'
REF_WAV_5 = 'latency_ref_2.wav'
REF_WAV_6 = 'latency_ref_3.wav'

ACT_WAV_0 = 'latency_act_0.wav'
ACT_WAV_1 = 'latency_act_1.wav'
ACT_WAV_2 = 'dropout_act_0.wav'
ACT_WAV_3 = 'dropout_act_1.wav'
ACT_WAV_4 = ACT_WAV_3
ACT_WAV_5 = 'latency_act_2.wav'
ACT_WAV_6 = 'latency_act_3.wav'

SILENT_WAV = 'silence.wav'


# The expected results
EXPECTED_LATENCIES_0 = [(0.15, 0.0),
                        (0.45, -0.01),
                        (0.75, float('nan')),
                        (1.05, 0.0),
                        (1.35, 0.1),
                        (1.65, 0.0),
                        (2.55, 0.0),
                        (2.85, 0.0),
                        (3.15, 0.0)]
EXPECTED_LATENCIES_1 = EXPECTED_LATENCIES_0
EXPECTED_LATENCIES_2 = 0.105
EXPECTED_LATENCIES_3 = 0.1

EXPECTED_DROPOUTS_0 = [(0.6, 0.65),
                       (1.125, 1.375),
                       (1.5, 1.95),
                       (2.15, 2.45),
                       (2.7, 3.3)]
EXPECTED_DROPOUTS_1 = [(0, 0.725)]
EXPECTED_DROPOUTS_2 = [(0.3, 0.725)]

# The desired precision of (timestamp, delay). Needed for gracefully handling
# different samplerates and numeric errors
PRECISION = [2, 3]


TESTFILE_FUND_PERIOD_SEC = 0.3
TESTFILE_PULSE_DURATION_SEC = 0.002
DROPOUT_TRESHOLD = 0.6
SILENCE_TRESHOLD = 0.05
MIN_SILENCE_LENGTH_SEC = 0.005


def _GetLatencies(ref_signal_path, act_signal_path):
  """Get the latencies between the given files.

  Args:
    ref_signal_path: (string) absolute path to handcrafted reference file.
    act_signal_path: (string) absolute path to handcrafted actual file.

  Returns:
    (list of tuple(float, float)) latency values with timestamps.
  """
  ref_wave_reader = wave_reader.WaveReader(wave.open(ref_signal_path))
  act_wave_reader = wave_reader.WaveReader(wave.open(act_signal_path))

  try:
    settings = analyzer.AnalysisSettings(
        TESTFILE_FUND_PERIOD_SEC, TESTFILE_PULSE_DURATION_SEC, DROPOUT_TRESHOLD,
        SILENCE_TRESHOLD, MIN_SILENCE_LENGTH_SEC)
    return analyzer.DetermineLatenciesAndDropouts(
        ref_wave_reader, act_wave_reader, settings)
  finally:
    act_wave_reader.Close()
    ref_wave_reader.Close()


class LatencyMeasurementTest(unittest.TestCase):
  """Basic functionallity UnitTests for the latency_measurement module."""

  def _CompareHandcraftedLatencyFiles(self, ref_signal_path, act_signal_path,
                                      expected_latencies):
    """Compares one pair of (ref, act) signals with predefined latency results.

    This helper function evaluates the latency of a given (ref, act) filepair
    and compares the latency values returned by the latency_measurement module
    with predefined expected results. Since we compare float values for numeric
    reasons we cannot expect the results to be totally accurate. Therefore only
    the first 2 decimal digits are checked for timestamps, while 3 decimal
    digits are checked for the latency values.

    Args:
      ref_signal_path: (string) absolute path to handcrafted reference file.
      act_signal_path: (string) absolute path to handcrafted actual file.
      expected_latencies: (list of tuple (float, float)) the expected latencies
        between the handcrafted files as (timestamp, delay). Unit is seconds.
    """
    delay, _ = _GetLatencies(ref_signal_path, act_signal_path)

    # Check values
    self.assertEquals(len(delay), len(expected_latencies))
    for i in range(len(expected_latencies)):
      for j in range(len(expected_latencies[0])):
        # Dropout on actual
        if math.isnan(expected_latencies[i][j]):
          self.assertTrue(math.isnan(delay[i][j]))
        # Valid point
        else:
          numpy.testing.assert_almost_equal(
              expected_latencies[i][j], delay[i][j], PRECISION[j])

  def testDetermineLatenciesAndDropouts_8kHz_S32L(self):
    """Checks the basic functionallity of the latency_measurement module.

    These basic checks are:
      * shifts of actual signal in respect to reference
      * handling of dropouts on both actual and reference
      * handling of 8kHz, signed 32Bit LE wave files
    """
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_0)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_0)

    self._CompareHandcraftedLatencyFiles(ref_signal_path, act_signal_path,
                                         EXPECTED_LATENCIES_0)

  def testDetermineLatenciesAndDropouts_48kHz_S16L(self):
    """Checks the basic functionallity of the latency_measurement module.

    These basic checks are:
      * shifts of actual signal in respect to reference
      * handling of dropouts on both actual and reference
      * handling of 48kHz, signed 16Bit LE wave files
    """
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_1)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_1)

    self._CompareHandcraftedLatencyFiles(ref_signal_path, act_signal_path,
                                         EXPECTED_LATENCIES_1)

  def testFollowerPeakBeforeRecordingStart(self):
    """Tests latencys if first window of follower has no peak."""
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_5)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_5)

    delay, _ = _GetLatencies(ref_signal_path, act_signal_path)

    for d in delay:
      self.assertAlmostEqual(EXPECTED_LATENCIES_2, d[1], places=3)

  def testFollowerPeakInPreviousChunk(self):
    """Tests latencys with leader and follower peak on different chunks."""
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_6)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_6)

    delay, _ = _GetLatencies(ref_signal_path, act_signal_path)

    for d in delay:
      self.assertAlmostEqual(EXPECTED_LATENCIES_3, d[1], places=3)

  def testExceptionOnDifferentSamplerates(self):
    """Checks if different samplerates for the signals are rejected.

    The latency measurement module is expected to raise an exception if the
    sampling frequency of the two input signals are not the same.
    """
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_1)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_0)

    with self.assertRaises(analyzer.InputSignalException):
      _GetLatencies(ref_signal_path, act_signal_path)

  # test normalization of the signals
  # test signals with an invalid sine pulse
  # test signals with silence in the borderline


class DropoutDetectionTest(unittest.TestCase):
  """Tests for dropout detection of the latency_measurement module."""

  def _CompareHandcraftedDropoutFiles(self, ref_signal_path, act_signal_path,
                                      expected_dropouts):
    """Compares one pair of (ref, act) signals with predefined dropout results.

    This helper function evaluates the dropouts on a given (ref, act) filepair
    and compares the dropout values returned by the latency_measurement module
    with predefined expected results. Since we compare float values for numeric
    reasons we cannot expect the results to be totally accurate. Therefore only
    the first 2 decimal digits are checked.

    Args:
      ref_signal_path: (string) absolute path to handcrafted reference file.
      act_signal_path: (string) absolute path to handcrafted actual file.
      expected_dropouts: (list of tuple (float, float)) the expected dropouts
        on the actual file as (timestamp_start, timestamp_end). Unit is seconds.
    """
    _, dropouts = _GetLatencies(ref_signal_path, act_signal_path)

    # Check values
    self.assertEquals(len(dropouts), len(expected_dropouts))
    for i, dropout in enumerate(expected_dropouts):
      for j in range(2):
        numpy.testing.assert_almost_equal(
            dropout[j], dropouts[i][j], PRECISION[0])

  def testDropoutDetection(self):
    """Basic checks for dropout detection of latency_measurement module.

    These basic checks are:
      * detection of short dropouts
      * detection of long (i.e. more then one window) dropouts
      * no false positive on expected silence (i.e. track change, resync)
      * dropout until playback end
    """

    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_2)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_2)

    self._CompareHandcraftedDropoutFiles(ref_signal_path, act_signal_path,
                                         EXPECTED_DROPOUTS_0)

  def testDropoutDetectionOnFollowerSilentBegin(self):
    """Cornercase: follower is silent at the beginning of the recording.

    This function checks the right handling of silence on follower on playback
    start (i.e. follower needs some time to join the leader) by the dropout
    detection mechanism.
    """
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_3)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_3)

    self._CompareHandcraftedDropoutFiles(ref_signal_path, act_signal_path,
                                         EXPECTED_DROPOUTS_1)

  def testDropoutDetectionOnBothSilentBegin(self):
    """Cornercase: leader and follower silent at the beginning of the recording.

    This function checks the right handling of silence on both leader and
    follower on playback start (i.e. both leader and follower need some time to
    start playing back) by the dropout detection mechanism.
    """
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_4)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, ACT_WAV_4)

    self._CompareHandcraftedDropoutFiles(ref_signal_path, act_signal_path,
                                         EXPECTED_DROPOUTS_2)

  def testDropoutDetectionOnSilentLeader(self):
    """Cornercase: leader is silent, yet follower is playing.

    In this scenario no dropouts shall be reported, since the module relies on
    the correctness of the reference signal. This scenartio can be detected by
    empty latency list.
    """
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, SILENT_WAV)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, REF_WAV_0)

    self._CompareHandcraftedDropoutFiles(ref_signal_path, act_signal_path, [])

  def testDropoutDetectionOnBothSilent(self):
    """Cornercase: both leader and follower are silent.

    In this scenario no dropouts shall be reported, since the module relies on
    the correctness of the reference signal. This scenartio can be detected by
    empty latency list.
    """
    ref_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, SILENT_WAV)
    act_signal_path = os.path.join(TEST_DATA_DIR_ABS_PATH, SILENT_WAV)

    self._CompareHandcraftedDropoutFiles(ref_signal_path, act_signal_path, [])

if __name__ == '__main__':
  unittest.main()
