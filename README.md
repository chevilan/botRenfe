# Bot Renfe

Este proyecto es un bot automatizado que busca trenes en tu abono de Renfe y los selecciona por ti. El bot se encarga de refrescar la página y seleccionar el tren deseado, ahorrándote tiempo y esfuerzo.

## Descripción

El bot está diseñado para ayudarte a encontrar y reservar trenes en tu abono de Renfe sin tener que estar constantemente refrescando la página. Una vez que inicias sesión y seleccionas el tren deseado, el bot se encargará de buscar el tren y reservarlo por ti.

## Requisitos

Para ejecutar este proyecto, necesitas tener instaladas las siguientes librerías de Python:

- `selenium`
- `webdriver-manager`
- `colorama`
- `cryptography`
- `python-dotenv`
- `twilio`

Puedes instalar todas las dependencias utilizando el archivo `requirements.txt`:

```bash
pip install -r requirements.txt
```
#Uso
Simplemente ejecutar main.py y seguir las instrucciones, se puede añadir un archivo .env con
export TWILIO_ACCOUNT_SID='[Tus datos de twilio]'
export TWILIO_AUTH_TOKEN='[Tus datos de twilio]'
si quieres que te avise al movil
