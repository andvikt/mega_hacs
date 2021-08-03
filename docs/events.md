Для быстрого старта рекомендую попробовать [мои шаблоны автоматизаций](blueprints.md)

## mega.binary {: #binary}
События можно использовать только в автоматизациях как триггер типа *event*
```yaml
- alias: some long click
  trigger:
    - platform: event
      event_type: mega.binary
      event_data:
        entity_id: binary_sensor.some_id
        type: long
  action:
    - service: light.toggle
      entity_id: light.some_light
```
!!! note "Возможные варианты поля type"
        - **press**: замыкание
        - **release**: размыкание (с гарантией, что не было долгого нажатия)
        
        *Эти типы доступны только в режиме click (настраивается на контроллере):*
        
        - **long**: долгое нажатие
        - **long_release**: размыкание после долгого нажатия
        - **single**: одинарный клик (в режиме кликов)
        - **double**: двойной клик

## mega.sensor
Этот вид событий более "технический", им имеет смысл пользоваться только если функциональности *mega.binary* не 
достаточно.
```yaml
# событие при перезагрузке меги
- alias: mega restart
  trigger:
    - platform: event
      event_type: mega.sensor
      event_data:
        st: 1
  action:
    # какой-то экшн
# Пример события с полями как есть прямо из меги
- alias: some double click
  trigger:
    - platform: event
      event_type: mega.sensor
      event_data:
        pt: 1
        click: 2
  action:
    - service: light.toggle
      entity_id: light.some_light
```
!!! note "События могут содержать следующие поля в event_data" 
    - **mega_id**: id как в конфиге HA
    - **pt**: номер порта
    - **cnt**: счетчик срабатываний
    - **mdid**: id как в конфиге контроллера
    - **click**: клик (подробнее в документации меги)
    - **port**: номер порта


## Отладка
Чтобы понять, какие события приходят, лучше всего воспользоваться панелью разработчика (кнопка ниже) и подписаться
на вкладке события на событие `mega.binary` или `mega.sensor`, понажимать физические кнопки на меге.

[![Open your Home Assistant instance and show your event developer tools.](https://my.home-assistant.io/badges/developer_events.svg)](https://my.home-assistant.io/redirect/developer_events/)
