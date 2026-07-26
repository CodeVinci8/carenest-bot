from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FINAL_MESSAGE = "Квиз завершён. Спасибо, что прошли его до конца!"
MAX_QUIZ_QUESTION_LENGTH = 800
MAX_QUIZ_OPTION_LENGTH = 64
MAX_PERSONAL_FIELD_LENGTH = 200
MAX_MESSAGE_LENGTH = 4000
TOKEN_PATTERN = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{20,}$")


class ConfigurationError(RuntimeError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class QuizQuestion:
    question: str
    options: tuple[str, ...]
    correct: int
    photo: str | None = None
    reactions: tuple[str, ...] = ()
    scores: tuple[int, ...] = ()


@dataclass(frozen=True)
class SchedulerSettings:
    enabled: bool = False
    hour: int = 9
    minute: int = 0
    timezone: str = "Europe/Moscow"


@dataclass(frozen=True)
class ComplimentSettings:
    enabled: bool = False
    interval_days: int = 3
    hour: int = 12
    minute: int = 0
    timezone: str = "UTC"
    safe_context: tuple[str, ...] = ()
    local_fallbacks: tuple[str, ...] = ("Ты умеешь делать обычный день заметно теплее.",)
    api_key: str | None = None
    base_url: str = "https://aiprimetech.io"
    model: str = "claude-haiku-4-5"


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    config_file: Path
    data_dir: Path
    database: Path
    quiz_media: Path
    support_media: Path
    favorite_media: Path
    memory_media: Path


@dataclass(frozen=True)
class AppConfig:
    product_name: str
    token: str | None
    allowed_ids: frozenset[int]
    recipient_id: int | None
    recipient_id_source: str | None
    recipient_name: str
    relationship_start_date: date | None
    final_quiz_message: str
    code_word: str
    morning_messages: tuple[str, ...]
    questions: tuple[QuizQuestion, ...]
    scheduler: SchedulerSettings
    compliments: ComplimentSettings
    paths: RuntimePaths

    def rendered_final_message(self) -> str:
        try:
            return self.final_quiz_message.format(
                recipient_name=self.recipient_name,
                code_word=self.code_word,
            )
        except (KeyError, ValueError):
            return self.final_quiz_message


@dataclass
class ConfigCheckResult:
    config: AppConfig | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.config is not None and not self.errors


def _resolve_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _load_environment(project_root: Path, env_file: Path | None) -> dict[str, str]:
    selected = _resolve_path(project_root, env_file) if env_file else project_root / ".env"
    values: dict[str, str] = {}
    if selected.is_file():
        values.update({key: value for key, value in dotenv_values(selected).items() if value})
    values.update(os.environ)
    return values


def _parse_positive_id(value: str | None, name: str, errors: list[str]) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = int(value.strip())
    except ValueError:
        errors.append(f"{name} должен быть положительным целым числом.")
        return None
    if parsed <= 0:
        errors.append(f"{name} должен быть положительным целым числом.")
        return None
    return parsed


def _parse_allowed_ids(value: str | None, errors: list[str]) -> frozenset[int]:
    if not value or not value.strip():
        errors.append("Не задан ALLOWED_IDS: укажите хотя бы один Telegram ID.")
        return frozenset()

    parsed: set[int] = set()
    for raw_id in value.split(","):
        identifier = _parse_positive_id(raw_id, "Каждый ID в ALLOWED_IDS", errors)
        if identifier is not None:
            parsed.add(identifier)
    if not parsed and not any("ALLOWED_IDS" in error for error in errors):
        errors.append("ALLOWED_IDS не содержит допустимых Telegram ID.")
    return frozenset(parsed)


def _load_json(path: Path, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    if not path.is_file():
        warnings.append(
            f"Файл персонализации не найден: {path}. Используются нейтральные настройки."
        )
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"Не удалось прочитать JSON-конфигурацию {path}: {error}.")
        return {}
    if not isinstance(data, dict):
        errors.append("Корень JSON-конфигурации должен быть объектом.")
        return {}
    return data


def _load_legacy_questions(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as error:
        errors.append(f"Не удалось прочитать старый quiz_data.py: {error}.")
        return []

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "QUESTIONS" for target in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                errors.append("QUESTIONS в quiz_data.py должен быть обычным списком данных.")
                return []
            if isinstance(value, list):
                return value
            errors.append("QUESTIONS в quiz_data.py должен быть списком.")
            return []

    errors.append("В quiz_data.py не найден список QUESTIONS.")
    return []


def _parse_questions(raw_questions: Any, errors: list[str]) -> tuple[QuizQuestion, ...]:
    if raw_questions is None:
        return ()
    if not isinstance(raw_questions, list):
        errors.append("quiz.questions должен быть списком.")
        return ()

    questions: list[QuizQuestion] = []
    for index, raw in enumerate(raw_questions, start=1):
        prefix = f"Вопрос {index}"
        if not isinstance(raw, dict):
            errors.append(f"{prefix} должен быть объектом.")
            continue
        text = raw.get("question")
        options = raw.get("options")
        correct = raw.get("correct")
        photo = raw.get("photo")
        reactions = raw.get("reactions", [])
        scores = raw.get("scores", [])
        valid = True

        if not isinstance(text, str) or not text.strip():
            errors.append(f"{prefix}: поле question должно содержать текст.")
            valid = False
        elif len(text.strip()) > MAX_QUIZ_QUESTION_LENGTH:
            errors.append(f"{prefix}: текст длиннее {MAX_QUIZ_QUESTION_LENGTH} символов.")
            valid = False
        if (
            not isinstance(options, list)
            or len(options) < 2
            or any(not isinstance(option, str) or not option.strip() for option in options)
        ):
            errors.append(f"{prefix}: options должен содержать минимум два непустых ответа.")
            valid = False
        elif any(len(option.strip()) > MAX_QUIZ_OPTION_LENGTH for option in options):
            errors.append(
                f"{prefix}: каждый вариант должен быть не длиннее "
                f"{MAX_QUIZ_OPTION_LENGTH} символов."
            )
            valid = False
        if not isinstance(correct, int) or isinstance(correct, bool):
            errors.append(f"{prefix}: correct должен быть индексом ответа.")
            valid = False
        elif isinstance(options, list) and not 0 <= correct < len(options):
            errors.append(f"{prefix}: индекс correct выходит за пределы options.")
            valid = False
        if photo is not None:
            if not isinstance(photo, str) or not photo.strip():
                errors.append(f"{prefix}: photo должен быть непустой строкой или null.")
                valid = False
            elif Path(photo).is_absolute() or ".." in Path(photo).parts:
                errors.append(f"{prefix}: photo должен быть безопасным относительным путём.")
                valid = False
        if reactions and (
            not isinstance(reactions, list)
            or not isinstance(options, list)
            or len(reactions) != len(options)
            or any(not isinstance(item, str) or not item.strip() for item in reactions)
        ):
            errors.append(f"{prefix}: reactions должен соответствовать вариантам ответа.")
            valid = False
        if scores and (
            not isinstance(scores, list)
            or not isinstance(options, list)
            or len(scores) != len(options)
            or any(not isinstance(item, int) or isinstance(item, bool) for item in scores)
        ):
            errors.append(f"{prefix}: scores должен содержать целое число для каждого ответа.")
            valid = False
        if valid:
            questions.append(
                QuizQuestion(
                    question=text.strip(),
                    options=tuple(option.strip() for option in options),
                    correct=correct,
                    photo=photo.strip() if isinstance(photo, str) else None,
                    reactions=tuple(item.strip() for item in reactions) if reactions else (),
                    scores=tuple(scores) if scores else (),
                )
            )
    return tuple(questions)


def _parse_date(value: Any, errors: list[str]) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        errors.append("relationship_start_date должен быть датой в формате ГГГГ-ММ-ДД.")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append("relationship_start_date должен быть корректной датой в формате ГГГГ-ММ-ДД.")
        return None


def _parse_scheduler(raw: Any, errors: list[str]) -> SchedulerSettings:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        errors.append("scheduler должен быть объектом.")
        raw = {}

    enabled = raw.get("enabled", False)
    hour = raw.get("hour", 9)
    minute = raw.get("minute", 0)
    timezone = raw.get("timezone", "Europe/Moscow")

    if not isinstance(enabled, bool):
        errors.append("scheduler.enabled должен быть true или false.")
        enabled = False
    if not isinstance(hour, int) or isinstance(hour, bool) or not 0 <= hour <= 23:
        errors.append("scheduler.hour должен быть целым числом от 0 до 23.")
        hour = 9
    if not isinstance(minute, int) or isinstance(minute, bool) or not 0 <= minute <= 59:
        errors.append("scheduler.minute должен быть целым числом от 0 до 59.")
        minute = 0
    if not isinstance(timezone, str) or not timezone.strip():
        errors.append("scheduler.timezone должен содержать имя часового пояса IANA.")
        timezone = "Europe/Moscow"
    else:
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            errors.append(f"Неизвестный часовой пояс IANA: {timezone}.")

    return SchedulerSettings(enabled=enabled, hour=hour, minute=minute, timezone=timezone)


def _parse_compliments(
    raw: Any,
    environment: dict[str, str],
    errors: list[str],
) -> ComplimentSettings:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        errors.append("compliments должен быть объектом.")
        raw = {}
    enabled = raw.get("enabled", False)
    interval_days = raw.get("interval_days", 3)
    hour = raw.get("hour", 12)
    minute = raw.get("minute", 0)
    timezone = raw.get("timezone", "UTC")
    safe_context = raw.get("safe_context", [])
    local_fallbacks = raw.get(
        "local_fallbacks",
        ["Ты умеешь делать обычный день заметно теплее."],
    )
    if not isinstance(enabled, bool):
        errors.append("compliments.enabled должен быть true или false.")
        enabled = False
    if (
        not isinstance(interval_days, int)
        or isinstance(interval_days, bool)
        or not 1 <= interval_days <= 365
    ):
        errors.append("compliments.interval_days должен быть целым числом от 1 до 365.")
        interval_days = 3
    if not isinstance(hour, int) or isinstance(hour, bool) or not 0 <= hour <= 23:
        errors.append("compliments.hour должен быть целым числом от 0 до 23.")
        hour = 12
    if not isinstance(minute, int) or isinstance(minute, bool) or not 0 <= minute <= 59:
        errors.append("compliments.minute должен быть целым числом от 0 до 59.")
        minute = 0
    if not isinstance(timezone, str) or not timezone.strip():
        errors.append("compliments.timezone должен содержать имя часового пояса IANA.")
        timezone = "UTC"
    else:
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            errors.append(f"Неизвестный часовой пояс IANA для compliments: {timezone}.")
    if not isinstance(safe_context, list) or any(
        not isinstance(item, str) or not item.strip() or len(item.strip()) > 200
        for item in safe_context
    ):
        errors.append("compliments.safe_context должен быть списком коротких непустых строк.")
        safe_context = []
    if (
        not isinstance(local_fallbacks, list)
        or not local_fallbacks
        or any(
            not isinstance(item, str) or not item.strip() or len(item.strip()) > 500
            for item in local_fallbacks
        )
    ):
        errors.append("compliments.local_fallbacks должен содержать хотя бы одну короткую строку.")
        local_fallbacks = ["Ты умеешь делать обычный день заметно теплее."]
    api_key = environment.get("AIPRIMETECH_API_KEY")
    base_url = environment.get("AIPRIMETECH_BASE_URL", "https://aiprimetech.io").rstrip("/")
    model = environment.get("AIPRIMETECH_MODEL", "claude-haiku-4-5").strip()
    parsed_url = urlparse(base_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        errors.append("AIPRIMETECH_BASE_URL должен быть корректным HTTPS-адресом.")
    if not model or any(character.isspace() for character in model):
        errors.append("AIPRIMETECH_MODEL должен содержать один идентификатор модели.")
    if enabled and not api_key:
        errors.append("Для включённых AI-комплиментов требуется AIPRIMETECH_API_KEY.")
    return ComplimentSettings(
        enabled=enabled,
        interval_days=interval_days,
        hour=hour,
        minute=minute,
        timezone=timezone,
        safe_context=tuple(item.strip() for item in safe_context),
        local_fallbacks=tuple(item.strip() for item in local_fallbacks),
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


def inspect_configuration(
    *,
    project_root: Path = DEFAULT_PROJECT_ROOT,
    config_file: Path | None = None,
    env_file: Path | None = None,
    require_secrets: bool = True,
    example: bool = False,
) -> ConfigCheckResult:
    project_root = project_root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    environment = _load_environment(project_root, env_file)
    product_name = environment.get("CARENEST_PRODUCT_NAME", "CareNest Bot").strip()
    if not product_name or len(product_name) > 80:
        errors.append("CARENEST_PRODUCT_NAME должен содержать от 1 до 80 символов.")
        product_name = "CareNest Bot"

    if config_file is not None:
        configured_path = config_file
    elif example:
        configured_path = Path("config/personalization.example.json")
    else:
        configured_path = Path(environment.get("CARENEST_CONFIG", "config/personalization.json"))
    resolved_config_file = _resolve_path(project_root, configured_path)
    raw = _load_json(resolved_config_file, errors, warnings)

    token = environment.get("TELEGRAM_TOKEN")
    if require_secrets:
        if not token:
            errors.append("Не задан TELEGRAM_TOKEN.")
        elif not TOKEN_PATTERN.fullmatch(token):
            errors.append("TELEGRAM_TOKEN имеет неверный формат.")
        allowed_ids = _parse_allowed_ids(environment.get("ALLOWED_IDS"), errors)
    else:
        allowed_ids = frozenset()

    recipient_source: str | None = None
    recipient_raw = environment.get("RECIPIENT_ID")
    if recipient_raw:
        recipient_source = "RECIPIENT_ID"
    elif environment.get("HER_ID"):
        recipient_raw = environment["HER_ID"]
        recipient_source = "HER_ID"
        warnings.append("Использован устаревший HER_ID; перенесите значение в RECIPIENT_ID.")
    recipient_id = _parse_positive_id(recipient_raw, recipient_source or "RECIPIENT_ID", errors)

    paths_raw = raw.get("paths", {})
    if not isinstance(paths_raw, dict):
        errors.append("paths должен быть объектом.")
        paths_raw = {}
    data_dir = _resolve_path(
        project_root, environment.get("CARENEST_DATA_DIR", paths_raw.get("data", "data"))
    )
    database = _resolve_path(project_root, paths_raw.get("database", data_dir / "wishlist.db"))
    quiz_media = _resolve_path(project_root, paths_raw.get("quiz_media", "media/quiz"))
    support_media = _resolve_path(project_root, paths_raw.get("support_media", "media/support"))
    favorite_media = _resolve_path(
        project_root,
        paths_raw.get("favorite_media", paths_raw.get("support_media", "media/support")),
    )
    memory_media = _resolve_path(project_root, paths_raw.get("memory_media", "media/memories"))

    legacy_database = project_root / "wishlist.db"
    if not database.exists() and legacy_database.is_file():
        database = legacy_database.resolve()
        warnings.append(
            "Найдена старая wishlist.db в корне проекта; она будет использована без переноса."
        )
    legacy_quiz_media = project_root / "photos"
    if not quiz_media.exists() and legacy_quiz_media.is_dir():
        quiz_media = legacy_quiz_media.resolve()
        warnings.append("Найдена старая папка photos; она будет использована для квиза.")
    legacy_support_media = project_root / "cute_photos"
    if not support_media.exists() and legacy_support_media.is_dir():
        support_media = legacy_support_media.resolve()
        warnings.append("Найдена старая папка cute_photos; она будет использована для поддержки.")

    if database.exists() and not database.is_file():
        errors.append(f"Путь к базе данных не является файлом: {database}.")
    elif database.parent.exists() and not database.parent.is_dir():
        errors.append(f"Родительский путь базы данных не является папкой: {database.parent}.")
    if quiz_media.exists() and not quiz_media.is_dir():
        warnings.append("Путь к фотографиям квиза не является папкой; будет использован текст.")
    if support_media.exists() and not support_media.is_dir():
        warnings.append("Путь к фотографиям поддержки не является папкой; будет использован текст.")
    for label, directory in (
        ("любимых фотографий", favorite_media),
        ("случайных воспоминаний", memory_media),
    ):
        if directory.exists() and not directory.is_dir():
            warnings.append(f"Путь к папке {label} некорректен; будет использован текст.")

    quiz_raw = raw.get("quiz", {})
    if quiz_raw is None:
        quiz_raw = {}
    if not isinstance(quiz_raw, dict):
        errors.append("quiz должен быть объектом.")
        quiz_raw = {}
    raw_questions = quiz_raw.get("questions")
    legacy_quiz = project_root / "quiz_data.py"
    if raw_questions is None and legacy_quiz.is_file():
        raw_questions = _load_legacy_questions(legacy_quiz, errors)
        warnings.append(
            "Вопросы загружены из старого quiz_data.py без выполнения Python-кода; "
            "перенесите их в JSON при удобном обновлении."
        )
    questions = _parse_questions(raw_questions, errors)

    scheduler = _parse_scheduler(raw.get("scheduler"), errors)
    compliments = _parse_compliments(raw.get("compliments"), environment, errors)
    morning_raw = raw.get("morning_messages", [])
    if not isinstance(morning_raw, list) or any(
        not isinstance(message, str) or not message.strip() for message in morning_raw
    ):
        errors.append("morning_messages должен быть списком непустых строк.")
        morning_messages: tuple[str, ...] = ()
    elif any(len(message.strip()) > MAX_MESSAGE_LENGTH for message in morning_raw):
        errors.append(
            f"Каждый текст в morning_messages должен быть не длиннее {MAX_MESSAGE_LENGTH} символов."
        )
        morning_messages = ()
    else:
        morning_messages = tuple(message.strip() for message in morning_raw)

    if scheduler.enabled and recipient_id is None:
        errors.append("Для включённого планировщика требуется RECIPIENT_ID.")
    if scheduler.enabled and not morning_messages:
        errors.append("Для включённого планировщика нужен хотя бы один текст morning_messages.")
    if recipient_id is not None and allowed_ids and recipient_id not in allowed_ids:
        errors.append("RECIPIENT_ID должен входить в ALLOWED_IDS.")
    if compliments.enabled and recipient_id is None:
        errors.append("Для включённых AI-комплиментов требуется RECIPIENT_ID.")

    relationship_date = _parse_date(raw.get("relationship_start_date"), errors)
    if relationship_date is None:
        warnings.append("Дата начала отношений не задана; счётчик дней будет недоступен.")

    recipient_name = raw.get("recipient_name", "близкий человек")
    final_message = raw.get("final_quiz_message", DEFAULT_FINAL_MESSAGE)
    code_word = raw.get("code_word", "")
    for field_name, value in (
        ("recipient_name", recipient_name),
        ("final_quiz_message", final_message),
        ("code_word", code_word),
    ):
        if not isinstance(value, str):
            errors.append(f"{field_name} должен быть строкой.")
    if isinstance(recipient_name, str) and len(recipient_name) > MAX_PERSONAL_FIELD_LENGTH:
        errors.append(
            f"recipient_name должен быть не длиннее {MAX_PERSONAL_FIELD_LENGTH} символов."
        )
    if isinstance(code_word, str) and len(code_word) > MAX_PERSONAL_FIELD_LENGTH:
        errors.append(f"code_word должен быть не длиннее {MAX_PERSONAL_FIELD_LENGTH} символов.")
    if not isinstance(final_message, str) or not final_message.strip():
        errors.append("final_quiz_message не должен быть пустым.")
    elif isinstance(recipient_name, str) and isinstance(code_word, str):
        try:
            rendered_final_message = final_message.format(
                recipient_name=recipient_name,
                code_word=code_word,
            )
        except (KeyError, ValueError):
            errors.append(
                "final_quiz_message содержит неверный шаблон; доступны только "
                "{recipient_name} и {code_word}."
            )
        else:
            if len(rendered_final_message) > MAX_MESSAGE_LENGTH:
                errors.append(
                    f"Итоговый final_quiz_message должен быть не длиннее "
                    f"{MAX_MESSAGE_LENGTH} символов."
                )

    for question_index, question in enumerate(questions, start=1):
        if question.photo and not (quiz_media / question.photo).is_file():
            warnings.append(
                f"Вопрос {question_index}: фотография не найдена, будет показан только текст."
            )
    if not support_media.is_dir():
        warnings.append("Папка с фотографиями поддержки не найдена; будет использован текст.")
    for label, directory in (
        ("любимых фотографий", favorite_media),
        ("случайных воспоминаний", memory_media),
    ):
        if not directory.is_dir():
            warnings.append(f"Папка {label} не найдена; будет использован текст.")
    writable_parent = database.parent
    while not writable_parent.exists() and writable_parent != writable_parent.parent:
        writable_parent = writable_parent.parent
    if not writable_parent.is_dir() or not os.access(writable_parent, os.W_OK):
        errors.append("Папка данных или её ближайший родитель недоступны для записи.")
    if not questions:
        warnings.append("В квизе нет вопросов; команда /quiz сообщит об этом пользователю.")

    paths = RuntimePaths(
        project_root=project_root,
        config_file=resolved_config_file,
        data_dir=data_dir,
        database=database,
        quiz_media=quiz_media,
        support_media=support_media,
        favorite_media=favorite_media,
        memory_media=memory_media,
    )
    config = AppConfig(
        product_name=product_name,
        token=token,
        allowed_ids=allowed_ids,
        recipient_id=recipient_id,
        recipient_id_source=recipient_source,
        recipient_name=recipient_name if isinstance(recipient_name, str) else "",
        relationship_start_date=relationship_date,
        final_quiz_message=final_message if isinstance(final_message, str) else "",
        code_word=code_word if isinstance(code_word, str) else "",
        morning_messages=morning_messages,
        questions=questions,
        scheduler=scheduler,
        compliments=compliments,
        paths=paths,
    )
    return ConfigCheckResult(config=config, errors=errors, warnings=warnings)


def load_configuration(**kwargs: Any) -> AppConfig:
    result = inspect_configuration(**kwargs)
    if not result.ok or result.config is None:
        raise ConfigurationError(result.errors)
    return result.config


def format_check_result(result: ConfigCheckResult) -> str:
    product_name = result.config.product_name if result.config else "CareNest"
    lines = [f"Проверка конфигурации {product_name}"]
    if result.config is not None:
        config = result.config
        lines.extend(
            [
                f"Конфигурация: {config.paths.config_file}",
                f"База данных: {config.paths.database}",
                f"Вопросов в квизе: {len(config.questions)}",
                (
                    "Планировщик: включён, "
                    f"{config.scheduler.hour:02d}:{config.scheduler.minute:02d} "
                    f"({config.scheduler.timezone})"
                    if config.scheduler.enabled
                    else "Планировщик: выключен"
                ),
                (
                    "Комплименты: включены, "
                    f"раз в {config.compliments.interval_days} дн., "
                    f"{config.compliments.hour:02d}:{config.compliments.minute:02d} "
                    f"({config.compliments.timezone})"
                    if config.compliments.enabled
                    else "Комплименты: выключены"
                ),
            ]
        )
    lines.extend(f"Ошибка: {error}" for error in result.errors)
    lines.extend(f"Предупреждение: {warning}" for warning in result.warnings)
    lines.append("Итог: конфигурация корректна." if result.ok else "Итог: найдены ошибки.")
    return "\n".join(lines)
