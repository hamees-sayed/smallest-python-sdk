import os
import json
import wave
import copy
import requests
from typing import Optional, Union, List

from smallest.exceptions import TTSError, APIError
from smallest.utils import (TTSOptions, validate_input, preprocess_text, add_wav_header, chunk_text,
get_smallest_languages, get_smallest_models, API_BASE_URL)

class Smallest:
    def __init__(
        self,
        api_key: str = None,
        model: Optional[str] = "lightning",
        sample_rate: Optional[int] = 24000,
        voice_id: Optional[str] = "emily",
        speed: Optional[float] = 1.0,
        add_wav_header: Optional[bool] = True,
        transliterate: Optional[bool] = False,
        remove_extra_silence: Optional[bool] = True
    ) -> None:
        """
        Smallest Instance for text-to-speech synthesis.

        This is a synchronous implementation of the text-to-speech functionality. 
        For an asynchronous version, please refer to the AsyncSmallest Instance.

        Args:
        - api_key (str): The API key for authentication, export it as 'SMALLEST_API_KEY' in your environment variables.
        - model (TTSModels): The model to be used for synthesis.
        - sample_rate (int): The sample rate for the audio output.
        - voice_id (TTSVoices): The voice to be used for synthesis.
        - speed (float): The speed of the speech synthesis.
        - add_wav_header (bool): Whether to add a WAV header to the output audio.
        - transliterate (bool): Whether to transliterate the text.
        - remove_extra_silence (bool): Whether to remove extra silence from the synthesized audio.

        Methods:
        - get_languages: Returns a list of available languages for synthesis.
        - get_voices: Returns a list of available voices for synthesis.
        - get_models: Returns a list of available models for synthesis.
        - synthesize: Converts the provided text into speech and returns the audio content.
        """
        self.api_key = api_key or os.environ.get("SMALLEST_API_KEY")
        if not self.api_key:
            raise TTSError()
        
        self.chunk_size = 250
        
        self.opts = TTSOptions(
            model=model,
            sample_rate=sample_rate,
            voice_id=voice_id,
            api_key=self.api_key,
            add_wav_header=add_wav_header,
            speed=speed,
            transliterate=transliterate,
            remove_extra_silence=remove_extra_silence
        )
    
        
    def get_languages(self) -> List[str]:
        """Returns a list of available languages."""
        return get_smallest_languages()
    
    def get_cloned_voices(self) -> str:
        """Returns a list of your cloned voices."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        res = requests.request("GET", f"{API_BASE_URL}/lightning-large/get_cloned_voices", headers=headers)
        if res.status_code != 200:
            raise APIError(f"Failed to get cloned voices: {res.text}. For more information, visit https://waves.smallest.ai/")
        
        return json.dumps(res.json(), indent=4, ensure_ascii=False)
    

    def get_voices(
            self,
            model: Optional[str] = "lightning"
        ) -> str:
        """Returns a list of available voices."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        res = requests.request("GET", f"{API_BASE_URL}/{model}/get_voices", headers=headers)
        if res.status_code != 200:
            raise APIError(f"Failed to get voices: {res.text}. For more information, visit https://waves.smallest.ai/")
        
        return json.dumps(res.json(), indent=4, ensure_ascii=False)
    

    def get_models(self) -> List[str]:
        """Returns a list of available models."""
        return get_smallest_models()
    
    
    def synthesize(
            self,
            text: str,
            save_as: Optional[str] = None,
            **kwargs
        ) -> Union[bytes, None]:
        """
        Synthesize speech from the provided text.

        Args:
        - text (str): The text to be converted to speech.
        - save_as (Optional[str]): If provided, the synthesized audio will be saved to this file path. 
                                   The file must have a .wav extension.
        - kwargs: Additional optional parameters to override `__init__` options for this call.

        Returns:
        - Union[bytes, None]: The synthesized audio content in bytes if `save_as` is not specified; 
                              otherwise, returns None after saving the audio to the specified file.

        Raises:
        - TTSError: If the provided file name does not have a .wav extension when `save_as` is specified.
        - APIError: If the API request fails or returns an error.
        """
        opts = copy.deepcopy(self.opts)
        for key, value in kwargs.items():
            setattr(opts, key, value)

        validate_input(preprocess_text(text), opts.model, opts.sample_rate, opts.speed)

        self.chunk_size = 250
        if opts.model == "lightning-large":
            self.chunk_size = 140

        chunks = chunk_text(text, self.chunk_size)
        audio_content = b""

        for chunk in chunks:
            payload = {
                "text": preprocess_text(chunk),
                "sample_rate": opts.sample_rate,
                "voice_id": opts.voice_id,
                "add_wav_header": False,
                "speed": opts.speed,
                "model": opts.model,
                "transliterate": opts.transliterate,
                "remove_extra_silence": opts.remove_extra_silence,
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            res = requests.post(f"{API_BASE_URL}/{opts.model}/get_speech", json=payload, headers=headers)
            if res.status_code != 200:
                raise APIError(f"Failed to synthesize speech: {res.text}. Please check if you have set the correct API key. For more information, visit https://waves.smallest.ai/")
            
            audio_content += res.content

        if save_as:
            if not save_as.endswith(".wav"):
                raise TTSError("Invalid file name. Extension must be .wav")
            
            with wave.open(save_as, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(opts.sample_rate)
                wf.writeframes(audio_content)
            return None
        
        if opts.add_wav_header:
            return add_wav_header(audio_content, opts.sample_rate)
    
        return audio_content
    
    
    def add_voice(self, display_name: str, file_path: str) -> str:
        """
        Instantly clone your voice synchronously.

        Args:
        - display_name (str): The display name for the new voice.
        - file_path (str): The path to the reference audio file to be cloned.

        Returns:
        - str: The response from the API as a formatted JSON string.

        Raises:
        - TTSError: If the file does not exist or is not a valid audio file.
        - APIError: If the API request fails or returns an error.
        """
        if not os.path.isfile(file_path):
            raise TTSError("Invalid file path. File does not exist.")
        
        ALLOWED_AUDIO_EXTENSIONS = ['.mp3', '.wav']
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise TTSError(f"Invalid file type. Supported formats are: {ALLOWED_AUDIO_EXTENSIONS}")
        
        url = f"{API_BASE_URL}/lightning-large/add_voice"
        payload = {'displayName': display_name}

        files = [('file', (os.path.basename(file_path), open(file_path, 'rb'), 'audio/wav'))]

        headers = {
            'Authorization': f"Bearer {self.api_key}",
        }

        response = requests.post(url, headers=headers, data=payload, files=files)
        if response.status_code != 200:
            raise APIError(f"Failed to add voice: {response.text}. For more information, visit https://waves.smallest.ai/")
        
        return json.dumps(response.json(), indent=4, ensure_ascii=False)
