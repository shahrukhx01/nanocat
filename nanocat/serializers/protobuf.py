#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import dataclasses
import json

from loguru import logger

import nanocat.frames.protobufs.frames_pb2 as frame_protos
from nanocat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    TextFrame,
    TranscriptionFrame,
    TransportMessageFrame,
    TransportMessageUrgentFrame,
)
from nanocat.serializers.base_serializer import FrameSerializer, FrameSerializerType


# Data class for converting transport messages into Protobuf format.
@dataclasses.dataclass
class MessageFrame:
    data: str


class ProtobufFrameSerializer(FrameSerializer):
    SERIALIZABLE_TYPES = {
        TextFrame: "text",
        OutputAudioRawFrame: "audio",
        TranscriptionFrame: "transcription",
        MessageFrame: "message",
    }
    SERIALIZABLE_FIELDS = {v: k for k, v in SERIALIZABLE_TYPES.items()}

    DESERIALIZABLE_TYPES = {
        TextFrame: "text",
        InputAudioRawFrame: "audio",
        TranscriptionFrame: "transcription",
    }
    DESERIALIZABLE_FIELDS = {v: k for k, v in DESERIALIZABLE_TYPES.items()}

    def __init__(self):
        pass

    @property
    def type(self) -> FrameSerializerType:
        return FrameSerializerType.BINARY

    async def serialize(self, frame: Frame) -> str | bytes | None:
        # Wrapping this messages as a JSONFrame to send
        if isinstance(frame, (TransportMessageFrame, TransportMessageUrgentFrame)):
            frame = MessageFrame(
                data=json.dumps(frame.message),
            )

        proto_frame = frame_protos.Frame()
        if type(frame) not in self.SERIALIZABLE_TYPES:
            logger.warning(f"Frame type {type(frame)} is not serializable")
            return None

        # ignoring linter errors; we check that type(frame) is in this dict above
        proto_optional_name = self.SERIALIZABLE_TYPES[type(frame)]  # type: ignore
        proto_attr = getattr(proto_frame, proto_optional_name)
        for field in dataclasses.fields(frame):  # type: ignore
            value = getattr(frame, field.name)
            if value and hasattr(proto_attr, field.name):
                setattr(proto_attr, field.name, value)

        return proto_frame.SerializeToString()

    async def deserialize(self, data: str | bytes) -> Frame | None:
        proto = frame_protos.Frame.FromString(data)
        which = proto.WhichOneof("frame")
        if which not in self.DESERIALIZABLE_FIELDS:
            logger.error("Unable to deserialize a valid frame")
            return None

        class_name = self.DESERIALIZABLE_FIELDS[which]
        args = getattr(proto, which)
        args_dict = {}
        for field in proto.DESCRIPTOR.fields_by_name[which].message_type.fields:
            args_dict[field.name] = getattr(args, field.name)

        # Remove special fields if needed
        id = getattr(args, "id", None)
        name = getattr(args, "name", None)
        pts = getattr(args, "pts", None)
        if "id" in args_dict:
            del args_dict["id"]
        if "name" in args_dict:
            del args_dict["name"]
        if "pts" in args_dict:
            del args_dict["pts"]

        # Create the instance
        instance = class_name(**args_dict)

        # Set special fields
        if id:
            setattr(instance, "id", id)
        if name:
            setattr(instance, "name", name)
        if pts:
            setattr(instance, "pts", pts)

        return instance
