from voice_recognition import voice_recognizer
import time

def test_multilingual_voice():
    """測試多語言語音識別"""
    
    print("測試多語言語音識別功能...")
    print("=" * 50)
    
    # 顯示可用語言
    languages = voice_recognizer.get_available_languages()
    print(f"可用語言: {languages}")
    
    # 顯示音頻設備
    print("\n音頻設備:")
    voice_recognizer.list_audio_devices()
    
    # 測試中文語音識別
    print("\n1. 測試中文語音識別")
    if voice_recognizer.start_listening(language='zh'):
        print("請說中文... (5秒後自動停止)")
        time.sleep(5)
        transcript = voice_recognizer.stop_listening()
        print(f"中文識別結果: {transcript}")
    else:
        print("❌ 中文語音識別啟動失敗")
    
    # 測試英文語音識別
    print("\n2. 測試英文語音識別")
    if voice_recognizer.start_listening(language='en'):
        print("Please speak English... (5 seconds auto stop)")
        time.sleep(5)
        transcript = voice_recognizer.stop_listening()
        print(f"English recognition result: {transcript}")
    else:
        print("❌ English voice recognition failed")
    
    print("\n測試完成！")

def test_audio_recording():
    """測試音頻錄製"""
    print("\n測試音頻錄製...")
    filename = voice_recognizer.record_audio_file(duration=3, user_id="test_user")
    if filename:
        print(f"音頻文件已保存: {filename}")
        
        # 測試轉錄
        print("轉錄音頻文件...")
        transcript = voice_recognizer.transcribe_audio_file(filename, language='zh')
        if transcript:
            print(f"轉錄結果: {transcript}")
        else:
            print("❌ 轉錄失敗")
    else:
        print("❌ 錄音失敗")

if __name__ == "__main__":
    test_multilingual_voice()
    test_audio_recording()