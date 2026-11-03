import os
import io
import re
import json
import time
import base64
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image

class VisionError(RuntimeError):
    """Ошибка при работе с Vision-моделью"""
    pass

class MediaNodeVisionClient:
    """
    Клиент для локальной Vision-модели (LM Studio / Ollama),
    построенный по проверенной архитектуре из l2/media_node.
    
    Особенности:
    - Автосжатие фото до 1024x1024 JPEG q85 (ускоряет инференс в 4-5 раз).
    - Строгая JSON Schema валидация ответа.
    - Очистка <think>...</think> тегов для reasoning-моделей.
    - Автопроверка доступности и запуск локального lms при необходимости.
    - Замер времени отклика (elapsed_seconds).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        backend: Optional[str] = None,
        timeout: float = 120.0
    ):
        self.backend = backend or os.getenv("MEDIA_VISION_BACKEND", "lmstudio")
        default_url = "http://127.0.0.1:1234" if self.backend == "lmstudio" else "http://127.0.0.1:11434"
        self.base_url = (base_url or os.getenv("MEDIA_VISION_URL", default_url)).rstrip("/").removesuffix("/v1")
        self.model = model_name or os.getenv("MEDIA_VISION_MODEL", "media-vision")
        self.timeout = float(os.getenv("MEDIA_VISION_TIMEOUT", str(timeout)))
        self.lms_bin = os.getenv("LMS_BIN_PATH", str(Path.home() / ".lmstudio" / "bin" / "lms"))

    def check_readiness(self) -> bool:
        """Проверка готовности модели к инференсу через быстрый пинг"""
        try:
            url = f"{self.base_url}/v1/chat/completions" if self.backend == "lmstudio" else f"{self.base_url}/api/chat"
            if self.backend == "lmstudio":
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Reply OK"}],
                    "max_tokens": 8,
                    "temperature": 0
                }
            else:
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Reply OK"}],
                    "stream": False
                }
            
            req = urllib.request.Request(
                url,
                json.dumps(payload).encode("utf-8"),
                {"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                body = json.load(response)
                if self.backend == "lmstudio":
                    choice = body.get("choices", [{}])[0]
                    return bool(choice.get("message", {}).get("content"))
                return bool(body.get("message", {}).get("content"))
        except Exception:
            return False

    def ensure_server_running(self) -> bool:
        """Если сервер на localhost выключен, пробуем поднять его через lms CLI"""
        if self.check_readiness():
            return True

        if "127.0.0.1" in self.base_url or "localhost" in self.base_url:
            if Path(self.lms_bin).exists():
                print(f"[VisionClient] Локальный LM Studio выключен. Пробуем запустить: {self.lms_bin} server start...")
                try:
                    subprocess.run([self.lms_bin, "server", "start", "--port", "1234", "--bind", "127.0.0.1"],
                                   check=True, timeout=30)
                    time.sleep(3)
                    return self.check_readiness()
                except Exception as e:
                    print(f"[VisionClient] Не удалось запустить lms server автоматически: {e}")
        return False

    def preprocess_image(self, image_path: str) -> str:
        """
        Механика media_node: сжатие до 1024x1024, RGB, JPEG quality 85.
        Возвращает чистый base64.
        """
        path = Path(image_path)
        if not path.exists():
            raise VisionError(f"Файл фото не найден: {image_path}")

        with Image.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("utf-8")

    def inspect_profile(
        self,
        image_paths: List[str],
        bio: str,
        name: str = "Девушка",
        age: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Проводит визуальную и текстовую верификацию анкеты по каноническому пайплайну.
        """
        started = time.monotonic()

        # 1. Сжатие и кодирование фото в base64
        encoded_images = []
        for p in image_paths:
            try:
                encoded_images.append(self.preprocess_image(p))
            except Exception as e:
                print(f"[VisionClient] Пропуск фото {p}: {e}")

        # 2. Формирование системного промпта
        system_instructions = (
            "You are an expert visual profile evaluator for dating scouting.\n"
            "Evaluate the candidate strictly based on visible visual evidence and bio text.\n"
            "Goals: casual dating, ONS, FWB, pleasant spontaneous meetings.\n"
            "Stop-factors (red flags): no real face, memes/animals/nature, heavy face-distorting filters, "
            "seeking marriage/serious only, social media baiting (Instagram/Telegram handles to gain followers).\n"
            "Return JSON matching the schema."
        )

        user_content_text = (
            f"Candidate: {name}, Age: {age or 'Unknown'}\n"
            f"Bio text: {bio or 'Empty'}\n"
            f"Attached photos count: {len(encoded_images)}"
        )

        # 3. Формирование полезной нагрузки для LM Studio
        if self.backend == "lmstudio":
            user_items = [{"type": "text", "text": user_content_text}]
            for b64 in encoded_images:
                user_items.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

            properties = {
                "has_real_person": {"type": "boolean"},
                "face_visible": {"type": "boolean"},
                "attractiveness_score": {"type": "number"},
                "casual_intent_score": {"type": "number"},
                "vibe_type": {"type": "string"},
                "is_match": {"type": "boolean"},
                "reason": {"type": "string"},
                "suggested_opener": {"type": "string"}
            }

            payload = {
                "model": self.model,
                "temperature": 0.2,
                "max_tokens": 1024,
                "messages": [
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": user_items}
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "profile_review",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": properties,
                            "required": list(properties.keys()),
                            "additionalProperties": False
                        }
                    }
                }
            }
            target_url = f"{self.base_url}/v1/chat/completions"
        else:
            # Ollama backend
            payload = {
                "model": self.model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
                "messages": [
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": user_content_text, "images": encoded_images}
                ]
            }
            target_url = f"{self.base_url}/api/chat"

        # 4. Отправка HTTP-запроса через стандартный urllib (без лишних тяжелых зависимостей)
        req = urllib.request.Request(
            target_url,
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.load(resp)

            if self.backend == "lmstudio":
                choice = body["choices"][0]
                content = choice["message"]["content"]
            else:
                content = body["message"]["content"]

            # Очистка <think> тегов (как в production_quality.py)
            cleaned_content = re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip()
            
            # Парсинг JSON
            if "```json" in cleaned_content:
                cleaned_content = cleaned_content.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_content:
                cleaned_content = cleaned_content.split("```")[1].split("```")[0].strip()

            result = json.loads(cleaned_content)
            elapsed = round(time.monotonic() - started, 3)
            result["elapsed_seconds"] = elapsed
            result["model"] = self.model
            result["backend"] = self.backend
            return result

        except Exception as exc:
            elapsed = round(time.monotonic() - started, 3)
            raise VisionError(
                f"Ошибка инференса Vision ({self.backend} @ {self.base_url}): {type(exc).__name__}: {exc} (время: {elapsed}с)"
            ) from exc
