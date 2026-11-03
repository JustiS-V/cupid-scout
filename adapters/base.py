from abc import ABC, abstractmethod
from typing import Generator
from core.models import ProfileData

class BasePlatformAdapter(ABC):
    @abstractmethod
    def connect(self):
        """Подключение к платформе/сессии"""
        pass

    @abstractmethod
    def fetch_next_profile(self) -> ProfileData:
        """Получить следующую анкету из ленты"""
        pass

    @abstractmethod
    def like(self, profile: ProfileData):
        """Поставить лайк / свайпнуть вправо"""
        pass

    @abstractmethod
    def dislike(self, profile: ProfileData):
        """Пропустить анкету / свайпнуть влево"""
        pass
