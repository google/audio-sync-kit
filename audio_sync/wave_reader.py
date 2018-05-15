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

"""Module to read wave files."""
import os
import struct
import wave

import numpy


class Error(Exception):
  pass


def _StringOfPackedNumberToList(string, format_char):
  """Converts numbers packed in a string to an array.

  Encoded integers are assumed to be little-endian.

  Args:
    string: (string) string containing packed little-endian numbers.
    format_char: (string) format char of the numbers packed in the string.
      Uses the same format strings as struct.unpack().

  Returns:
    (list) A list of numbers unpacked from the string.
  """
  # Need to specify the endianess as, for example,
  # struct.calcsize('l') == 8 while struct.calcsize('<l') == 4.
  count = len(string) / struct.calcsize('<%s' % format_char)
  format_string = '<%d%s' % (count, format_char)
  return list(struct.unpack(format_string, string))


def _GetFormatCharForStructUnpack(int_width):
  """Gets the sample's integer format char to use with struct.unpack.

  It is assumed that 1-byte width samples are unsigned, all other
  sizes are signed.

  Args:
    int_width: (int) width of the integer in bytes. Can be 1, 2, or 4.

  Returns:
    The format char corresponding to the int described by the
    arguments in the format used by the struct module.

  Raises:
    ValueError: if any of the parameters is invalid.
  """
  is_signed = False if int_width == 1 else True
  format_chars = [None, 'b', 'h', None, 'i']
  if int_width > len(format_chars) or not format_chars[int_width]:
    raise ValueError('Invalid width %d.' % int_width)
  format_char = format_chars[int_width]
  return format_char if is_signed else format_char.upper()


def Pcm2Float(sig, scaler=1):
  """Convert Integer PCM signal to floating point array.

  Args:
    sig: (array_like) Input array, must have (signed) integer type.
    scaler: (number). Upper bound for the values in the array. Used to
    normalize the values to range [-1, 1]. There is no check in this function
    to assure scaler is actually a valid upper bound!

  Returns:
    (list of float) floating point data.
  """
  # Normalize the values to [-1, 1]
  return numpy.asarray(sig) / float(scaler)


class WaveReader(object):
  """Class to read the contents of .wav files.

  Differs from the standard wave.wave_read in that the samples are
  obtained as a list of ints, not as a string.
  """

  def __init__(self, wave_read):
    """Initializer.

    Args:
      wave_read: an open instance of wave.wave_read.

    Raises:
      ValueError: if wave_read evaluates to False.
    """
    if not wave_read:
      raise ValueError('wave_read evaluated to False.')
    self._wave_reader = wave_read

  def __repr__(self):
    """Return the list of samples as a string."""
    n = self.GetNumberOfSamples()
    samples = self.ReadSamples(0, n)
    rate = self.GetSamplingRate()
    width = self.GetSampleWidth()
    return str({'rate': rate, 'width': width, 'samples': samples})

  def ReadSamples(self, position_start_reading=0, num_samples=-1):
    """Reads a chunk from the wave files.

    Args:
      position_start_reading: (int) the position in the file from where the
        chunk starts.
      num_samples: (int) size of the chunk to be read. Defaults to -1,
        meaning to read all the remaining samples.

    Returns:
      (list of int) The sample list as a list of ints.
    """
    self._wave_reader.setpos(position_start_reading)
    frames_string = self._wave_reader.readframes(num_samples)
    width = self._wave_reader.getsampwidth()
    format_char = _GetFormatCharForStructUnpack(width)
    return _StringOfPackedNumberToList(frames_string, format_char)

  def GetSamplingRate(self):
    """Gets the sampling rate."""
    return self._wave_reader.getframerate()

  def GetNumberOfSamples(self):
    """Gets the number of frames."""
    return self._wave_reader.getnframes()

  def GetSampleWidth(self):
    """Gets the framewidth in bytes."""
    return self._wave_reader.getsampwidth()

  def Rewind(self):
    """Resets the pointer position to the beginning of the file."""
    self._wave_reader.rewind()

  def Close(self):
    """Closes the file."""
    self._wave_reader.close()


def CreateWaveReader(wave_path):
  """Creates a wave reader.

  Args:
    wave_path: (string) path to the wave file.

  Returns:
    A WaveReader object.

  Raises:
    Error: if the file doesn't exist or is empty.
  """
  if not os.path.exists(wave_path):
    raise Error('Wave file %s doesn\'t exist.' % wave_path)
  if os.path.getsize(wave_path) == 0:
    raise Error('Wave file %s is empty.' % wave_path)
  reader = WaveReader(wave.open(wave_path))
  if not reader.ReadSamples():
    raise Error('No samples captured in file %s.' % wave_path)
  return reader
