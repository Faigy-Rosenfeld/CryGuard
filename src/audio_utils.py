import librosa
import numpy as np


def load_audio(file_path, sr=22050):
    audio, sample_rate = librosa.load(file_path, sr=sr)
    return audio, sample_rate


def extract_melspectrogram(audio, sr=22050, n_mels=128):
    mel = librosa.feature.melspectrogram(y=audio, sr=sr, n_mels=n_mels)
    return librosa.power_to_db(mel, ref=np.max)
