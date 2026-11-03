import json
import time
import base64
import random
import urllib.request
from pathlib import Path
from typing import Any, Optional, Dict, List
import websocket

class DirectTinderCDP:
    """
    Прямой CDP-клиент к вкладке Tinder через WebSocket без зависимостей от тяжелых фреймворков.
    Работает мгновенно, не виснет из-за сторонних вкладок/капч.
    """
    def __init__(self, cdp_port: int = 9222):
        self.cdp_port = cdp_port
        self.ws = None
        self.msg_id = 0
        self._connect()

    def _connect(self):
        url = f"http://127.0.0.1:{self.cdp_port}/json/list"
        data = json.loads(urllib.request.urlopen(url, timeout=5).read().decode())
        tinder_target = None
        for t in data:
            if "tinder.com" in t.get("url", ""):
                tinder_target = t
                break
        
        if not tinder_target:
            raise RuntimeError("Вкладка Tinder не найдена в браузере!")

        ws_url = tinder_target["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(ws_url, timeout=10)
        
        # Включаем Runtime и DOM
        self._call("Runtime.enable")
        self._call("DOM.enable")

    def _call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self.msg_id += 1
        req_id = self.msg_id
        payload = {"id": req_id, "method": method}
        if params:
            payload["params"] = params
        
        self.ws.send(json.dumps(payload))
        
        # Читаем ответы до нужного id
        while True:
            raw = self.ws.recv()
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP Error in {method}: {msg['error']}")
                return msg.get("result", {})

    def evaluate(self, expression: str) -> Any:
        res = self._call("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        result_obj = res.get("result", {})
        if "value" in result_obj:
            return result_obj["value"]
        return result_obj

    def screenshot(self, output_path: str):
        res = self._call("Page.captureScreenshot", {"format": "jpeg", "quality": 85})
        data = base64.b64decode(res["data"])
        with open(output_path, "wb") as f:
            f.write(data)

    def switch_tab(self, tab_name: str):
        """tab_name: 'Пари' (Matches) или 'Повідомлення' (Messages)"""
        js = f"""(() => {{
            const buttons = Array.from(document.querySelectorAll('button[role="tab"]'));
            const target = buttons.find(b => b.innerText.includes('{tab_name}'));
            if (target) {{
                target.click();
                return true;
            }}
            return false;
        }})()"""
        return self.evaluate(js)

    def open_chat(self, match_id: str):
        """Кликает по ссылке диалога в боковой панели"""
        js = f"""(() => {{
            const link = document.querySelector('a[href*="{match_id}"]');
            if (link) {{
                link.click();
                return true;
            }}
            return false;
        }})()"""
        return self.evaluate(js)

    def set_textarea_text_and_send(self, text: str, auto_send: bool = True):
        """Вводит текст в поле ввода с событием input и нажимает кнопку отправки"""
        # Сначала вставляем текст и триггерим события React
        js_input = f"""(() => {{
            const ta = document.querySelector('textarea');
            if (!ta) return false;
            
            // Фокус
            ta.focus();
            
            // Устанавливаем значение через prototype setter для React
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
            nativeInputValueSetter.call(ta, {json.dumps(text)});
            
            // Триггерим события
            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()"""
        
        ok = self.evaluate(js_input)
        if not ok:
            return False

        time.sleep(random.uniform(1.0, 1.8))

        if auto_send:
            # Находим кнопку "Надіслати" / "Send" или нажимаем Enter
            js_send = """(() => {
                const ta = document.querySelector('textarea');
                // Ищем кнопку отправки
                const btn = Array.from(document.querySelectorAll('button')).find(b => {
                    const t = (b.innerText || '').toLowerCase();
                    const aria = (b.getAttribute('aria-label') || '').toLowerCase();
                    return t.includes('надіслати') || t.includes('send') || aria.includes('надіслати') || aria.includes('send');
                });
                if (btn && !btn.disabled) {
                    btn.click();
                    return 'button_clicked';
                }
                if (ta) {
                    // Симулируем нажатие клавиши Enter
                    const event = new KeyboardEvent('keydown', {
                        bubbles: true,
                        cancelable: true,
                        key: 'Enter',
                        code: 'Enter',
                        keyCode: 13
                    });
                    ta.dispatchEvent(event);
                    return 'enter_dispatched';
                }
                return false;
            })()"""
            return self.evaluate(js_send)
        return 'drafted'

    def close(self):
        if self.ws:
            self.ws.close()

if __name__ == "__main__":
    cdp = DirectTinderCDP()
    print("CDP connected successfully!")
    title = cdp.evaluate("document.title")
    url = cdp.evaluate("window.location.href")
    print(f"Title: {title} | URL: {url}")
    cdp.close()
