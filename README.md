# Copy of J.A.R.V.I.S

Asistente de voz local en español con Ollama/Qwen 3.5 4B, reconocimiento Whisper Medium y detector de voz Silero y voz neuronal Piper. Usa el micrófono **USB PnP Audio Device** y la salida de audio predeterminada del sistema. Tiene un perfil de voz inspirado en JARVIS latino, sin reproducir la voz exacta del actor.

## Preparar una copia del repositorio

Este proyecto está orientado a Linux con PipeWire/PulseAudio y systemd. Requiere Python 3.10 o posterior, Ollama y las herramientas `parec`, `paplay`, `espeak-ng`, `ffmpeg`, `wpctl`, `playerctl` y `pdftotext` disponibles en el sistema.

Desde la carpeta del repositorio:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp config.example.json config.json
```

Edite `config.json` para su micrófono y sus carpetas. El repositorio no incluye los modelos descargados: coloque Whisper Medium compatible con faster-whisper en `models/faster-whisper-medium/` y la voz Piper `es_MX-claude-high.onnx`, junto con su archivo `.onnx.json`, en `models/voices/`. Consulte las fuentes enlazadas al final para obtenerlos. Con Ollama instalado y en ejecución, descargue el modelo:

```bash
ollama pull qwen3.5:4b
.venv/bin/python jarvis.py --check
.venv/bin/python jarvis.py
```

Los comandos `jarvis iniciar`, `jarvis detener` y similares de esta documentación pertenecen al lanzador y servicio instalados en el equipo original. Para una copia nueva, ejecute `.venv/bin/python jarvis.py` directamente; también acepta las opciones `--text`, `--say`, `--tools` y `--connect-google` descritas abajo.

La configuración personal, las credenciales, los modelos, las muestras de audio, el entorno virtual y las copias antiguas de archivos quedan fuera de Git mediante `.gitignore`.

## Iniciar y hablar

Abra Jarvis desde el menú o use:

```bash
jarvis iniciar
jarvis detener
jarvis estado
jarvis registro
```

Puede decir **«Jarvis, abre el navegador»** en una sola frase. También puede decir **«Jarvis»** o **«asistente»**, esperar la respuesta y dar la orden. Durante los primeros 45 segundos después de iniciarlo y durante 45 segundos después de cada respuesta puede dar órdenes sin repetir el nombre. Diga **«detente»**, **«para»** o **«deja de escuchar»** para cerrar Jarvis mientras está escuchando, incluso si ya terminó esa ventana.

El micrófono se pausa al generar y reproducir las respuestas. No admite interrupciones mientras habla. La voz y la IA funcionan sin Internet tras la descarga inicial. Navegación y Google requieren conexión.

## Control del PC

Ejemplos:

- «Estado del sistema», «cuánta memoria queda», «espacio en disco», «uso de CPU», «estado de la red».
- «Qué aplicaciones están abiertas».
- «Abre calculadora», «abre terminal», «abre archivos», «abre editor», «abre Steam», «abre Discord».
- «Enfoca archivos», «cambia a terminal».
- «Pausa la música», «reanuda la música», «siguiente canción», «canción anterior», «qué está sonando».
- «Pon el volumen al 35 por ciento», «sube el volumen», «baja el volumen».
- «Qué hora es», «qué día es».

El control multimedia requiere un reproductor compatible con MPRIS, como el navegador con una canción o vídeo activo. Las aplicaciones disponibles se muestran con `jarvis --tools`. Jarvis solo lanza las aplicaciones habilitadas, sin ejecutar comandos arbitrarios dictados o generados por la IA. Algunas paráfrasis se interpretan con Ollama; puede usar los ejemplos exactos si interpreta mal una petición.

## Archivos y notas

Puede buscar en Documents, Downloads, Desktop, Projects y Notes. Las carpetas se ajustan en `file_roots` dentro de `config.json`.

- «Busca archivos factura».
- «Abre el primero».
- «Lee el archivo informe.txt».
- «Resume el primero».
- «Resúmelo» (el último documento seleccionado).
- «Toma nota comprar café mañana».

Los números corresponden a la última búsqueda de archivos dentro de la misma sesión. Si hay varios resultados, pida el número deseado. `--text` crea una sesión nueva en cada ejecución y no conserva esos números entre comandos.

Lee texto, PDF con texto, DOCX y ODT. Los PDF escaneados requieren OCR y aún no se leen. Los documentos tienen un límite de 25 MB; los PDF se limitan a las primeras 30 páginas. Los resúmenes toman hasta 18.000 caracteres y la lectura literal se limita a 3.500. No abre ejecutables ni accesos directos. Las notas nuevas se guardan en `~/Notes/Jarvis`; no sobrescribe documentos existentes. Las carpetas ocultas, configuraciones y enlaces que salen de las carpetas habilitadas se excluyen.

## Navegador

- «Busca en Internet cómo preparar pasta» abre los resultados.
- «Busca en YouTube música de jazz» abre los resultados; no garantiza reproducción automática.
- «Abre Gmail», «abre calendario», «abre Drive», «abre WhatsApp» o «abre YouTube».
- «Resume la página https://example.com» lee y resume esa dirección pública.

La lectura directa de páginas funciona con HTML o texto públicos. No lee pestañas abiertas ni el contenido de páginas que requieren iniciar sesión. No maneja formularios ni publica mensajes. Las páginas con mucho JavaScript pueden no proporcionar texto útil.

## Gmail y Google Calendar

La integración de lectura está instalada, pero **necesita autorización de su cuenta**. Consulte [GOOGLE_SETUP.md](GOOGLE_SETUP.md) para crear el cliente OAuth de escritorio y conectar la cuenta:

```bash
jarvis conectar-google
```

Después de autorizar:

- «Mis correos» (hasta cinco mensajes de la bandeja de entrada).
- «Correos sin leer».
- «Lee el correo uno» (de la lista anterior, en la misma sesión).
- «Qué tengo hoy», «qué tengo mañana», «próximos eventos».

No envía correos ni modifica eventos. Abre Gmail o Calendar en el navegador cuando quiera hacerlo manualmente. La autorización de este programa es independiente de las conexiones de este chat.

## Privacidad y registros

Los documentos y sus resúmenes se procesan con Ollama en este PC. Las grabaciones y transcripciones no se guardan. El historial de conversación y las selecciones de archivos/correos duran durante la sesión en memoria. Las notas se guardan solo cuando se solicitan.

`log_responses` está desactivado: el diario registra que se reprodujo una respuesta, sin guardar su contenido. Las respuestas anteriores a esta ampliación pueden seguir presentes en el diario del sistema. `jarvis --text` muestra la respuesta en la terminal porque se solicita expresamente.

Los permisos de lectura de Google y su token se detallan en GOOGLE_SETUP.md. El contenido de las fuentes se resume como datos y no se utiliza para decidir nuevas acciones sobre el equipo.

## Voz

`tts_engine` selecciona `piper` (principal) o `espeak` (respaldo). Piper usa `models/voices/es_MX-claude-high.onnx`. El perfil `voice_effect: "jarvis_latino"` aplica tono ligeramente más grave, ecualización y compresión suaves. `voice_pitch: 0.94` ajusta el tono y `piper_length_scale: 1.05` da un ritmo algo más pausado. Para quitar el efecto use `voice_effect: "none"`.

```bash
jarvis --say 'A su disposición, señor. ¿En qué puedo asistirle?'
```

## Configuración y diagnóstico

Edite `config.json` y reinicie:

```bash
systemctl --user restart jarvis.service
jarvis --check
jarvis --tools
jarvis --text 'estado del sistema'
ollama ps
```

`source` selecciona el micrófono PulseAudio por su nombre. `sink` selecciona la salida; vacío respeta la salida predeterminada. Liste dispositivos con `pactl list short sources` y `pactl list short sinks`. `followup_seconds` controla el tiempo para continuar la conversación. `natural_commands` activa la interpretación de paráfrasis con IA. Las aplicaciones permitidas pueden personalizarse con un objeto `apps` cuyos valores sean listas de ejecutable y argumentos, sin shell.

Ollama usa Vulkan, escucha en 127.0.0.1:11434 y tiene las funciones de nube desactivadas. Su servicio se inicia con el sistema. Jarvis se inicia manualmente y no activa el micrófono después de reiniciar, salvo que habilite expresamente su inicio automático:

```bash
systemctl --user enable jarvis.service
```

Puede revertirlo con `systemctl --user disable jarvis.service`.

## Desarrollo

Las nuevas herramientas viven en `capabilities.py` y Google en `google_services.py`. Las dependencias de Python se declaran en `requirements.txt` y se instalan en `.venv`, separadas del Python del sistema. Las copias locales anteriores a la ampliación se excluyen del repositorio.

Pruebas:

```bash
cd ~/Projects/jarvis
.venv/bin/python -m unittest discover -s tests -v
```

Fuentes: [Vosk](https://alphacephei.com/vosk/models), [Piper](https://github.com/OHF-Voice/piper1-gpl), [Ollama](https://docs.ollama.com/api/chat), [playerctl](https://github.com/altdesktop/playerctl), [Gmail API](https://developers.google.com/workspace/gmail/api/quickstart/python), [Calendar API](https://developers.google.com/workspace/calendar/api/quickstart/python).

## Corrección del reconocimiento de órdenes

Se sustituyó el reconocimiento Vosk pequeño por Whisper Medium multilingüe con cálculo int8 en CPU, local y sin descargas al arrancar. Silero detecta la voz y espera 0,9 segundos de silencio para cerrar una frase. Conserva un segundo previo al comienzo para no perder la primera palabra. La palabra de activación ya no corta el resto de la petición.

Las formas «puedes abrirme el navegador», «por favor abre el navegador» y las órdenes de parada se procesan directamente. Se eliminó la activación ambigua «ya ves». Los nombres de aplicaciones largos pueden corregirse si hay una única coincidencia claramente cercana dentro de las aplicaciones habilitadas.

La transcripción toma aproximadamente 1–2 segundos en las muestras de prueba de este equipo; la latencia real depende del audio. Se comprobaron nueve órdenes sintetizadas desde audio hasta intención, además de 22 pruebas de lógica. Esto no sustituye una prueba con su voz y ruido ambiente.

Si una frase sigue fallando, ejecute manualmente:

```bash
jarvis --listen-test
```

Durante 30 segundos muestra en esa terminal lo que oye y cómo interpreta cada frase, sin ejecutar acciones. No guarda audio ni transcripciones. Salga antes con Ctrl+C. Así puede comprobar si el problema viene del micrófono, de la transcripción o de la interpretación.

Jarvis permanece detenido hasta iniciarlo manualmente; este cambio no habilita el arranque automático. Sigue sin escuchar mientras reproduce una respuesta: dé la orden de parada cuando termine de hablar, o use `jarvis detener` desde la terminal para detenerlo inmediatamente.

La prueba de audio reproducible se ejecuta con:

```bash
cd ~/Projects/jarvis
.venv/bin/python tests/check_audio.py
```

[Reconocimiento faster-whisper](https://github.com/SYSTRAN/faster-whisper).
