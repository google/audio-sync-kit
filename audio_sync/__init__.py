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

"""Package to measure audio sync."""
import wave

from audio_sync import analyzer
from audio_sync import wave_reader


DEFAULT_TEST_AUDIO_SETTINGS = analyzer.AnalysisSettings(
    period_secs=0.1,
    pulse_duration_secs=0.002,
    dropout_threshold=0.5,
    silence_threshold=0.05,
    min_silence_len_secs=0.001)


def AnalyzeAudios(ref_signal_path, act_signal_path,
                  settings=DEFAULT_TEST_AUDIO_SETTINGS):
  """Get the latencies between the given files.

  Args:
    ref_signal_path: (string) absolute path to handcrafted reference file.
    act_signal_path: (string) absolute path to handcrafted actual file.
    settings: (AnalysisSettings) the properties of the audio
      played by the sources.

  Returns:
    A 2-tuple:
    - Element 0: (list of tuple(float, float)) measured latencies with the
      format (<time>, <latency>).
    - Element 1: (list of tuple(float, float)) detected dropouts with the
      format (<dropout_start_secs>, <dropout_end_secs>).
  """
  ref_wave_reader = wave_reader.WaveReader(wave.open(ref_signal_path))
  act_wave_reader = wave_reader.WaveReader(wave.open(act_signal_path))

  try:
    return analyzer.DetermineLatenciesAndDropouts(
        ref_wave_reader, act_wave_reader, settings)
  finally:
    act_wave_reader.Close()
    ref_wave_reader.Close()
