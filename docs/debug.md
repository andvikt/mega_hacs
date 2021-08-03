[Сообщить о проблеме](https://github.com/andvikt/mega_hacs/issues/new?assignees=&labels=&template=bug-report.md&title=){ .md-button .md-button--primary }

В первую очередь проверьте лог на наличие ошибок, доступ к логу возможен по кнопке ниже.

[![Open your Home Assistant instance and show your Home Assistant logs.](https://my.home-assistant.io/badges/logs.svg)](https://my.home-assistant.io/redirect/logs/)

Так же будет очень полезно прикладывать детальный лог, который можно включить в конфиге так:
```yaml
logger:
  default: info
  logs:
    custom_components.mega: debug
```
Для просмотра логов рекомендуется использовать [logviewer](https://github.com/hassio-addons/addon-log-viewer)

