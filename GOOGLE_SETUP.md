# Autorizar Gmail y Google Calendar para Jarvis

La integración está instalada. Falta crear un cliente OAuth y autorizar su cuenta en el navegador. Jarvis usa sus propias credenciales; no hereda las conexiones de este chat. No necesita una clave de IA de pago ni debe escribir su contraseña en Jarvis.

## Preparación en Google

1. Abra https://console.cloud.google.com/ y cree o seleccione un proyecto para Jarvis.
2. En «APIs y servicios → Biblioteca», habilite **Gmail API** y **Google Calendar API**.
3. Configure «Google Auth Platform» o la pantalla de consentimiento OAuth. Si el proyecto está en modo de prueba y es externo, añada su propia dirección en «Usuarios de prueba / Test users».
4. En «Clientes / Credenciales», cree un **ID de cliente OAuth de tipo Aplicación de escritorio**. No elija aplicación web ni cuenta de servicio.
5. Descargue el archivo JSON del cliente a su equipo. No lo pegue en el chat.

## Conexión

Ejecute desde su terminal:

```bash
jarvis conectar-google
```

Elija el JSON descargado. Se abrirá la pantalla de autorización de Google. También puede indicar la ruta directamente:

```bash
jarvis --connect-google /ruta/al/cliente.json
```

Jarvis solicita exclusivamente:

- Lectura de Gmail.
- Lectura de eventos de Google Calendar.

No solicita permisos para enviar correo, borrar mensajes ni modificar eventos. La lectura de mensajes no los marca como leídos. El token se guarda en `~/.config/jarvis/google-token.json` con permisos 600 dentro de una carpeta con permisos 700. El proceso de autorización usa un puerto local temporal y tiene un límite de tres minutos.

## Pruebas

```bash
jarvis --text 'mis correos'
jarvis --text 'qué tengo hoy'
```

Por voz:

- «Asistente», espere la respuesta y diga «mis correos».
- «Lee el correo uno» elige un mensaje de esa lista durante la misma sesión.
- «Correos sin leer».
- «Qué tengo hoy».
- «Qué tengo mañana».
- «Próximos eventos» (próximos siete días, calendario principal).

## Si Google rechaza el acceso

Compruebe que habilitó las dos APIs y añadió su cuenta como usuario de prueba. Un cliente externo en modo de prueba puede requerir que vuelva a autorizarlo periódicamente. Jarvis le indicará si debe reconectar. No desactive las protecciones de su cuenta.

Para revocar el acceso, quite Jarvis en las conexiones de terceros de su cuenta de Google: https://myaccount.google.com/connections .

Documentación oficial:

- https://developers.google.com/workspace/gmail/api/quickstart/python
- https://developers.google.com/workspace/calendar/api/quickstart/python
