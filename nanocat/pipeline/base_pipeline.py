#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

from abc import abstractmethod
from typing import List

from nanocat.processors.frame_processor import FrameProcessor


class BasePipeline(FrameProcessor):
    def __init__(self):
        super().__init__()
