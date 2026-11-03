from pydantic import BaseModel, Field
from typing import List, Optional

class ProfileData(BaseModel):
    platform: str
    profile_id: str
    name: Optional[str] = "Unknown"
    age: Optional[int] = None
    city: Optional[str] = None
    bio: str = ""
    photo_paths: List[str] = Field(default_factory=list)
    raw_text: Optional[str] = ""

class EvaluationResult(BaseModel):
    has_real_person: bool = Field(description="Есть ли реальный человек на фото (не картинка, не мем, не пейзаж)")
    face_visible: bool = Field(description="Видно ли четко лицо")
    attractiveness_score: float = Field(description="Оценка внешности/ухоженности/фигуры от 0 до 10 по типажу пользователя", ge=0.0, le=10.0)
    vibe_type: str = Field(description="Типаж/вайб: party, casual, alt, sports, glam, cringe, etc.")
    casual_intent_score: float = Field(description="Оценка вероятности ONS/FWB/легкого общения (0-10)", ge=0.0, le=10.0)
    is_match: bool = Field(description="Итоговый вердикт: свайпать вправо или нет")
    red_flags: List[str] = Field(default_factory=list, description="Список стоп-факторов (поиск мужа, инста-байтер, фейк)")
    green_flags: List[str] = Field(default_factory=list, description="Список плюсов (вайб, открытость, совпадение вкусов)")
    reason: str = Field(description="Краткий вердикт для пользователя")
    suggested_opener: str = Field(description="Остроумный контекстный оупенер для первого сообщения")
