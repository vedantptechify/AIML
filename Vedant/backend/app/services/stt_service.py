# Deepgram / Whisper / Azure integration
import os
import aiohttp
from typing import AsyncIterator, Optional, List
from utils.redis_utils import get_audio_chunks
from utils import audio_utils


class STTProvider:
    async def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> str:
        raise NotImplementedError

    async def stream_transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> AsyncIterator[str]:
        text = await self.transcribe(audio_bytes, language)
        yield text


class AzureWhisperProvider(STTProvider):
    def __init__(self):
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment = os.getenv("AZURE_OPENAI_WHISPER_DEPLOYMENT")
        self.api_version = os.getenv("AZURE_OPENAI_WHISPER_API_VERSION")

        if not all([self.api_key, self.api_base, self.deployment, self.api_version]):
            raise ValueError("Missing Azure Whisper configuration. Check your environment variables.")

    async def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> str:
        url = f"{self.api_base}/openai/deployments/{self.deployment}/audio/transcriptions?api-version={self.api_version}"
        headers = {"api-key": self.api_key}

        form = aiohttp.FormData()
        if language:
            form.add_field("language", language)
        form.add_field("file", audio_bytes, filename="audio.wav", content_type="application/octet-stream")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
            async with session.post(url, headers=headers, data=form) as response:
                data = await response.json()
                if response.status != 200:
                    raise RuntimeError(f"Azure Whisper Error: {response.status} - {data}")
                return data.get("text", "")


class DeepgramProvider(STTProvider):
    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        self.api_url = "https://api.deepgram.com/v1/listen"

        if not self.api_key:
            raise ValueError("Missing Deepgram API key. Please set DEEPGRAM_API_KEY.")

    async def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> str:
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav"
        }

        params = {}
        if language:
            params["language"] = language

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
            async with session.post(self.api_url, headers=headers, params=params, data=audio_bytes) as response:
                data = await response.json()
                if response.status != 200:
                    raise RuntimeError(f"Deepgram Error: {response.status} - {data}")

                results = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])
                return results[0].get("transcript", "")


class STTService:
    def __init__(self, provider: Optional[STTProvider] = None):
        self.provider = provider or DeepgramProvider()

    async def transcribe_session(self, session_id: str, language: Optional[str] = None) -> str:
        chunks: List[bytes] = await get_audio_chunks(session_id)
        if not chunks:
            return ""

        audio_data = audio_utils.merge_chunks(chunks)
        audio_data = audio_utils.converted_audio_compatible(audio_data)
        return await self.provider.transcribe(audio_data, language)

    async def stream_transcribe_session(self, session_id: str, language: Optional[str] = None) -> AsyncIterator[str]:
        text = await self.transcribe_session(session_id, language)
        yield text




stt_service = STTService()
