# 🎁 GiftNinjaBot

<details>
<summary>🇺🇦 Українська</summary>

> **Автоматизація подарунків. Жодної бюрократії. Просто Telegram, просто працює.**

---

## 🤖 Що це взагалі?

**GiftNinjaBot** — простий, але реально корисний телеграм-бот, який сам знаходить, фільтрує та купує подарунки з маркетплейсу. Навіщо вручну моніторити та натискати «купити», якщо це може робити бот? Підтримується класичний режим бота та режим юзербота (ваш Telegram-акаунт, не бійтеся, інструкції нижче). Все безкоштовно, без комісії, без підводних каменів. Код відкритий.

---

## 🧩 Основні фішки

* Гнучкі фільтри: ціна, ліміти, саплай і все таке.
* Можна підключитися як звичайний бот або використовувати свій Telegram-акаунт (юзербот) — ліміти та обмеження знімаються.
* SOCKS5-проксі? Так, спокійно.
* Два потоки пошуку — бот і юзербот одночасно. Що дешевше/свіжіше — те й купимо.
* До 3-х профілів, різні отримувачі та бюджети. Хочете дарувати — даруйте!
* Сповіщення — коли завдання виконано або подарунок куплено.
* Меню — прямо в Telegram, нічого не треба пам'ятати.
* Лічильник покупок і автостоп, щоб не витратити все за ніч.
* Поповнення та повернення коштів через Telegram Stars (без комісії, анонімно).
* Баланс можна поповнити з будь-якого акаунту (не тільки свого).
* Тестовий режим: купіть фейковий подарунок за 15 зірок — нічого не зламається.
* У будь-який момент можна вивантажити/повернути всі зірки однією командою.

---

## 🛠 Як запустити (швидше тільки зробити самому)

```bash
git clone https://github.com/mirvald-space/GiftNinjaBot.git
cd GiftNinjaBot
pip install -r requirements.txt
```

Створіть файл `.env` у корені:

```env
TELEGRAM_BOT_TOKEN="тут_ваш_токен_бота"
TELEGRAM_USER_ID="ваш_telegram_id"

# Налаштування для вебхуків (опціонально)
# WEBHOOK_HOST="https://ваш-домен.com"  # Ваш домен або публічна IP-адреса з https://
# WEBHOOK_PATH="/webhook"  # Шлях для вебхука (за замовчуванням: /webhook)
# WEBAPP_HOST="0.0.0.0"  # Хост для веб-сервера (за замовчуванням: 0.0.0.0)
# WEBAPP_PORT=10000  # Порт для веб-сервера (за замовчуванням: 10000)
```

> Де взяти токен: [@BotFather](https://t.me/BotFather).
> Де взяти ID: [@userinfobot](https://t.me/userinfobot).

Запуск:

```bash
python main.py
```

### Використання вебхуків

Для запуску бота з вебхуками, вам потрібно:
1. Мати домен з SSL-сертифікатом або публічну IP-адресу
2. Розкоментувати та налаштувати параметри WEBHOOK_* у файлі `.env`
3. Переконатися, що порт відкритий у вашому фаєрволі
4. Запустити бота: `python main.py`

---

## 🗂 Як все влаштовано

* `main.py` — точка входу, запускати сюди
* `handlers/` — всі сценарії та реакції на кнопки/команди
* `middlewares/` — кастомні фільтри та безпека
* `services/` — вся «магія»: логіка, баланс, покупки, меню тощо
* `utils/` — логування, проксі, моки та інший допоміжний треш
* `config.json`, `.env` — конфіги та секрети (не пушьте в git)

---

## 🏭 Для своїх (розробників)

* Будь-який хендлер можна кастомізувати: просто дописуйте в `handlers/`.
* Все, що рахує гроші або щось купує, лежить в `services/`.
* Хочете прокинути новий спосіб логіну/авторизації/проксі — дивіться `middlewares/`.
* Хелпери — в `utils/`.

---

## 🤝 Кому писати, якщо все зламалося

* [@mirvaId](https://t.me/mirvaId) — автор, відповідає, якщо не спить
* [GiftNinja](https://t.me/+kJTdSYRGDc45OTE8) — новини/апдейти, якщо цікаво

---

## ⚖️ Ліцензія

MIT. Все чесно, використовуйте, робіть свої форки, кидайте pull-request'и. Тільки не продавайте як свою суперрозробку, інакше буде образливо.

---

**Ставте зірку ⭐ якщо проект допоміг або просто сподобався.
Не для корпоратів. Для тих, хто робить сам.**

</details>

<details>
<summary>🇷🇺 Русский</summary>

> **Автоматизация подарков. Никакой бюрократии. Просто Telegram, просто работает.**

---

## 🤖 Что это вообще?

**GiftNinjaBot** — простой, но реально полезный телеграм-бот, который сам находит, фильтрует и покупает подарки из маркетплейса. Зачем ручками мониторить и жать «купить», если может делать бот? Поддерживается классический режим бота и режим юзербота (ваш Telegram-аккаунт, не бойтесь, инструкции ниже). Всё бесплатно, без комиссии, без подводных камней. Код открыт.

---

## 🧩 Основные фишки

* Гибкие фильтры: цена, лимиты, саплай и всё такое.
* Можно подключиться как обычный бот или использовать свой Telegram-аккаунт (юзербот) — лимиты и обвесы снимаются.
* SOCKS5-прокси? Да, спокойно.
* Два потока поиска — бот и юзербот одновременно. Что дешевле/свежей — то и купим.
* До 3-х профилей, разные получатели и бюджеты. Хотите дарить — дарите!
* Уведомления — когда задача выполнена или подарок куплен.
* Меню — прямо в Telegram, ничего не надо помнить.
* Счётчик покупок и автостоп, чтобы не потратить всё за ночь.
* Пополнение и возврат средств через Telegram Stars (бескомиссионно, анонимно).
* Баланс можно пополнить с любого аккаунта (не только своего).
* Тестовый режим: купите фейковый подарок за 15 звёзд — ничего не сломается.
* В любой момент можно выгрузить/вернуть все звёзды одной командой.

---

## 🛠 Как запустить (быстрее только сделать самому)

```bash
git clone https://github.com/mirvald-space/GiftNinjaBot.git
cd GiftNinjaBot
pip install -r requirements.txt
```

Создайте файл `.env` в корне:

```env
TELEGRAM_BOT_TOKEN="тут_ваш_токен_бота"
TELEGRAM_USER_ID="ваш_telegram_id"

# Настройки для вебхуков (опционально)
# WEBHOOK_HOST="https://ваш-домен.com"  # Ваш домен или публичный IP-адрес с https://
# WEBHOOK_PATH="/webhook"  # Путь для вебхука (по умолчанию: /webhook)
# WEBAPP_HOST="0.0.0.0"  # Хост для веб-сервера (по умолчанию: 0.0.0.0)
# WEBAPP_PORT=10000  # Порт для веб-сервера (по умолчанию: 10000)
```

> Где взять токен: [@BotFather](https://t.me/BotFather).
> Где взять ID: [@userinfobot](https://t.me/userinfobot).

Запуск:

```bash
python main.py
```

### Использование вебхуков

Для запуска бота с вебхуками, вам нужно:
1. Иметь домен с SSL-сертификатом или публичный IP-адрес
2. Раскомментировать и настроить параметры WEBHOOK_* в файле `.env`
3. Убедиться, что порт открыт в вашем фаерволе
4. Запустить бота: `python main.py`

---

## 🗂 Как всё устроено

* `main.py` — точка входа, запускать сюда
* `handlers/` — все сценарии и реакции на кнопки/команды
* `middlewares/` — кастомные фильтры и безопасность
* `services/` — вся «магия»: логика, баланс, покупки, меню и прочее
* `utils/` — логирование, прокси, моки и прочий хелперный треш
* `config.json`, `.env` — конфиги и секреты (не пушьте в git)

---

## 🏭 Для своих (разработчиков)

* Любой хендлер можно кастомить: просто дописывайте в `handlers/`.
* Всё, что считает деньги или что-то покупает, лежит в `services/`.
* Хотите прокинуть новый способ логина/авторизации/прокси — смотрите `middlewares/`.
* Хелперы — в `utils/`.

---

## 🤝 Кому писать, если всё сломалось

* [@mirvaId](https://t.me/mirvaId) — автор, отвечает, если не спит
* [GiftNinja](https://t.me/+kJTdSYRGDc45OTE8) — новости/апдейты, если интересно

---

## ⚖️ Лицензия

MIT. Всё честно, используйте, делайте свои форки, кидайте pull-request'ы. Только не продавайте как свою суперразработку, иначе обидно будет.

---

**Ставьте звезду ⭐ если проект помог или просто понравился.
Не для корпоратов. Для тех, кто делает сам.**

</details>

<details open>
<summary>🇬🇧 English</summary>

> **Gift automation. No bureaucracy. Just Telegram, just works.**

---

## 🤖 What is this?

**GiftNinjaBot** is a simple but genuinely useful Telegram bot that automatically finds, filters, and purchases gifts from marketplaces. Why manually monitor and click "buy" when a bot can do it for you? It supports both classic bot mode and userbot mode (your Telegram account, don't worry, instructions below). Everything is free, no commission, no hidden catches. The code is open source.

---

## 🧩 Key Features

* Flexible filters: price, limits, supply, and more.
* Connect as a regular bot or use your Telegram account (userbot) — removes limits and restrictions.
* SOCKS5 proxy? Yes, no problem.
* Two search streams — bot and userbot simultaneously. Whatever is cheaper/fresher — that's what we'll buy.
* Up to 3 profiles, different recipients and budgets. Want to give gifts? Go ahead!
* Notifications — when a task is completed or a gift is purchased.
* Menu — right in Telegram, nothing to memorize.
* Purchase counter and auto-stop to prevent spending everything overnight.
* Deposit and withdraw funds via Telegram Stars (no commission, anonymous).
* Balance can be topped up from any account (not just your own).
* Test mode: buy a fake gift for 15 stars — nothing will break.
* At any time, you can withdraw/return all stars with a single command.

---

## 🛠 How to Launch (faster than doing it yourself)

```bash
git clone https://github.com/mirvald-space/GiftNinjaBot.git
cd GiftNinjaBot
pip install -r requirements.txt
```

Create a `.env` file in the root:

```env
TELEGRAM_BOT_TOKEN="your_bot_token_here"
TELEGRAM_USER_ID="your_telegram_id"

# Webhook settings (optional)
# WEBHOOK_HOST="https://your-domain.com"  # Your domain or public IP with https://
# WEBHOOK_PATH="/webhook"  # Path for webhook (default: /webhook)
# WEBAPP_HOST="0.0.0.0"  # Host to bind the web server to (default: 0.0.0.0)
# WEBAPP_PORT=10000  # Port to run the web server on (default: 10000)
```

> Where to get the token: [@BotFather](https://t.me/BotFather).
> Where to get your ID: [@userinfobot](https://t.me/userinfobot).

Launch:

```bash
python main.py
```

### Using Webhooks

To run the bot with webhooks, you need to:
1. Have a domain with an SSL certificate or a public IP address
2. Uncomment and configure the WEBHOOK_* parameters in the `.env` file
3. Ensure the port is open in your firewall
4. Run the bot: `python main.py`

---

## 🗂 How It's Organized

* `main.py` — entry point, run from here
* `handlers/` — all scenarios and reactions to buttons/commands
* `middlewares/` — custom filters and security
* `services/` — all the "magic": logic, balance, purchases, menu, etc.
* `utils/` — logging, proxies, mocks, and other helper stuff
* `config.json`, `.env` — configs and secrets (don't push to git)

---

## 🏭 For Developers

* Any handler can be customized: just add to `handlers/`.
* Everything that counts money or makes purchases is in `services/`.
* Want to add a new login/authentication/proxy method — see `middlewares/`.
* Helpers — in `utils/`.

---

## 🤝 Who to Contact if Something Breaks

* [@mirvaId](https://t.me/mirvaId) — author, responds when not sleeping
* [GiftNinja](https://t.me/+kJTdSYRGDc45OTE8) — news/updates, if you're interested

---

## ⚖️ License

MIT. Everything's fair, use it, make your forks, send pull requests. Just don't sell it as your super development, that would be disappointing.

---

**Star the project ⭐ if it helped you or you simply liked it.
Not for corporations. For those who do it themselves.**

</details>
