from pathlib import Path


class VoiceAuthenticator:

    def __init__(self):
        self.voice_profile = None
        self.profile_path = "data/voice_profile.npy"
        self.is_enrolled = False
        Path("data").mkdir(parents=True, exist_ok=True)
        self._load_profile()

    def enroll(self, audio_samples: list) -> bool:
        import numpy as np

        features = []
        for sample in audio_samples:
            feat = self._extract_features(sample)
            features.append(feat)

        self.voice_profile = np.mean(features, axis=0)
        np.save(self.profile_path, self.voice_profile)
        self.is_enrolled = True
        print("[Auth] Voice profile enrolled successfully")
        return True

    def verify(self, audio_path: str) -> dict:
        if not self.is_enrolled:
            return {
                "verified": True,
                "confidence": 1.0,
                "reason": "Not enrolled — open access",
            }

        features = self._extract_features(audio_path)
        similarity = self._cosine_similarity(features, self.voice_profile)

        threshold = 0.75
        verified = similarity >= threshold

        return {
            "verified": verified,
            "confidence": float(similarity),
            "reason": (
                "Voice matched" if verified else f"Voice mismatch ({similarity:.0%})"
            ),
        }

    def _extract_features(self, audio_path: str):
        import numpy as np
        import soundfile as sf

        audio, _ = sf.read(audio_path)

        energy = np.array(
            [
                np.sum(audio[index:index + 512] ** 2)
                for index in range(0, len(audio) - 512, 256)
            ]
        )

        zcr = np.array(
            [
                np.sum(np.abs(np.diff(np.sign(audio[index:index + 512]))))
                for index in range(0, len(audio) - 512, 256)
            ]
        )

        energy_feat = energy[:50] if len(energy) >= 50 else np.pad(energy, (0, 50 - len(energy)))
        zcr_feat = zcr[:50] if len(zcr) >= 50 else np.pad(zcr, (0, 50 - len(zcr)))

        features = np.concatenate([energy_feat, zcr_feat])

        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm

        return features

    def _cosine_similarity(self, a, b) -> float:
        import numpy as np

        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(dot / norm)

    def _load_profile(self):
        import numpy as np

        if Path(self.profile_path).exists():
            self.voice_profile = np.load(self.profile_path)
            self.is_enrolled = True
            print("[Auth] Voice profile loaded")
