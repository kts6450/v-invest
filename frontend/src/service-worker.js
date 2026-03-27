/**
 * PWA Service Worker - V-Invest
 *
 * [캐싱 전략]
 *   - Shell (App.js, CSS, 아이콘): Cache-First (오프라인 지원)
 *   - API 응답: Network-First (항상 최신 데이터 우선)
 *   - 폰트: Stale-While-Revalidate
 *
 * [푸시 알림]
 *   n8n 리포트 도착 시 백엔드 → Web Push → Service Worker → 알림
 *   (백엔드에서 web-push 라이브러리 사용 예정)
 */

const CACHE_NAME   = "v-invest-v1";
const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/static/js/main.chunk.js",
  "/static/css/main.chunk.css",
  "/manifest.json",
  "/icon-192.png",
  "/icon-512.png",
];

// ── 설치: Shell 자산 사전 캐싱 ──
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("[SW] Shell 캐싱 완료");
      return cache.addAll(SHELL_ASSETS).catch(() => {}); // 개발환경 파일 없어도 무시
    })
  );
  self.skipWaiting();
});

// ── 활성화: 이전 버전 캐시 삭제 ──
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── 네트워크 요청 인터셉트 ──
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url         = new URL(request.url);

  // API 요청: Network-First (최신 데이터 우선)
  if (url.pathname.startsWith("/api") || url.port === "8000") {
    event.respondWith(
      fetch(request)
        .catch(() => caches.match(request)) // 오프라인 시 캐시 fallback
    );
    return;
  }

  // 폰트: Stale-While-Revalidate
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          const network = fetch(request).then((res) => {
            cache.put(request, res.clone());
            return res;
          });
          return cached || network;
        })
      )
    );
    return;
  }

  // Shell: Cache-First
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request))
  );
});


// ── 푸시 알림 수신 ──
self.addEventListener("push", (event) => {
  const data = event.data?.json() || {};
  const title = data.title || "V-Invest 알림";
  const body  = data.body  || "새 AI 투자 리포트가 도착했습니다.";

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon:   "/icon-192.png",
      badge:  "/icon-192.png",
      vibrate: [200, 100, 200],      // 촉각 피드백 패턴 (시각 장애인용)
      tag:    "v-invest-report",     // 같은 tag = 기존 알림 교체 (중복 방지)
      actions: [
        { action: "open",   title: "열기" },
        { action: "dismiss", title: "닫기" },
      ],
      data: { url: data.url || "/" },
    })
  );
});


// ── 알림 클릭 처리 ──
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  if (event.action === "dismiss") return;

  const targetUrl = event.notification.data?.url || "/";
  event.waitUntil(
    clients.matchAll({ type: "window" }).then((clientList) => {
      const existing = clientList.find((c) => c.url === targetUrl);
      if (existing) return existing.focus();
      return clients.openWindow(targetUrl);
    })
  );
});
