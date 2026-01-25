# VOX Brain v2: Symbolic Intelligence

Это переосмысление RAG для работы с кодом. Вместо нарезки файлов на текстовые чанки, система использует **Tree-sitter** для извлечения символов (классов, функций, интерфейсов).

## Почему это лучше v1?
1. **Symbolic Index:** Мы индексируем не "строки", а "сущности". Ты всегда получаешь определение функции или класса целиком.
2. **Hybrid Search:** Система сначала ищет совпадения в именах символов (SQL ILIKE), а затем добирает контекст через векторы (pgvector).
3. **No Noise:** Из индекса исключены тесты, статика, скомпилированные файлы и миграции.

## Как использовать
Инструмент находится в `/home/lexx/MyWork/AI/vox-brain-v2/`.

### 1. Индексация
```bash
./.venv/bin/python vox2.py index /path/to/project
```

### 2. Поиск (Главное оружие)
```bash
./.venv/bin/python vox2.py search "Salary calculation logic"
```

## Структура
- `core/parser.py`: Python парсер (AST).
- `core/parser_ts.py`: TypeScript/TSX парсер (AST).
- `core/storage.py`: Интеграция с Postgres + pgvector.
- `core/engine.py`: Логика гибридного поиска.

## Состояние
На 25.01.2026 проиндексирован проект `tamga` (backend + frontend/src). Данные лежат в локальном Postgres `tamga_local`.
