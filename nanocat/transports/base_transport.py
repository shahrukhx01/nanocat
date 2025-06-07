#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

from abc import abstractmethod
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from nanocat.audio.turn.base_turn_analyzer import BaseTurnAnalyzer
from nanocat.audio.vad.vad_analyzer import VADAnalyzer
from nanocat.processors.frame_processor import FrameProcessor
from nanocat.utils.base_object import BaseObject


class TransportParams(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    audio_out_enabled: bool = False
    audio_out_sample_rate: Optional[int] = None
    audio_out_channels: int = 1
    audio_out_bitrate: int = 96000
    audio_out_10ms_chunks: int = 4
    audio_out_destinations: List[str] = []
    audio_in_enabled: bool = False
    audio_in_sample_rate: Optional[int] = None
    audio_in_channels: int = 1
    audio_in_stream_on_start: bool = True
    audio_in_passthrough: bool = True
    vad_enabled: bool = False
    vad_audio_passthrough: bool = False
    vad_analyzer: Optional[VADAnalyzer] = None
    turn_analyzer: Optional[BaseTurnAnalyzer] = None


class BaseTransport(BaseObject):
    def __init__(
        self,
        *,
        name: Optional[str] = None,
        input_name: Optional[str] = None,
        output_name: Optional[str] = None,
    ):
        super().__init__(name=name)
        self._input_name = input_name
        self._output_name = output_name

    @abstractmethod
    def input(self) -> FrameProcessor:
        pass

    @abstractmethod
    def output(self) -> FrameProcessor:
        pass
