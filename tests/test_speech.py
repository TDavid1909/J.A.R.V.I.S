import unittest
from unittest.mock import patch
import numpy as np

from commands import clean_request, wake_command, is_stop_request
from speech import UtteranceSegmenter, FRAME_BYTES
from capabilities import Capabilities
import jarvis


class CommandTests(unittest.TestCase):
    def test_stop_variants_never_reach_chat_or_tools(self):
        phrases = ('detente', 'Para', 'Deja de escuchar', 'Puedes detenerte por favor',
                   'Jarvis, detente.', 'Asistente, deja de escuchar', 'Por favor, párate')
        with patch.object(jarvis.CAPABILITIES, 'handle') as handle:
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    answer, done = jarvis.respond(phrase, [])
                    self.assertTrue(done)
                    self.assertIn('luego', answer)
            handle.assert_not_called()

    def test_stop_does_not_match_media_or_negations(self):
        for phrase in ('Para la música', 'No te detengas', 'Explícame qué significa detente'):
            self.assertFalse(is_stop_request(phrase))

    def test_wake_preserves_whole_command_and_avoids_phonetic_false_positives(self):
        words = ['jarvis', 'asistente']
        self.assertEqual(wake_command('Jarvis, abre el navegador.', words), 'abre el navegador')
        self.assertEqual(wake_command('Oye Jarvis, detente', words), 'detente')
        self.assertEqual(wake_command('Asistente', words), '')
        for text in ('ya ves, abre navegador', 'hablaba con Jarvis ayer', 'Jarvisiano es una palabra'):
            self.assertIsNone(wake_command(text, words))

    def test_browser_variants_do_not_need_llm(self):
        tools = Capabilities({'ollama_model': 'test'})
        with patch.object(tools, 'classify') as classify, patch('capabilities.launch') as launch:
            for text in ('abre el navegador', 'puedes abrir el navegador',
                         'Podrías abrirme el navegador por favor', 'abre el navegador web',
                         'abre Opera GX', 'por favor abre el browser', 'abre el naberador'):
                with self.subTest(text=text):
                    self.assertEqual(tools.handle(text), 'Abriendo navegador.')
            self.assertEqual(launch.call_count, 7)
            classify.assert_not_called()

    def test_politeness_preserves_filename(self):
        self.assertEqual(clean_request('¿Podrías abrirme el archivo Informe Médico.pdf, por favor?'),
                         'abre el archivo Informe Médico.pdf')


class FakeVAD:
    def __init__(self):
        self.probability = 0.0
    def reset(self):
        pass
    def __call__(self, frame):
        return self.probability


class SegmentationTests(unittest.TestCase):
    def test_does_not_cut_phrase_on_short_pause(self):
        vad = FakeVAD()
        segmenter = UtteranceSegmenter({'speech_end_silence': 0.9}, vad=vad)
        frame = bytes(FRAME_BYTES)
        for _ in range(20):
            self.assertIsNone(segmenter.feed(frame))
        vad.probability = 0.8
        for _ in range(10):
            self.assertIsNone(segmenter.feed(frame))
        vad.probability = 0.0
        for _ in range(15):  # Pausa de 480 ms entre nombre y orden.
            self.assertIsNone(segmenter.feed(frame))
        vad.probability = 0.8
        for _ in range(20):
            self.assertIsNone(segmenter.feed(frame))
        vad.probability = 0.0
        result = None
        for _ in range(29):
            output = segmenter.feed(frame)
            if output:
                result = output
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 50 * FRAME_BYTES)

    def test_silence_never_yields_command(self):
        segmenter = UtteranceSegmenter({}, vad=FakeVAD())
        for _ in range(200):
            self.assertIsNone(segmenter.feed(bytes(FRAME_BYTES)))

    def test_one_click_of_noise_is_not_an_utterance(self):
        vad = FakeVAD()
        segmenter = UtteranceSegmenter({}, vad=vad)
        vad.probability = 1.0
        self.assertIsNone(segmenter.feed(bytes(FRAME_BYTES)))
        vad.probability = 0.0
        for _ in range(40):
            self.assertIsNone(segmenter.feed(bytes(FRAME_BYTES)))


if __name__ == '__main__':
    unittest.main()
