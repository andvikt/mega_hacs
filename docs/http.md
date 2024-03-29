Контроллер оповещает сервер о своих событиях, например, нажали кнопку выключателя или сработал датчик движения,
для этого в интеграции реализован http-сервер, для его работы необходимо прописать
в настройках меги следующие параметры:

```yaml
srv: "192.168.1.4:8123" # ip:port вашего HA
script: "mega" # это api интеграции, к которому будет обращаться контроллер
```

!!! note "Внимание!" 
    Не используйте **srv loop** на контроллере - это может приводить к ложным срабатываниям входов. Вместо srv loop 
    интеграция будет сама обновлять все состояния портов с заданным интервалом

За события будут отвечать объекты типа *binary_sensor* - их статус будет меняться на **on** при замыкании
контакта, на **off** при размыкании, а так же для более сложного контроля (двойные, долгие нажатия) предусмотрены
события с типом *mega.binary*, [об этом подробнее в разделе события](events.md)

Так же вы можете [воспользоваться моими шаблонами автоматизаций](blueprints.md) для быстрого понимания, как всем этим 
пользоваться.

## Ответ на входящие события от контроллера

Контроллер ожидает ответ от сервера, который может быть сценарием (по умолчанию интеграция отвечает `d`, что означает 
запустить то что прописано в поле act в настройках порта).

*Внимание!* По умолчанию в настройках интеграции стоит опция `имитация ответа` - это означает, что сервер вместо ответа
делает запрос к меге с необходимой командой - это вынужденная мера, тк встроенный в HA сервер разбивает пакет на части,
а контроллер не работает с такими пакетами. В целом, `имитация ответа` полностью закрывает эту проблему, единственный
недостаток - это небольшая задержка в ответе.

Для максимальной скорости реакции, можно воспользоваться 
[аддоном](https://github.com/andvikt/mega_addon/tree/master/mega-proxy), подробности в документации аддона.

[Поддерживаются шаблоны HA.](yaml.md#binary) Это может быть использовано, например, для запоминания яркости (тк сам контроллер этого не 
умеет).

## Отладка шаблонов {: #temp-debug }
Отладку шаблонов рекомендуется проводить в специальном меню HA, которое находится в `Панель разработчика` - `Шаблоны`

Вот пример, с которого можно начать:
```yaml
{## Переменные, которые передает контроллер, указываются только в тесте ##}
{% set m = 1%}
{% set pt = 2%}
{% set mdid = 'mega'%}
{## Шаблон ответа ##}
{% if m in [0, 1] %}d{% endif %}
```

## Отладка ответов http-сервера {: #http-response }
Для отладки ответов сервера можно самим имитировать запросы контроллера, если у вас есть доступ к консоли HA:
```shell
curl -v -X GET 'http://localhost:8123/mega?pt=5&m=1&mdid=mymega1'
```
Где mymega1 - id устройства mega, который нужно узнать по url `http://192.168.1.14/sec/?cf=2`

При этом необходимо так же в настройках интеграции прописать хост, с которого вы будете обращаться,
[подробнее](yaml.md#allow_hosts)

И тогда можно с локальной машины делать запросы на ваш сервер HA:
```shell
curl -v -X GET 'http://192.168.88.1.4:8123/mega?pt=5&m=1&mdid=mymega1'
```
В ответ будет приходить либо d, либо скрипт, который вы настроили