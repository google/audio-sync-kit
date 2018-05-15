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

"""Functional tests for the latency measurement CLI."""
import json
import math
import os
import unittest

from audio_sync import cli


# Absolute path to the folder containing the handcrafted (ref, act) filepairs
TEST_DATA_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), 'test_data')

# Delay
DELAY1_PATH = os.path.join(TEST_DATA_DIR, 'latency_ref_2.wav')
DELAY2_PATH = os.path.join(TEST_DATA_DIR, 'latency_act_2.wav')
# Dropout
DROPOUT1_PATH = os.path.join(TEST_DATA_DIR, 'dropout_ref_0.wav')
DROPOUT2_PATH = os.path.join(TEST_DATA_DIR, 'latency_ref_1.wav')
CLI_PATH = cli.__file__
# Delay + dropout
DELAY_DROPOUT1_PATH = os.path.join(TEST_DATA_DIR, 'dropout_ref_0.wav')
DELAY_DROPOUT2_PATH = os.path.join(TEST_DATA_DIR, 'dropout_act_1.wav')


def _RunCli(*args):
  output = []
  orig_print = cli._Print
  # pylint: disable=unnecessary-lambda
  cli._Print = lambda message: output.append(message)
  try:
    try:
      cli._Main(['--period', '0.3'] + list(args))
    except SystemExit as e:
      return e.code, '\n'.join(output)
    raise Exception('Program did not exit properly.')
  finally:
    cli._Print = orig_print


def _AssertDropoutListIsValid(dropout_list):
  for i, dropout in enumerate(dropout_list):
    assert len(dropout) == 2, 'Invalid dropout %s at index %d.' % (dropout, i)
    try:
      float(dropout[0])
      float(dropout[1])
    except TypeError:
      raise AssertionError('Invalid dropout %s at index %d.' % (dropout, i))


class LatencyMeasurementCliExitCodesTest(unittest.TestCase):
  """Tests to verify exit codes from the latency measurement CLI."""

  def testExitCodeWhenMissingParams(self):
    """Verifies code when there are errors in the arguments."""
    exit_code, _ = _RunCli()
    self.assertEqual(exit_code, 127)

  def testSuccessExitCode(self):
    """Verifies code when latencies < threshold and no dropouts."""
    exit_code, _ = _RunCli(DELAY1_PATH, DELAY1_PATH)
    self.assertEqual(exit_code, 0)

  def testLatencyThresholdExceededExitCode(self):
    """Verifies code when there are latencies > threshold and no dropouts."""
    exit_code, _ = _RunCli(DELAY1_PATH, DELAY2_PATH)
    self.assertEqual(exit_code, 1)

  def testLatencyThresholdExceededAndDropoutExitCode(self):
    """Verifies code when there are latencies > threshold and dropouts."""
    exit_code, _ = _RunCli(DELAY_DROPOUT1_PATH, DELAY_DROPOUT2_PATH)
    self.assertEqual(exit_code, 1)

  def testDropoutExitCode(self):
    """Verifies code when there are dropouts and no latencies > threshold."""
    exit_code, _ = _RunCli(DROPOUT1_PATH, DROPOUT2_PATH)
    self.assertEqual(exit_code, 2)


class LatencyMeasurementCliCalculatePercentilesTest(unittest.TestCase):
  """Tests for the CalculatePercentiles function."""

  def _GenerateLatencies(self, n=10):
    return [(n - abs(x), x * -0.1) for x in xrange(-n, 0)]

  def _AssertLatencyPercentilesAreEqual(self, expected_arr, actual_arr):
    for expected, actual in zip(expected_arr, actual_arr):
      self.assertEqual(expected[0], actual[0])
      self.assertAlmostEqual(expected[1], actual[1])

  def testMixedDelays(self):
    """Verifies percentiles when latency values are positive and negative."""
    latencies = self._GenerateLatencies()
    percentiles = cli.CalculatePercentiles(latencies)
    self._AssertLatencyPercentilesAreEqual(
        [(0, 0.1), (50, 0.55), (75, 0.775), (90, 0.91),
         (95, 0.955), (99, 0.991), (100, 1.0)],
        percentiles)

  def testNoLatencies(self):
    """Verifies percentiles when there are not latency values."""
    percentiles = cli.CalculatePercentiles([])
    expected_percentiles = [0, 50, 75, 90, 95, 99, 100]
    for actual, expected in zip(percentiles, expected_percentiles):
      self.assertEqual(actual[0], expected)
      self.assertTrue(math.isnan(actual[1]))


class LatencyMeasurementCliOutputTest(unittest.TestCase):
  """Tests to verify the output from the latency measurement CLI."""

  def testPrintParsableOutput(self):
    """Verifies output is a valid JSON with --parsable_output."""
    _, output = _RunCli(DELAY1_PATH, DELAY1_PATH, '--parsable_output')
    json_output = json.loads(output)
    self.assertIn('dropouts', json_output)
    self.assertIn('latencies', json_output)

  def testPrintStats(self):
    """Verifies stats are printed with --print_percentiles."""
    _, output = _RunCli(DELAY1_PATH, DELAY1_PATH, '--print_percentiles')
    self.assertNotEqual(output, '')

# TODO(omarestrada): Check that specifying other audio parameters work.


if __name__ == '__main__':
  unittest.main()
