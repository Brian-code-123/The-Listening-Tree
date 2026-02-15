# Language Support Setup Guide

## 繁體中文（廣東話）語音識別設置指南

This guide explains how to set up Cantonese/Chinese speech recognition for the chatbot.

## Prerequisites

The application supports bilingual speech recognition:
- **English**: Vosk offline model (already included)
- **繁體中文 (Cantonese)**: SenseVoiceSmall from Alibaba FunAudioLLM (automatic download)

## Setup Instructions

### Step 1: Install Required Dependencies

The application will automatically download the Cantonese model on first use. Simply ensure you have the required packages:

```bash
pip install -r requirements.txt
```

This will install:
- `funasr` - Alibaba's speech recognition framework
- `funasr-onnx` - ONNX runtime support
- `torchaudio` - Audio processing for PyTorch

### Step 2: Model Information

#### English Speech Recognition
- **Model**: Vosk Small English US 0.15
- **Location**: `voice_models/vosk-model-small-en-us-0.15/`
- **Type**: Offline, pre-downloaded
- **Size**: ~40 MB

#### Cantonese Speech Recognition  
- **Model**: SenseVoiceSmall (FunAudioLLM)
- **Source**: HuggingFace Hub - `FunAudioLLM/SenseVoiceSmall`
- **Type**: Auto-download on first use
- **Size**: ~300 MB (downloaded to cache)
- **Performance**: 
  - State-of-the-art Cantonese ASR
  - 5-15x faster than Whisper
  - Supports emotion recognition
  - Trained on 9,600 hours of Cantonese speech

### Step 3: How It Works

When you start the Flask server, the application will:

1. Load the English Vosk model (instant - already local)
2. Attempt to load SenseVoiceSmall for Cantonese:
   - First run: Downloads from HuggingFace (~300 MB)
   - Subsequent runs: Loads from local cache

You should see console output like:
```
✓ English Vosk model loaded from voice_models/vosk-model-small-en-us-0.15
Loading SenseVoiceSmall model for Cantonese recognition...
✓ SenseVoiceSmall (Cantonese) model loaded successfully
```

### Step 4: Usage

1. Start the Flask server:
   ```bash
   python run.py
   ```

2. Log in to the application

3. **Switch Language:**
   - Click `EN` button → English interface + English speech recognition
   - Click `繁中` button → 繁體中文介面 + 廣東話語音識別

4. **Use Voice Input:**
   - Click the microphone button
   - Speak in the selected language:
     - English when `EN` is selected
     - 廣東話 when `繁中` is selected
   - The appropriate model will automatically process your speech

## Technical Details

### Language Detection
- **Automatic routing**: The `/transcribe` endpoint automatically selects the appropriate model based on the user's language preference
- **Session-based**: Language preference is stored in Flask session and database

### Model Comparison

| Feature | English (Vosk) | Cantonese (SenseVoice) |
|---------|----------------|------------------------|
| Model Size | 40 MB | 300 MB |
| Download | Pre-included | Auto-download |
| Speed | Very Fast | Ultra Fast (15x faster than Whisper) |
| Accuracy | High | State-of-the-art |
| Offline | ✓ Yes | ✓ Yes (after first download) |
| Punctuation | ✗ No | ✓ Yes |
| Emotion Detection | ✗ No | ✓ Yes |

### SenseVoiceSmall Features
- Multilingual support (50+ languages including Cantonese)
- Non-autoregressive architecture for low latency
- Emotion recognition capabilities
- Audio event detection (applause, laughter, etc.)
- Trained on 9,600 hours of Cantonese speech data

## Troubleshooting

### Model Download Issues

If SenseVoiceSmall fails to download:

```
⚠ Could not load SenseVoiceSmall model: Connection timeout
```

**Solutions:**
1. **Check internet connection** - First download requires internet
2. **Manual cache setup:**
   ```bash
   # Pre-download the model
   python -c "from funasr import AutoModel; AutoModel(model='FunAudioLLM/SenseVoiceSmall', hub='hf')"
   ```
3. **Check disk space** - Model requires ~300 MB
4. **Firewall/Proxy**: Ensure HuggingFace Hub access is allowed

### Voice Recognition Not Working

1. **Check browser permissions:**
   - Browser → Settings → Privacy & Security → Microphone
   - Allow microphone access for localhost

2. **Verify model loading:**
   ```
   python run.py
   ```
   Look for: `✓ SenseVoiceSmall (Cantonese) model loaded successfully`

3. **Check console for errors:**
   - Open browser Developer Tools (F12)
   - Monitor Console and Network tabs

4. **Test microphone:**
   - Speak clearly, 6-12 inches from microphone
   - Try English first to verify microphone works

### Poor Recognition Accuracy

**For Cantonese:**
- Speak in standard Cantonese (廣州話/香港粵語)
- Speak at moderate pace, enunciate clearly
- Reduce background noise
- Position microphone properly
- SenseVoice performs best with natural conversational Cantonese

**For English:**
- Use clear American English accent for best results
- Avoid extremely fast speech

### Memory Issues

If you encounter memory errors:
```
RuntimeError: [enforce fail at alloc_cpu.cpp:114] data. DefaultCPUAllocator: not enough memory
```

**Solutions:**
1. **Close other applications** to free RAM
2. **Use CPU mode** (already default):
   ```python
   device="cpu"  # in run.py model loading
   ```
3. **System Requirements:**
   - Minimum: 4 GB RAM
   - Recommended: 8 GB RAM

## GPU Acceleration (Optional)

To use GPU for faster Cantonese recognition, modify [run.py](run.py#L75):

```python
sensevoice_model = AutoModel(
    model="FunAudioLLM/SenseVoiceSmall",
    device="cuda:0",  # Change from "cpu" to "cuda:0"
    hub="hf",
)
```

**Requirements:**
- NVIDIA GPU with CUDA support
- PyTorch with CUDA installed
- Adequate GPU memory (2+ GB VRAM)

## Docker Setup

Update your Dockerfile to support the new dependencies:

```dockerfile
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . /app
WORKDIR /app

# Model will auto-download on first use
EXPOSE 5000
CMD ["python", "run.py"]
```

## Language Support Table

| Language | Code | Voice Model | Transcription | UI Translation | Notes |
|----------|------|-------------|---------------|----------------|-------|
| English | en | Vosk Small EN | ✓ | ✓ | Offline, 40 MB |
| Traditional Chinese (Cantonese) | zh-HK | SenseVoiceSmall | ✓ | ✓ | Auto-download, 300 MB |

## Performance Benchmarks

### Cantonese Recognition (Character Error Rate)

Based on [cantonese_asr_eval](https://github.com/AlienKevin/cantonese_asr_eval):

| Domain | SenseVoice CER |
|--------|----------------|
| Mixed | 5.55% |
| Daily Use | 5.64% |
| Commands | 7.45% |
| Yue & English | 9.05% |
| Storytelling | 14.67% |
| Synthetic | 10.58% |

### Inference Speed
- **SenseVoice**: ~70ms for 10 seconds of audio
- **Whisper Large**: ~1050ms (15x slower)

## Additional Resources

- **SenseVoice GitHub**: https://github.com/FunAudioLLM/SenseVoice
- **SenseVoice HuggingFace**: https://huggingface.co/FunAudioLLM/SenseVoiceSmall
- **FunASR Documentation**: https://github.com/modelscope/FunASR
- **Cantonese ASR Evaluation**: https://github.com/AlienKevin/cantonese_asr_eval

## Getting Help

If you encounter issues:
1. Check terminal logs: `python run.py`
2. Review browser console (F12 → Console)
3. Verify microphone permissions
4. Test with English first to isolate the issue
5. Check [GitHub Issues](https://github.com/FunAudioLLM/SenseVoice/issues) for known problems

---

**Last Updated**: February 2026  
**Tech Stack**: Flask + Vosk (EN) + SenseVoiceSmall (廣東話)
