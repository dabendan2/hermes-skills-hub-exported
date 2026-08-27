from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseHospitalModule(ABC):
    """
    Base hospital module interface.
    """
    @abstractmethod
    def dept(self, keyword: str = "") -> Dict[str, Any]:
        pass

    @abstractmethod
    def schedule(self, dept: str, doctor: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        pass

    @abstractmethod
    def progress(self, dept: str, doctor: str = "", session: str = "", room: str = "", number: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        pass

    @abstractmethod
    def records(self, id_number: str = "", birthday: str = "", branch: str = "", **kwargs) -> Dict[str, Any]:
        pass
