#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from loguru import logger

from nanocat.audio.turn.base_turn_analyzer import (
    BaseTurnAnalyzer,
    EndOfTurnState,
)
from nanocat.audio.vad.vad_analyzer import VADAnalyzer, VADState
from nanocat.frames.frames import (
    BotInterruptionFrame,
    CancelFrame,
    EmulateUserStartedSpeakingFrame,
    EmulateUserStoppedSpeakingFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    StartFrame,
    StartInterruptionFrame,
    StopInterruptionFrame,
    SystemFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADParamsUpdateFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from nanocat.processors.frame_processor import FrameDirection, FrameProcessor
from nanocat.transports.base_transport import TransportParams


class BaseInputTransport(FrameProcessor):
    def __init__(self, params: TransportParams, **kwargs):
        super().__init__(**kwargs)
        self._params = params

        # initialized from the input frame
        self._sample_rare = 0
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._audio_task = None
        self._params.audio_in_passthrough = True
        self._params.audio_in_enabled = True

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def vad_analyzer(self) -> Optional[VADAnalyzer]:
        return self._params.vad_analyzer

    @property
    def turn_analyzer(self) -> Optional[BaseTurnAnalyzer]:
        return self._params.turn_analyzer

    async def start(self, frame: StartFrame):
        self._sample_rate = frame.audio_in_sample_rate

        if self._params.vad_enabled:
            self._params.vad_analyzer.set_sample_rate(self._sample_rate)

        if self._params.audio_in_enabled:
            self._audio_in_queue = asyncio.Queue()
            self._audio_task = self.create_task(self._audio_task_handler())

    async def stop(self, frame: EndFrame):
        if self._audio_task and self._audio_in_enabled:
            await self.cancel_task(self._audio_task)
            self._audio_task = None

    async def cancel(self, frame: CancelFrame):
        if self._audio_task and self._audio_in_enabled:
            await self.cancel_task(self._audio_task)
            self._audio_task = None

    async def push_audio_frame(self, frame: InputAudioRawFrame):
        if self._audio_in_queue:
            await self._audio_in_queue.put(frame)

    #
    # Frame processor
    #

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, StartFrame):
            await self.push_frame(frame)
            await self.start(frame)
        elif isinstance(frame, CancelFrame):
            await self.cancel(frame)
            await self.push_frame(frame)
        elif isinstance(frame, BotInterruptionFrame):
            await self._handle_bot_interruption(frame)
        elif isinstance(frame, EmulateUserStartedSpeakingFrame):
            logger.debug("Emulate user started speaking")
            await self._handle_user_interruption(
                UserStartedSpeakingFrame(emulated=True)
            )
        elif isinstance(frame, EmulateUserStoppedSpeakingFrame):
            logger.debug("Emulate user stopped speaking")
            await self._handle_user_interruption(
                UserStoppedSpeakingFrame(emulated=True)
            )
        elif isinstance(frame, SystemFrame):
            await self.push_frame(frame)
        elif isinstance(frame, EndFrame):
            await self.push_frame(frame)
            await self.stop(frame)
        elif isinstance(frame, VADParamsUpdateFrame):
            if self._vad_analyzer:
                self.vad_analyzer.set_params(frame.vad_params)
        else:
            await self.push_frame(frame)

    #
    # Handle interruptions
    #

    async def _handle_bot_interruption(self, frame: BotInterruptionFrame):
        logger.debug("Bot interruption")
        if self.interruptions_allowed:
            await self._start_interruption()
            await self.push_frame(StartInterruptionFrame())

    async def _handle_user_interruption(self, frame: Frame):
        if isinstance(frame, UserStartedSpeakingFrame):
            logger.debug("User started speaking")
            await self.push_frame(frame)
            # Make sure we notify about interruptions quickly out-of-band.
            if self.interruptions_allowed:
                await self._start_interruption()
                # Push an out-of-band frame (i.e. not using the ordered push
                # frame task) to stop everything, specially at the output
                # transport.
                await self.push_frame(StartInterruptionFrame())
        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.debug("User stopped speaking")
            await self.push_frame(frame)
            if self.interruptions_allowed:
                await self._stop_interruption()
                await self.push_frame(StopInterruptionFrame())

    #
    # Handle VAD
    #

    async def _vad_analyze(self, audio_frame: InputAudioRawFrame) -> VADState:
        state = VADState.QUIET
        if self.vad_analyzer:
            state = await self.get_event_loop().run_in_executor(
                self._executor, self.vad_analyzer.analyze_audio, audio_frame.audio
            )
        return state

    async def _handle_vad(self, audio_frame: InputAudioRawFrame, vad_state: VADState):
        new_vad_state = await self._vad_analyze(audio_frame)
        logger.info(f"VAD: {new_vad_state}")
        if (
            new_vad_state != vad_state
            and new_vad_state != VADState.STARTING
            and new_vad_state != VADState.STOPPING
        ):
            frame = None
            # If the turn analyser is enabled, this will prevent:
            # - Creating the UserStoppedSpeakingFrame
            # - Creating the UserStartedSpeakingFrame multiple times
            can_create_user_frames = (
                self._params.turn_analyzer is None
                or not self._params.turn_analyzer.speech_triggered
            )
            if new_vad_state == VADState.SPEAKING:
                logger.info("VAD: User started speaking")
                await self.push_frame(VADUserStartedSpeakingFrame())
                if can_create_user_frames:
                    frame = UserStartedSpeakingFrame()
            elif new_vad_state == VADState.QUIET:
                logger.info("VAD: User stopped speaking")
                await self.push_frame(VADUserStoppedSpeakingFrame())
                if can_create_user_frames:
                    frame = UserStoppedSpeakingFrame()

            if frame:
                await self._handle_user_interruption(frame)

            vad_state = new_vad_state
        return vad_state

    async def _handle_end_of_turn(self):
        pass

    async def _handle_end_of_turn_complete(self, state: EndOfTurnState):
        pass

    async def _run_turn_analyzer(
        self,
        frame: InputAudioRawFrame,
        vad_state: VADState,
        previous_vad_state: VADState,
    ):
        pass

    async def _audio_task_handler(self):
        vad_state: VADState = VADState.QUIET
        while True:
            frame: InputAudioRawFrame = await self._audio_in_queue.get()
            logger.info(f"Audio: {len(frame.audio)} bytes")
            # Check VAD and push event if necessary. We just care about
            # changes from QUIET to SPEAKING and vice versa.
            previous_vad_state = vad_state
            if self._params.vad_analyzer:
                vad_state = await self._handle_vad(frame, vad_state)

            if self._params.turn_analyzer:
                await self._run_turn_analyzer(frame, vad_state, previous_vad_state)

            # Push audio downstream if passthrough is set.
            if self._params.audio_in_passthrough:
                await self.push_frame(frame)

            self._audio_in_queue.task_done()
