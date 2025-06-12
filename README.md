# Bot Renfe

Este proyecto es un bot automatizado que busca trenes en tu abono de Renfe y los selecciona por ti. El bot se encarga de refrescar la página y seleccionar el tren deseado, ahorrándote tiempo y esfuerzo.

## Descripción

El bot está diseñado para ayudarte a encontrar y reservar trenes en tu abono de Renfe sin tener que estar constantemente refrescando la página. Una vez que inicias sesión y seleccionas el abono, podrás seleccionar una fecha y un trayecto (ida o vuelta) y los viajes (horas) que mejor te convengan. El bot intentará cogerlos indefinidamente hasta que consiga uno de ellos.

## Requisitos

Tener Playwright junto con sus navegadores.

Para ejecutar este proyecto, necesitas tener instaladas las siguientes librerías de Python:

- `PyQt6`
- `playwright`

Puedes instalar todas las dependencias utilizando el archivo `requirements.txt`:

```bash
pip install -r requirements.txt
```
## Uso
Simplemente ejecutar login.py y seguir las instrucciones. 

## Consideraciones
Renfe posiblemente solicite un captcha al iniciar sesión, por lo que se recomienda usar el inicio de sesión manual.
