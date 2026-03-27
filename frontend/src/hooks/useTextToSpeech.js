/**
 * useTextToSpeech - 텍스트 음성 변환 커스텀 훅
 *
 * [전략]
 *   1순위: Web Speech API SpeechSynthesis (브라우저 내장, 즉시, 무료)
 *   2순위: OpenAI TTS API (백엔드 /voice/tts, 고품질 nova 목소리)
 *
 * [시각 장애인 UX]
 *   - speak() 호출 시 자동으로 이전 발화 중지 후 새 발화 시작
 *   - 읽기 중 강조 단어 하이라이트 (SpeechSynthesis.onboundary)
 *   - 재생 완료 시 진동 피드백
 *
 * [사용법]
 *   const { speak, stop, isSpeaking } = useTextToSpeech();
 *   speak("비트코인 현재가 9만 3천 달러");
 */
import { useState, useRef, useCallback } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useTextToSpeech({ useOpenAI = false, voice = "nova", speed = 1.0 } = {}) {
  const [isSpeaking,    setIsSpeaking]    = useState(false);
  const [currentWord,   setCurrentWord]   = useState("");  // 현재 읽는 단어 (하이라이트용)
  const [error,         setError]         = useState(null);

  const utteranceRef = useRef(null);
  const audioRef     = useRef(null);


  // ── 음성 재생 ──
  const speak = useCallback(async (text) => {
    if (!text?.trim()) return;
    stop(); // 이전 발화 중지
    setError(null);

    if (useOpenAI) {
      await _speakWithOpenAI(text, voice, speed, audioRef, setIsSpeaking, setError);
    } else {
      _speakWithWebSpeech(text, utteranceRef, setIsSpeaking, setCurrentWord);
    }
  }, [useOpenAI, voice, speed]);


  // ── 음성 중지 ──
  const stop = useCallback(() => {
    // Web Speech 중지
    window.speechSynthesis?.cancel();
    // OpenAI 오디오 중지
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsSpeaking(false);
    setCurrentWord("");
  }, []);


  // ── 일시정지 / 재개 ──
  const pause  = useCallback(() => {
    window.speechSynthesis?.pause();
    audioRef.current?.pause();
  }, []);

  const resume = useCallback(() => {
    window.speechSynthesis?.resume();
    audioRef.current?.play();
  }, []);


  return { speak, stop, pause, resume, isSpeaking, currentWord, error };
}


// ── Web Speech API TTS (무료, 즉시) ──
function _speakWithWebSpeech(text, utteranceRef, setIsSpeaking, setCurrentWord) {
  const synth     = window.speechSynthesis;
  const utterance = new SpeechSynthesisUtterance(text);

  utterance.lang  = "ko-KR";
  utterance.rate  = 1.0;
  utterance.pitch = 1.0;

  // 한국어 목소리 선택 (있으면)
  const voices     = synth.getVoices();
  const korVoice   = voices.find((v) => v.lang.startsWith("ko"));
  if (korVoice) utterance.voice = korVoice;

  utterance.onstart = () => setIsSpeaking(true);
  utterance.onend   = () => {
    setIsSpeaking(false);
    setCurrentWord("");
    navigator.vibrate?.([50]);
  };

  // 단어 경계 이벤트 → 현재 읽는 단어 추적 (UI 하이라이트)
  utterance.onboundary = (e) => {
    if (e.name === "word") {
      setCurrentWord(text.substring(e.charIndex, e.charIndex + e.charLength));
    }
  };

  utteranceRef.current = utterance;
  synth.speak(utterance);
}


// ── OpenAI TTS API (고품질 nova 목소리) ──
async function _speakWithOpenAI(text, voice, speed, audioRef, setIsSpeaking, setError) {
  try {
    setIsSpeaking(true);
    const res = await fetch(`${API_BASE}/voice/tts`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ text, voice, speed }),
    });

    if (!res.ok) throw new Error("TTS API 오류");

    const blob     = await res.blob();
    const audioUrl = URL.createObjectURL(blob);
    const audio    = new Audio(audioUrl);

    audio.onended = () => {
      setIsSpeaking(false);
      URL.revokeObjectURL(audioUrl);
      navigator.vibrate?.([50]);
    };

    audioRef.current = audio;
    await audio.play();

  } catch (e) {
    setError(e.message);
    setIsSpeaking(false);
    // fallback to Web Speech
    _speakWithWebSpeech(text, { current: null }, setIsSpeaking, () => {});
  }
}
