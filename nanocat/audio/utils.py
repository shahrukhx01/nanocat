#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import numpy as np
import pyloudnorm as pyln
import soxr


from abc import ABC, abstractmethod


class BaseAudioResampler(ABC):
    """Abstract base class for audio resampling. This class defines an
    interface for audio resampling implementations.
    """

    @abstractmethod
    async def resample(self, audio: bytes, in_rate: int, out_rate: int) -> bytes:
        """
        Resamples the given audio data to a different sample rate.

        This is an abstract method that must be implemented in subclasses.

        Parameters:
            audio (bytes): The audio data to be resampled, represented as a byte string.
            in_rate (int): The original sample rate of the audio data (in Hz).
            out_rate (int): The desired sample rate for the resampled audio data (in Hz).

        Returns:
            bytes: The resampled audio data as a byte string.
        """
        pass


class SOXRAudioResampler(BaseAudioResampler):
    """Audio resampler implementation using the SoX resampler library."""

    def __init__(self, **kwargs):
        pass

    async def resample(self, audio: bytes, in_rate: int, out_rate: int) -> bytes:
        if in_rate == out_rate:
            return audio
        audio_data = np.frombuffer(audio, dtype=np.int16)
        resampled_audio = soxr.resample(audio_data, in_rate, out_rate, quality="VHQ")
        result = resampled_audio.astype(np.int16).tobytes()
        return result


def create_default_resampler(**kwargs) -> BaseAudioResampler:
    return SOXRAudioResampler(**kwargs)


def normalize_value(value, min_value, max_value):
    normalized = (value - min_value) / (max_value - min_value)
    normalized_clamped = max(0, min(1, normalized))
    return normalized_clamped


def calculate_audio_volume(audio: bytes, sample_rate: int) -> float:
    audio_np = np.frombuffer(audio, dtype=np.int16)
    audio_float = audio_np.astype(np.float64)

    block_size = audio_np.size / sample_rate
    meter = pyln.Meter(sample_rate, block_size=block_size)
    loudness = meter.integrated_loudness(audio_float)

    # Loudness goes from -20 to 80 (more or less), where -20 is quiet and 80 is
    # loud.
    loudness = normalize_value(loudness, -20, 80)

    return loudness


def exp_smoothing(value: float, prev_value: float, factor: float) -> float:
    return prev_value + factor * (value - prev_value)
