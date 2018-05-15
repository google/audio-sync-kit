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

"""Functional tests for the plot module."""

import unittest

from audio_sync import plot


class IntersectsTest(unittest.TestCase):

  def _CheckIntersection(self, expected_val, range1, range2):
    self.assertEqual(expected_val, plot._Intersects(range1, range2))
    self.assertEqual(expected_val, plot._Intersects(range2, range1))

  def testInvalidRange(self):
    with self.assertRaises(ValueError):
      plot._Intersects((2, 1), (1, 2))
    with self.assertRaises(ValueError):
      plot._Intersects((1, 2), (2, 1))
    with self.assertRaises(ValueError):
      plot._Intersects((1, 2), (1, -2))
    with self.assertRaises(ValueError):
      plot._Intersects((1, -2), (1, 2))

  def testIntersection(self):
    self._CheckIntersection(True, (1, 2), (1, 3))  # Containment.
    self._CheckIntersection(True, (1, 3), (2, 3))  # Right overlap.
    self._CheckIntersection(True, (1, 3), (0, 2))  # Left overlap.

  def testNegativeIntersection(self):
    self._CheckIntersection(True, (-1, 2), (-2, 3))  # Containment.
    self._CheckIntersection(True, (-1, 3), (2, 4))  # Right overlap.
    self._CheckIntersection(True, (-3, -1), (-5, -2))  # Left overlap.

  def testNoIntersection(self):
    self._CheckIntersection(False, (1, 3), (4, 5))
    self._CheckIntersection(False, (1, 3), (3, 4))  # Boundaries


class PlotTest(unittest.TestCase):

  def testGetTimeline(self):
    latencies = [
        (0.1495, -0.0111875), (0.4495, 0.0), (0.7495, 0.0),
        (1.0495, 0.026), (1.3495, -0.04375), (1.6495, float('nan'))]
    dropouts = [
        (0.1999, 0.2106), (1.3432, 1.375), (1.4432, 1.95)]
    conditions = plot.GetConditionsInTimeframe(
        latencies, dropouts, 2.0, 40, 0.02)
    self.assertEqual(
        ''.join(*zip(*conditions)),
        '...oo...............<.....ooooooooooooo.')


if __name__ == '__main__':
  unittest.main()
