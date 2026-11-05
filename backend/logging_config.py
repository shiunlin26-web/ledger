"""【關卡 11】log 的設定：統一格式、可以切成 JSON

為什麼要管 log？
- 本機出錯你看得到 terminal；正式環境你看不到螢幕，只剩 log。log 沒寫好 = 半夜壞掉時什麼都查不到
- 正式環境的 log 會被平台（Render）收集、搜尋。**一行一筆 JSON** 最好處理：
  每筆都有 level、時間、訊息，還能帶自訂欄位（request_id、路徑、耗時……）

Python 內建的 logging 就夠用，不需要額外套件。這裡做兩件事：
1. 自訂一個 Formatter，可以輸出純文字（本機）或 JSON（正式環境）
2. 把 uvicorn 自己的 logger 也接到同一個格式，不然會有兩種長相的 log 混在一起
"""

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """把一筆 log 變成一行 JSON"""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # logger.info("...", extra={"request_id": ...}) 這種自訂欄位會掛在 record 上，一起輸出
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            entry[key] = value
        # 有例外時把 traceback 也放進去（Sentry 會另外收，但 log 裡有一份方便直接看）
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """本機用：一行好讀的文字，自訂欄位接在後面"""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<8} {record.name}: {record.getMessage()}"
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STANDARD_ATTRS and not k.startswith("_")
        }
        if extras:
            base += "  " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


# LogRecord 內建的屬性，輸出時要跳過，剩下的才是我們用 extra= 加的
_STANDARD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "taskName",
    "color_message",  # uvicorn 自己加的，只是帶顏色的訊息副本，不用輸出
}


def setup_logging(level: str = "INFO", json_output: bool = False) -> None:
    """程式啟動時呼叫一次（main.py）"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output else TextFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn 有自己的 logger 和 handler，清掉讓它們走我們的 root handler，格式才會一致。
    # uvicorn.access（每個請求一行）關掉：我們自己的 middleware 會記，而且記得更多
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
