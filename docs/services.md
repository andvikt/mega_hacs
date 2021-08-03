Все сервисы доступны в меню разработчика с описанием и примерами использования
```yaml
mega.save:
  description: Сохраняет текущее состояние портов (?cmd=s)
  fields:
    mega_id:
      description: ID меги, можно оставить пустым, тогда будут сохранены все зарегистрированные меги
      example: "mega"

mega.get_port:
  description: Запросить текущий статус порта (или всех)
  fields:
    mega_id:
      description: ID меги, можно оставить пустым, тогда будут порты всех зарегистрированных мег
      example: "mega"
    port:
      description: Номер порта (если не заполнять, будут запрошены все порты сразу)
      example: 1

mega.run_cmd:
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