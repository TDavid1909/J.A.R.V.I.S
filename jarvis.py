#!/usr/bin/env python3
"""Jarvis local: Vosk, PipeWire, eSpeak NG y Ollama."""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess as sp
import sys
import tempfile
import time
import unicodedata
import urllib.request
import wave
from urllib.parse import quote_plus

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / 'config.json').read_text())
from commands import clean_request, is_stop_request, wake_command as detect_wake
from capabilities import Capabilities
CAPABILITIES = Capabilities(CONFIG)
SYSTEM = ('Eres Jarvis, un asistente de voz en CachyOS. Responde siempre en español, '
          'con un máximo de tres frases breves, sin Markdown ni listas. '
          'No afirmes ejecutar acciones ni tener acceso a datos en tiempo real. '
          'Solo conversas; otra parte del programa gestiona órdenes del equipo. '
          'Habla con la cortesía serena de un asistente personal: usa usted, '
          'frases precisas y humor seco ocasional. Puedes usar señor con moderación. '
          'No inventes diagnósticos, accesos ni acciones realizadas.')
HELP = ('Puedes preguntarme lo que quieras. También puedes decir: qué hora es, '
        'qué día es, abre navegador, abre terminal, abre archivos, busca seguido de tu búsqueda, '
        'sube el volumen, baja el volumen, nueva conversación o detente.')

def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn').strip(' ¿?¡!.,')

def wake_command(text):
    return detect_wake(text, CONFIG['wake_words'])

_piper_voice = None

def synthesize_speech(text, wav):
    global _piper_voice
    if CONFIG.get('tts_engine', 'espeak') == 'piper':
        try:
            from piper import PiperVoice, SynthesisConfig
            if _piper_voice is None:
                _piper_voice = PiperVoice.load(str(BASE / CONFIG['piper_model']))
            with wave.open(str(wav), 'wb') as output:
                _piper_voice.synthesize_wav(text, output, syn_config=SynthesisConfig(
                    length_scale=CONFIG.get('piper_length_scale', 1.0)))
            return
        except Exception as exc:
            print(f'Piper no pudo generar la voz; usando eSpeak: {exc}', file=sys.stderr, flush=True)
    sp.run(['espeak-ng', '-v', CONFIG['voice'], '-s', str(CONFIG['speed']),
            '-w', str(wav), '--stdin'], input=text, text=True, check=True, timeout=60)

def voice_effect(wav):
    if CONFIG.get('voice_effect') != 'jarvis_latino':
        return wav
    processed = wav.with_name('speech-jarvis.wav')
    pitch = max(0.85, min(1.1, float(CONFIG.get('voice_pitch', 0.94))))
    filters = (f'rubberband=pitch={pitch},highpass=f=75,lowpass=f=8500,'
               'equalizer=f=170:t=q:w=0.8:g=1.5,'
               'equalizer=f=3000:t=q:w=1:g=1.2,'
               'acompressor=threshold=0.18:ratio=2:attack=10:release=100:makeup=1.1,'
               'alimiter=limit=0.90:level=false')
    try:
        sp.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                '-i', str(wav), '-af', filters, '-c:a', 'pcm_s16le', str(processed)],
               check=True, timeout=30)
        return processed
    except (OSError, sp.SubprocessError) as exc:
        print(f'No se pudo aplicar el perfil de voz: {exc}', file=sys.stderr, flush=True)
        return wav

def speak(text):
    if CONFIG.get('log_responses', False):
        print('Jarvis: ' + text, flush=True)
    else:
        print('Jarvis: reproduciendo respuesta de voz.', flush=True)
    with tempfile.TemporaryDirectory(prefix='jarvis-') as tmp:
        wav = Path(tmp) / 'speech.wav'
        synthesize_speech(text, wav)
        wav = voice_effect(wav)
        playback = ['paplay', '--client-name=Jarvis', '--stream-name=Voz de Jarvis']
        if CONFIG.get('sink'):
            playback += ['--device=' + CONFIG['sink']]
        sp.run(playback + [str(wav)], check=True, timeout=120)

def launch(argv):
    sp.Popen(argv, stdout=sp.DEVNULL, stderr=sp.DEVNULL, start_new_session=True)

def respond(text, history):
    named_command = wake_command(text)
    text = clean_request(named_command if named_command is not None else text)
    command = normalize(text)
    if is_stop_request(text):
        return 'Hasta luego.', True
    if command in ('ayuda', 'que puedes hacer'):
        return ('Puedo controlar aplicaciones y música, consultar el equipo, buscar, abrir, leer y resumir archivos, '
                'guardar notas, abrir páginas y resumir una URL. Con su autorización de Google también puedo leer '
                'Gmail y su agenda. Ejemplos: estado del sistema, pausa la música, busca archivos factura, '
                'resume el primero, abre Gmail, mis correos o qué tengo hoy.'), False
    if command in ('nueva conversacion', 'olvida la conversacion', 'borra la conversacion'):
        history.clear()
        return 'Empezamos una conversación nueva.', False
    tool_answer = CAPABILITIES.handle(text)
    if tool_answer is not None:
        history.extend([{'role': 'user', 'content': text}, {'role': 'assistant', 'content': tool_answer[:4000]}])
        del history[:-12]
        return tool_answer, False
    if re.fullmatch(r'(?:dime )?(?:que hora es|la hora)', command):
        return 'Son las ' + dt.datetime.now().strftime('%H:%M') + '.', False
    if command in ('que dia es', 'que fecha es', 'dime la fecha'):
        now = dt.datetime.now()
        months = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
        return f'Hoy es {now.day} de {months[now.month-1]} de {now.year}.', False
    apps = {'abre navegador': ['xdg-open', 'https://duckduckgo.com'],
            'abre el navegador': ['xdg-open', 'https://duckduckgo.com'],
            'abre firefox': ['firefox'], 'abre terminal': ['kitty'],
            'abre la terminal': ['kitty'], 'abre archivos': ['dolphin'],
            'abre el explorador': ['dolphin']}
    if command in apps:
        launch(apps[command])
        return 'Abriendo.', False
    if command.startswith(('busca ', 'buscar ')):
        query = command.split(' ', 1)[1]
        launch(['xdg-open', 'https://duckduckgo.com/?q=' + quote_plus(query)])
        return 'Buscando ' + query + '.', False
    volumes = {'sube el volumen': '5%+', 'baja el volumen': '5%-'}
    if command in volumes:
        sp.run(['wpctl', 'set-volume', '-l', '1.0', '@DEFAULT_AUDIO_SINK@', volumes[command]],
               check=True, timeout=5)
        return 'Volumen ajustado.', False
    if command in ('silencia el audio', 'quita el sonido', 'activa el sonido'):
        sp.run(['wpctl', 'set-mute', '@DEFAULT_AUDIO_SINK@',
                '0' if command == 'activa el sonido' else '1'], check=True, timeout=5)
        return 'Hecho.', False
    payload = {'model': CONFIG['ollama_model'], 'stream': False, 'think': False,
               'messages': [{'role': 'system', 'content': SYSTEM}] + history[-12:] +
                           [{'role': 'user', 'content': text}],
               'keep_alive': '5m', 'options': {'num_ctx': 4096, 'num_predict': 220}}
    req = urllib.request.Request('http://127.0.0.1:11434/api/chat',
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            answer = json.load(response)['message']['content'].strip()
        answer = re.sub(r'<think>.*?</think>', '', answer, flags=re.S).strip()
        if not answer:
            raise ValueError('Respuesta vacía de Ollama')
        history.extend([{'role': 'user', 'content': text}, {'role': 'assistant', 'content': answer}])
        del history[:-12]
        return answer, False
    except (OSError, ValueError, KeyError) as exc:
        print(f'Ollama: {exc}', file=sys.stderr, flush=True)
        return 'No pude contactar con la IA local. Revisa Ollama e inténtalo de nuevo.', False

def capture():
    args = ['parec', '--raw', '--format=s16le', '--rate=16000', '--channels=1', '--latency-msec=100']
    if CONFIG.get('source'):
        args += ['--device=' + CONFIG['source']]
    return sp.Popen(args, stdout=sp.PIPE)

def stop_capture(proc):
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except sp.TimeoutExpired:
        proc.kill()
        proc.wait()
    proc.stdout.close()

def listen(diagnostic_seconds=0):
    from speech import SpeechRecognizer, UtteranceSegmenter, FRAME_BYTES
    recognizer = SpeechRecognizer(CONFIG)
    segmenter = UtteranceSegmenter(CONFIG)
    history, proc = [], None
    active_until = time.monotonic() + CONFIG['followup_seconds']
    if diagnostic_seconds:
        print('Prueba de escucha: diga una orden. Mostrará el texto, sin ejecutar acciones.', flush=True)
    else:
        speak('A su disposición, señor. Puede decir Jarvis, seguido de su orden en una sola frase.')
        active_until = time.monotonic() + CONFIG['followup_seconds']
    deadline = time.monotonic() + diagnostic_seconds if diagnostic_seconds else None
    try:
        proc = capture()
        while deadline is None or time.monotonic() < deadline:
            if deadline is not None and not select.select([proc.stdout], [], [], 0.2)[0]:
                continue
            data = proc.stdout.read(FRAME_BYTES)
            if len(data) != FRAME_BYTES:
                raise RuntimeError('No se pudo leer el micrófono. Revise el dispositivo USB PnP.')
            pcm = segmenter.feed(data)
            if pcm is None:
                continue
            # La frase ya terminó. El nombre nunca interrumpe el resto de la orden.
            stop_capture(proc)
            proc = None
            text = recognizer.transcribe(pcm)
            if diagnostic_seconds:
                command = wake_command(text)
                command = clean_request(text if command is None else command)
                print('Oído: ' + (text or '(sin voz reconocible)'), flush=True)
                print('Orden: ' + command, flush=True)
                print('Interpretación: ' + ('detener Jarvis' if is_stop_request(command)
                      else str(CAPABILITIES.parse(command))), flush=True)
            elif text:
                command = wake_command(text)
                if command is None and (time.monotonic() <= active_until or is_stop_request(text)):
                    command = text
                if command is not None:
                    if not command:
                        speak('Le escucho, señor.')
                    else:
                        try:
                            answer, done = respond(command, history)
                        except (OSError, sp.SubprocessError) as exc:
                            print(type(exc).__name__, file=sys.stderr, flush=True)
                            answer, done = 'No pude completar esa acción.', False
                        speak(answer)
                        if done:
                            return
                    active_until = time.monotonic() + CONFIG['followup_seconds']
            segmenter.reset()
            proc = capture()
    finally:
        stop_capture(proc)

def diagnose():
    import shutil
    for tool in ('parec', 'paplay', 'espeak-ng', 'wpctl', 'playerctl', 'pdftotext'):
        if not shutil.which(tool):
            raise RuntimeError('Falta ' + tool)
    if CONFIG.get('tts_engine') == 'piper':
        from piper import PiperVoice
        PiperVoice.load(str(BASE / CONFIG['piper_model']))
    from speech import SpeechRecognizer, StreamingVAD
    SpeechRecognizer(CONFIG)
    StreamingVAD()
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags', timeout=5) as r:
        models = [m['name'] for m in json.load(r)['models']]
    if CONFIG['ollama_model'] not in models:
        raise RuntimeError('Falta el modelo de Ollama: ' + CONFIG['ollama_model'])
    proc = capture()
    try:
        if not select.select([proc.stdout], [], [], 5)[0] or not proc.stdout.read(4000):
            raise RuntimeError('No se reciben datos del micrófono')
    finally:
        stop_capture(proc)
    print('OK: dependencias, modelo español, Ollama y acceso al micrófono.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--text', help='Prueba una pregunta escrita sin micrófono')
    parser.add_argument('--speak', action='store_true', help='Lee la respuesta de --text')
    parser.add_argument('--say', help='Reproduce exactamente este texto para probar el audio')
    parser.add_argument('--connect-google', metavar='CLIENT_JSON', help='Autorizar Gmail y Calendar con credenciales OAuth de escritorio')
    parser.add_argument('--tools', action='store_true', help='Mostrar las herramientas habilitadas y el estado de Google')
    parser.add_argument('--listen-test', action='store_true', help='Escuchar 30 segundos y mostrar la transcripción sin ejecutar órdenes')
    args = parser.parse_args()
    if args.connect_google:
        from google_services import GoogleServices
        GoogleServices().connect(args.connect_google)
    elif args.tools:
        from google_services import GoogleServices
        print('Aplicaciones: ' + ', '.join(CAPABILITIES.apps))
        print('Carpetas: ' + ', '.join(str(p) for p in CAPABILITIES.roots))
        print('Multimedia: playerctl. Navegador: búsquedas, páginas públicas y resumen de URL.')
        print('Google: ' + ('token guardado; falta verificar acceso' if GoogleServices().connected() else 'pendiente de autorización'))
    elif args.listen_test:
        listen(diagnostic_seconds=30)
    elif args.say is not None:
        speak(args.say)
    elif args.check:
        diagnose()
    elif args.text:
        answer, _ = respond(args.text, [])
        speak(answer) if args.speak else print(answer)
    else:
        lock = open(Path(os.environ.get('XDG_RUNTIME_DIR', '/tmp')) / f'jarvis-{os.getuid()}.lock', 'w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit('Jarvis ya está escuchando.')
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        listen()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nJarvis detenido.')
    except Exception as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
