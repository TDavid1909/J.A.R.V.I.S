"""Captura de frases completas con Silero VAD y transcripción local Whisper."""
from collections import deque
from pathlib import Path
import numpy as np

SAMPLE_RATE = 16000
FRAME_SAMPLES = 512
FRAME_BYTES = FRAME_SAMPLES * 2


class StreamingVAD:
    def __init__(self):
        from faster_whisper.vad import get_vad_model
        self.model = get_vad_model()
        names = {item.name for item in self.model.session.get_inputs()}
        if names != {'input', 'h', 'c'}:
            raise RuntimeError('La versión de Silero VAD instalada no es compatible con este capturador.')
        self.reset()

    def reset(self):
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, 64), dtype=np.float32)

    def __call__(self, frame):
        data = np.frombuffer(frame, dtype='<i2').astype(np.float32)[None, :] / 32768.0
        audio = np.concatenate((self.context, data), axis=1)
        output, self.h, self.c = self.model.session.run(None, {'input': audio, 'h': self.h, 'c': self.c})
        self.context = data[:, -64:]
        return float(np.asarray(output).reshape(-1)[-1])


class UtteranceSegmenter:
    def __init__(self, config, vad=None):
        self.vad = vad if vad is not None else StreamingVAD()
        self.threshold = float(config.get('speech_threshold', 0.5))
        self.silence_frames = max(1, round(float(config.get('speech_end_silence', 0.9)) * SAMPLE_RATE / FRAME_SAMPLES))
        self.max_frames = round(float(config.get('speech_max_seconds', 25)) * SAMPLE_RATE / FRAME_SAMPLES)
        self.reset()

    def reset(self):
        self.leading = deque(maxlen=32)  # Un segundo de margen para no perder la primera palabra.
        self.frames = []
        self.quiet = 0
        self.voiced = 0
        self.vad.reset()

    def feed(self, frame):
        if len(frame) != FRAME_BYTES:
            raise ValueError('El capturador requiere bloques de 512 muestras mono de 16 bits.')
        probability = self.vad(frame)
        voiced = probability >= (self.threshold if not self.frames else self.threshold - 0.15)
        if not self.frames:
            self.leading.append(frame)
            if not voiced:
                return None
            self.frames = list(self.leading)
            self.voiced = 1
            return None
        self.frames.append(frame)
        if voiced:
            self.quiet = 0
            self.voiced += 1
        else:
            self.quiet += 1
        if self.quiet < self.silence_frames and len(self.frames) < self.max_frames:
            return None
        # La espera de fin de frase no debe añadir casi un segundo de silencio al ASR.
        tail = max(0, self.quiet - 4)
        frames = self.frames[:-tail] if tail else self.frames
        result = b''.join(frames) if self.voiced >= 4 else None
        self.reset()
        return result


class SpeechRecognizer:
    def __init__(self, config):
        from faster_whisper import WhisperModel
        base = Path(__file__).resolve().parent
        self.model = WhisperModel(str(base / config['speech_model']), device='cpu',
                                  compute_type='int8', cpu_threads=6, num_workers=1,
                                  local_files_only=True)

    def transcribe(self, pcm):
        audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
        if len(audio) < SAMPLE_RATE // 5 or np.sqrt(np.mean(audio * audio)) < 0.0005:
            return ''
        # Solo nombres propios como contexto; ninguna lista de órdenes para completar.

        segments, _ = self.model.transcribe(audio, language='es', task='transcribe',
            beam_size=5, temperature=0.0, condition_on_previous_text=False,
            initial_prompt='Conversación en español con Jarvis. Nombres propios: Jarvis, Steam, Discord, Gmail, YouTube.',
            vad_filter=False, no_speech_threshold=0.6, log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4, word_timestamps=False)
        kept = [s.text.strip() for s in segments if s.avg_logprob >= -1.0 and s.no_speech_prob < 0.7]
        return ' '.join(kept).strip()
