**blueprints** - это удобные шаблоны автоматизаций, которые помогают строить автоматизацию из
интерфейса и ими легко делиться. Все ваши шаблоны доступны из специального меню. 

[![Open your Home Assistant instance and show your blueprints.](https://my.home-assistant.io/badges/blueprints.svg)](https://my.home-assistant.io/redirect/blueprints/)

[Официальная документация по blueprints](https://www.home-assistant.io/docs/blueprint/)

## Общее
Здесь я делюсь шаблонами, в которых используются события из моей интеграции. 

Если вы хотите сделать что-то подобное своими руками, то можно использовать мои шаблоны как отправную точку.

Во всех шаблонах в качестве триггера используется событие **mega.binary** и доступен выбор типа, 
[подробное описание типов здесь](events.md#binary).

## Включить что-то
Этот шаблон лучше всего подходит для включения сценариев/сцен или любых других объектов по нажатию какой-то кнопки или 
обнаружению движения.

!!! note "Движение"
    Датчики движения - это такие же *binary_sensor* как и обычные выключатели. В зависимости от настроек контроллера
    будут приходить события либо типа **single** (если настроен режим click), либо **press**

Опционально так же доступна настройка автоматического выключения по таймеру, если указан 0 (по умолчанию), таймер не 
будет использован.

Опционально доступен так же *блокирующий объект* и *период блокировки*. Например, если в одной комнате с датчиком 
движения есть выключатель, тогда его можно указать как *блокирующий объект* и в течении *периода блокировки* 
после нажатия выключателя события с датчика движения будут игнорироваться.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgist.github.com%2Fandvikt%2Fb78459f4f43862d04c7fbba20d6893c7)

[Исходный код](https://gist.github.com/andvikt/b78459f4f43862d04c7fbba20d6893c7)
## Переключить состояние
Классическое управление светом с кнопки без фиксации: нажали кнопку - свет выключился, если он сейчас включен, и наоборот. 
Если вам нужно управлять несколькими светильниками, то необходимо будет 
[создать группу света](https://www.home-assistant.io/integrations/light.group/)

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgist.github.com%2Fandvikt%2Fefb48535b1b9d998fe3dbe9a3efcea2c)

[Исходный код](https://gist.github.com/andvikt/efb48535b1b9d998fe3dbe9a3efcea2c)
## Выключатель с фиксацией
Если выбран тип "нестрогий", то при каждом переключении состояния выключателя состоянии целевого объекта так же будет 
меняться. Этот режим рекомендуется, тк в случае переключения состояния с сервера, в случае со строгим типом будет
"рассинхрон" - вам придется сначала выключатель привести в соответствие с текущим состоянием света. 

Если выбран тип "строгий", то будет строгое соответсвие состояний, те выкл==выкл и наоборот.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgist.github.com%2Fandvikt%2F9addf966db75d0964143177963f40bb9)

[Исходный код](https://gist.github.com/andvikt/9addf966db75d0964143177963f40bb9)
## Универсальный шаблон
Универсальный шаблон, с помощью которого можно выбрать любое событие меги, привязать
к нему набор произвольных действий

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgist.github.com%2Fandvikt%2Fbe1f683d308050b8972f9efa8aec465f)

[Исходный код](https://gist.github.com/andvikt/be1f683d308050b8972f9efa8aec465f)