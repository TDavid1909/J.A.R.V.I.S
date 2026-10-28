"""Prueba optativa de audio a intención, sin micrófono ni ejecución de acciones."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import wave

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from piper import PiperVoice
from speech import SpeechRecognizer, UtteranceSegmenter, FRAME_BYTES
from commands import wake_command, clean_request, is_stop_request
from capabilities import Capabilities


def main():
    config = json.loads((BASE / 'config.json').read_text())
    if len(sys.argv) > 1:
        config['speech_model'] = sys.argv[1]
    voice = PiperVoice.load(str(BASE / config['piper_model']))
    recognizer = SpeechRecognizer(config)
    tools = Capabilities(config)
    phrases = [('Jarvis, abre el navegador.', ('open_app', 'navegador')),
               ('Jarvis, detente.', ('stop', '')),
               ('Asistente, por favor abre el navegador.', ('open_app', 'navegador')),
               ('Puedes abrirme el navegador, por favor.', ('open_app', 'navegador')),
               ('Detente.', ('stop', '')),
               ('Deja de escuchar.', ('stop', '')),
               ('Para la música.', ('media', 'pause')),
               ('Pon la siguiente canción.', ('media', 'next')),
               ('Abre Steam.', ('open_app', 'steam'))]
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        for phrase, expected in phrases:
            wav = Path(tmp) / 'phrase.wav'
            with wave.open(str(wav), 'wb') as out:
                voice.synthesize_wav(phrase, out)
            pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(wav),
                                           '-f', 's16le', '-ar', '16000', '-ac', '1', '-'])
            raw = pcm + bytes(64000)
            segmenter = UtteranceSegmenter(config)
            utterances = []
            for offset in range(0, len(raw)-FRAME_BYTES+1, FRAME_BYTES):
                result = segmenter.feed(raw[offset:offset+FRAME_BYTES])
                if result:
                    utterances.append(result)
            started = time.monotonic()
            heard = ' '.join(recognizer.transcribe(data) for data in utterances)
            named = wake_command(heard, config['wake_words'])
            command = clean_request(heard if named is None else named)
            intent = ('stop', '') if is_stop_request(command) else tools.parse(command)
            matched = intent is not None and (intent[0], intent[1].casefold()) == expected
            # Las órdenes con nombre deben mantener la activación tras transcribir.
            if phrase.startswith(('Jarvis', 'Asistente')) and named is None:
                matched = False
            print(f'{"OK" if matched else "FALLO"}: {phrase} -> {heard!r} -> {intent} '
                  f'({time.monotonic()-started:.2f}s)', flush=True)
            if not matched:
                failures.append(phrase)
    assert not failures, failures
    print('OK: 9/9 órdenes de audio, sin ejecutar acciones.')


if __name__ == '__main__':
    main()
