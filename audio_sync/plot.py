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

import logging


CONDITION_NONE = '.'
CONDITION_DROPOUT = 'o'
CONDITION_NEGATIVE_LATENCY_EXCEEDED = '>'
CONDITION_POSITIVE_LATENCY_EXCEEDED = '<'
NUM_CONDITIONS = 3


def _Intersects(range1, range2):
  """Tells if two number ranges intersect.

  Args:
    range1: (tuple(num, num)) tuple representing a range. The
      first number must be <= the second number.
    range2: (tuple(num, num)) tuple representing a range. The
      first number must be <= the second number.

  Returns:
    True if the ranges intersect False otherwise.

  Raises:
    ValueError: if the ranges are invalid.
  """
  if range1[0] > range1[1]:
    raise ValueError('range1 is inverted.')
  if range2[0] > range2[1]:
    raise ValueError('range2 is inverted.')
  return not (range1[1] <= range2[0] or range1[0] >= range2[1])


def GetConditionsInTimeframe(
    latencies, dropouts, timeframe_secs, num_intervals, latency_threshold_secs):
  """Gets the list of conditions occurring during the specified timeframe.

  Args:
    latencies: (list of 2-tuple) latencies measured during the timeframe.
    dropouts: (list of 2-tuple) dropouts detected during the timeframe.
    timeframe_secs: (float) duration of the timeframe.
    num_intervals: (int) number of intervals to split the timeframe.
    latency_threshold_secs: (float) Latencies greater than this threshold
      are flagged as invalid.

  Returns:
    (list of sets) a list of |num_intervals| sets specifying the
    conditions that occurred in each interval.
  """
  interval_secs = timeframe_secs / num_intervals
  i = j = 0
  t = 0.0
  timeline = []
  for _ in xrange(num_intervals):
    next_t = t + interval_secs
    conditions = set()

    # Check latencies.
    while (i < len(latencies) and
           latencies[i][0] >= t and
           latencies[i][0] < next_t):
      delay = latencies[i][1]
      if delay == float('nan'):
        continue
      if delay > latency_threshold_secs:
        conditions.add(CONDITION_POSITIVE_LATENCY_EXCEEDED)
      elif delay < -latency_threshold_secs:
        conditions.add(CONDITION_NEGATIVE_LATENCY_EXCEEDED)
      i += 1

    # Check dropouts.
    while j < len(dropouts):
      if _Intersects(dropouts[j], (t, next_t)):
        conditions.add(CONDITION_DROPOUT)
      if dropouts[j][1] >= next_t:
        break
      j += 1

    if not conditions:
      conditions.add(CONDITION_NONE)

    logging.debug('Found conditions %s within interval [%f, %f).',
                  str(conditions), t, next_t)

    timeline.append(conditions)
    t = next_t
  return timeline


def GetPlotString(conditions_timeline, timeline_secs, num_ticks):
  """Gets a string representing the plot of the timeline.

  Args:
    conditions_timeline: (list of sets) a list of sets
      specifying the conditions that occurred in each interval.
    timeline_secs: (float) duration of the timeline.
    num_ticks: (int) number of ticks to plot in the timeline.

  Returns:
    (string) a string representing the timeline.

  Raises:
    ValueError: if the length of the timeline is not a multiple of
      |num_ticks|.
  """
  num_intervals = len(conditions_timeline)
  if num_intervals % num_ticks != 0:
    raise ValueError('num_intervals (%d) mod num_ticks (%d) must be 0.' % (
        num_intervals, num_ticks))
  # Conditions.
  conditions_list = [
      ' ' * (NUM_CONDITIONS - len(x)) + ''.join(x) for x in conditions_timeline
  ]
  # Ticks.
  dots_per_tick = num_intervals // num_ticks
  padding = ' ' * (dots_per_tick - 1)
  ticks_line = (padding + '|') * num_ticks
  # Times.
  tick_duration_secs = timeline_secs / num_ticks
  times = []
  for i in xrange(1, num_ticks + 1):
    t_str = '%.2fs' % (i * tick_duration_secs)
    times.append((dots_per_tick - len(t_str)) * ' ' + t_str)
  times_line = ''.join(times)
  return '\n'.join(
      [''.join(x) for x in zip(*conditions_list)] + [ticks_line] + [times_line])
