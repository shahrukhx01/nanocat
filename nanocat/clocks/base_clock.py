from abc import ABC, abstractmethod


class BaseClock(ABC):
    @abstractmethod
    def get_time(self) -> int:
        pass

    @abstractmethod
    def start(self):
        pass
