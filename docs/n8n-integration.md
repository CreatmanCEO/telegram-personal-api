# Интеграция с n8n

Эта инструкция описывает, как интегрировать Telegram User API с n8n для автоматизации отправки сообщений.

## Подготовка

1. У вас должен быть установлен и настроен Telegram User API
2. У вас должен быть доступ к n8n (в нашем случае https://n8n.itpovar.ru)
3. API должно быть доступно через HTTPS (в нашем случае https://tg-api.itpovar.ru)

## Настройка n8n для отправки текстовых сообщений

### Шаг 1: Создание нового workflow

1. Откройте n8n в браузере
2. Нажмите на "Create workflow"
3. Назовите ваш workflow, например, "Telegram Message Sender"

### Шаг 2: Добавление триггера

Добавьте триггер, который будет запускать отправку сообщения. Это может быть:
- Webhook (для вызова через HTTP запрос)
- Schedule (для регулярной отправки)
- Другой триггер на ваш выбор

### Шаг 3: Настройка данных сообщения

1. Добавьте ноду "Set" для настройки данных сообщения
2. Настройте следующие параметры:
   - `recipient`: Имя пользователя, ID чата или номер телефона получателя
   - `message`: Текст сообщения

### Шаг 4: Настройка HTTP Request ноды

1. Добавьте ноду "HTTP Request"
2. Настройте следующие параметры:
   - **Method**: POST
   - **URL**: https://tg-api.itpovar.ru/send/text
   - **Authentication**: Basic Auth
   - **Username**: admin
   - **Password**: ваш_пароль
   - **Body Content Type**: JSON
   - **Request Body**:
     ```json
     {
       "recipient": "{{$node['Set'].json.recipient}}",
       "text": "{{$node['Set'].json.message}}"
     }
     ```

### Шаг 5: Тестирование workflow

1. Соедините ноды: Триггер -> Set -> HTTP Request
2. Сохраните workflow
3. Запустите тестовое выполнение workflow

## Отправка файлов через n8n

Для отправки файлов через API требуется немного другой подход:

### Шаг 1: Подготовка файла

1. Добавьте ноду "Read Binary File" или любую другую, которая даст бинарные данные файла
2. Если файл должен быть динамическим, используйте соответствующие ноды

### Шаг 2: Настройка HTTP Request ноды для отправки файла

1. Добавьте ноду "HTTP Request"
2. Настройте следующие параметры:
   - **Method**: POST
   - **URL**: https://tg-api.itpovar.ru/send/file
   - **Authentication**: Basic Auth
   - **Username**: admin
   - **Password**: ваш_пароль
   - **Body Content Type**: Form-Data
   - **Form Data Fields**:
     - `recipient`: Имя пользователя, ID чата или номер телефона получателя
     - `caption`: Описание файла (опционально)
     - `file`: Выберите опцию "Add File" и свяжите с бинарным выводом предыдущей ноды

### Пример готового workflow

В репозитории есть готовый пример workflow, который вы можете импортировать в n8n:
`examples/n8n-workflow.json`

Для импорта:
1. В n8n нажмите на вкладку "Workflows"
2. Нажмите кнопку "Import"
3. Выберите файл `examples/n8n-workflow.json`
4. Настройте параметры (в особенности пароль для API) перед запуском

## Расширенные возможности

### Динамическое формирование получателей

Вы можете использовать функции n8n для динамического определения получателей, например:

```javascript
// В ноде Function
return {
  json: {
    recipient: $node["Input"].json.to_username || "@default_username",
    message: $node["Input"].json.message
  }
}
```

### Обработка ошибок

Для обработки возможных ошибок добавьте ноду "IF" после HTTP Request:

1. Настройте условие: `{{$node["HTTP Request"].json.status == "success"}}`
2. Если true: продолжить нормальный поток
3. Если false: обработать ошибку (например, отправить уведомление)

## Советы и рекомендации

1. **Тестирование**: Всегда тестируйте workflow с небольшим числом получателей
2. **Безопасность**: Храните пароль API в n8n credentials, а не непосредственно в workflow
3. **Разделение потоков**: Для сложных сценариев разделяйте workflow на логические части
4. **Мониторинг**: Настройте уведомления о сбоях в работе workflow
