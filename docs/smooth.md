Начиная с версии `1.0.0` интеграция поддерживает плавные переходы. Функция реализована
как на аппаратном уровне, так и на программном.

Для аппаратной поддержки в настройках контроллера диммируемого порта необходимо включить опцию smooth.

В чем разница между аппаратной и программной реализацией? Контроллер на аппаратном уровне умеет медленно
менять значение pwm-порта, рекомендуется для всех портов с поддержкой этого режима использовать именно его,
тк будет обеспечена максимальная плавность для любого числа устройств одновременно.
Плавность программного диммирования ограничена ресурсами вашего сервера и скоростью ответа контроллера,
если вы будете довольно быстро (за пару секунд) диммировать сразу группу
света из нескольких светильков, то в программной реализации возможно увидеть скачки.

Тем не менее, pwm-расширитель не умеет аппаратно сглаживать диммирование, поэтому для него есть смысл воспользоваться 
программной реализацией

Для запуска плавного перехода можно воспользоваться штатными сервисами, например:
```yaml
action:
  service: light.turn_on
  entity_id: light.some_light
  data:
    # свет будет плавно включаться в течении 30 секунд    
    brightness_pct: 50
    transition: 10 # кол-во секунд на переход
```
Так же любые диммируемые каналы могут участвовать в сценах, а эти сцены в свою очередь будут поддерживать опцию transition:
```yaml
action:
  service: scene.turn_on
  target:
    entity_id: scene.romantic
  data:
    transition: 2.5
```

Плавность реализована в любых диммируемых объектах: свет, rgb-ленты. 

Кроме того, возможно установить плавность по-умолчанию (имеет смысл использовать на pwm-расширителе), для этого в yaml-конфиге
следует добавить опцию smooth:
```yaml
mega:
  mega1:
    10e1:    
      smooth: 1 # если указать, то порт будет диммироваться плавно (от 0 до 100% за <smooth> секунд)
        # опцию smooth можно использовать и на обычном pwm-порте, но в этом мало необходимости, лучше использовать 
        # встроенный в контроллер механизм smooth
```

Для светодиодных лент smooth по умолчанию установлен в 1 секунду, 
подробнее [тут](yaml.md#rgb)