from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

from aiogram.exceptions import TelegramAPIError

from carenest.app import run_bot
from carenest.config import format_check_result, inspect_configuration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CareNest — персональный Telegram-бот")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="проверить конфигурацию без подключения к Telegram",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="проверить безопасный пример конфигурации без секретов",
    )
    parser.add_argument("--config", type=Path, help="путь к JSON-файлу персонализации")
    parser.add_argument("--env-file", type=Path, help="путь к файлу переменных окружения")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.example and not args.check_config:
        parser.error("параметр --example используется только вместе с --check-config")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    result = inspect_configuration(
        config_file=args.config,
        env_file=args.env_file,
        require_secrets=not args.example,
        example=args.example,
    )
    if args.check_config:
        print(format_check_result(result))
        return 0 if result.ok else 2
    if not result.ok or result.config is None:
        for error in result.errors:
            logging.error("Ошибка конфигурации: %s", error)
        logging.error("Запуск остановлен. Исправьте конфигурацию или выполните --check-config.")
        return 2
    for warning in result.warnings:
        logging.warning("Предупреждение конфигурации: %s", warning)

    try:
        asyncio.run(run_bot(result.config))
    except KeyboardInterrupt:
        logging.info("Остановка по запросу пользователя.")
    except (OSError, RuntimeError, TelegramAPIError) as error:
        logging.error("CareNest завершён с ошибкой: %s", error)
        return 1
    return 0
