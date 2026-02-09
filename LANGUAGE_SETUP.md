# Language Support Setup Guide

## 繁體中文（廣東話）語音識別設置指南

This guide explains how to set up Cantonese/Chinese speech recognition for the chatbot.

## Prerequisites

The application already supports English voice recognition. To add Cantonese support, you need to download the Chinese Vosk model.

## Step 1: Download the Chinese Vosk Model

1. Visit the Vosk models page: https://alphacephei.com/vosk/models

2. Download the **Chinese model**: `vosk-model-cn-0.22`
   - Direct download link: https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip
   - Size: ~1.2 GB
   - This model supports Mandarin and can understand Cantonese to some extent

3. For better Cantonese support, you can also try:
   - `vosk-model-small-cn-0.22` (smaller, faster, 42 MB)

## Step 2: Extract and Place the Model

### macOS/Linux:

```bash
# Navigate to the project directory
cd /Users/lochunman/Desktop/Companion-Chatbot-for-Reducing-Loneliness-in-Elderly-Populations

# Create voice_models directory if it doesn't exist
mkdir -p voice_models

# Extract the downloaded model
cd voice_models
unzip ~/Downloads/vosk-model-cn-0.22.zip

# Verify the structure
ls -la vosk-model-cn-0.22
```

### Windows:

```cmd
cd voice_models
# Extract the downloaded ZIP file to voice_models/vosk-model-cn-0.22
```

## Step 3: Verify Installation

After extraction, your project structure should look like:

```
voice_models/
  ├── vosk-model-small-en-us-0.15/    # English model (already exists)
  │   ├── am/
  │   ├── conf/
  │   ├── graph/
  │   └── ivector/
  └── vosk-model-cn-0.22/              # Chinese model (newly added)
      ├── am/
      ├── conf/
      ├── graph/
      └── ivector/
```

## Step 4: Test the Application

1. Start the Flask server:
   ```bash
   python run.py
   ```

2. Check the console output. You should see:
   ```
   ✓ Cantonese model loaded from voice_models/vosk-model-cn-0.22
   ```

3. Log in and switch language to 繁中 (Traditional Chinese)

4. Click the microphone button and speak in Cantonese

## Language Switching

### In the Application:

- **Top-right corner buttons:**
  - `EN` - Switch to English
  - `繁中` - Switch to Traditional Chinese (繁體中文)

- **Voice Recognition:**
  - When language is set to EN → Uses English voice model
  - When language is set to 繁中 → Uses Chinese voice model

### Supported Languages:

| Language | Code | Voice Model | UI Translation |
|----------|------|-------------|----------------|
| English | en | vosk-model-small-en-us-0.15 | ✓ |
| Traditional Chinese (Cantonese) | zh-HK | vosk-model-cn-0.22 | ✓ |

## Troubleshooting

### Model Not Loading

If you see this warning:
```
⚠ Cantonese model not found at voice_models/vosk-model-cn-0.22
```

**Solution:**
- Verify the model directory name matches exactly: `vosk-model-cn-0.22`
- Check that all required subdirectories (am, conf, graph, ivector) exist
- Ensure proper file permissions

### Voice Recognition Not Working

1. **Check browser permissions:**
   - Browser → Settings → Privacy & Security → Microphone
   - Allow microphone access for localhost/your domain

2. **Check console for errors:**
   - Open browser Developer Tools (F12)
   - Look for JavaScript errors in the Console tab

3. **Test microphone:**
   - Try recording in the normal mode first
   - Speak clearly, 6-12 inches from microphone

### Poor Recognition Accuracy

**For Cantonese:**
- The model works best with standard Cantonese pronunciation
- Speak clearly and at a moderate pace
- Reduce background noise
- Try the accessibility mode for better voice-first interaction

## Alternative Models

### For Better Cantonese Support:

1. **Smaller/Faster Model:**
   ```
   vosk-model-small-cn-0.22 (42 MB)
   https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip
   ```

2. **Larger/More Accurate Model:**
   ```
   vosk-model-cn-0.22 (1.2 GB) - Recommended
   https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip
   ```

## Docker Setup

If using Docker, update the Dockerfile to download the Chinese model:

```dockerfile
# Add this in the builder stage
RUN cd /app/voice_models && \
    wget https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip && \
    unzip vosk-model-cn-0.22.zip && \
    rm vosk-model-cn-0.22.zip
```

## Notes

- The Chinese model supports both Mandarin and Cantonese, with better accuracy for Mandarin
- For best results with Cantonese, consider training a custom model or using cloud-based services
- Voice models are loaded once at application startup and kept in memory
- Each model requires approximately 400-800 MB of RAM when loaded

## Getting Help

If you encounter issues:
1. Check the console logs in the terminal running `python run.py`
2. Review browser console for JavaScript errors
3. Verify microphone permissions in your browser
4. Test with the English model first to isolate the issue

## Additional Resources

- Vosk API Documentation: https://alphacephei.com/vosk/
- Vosk Models List: https://alphacephei.com/vosk/models
- GitHub Repository: https://github.com/alphacep/vosk-api
