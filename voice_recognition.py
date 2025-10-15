import json
import queue
import sounddevice as sd
import vosk
import numpy as np
import threading
import time
from datetime import datetime
import webrtcvad
import wave
import os

class VoiceRecognition:
    def __init__(self, model_path="voice_models/vosk-model-en-us-0.22"):
        """
        初始化語音識別引擎
        Args:
            model_path: Vosk 模型路徑
        """
        print("加載 Vosk 語音識別模型中...")
        
        # 檢查模型是否存在
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk 模型未找到: {model_path}")
        
        # 加載 Vosk 模型
        self.model = vosk.Model(model_path)
        self.sample_rate = 16000
        self.device = None
        
        # 音頻緩衝區
        self.audio_queue = queue.Queue()
        self.is_listening = False
        self.recognition_thread = None
        
        # 語音活動檢測
        self.vad = webrtcvad.Vad(2)  # 中等靈敏度
        self.vad_frame_duration = 30  # ms
        
        # 會話管理
        self.current_session = None
        self.partial_results = ""
        
    def list_audio_devices(self):
        """列出可用的音頻設備"""
        devices = sd.query_devices()
        print("可用的音頻設備:")
        for i, device in enumerate(devices):
            print(f"{i}: {device['name']} (輸入通道: {device['max_input_channels']})")
        return devices
    
    def audio_callback(self, indata, frames, time, status):
        """音頻回調函數"""
        if status:
            print(f"音頻流錯誤: {status}")
        
        # 將音頻數據放入隊列
        audio_data = indata.copy()
        self.audio_queue.put(audio_data)
    
    def process_audio_stream(self):
        """處理音頻流進行語音識別"""
        rec = vosk.KaldiRecognizer(self.model, self.sample_rate)
        rec.SetWords(True)
        
        print("語音識別引擎就緒...")
        
        while self.is_listening:
            try:
                # 從隊列獲取音頻數據
                audio_data = self.audio_queue.get(timeout=1.0)
                
                # 轉換為單聲道和正確的格式
                if audio_data.ndim > 1:
                    audio_data = audio_data[:, 0]  # 取第一個聲道
                
                # 轉換為字節數據
                audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                
                # 語音活動檢測
                if self._voice_activity_detection(audio_bytes):
                    # 接受音頻數據進行識別
                    if rec.AcceptWaveform(audio_bytes):
                        result = json.loads(rec.Result())
                        text = result.get('text', '').strip()
                        if text:
                            print(f"識別結果: {text}")
                            self._save_voice_result(text, "final")
                            self.current_session = text
                    
                    else:
                        # 部分結果
                        partial_result = json.loads(rec.PartialResult())
                        partial_text = partial_result.get('partial', '').strip()
                        if partial_text and partial_text != self.partial_results:
                            self.partial_results = partial_text
                            print(f"部分結果: {partial_text}")
                            
            except queue.Empty:
                continue
            except Exception as e:
                print(f"音頻處理錯誤: {e}")
    
    def _voice_activity_detection(self, audio_bytes):
        """語音活動檢測"""
        try:
            # 檢查音頻幀是否包含語音
            return self.vad.is_speech(audio_bytes, self.sample_rate)
        except:
            return True  # 如果 VAD 失敗，默認接受所有音頻
    
    def start_listening(self, device_index=None):
        """開始語音監聽"""
        if self.is_listening:
            print("已經在監聽中...")
            return
        
        try:
            # 設置音頻流參數
            device_info = sd.query_devices(device_index, 'input')
            self.sample_rate = int(device_info['default_samplerate'])
            
            # 啟動音頻流
            self.audio_stream = sd.InputStream(
                device=device_index,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=8000,  # 500ms chunks
                callback=self.audio_callback,
                dtype='float32'
            )
            
            self.audio_stream.start()
            self.is_listening = True
            
            # 啟動識別線程
            self.recognition_thread = threading.Thread(target=self.process_audio_stream)
            self.recognition_thread.daemon = True
            self.recognition_thread.start()
            
            print("語音監聽已啟動...")
            
        except Exception as e:
            print(f"啟動語音監聽失敗: {e}")
            raise
    
    def stop_listening(self):
        """停止語音監聽"""
        if not self.is_listening:
            return
        
        self.is_listening = False
        
        if hasattr(self, 'audio_stream'):
            self.audio_stream.stop()
            self.audio_stream.close()
        
        if self.recognition_thread and self.recognition_thread.is_alive():
            self.recognition_thread.join(timeout=2.0)
        
        print("語音監聽已停止")
    
    def get_current_transcript(self):
        """獲取當前識別結果"""
        result = self.current_session
        self.current_session = None  # 清除當前會話
        return result
    
    def record_audio_file(self, duration=5, filename=None):
        """錄製音頻文件（用於測試）"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recordings/recording_{timestamp}.wav"
        
        print(f"開始錄製 {duration} 秒...")
        
        # 確保目錄存在
        os.makedirs("recordings", exist_ok=True)
        
        # 錄製音頻
        audio_data = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        
        # 保存為 WAV 文件
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
        
        print(f"音頻已保存: {filename}")
        return filename
    
    def _save_voice_result(self, text, result_type):
        """保存語音識別結果（用於日誌和分析）"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'text': text,
                'type': result_type
            }
            
            # 保存到日誌文件
            os.makedirs("voice_logs", exist_ok=True)
            log_file = "voice_logs/voice_recognition.log"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            print(f"保存語音日誌失敗: {e}")

# 全局語音識別實例
voice_recognizer = VoiceRecognition()