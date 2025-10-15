import time
from voice_recognition import voice_recognizer

def test_voice_recognition():
    print("測試語音識別功能...")
    
    try:
        # 列出音頻設備
        print("音頻設備列表:")
        voice_recognizer.list_audio_devices()
        
        # 啟動語音識別
        print("啟動語音識別...")
        voice_recognizer.start_listening()
        
        # 監聽 10 秒
        print("請說話... (10秒後自動停止)")
        time.sleep(10)
        
        # 停止並獲取結果
        voice_recognizer.stop_listening()
        transcript = voice_recognizer.get_current_transcript()
        
        if transcript:
            print(f"最終識別結果: {transcript}")
        else:
            print("沒有識別到語音")
            
    except Exception as e:
        print(f"測試失敗: {e}")

if __name__ == "__main__":
    test_voice_recognition()