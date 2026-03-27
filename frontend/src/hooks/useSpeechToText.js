/**
 * useSpeechToText - 음성 인식 커스텀 훅
 *
 * [전략]
 *   1순위: Web Speech API (브라우저 내장, 무료, 실시간)
 *   2순위: OpenAI Whisper API (백엔드 /voice/stt, 높은 정확도)
 *
 * [시각 장애인 UX]
 *   - 인식 중 시각적 피드백 대신 진동(navigator.vibrate) + 상태 텍스트
 *   - 에러 시 TTS 음성 안내
 *   - 자동 재시작(continuous mode) 지원
 *
 * [사용법]
 *   const { transcript, isListening, startListening, stopListening, error } = useSpeechToText();
 *   <button onPointerDown={startListening} onPointerUp={stopListening}>
 *     {isListening ? "듣는 중..." : "마이크"}
 *   </button>
 */
import { useState, useRef, useCallback, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useSpeechToText({ onResult, useWhisper = false } = {}) {
  const [transcript,  setTranscript]  = useState("");
  const [isListening, setIsListening] = useState(false);
  const [error,       setError]       = useState(null);
  const [interimText, setInterimText] = useState(""); // 실시간 중간 결과

  const recognitionRef  = useRef(null);   // Web Speech API SpeechRecognition
  const mediaRecorderRef = useRef(null);  // Whisper 모드용 MediaRecorder
  const audioChunksRef  = useRef([]);

  // ── Web Speech API 초기화 ──
  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition || useWhisper) return;

    const recognition = new SpeechRecognition();
    recognition.lang        = "ko-KR";     // 한국어 인식
    recognition.continuous  = false;       // 한 발화 후 자동 중지
    recognition.interimResults = true;     // 실시간 중간 결과 표시

    recognition.onresult = (event) => {
      let interim = "", final = "";
      for (const result of event.results) {
        if (result.isFinal) final   += result[0].transcript;
        else                interim += result[0].transcript;
      }
      setInterimText(interim);
      if (final) {
        setTranscript(final);
        onResult?.(final);
      }
    };

    recognition.onstart = () => {
      setIsListening(true);
      setError(null);
      // 진동으로 녹음 시작 알림 (시각 장애인 촉각 피드백)
      navigator.vibrate?.([100]);
    };

    recognition.onend = () => {
      setIsListening(false);
      setInterimText("");
      navigator.vibrate?.([50]);
    };

    recognition.onerror = (e) => {
      setError(`음성 인식 오류: ${e.error}`);
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => recognition.abort();
  }, [useWhisper, onResult]);


  // ── 녹음 시작 ──
  const startListening = useCallback(async () => {
    setError(null);
    setTranscript("");

    if (useWhisper) {
      // Whisper 모드: MediaRecorder로 오디오 캡처
      await _startWhisperRecording(
        mediaRecorderRef,
        audioChunksRef,
        setIsListening,
        setTranscript,
        setError,
        onResult,
      );
    } else {
      // Web Speech API 모드
      recognitionRef.current?.start();
    }
  }, [useWhisper, onResult]);


  // ── 녹음 중지 ──
  const stopListening = useCallback(async () => {
    if (useWhisper) {
      mediaRecorderRef.current?.stop();
    } else {
      recognitionRef.current?.stop();
    }
    setIsListening(false);
  }, [useWhisper]);


  return {
    transcript,
    interimText,
    isListening,
    error,
    startListening,
    stopListening,
  };
}


// ── Whisper 백엔드 연동 (고정밀 모드) ──
async function _startWhisperRecording(
  mediaRecorderRef, audioChunksRef,
  setIsListening, setTranscript, setError, onResult,
) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    audioChunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      const blob     = new Blob(audioChunksRef.current, { type: "audio/webm" });
      const formData = new FormData();
      formData.append("audio", blob, "recording.webm");

      try {
        const res  = await fetch(`${API_BASE}/voice/stt`, {
          method: "POST",
          body:   formData,
        });
        const data = await res.json();
        setTranscript(data.text || "");
        onResult?.(data.text || "");
      } catch (e) {
        setError("Whisper STT 오류: " + e.message);
      } finally {
        stream.getTracks().forEach((t) => t.stop());
      }
    };

    recorder.start();
    mediaRecorderRef.current = recorder;
    setIsListening(true);
    navigator.vibrate?.([100]);
  } catch (e) {
    setError("마이크 접근 오류: " + e.message);
  }
}
