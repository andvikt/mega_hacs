# MegaD HomeAssistant custom component

Интеграция с [MegaD-2561](https://www.ab-log.ru/smart-house/ethernet/megad-2561)

## Основные особенности:
- Все порты автоматически добавляются как устройства (для обычных релейных выходов создается 
  `light`, для шим - `light` с поддержкой яркости, для цифровых входов `binary_sensor`, для температурных датчиков
  `sensor`)
- Возможность работы с несколькими megad
- Обратная связь по mqtt
- Команды выполняются друг за другом без конкурентного доступа к ресурсам megad
- Поддержка температурных датчиков в режиме шины

## Устройства
Поддерживаются устройства: light, switch, binary_sensor, sensor. light может работать как диммер

## Установка
Рекомендованнй способ - через [HACS](https://hacs.xyz/docs/installation/installation).
После установки HACS, нужно перейти в меню hacs -> integrations, далее в верхнем правом углу
нажать три точки, где будет `Custom repositories`, открыть, нажать add и добавить `https://github.com/andvikt/mega_hacs.git`

Альтернативный способ установки:
```shell
# из папки с конфигом
wget -q -O - https://raw.githubusercontent.com/andvikt/mega_hacs/master/install.sh | bash -
```
Перезагрузить HA

Для обновления повторить

## Зависимости
Перед использованием необходимо настроить интеграцию mqtt в HomeAssistant

## Настройка из веб-интерфейса
`Настройки` -> `Интеграции` -> `Добавить интеграцию` в поиске ищем mega

## Сервисы
```yaml
save:
  description: Сохраняет текущее состояние портов (?cmd=s)
  fields:

    mega_id:
      description: ID меги, можно оставить пустым, тогда будут сохранены все зарегистрированные меги
      example: "mega"

get_port:
  description: Запросить текущий статус порта (или всех)
  fields:
    mega_id:
      description: ID меги, можно оставить пустым, тогда будут порты всех зарегистрированных мег
      example: "mega"
    port:
      description: Номер порта (если не заполнять, будут запрошены все порты сразу)
      example: 1

run_cmd:
  description: Выполнить любую произвольную команду
  fields:

    mega_id:
      description: ID меги
      example: "mega"
    port:
      description: Номер порта (это не порт, которым мы управляем, а порт с которого шлем команду)
      example: 1
    cmd:
      description: Любая поддерживаемая мегой команда
      example: "1:0"

```

## Отладка
Если возникают проблемы, можно включить детальный лог, для этого в конфиг добавить:
```yaml
logger:
  default: info
  logs:
    custom_components.mega: debug
```
