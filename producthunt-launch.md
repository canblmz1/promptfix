PRODUCT HUNT LAUNCH CHECKLIST

=== HESAP ===
1. https://www.producthunt.com/ adresine git
2. "Sign Up" ile kaydol (Google ile daha kolay)
3. Profili doldur (foto, bio, Twitter/LinkedIn bağlantıları)

=== ÜRÜN SAYFASI HAZIRLIK ===

Tagline (60 karakter max):
"Local prompt rewriter with built-in evaluation for AI coding agents"

Açıklama (uzun):
PromptFix is an open-source prompt engineering workbench that turns rough coding requests into structured, actionable prompts. It runs 100% locally, works with Groq/Ollama/OpenAI APIs, and includes a 40-test evaluation suite.

Key features:
- Intent detection (bugfix/feature/performance, supports English + Turkish)
- Output guard with validation and deterministic fallback
- Browser extension + global hotkeys + CLI
- Threaded chat with streaming and snippet support
- Built-in evaluation: rule-based and LLM judge scoring

Tech stack: Python 3.10+, vanilla JS, Flask. No React, no Docker, no SaaS.

Categories:
- Developer Tools
- Productivity
- Open Source
- AI

=== GÖRSELLER ===
[ ] Logo/Thumbnail (240x240 veya 500x500)
[ ] GIF demo (5-10 saniye, prompt öncesi/sonrası)
[ ] Screenshot 1: Ana arayüz/CLI kullanımı
[ ] Screenshot 2: Extension kullanımı
[ ] Screenshot 3: Chat arayüzü
[ ] Screenshot 4: Evaluation sonuçları

=== MAKER YORUMU (ilk yorum) ===
Hi Product Hunt! 👋

I built PromptFix because my prompts sucked and I was too lazy to improve them manually.

Every time I wrote "fix the login bug" I got garbage code back. Not because the AI is dumb, but because my prompt had zero context, zero scope, and zero guardrails.

So I built a tiny local tool that does the rewriting for me. Select text, hit a hotkey, get a proper prompt.

The built-in evaluation is what I'm most proud of — most prompt tools just "hope" the output is good. PromptFix tests itself with 40 scenarios and scores the results.

Runs 100% local. MIT licensed. Open source: https://github.com/canblmz1/promptfix

Try it, break it, tell me what sucks. I actually respond.

=== YAYINLAMA ===
- En iyi gün: PAZARTESİ
- En iyi saat: UTC 00:01 (gece yarısı)
- Türkiye saati: Salı 03:01
- Yayınlama öncesi 1 hafta "Coming Soon" sayfası oluştur (hunter bul)

=== HUNTER BULMA ===
- Product Hunt'ta aktif, takipçisi çok olan hunter'lar var
- DM at: "Would you hunt my open-source tool?"
- Alternatif: Kendin hunter ol (ama takipçisi olan biri daha iyi)

=== LAUNCH GÜNÜ ===
[ ] 00:01 UTC'de yayınla
[ ] Twitter'dan duyur
[ ] Her yoruma ilk 2 saat cevap ver
[ ] LinkedIn'den paylaş
[ ] Hacker News'e "Show HN" dene (hala kapalıysa bekle)
[ ] Dev.to'dan launch yazısı yayınla
[ ] Reddit r/SideProject'e (karma yetince)

=== SONRA ===
[ ] Gün sonu analytics kontrolü
[ ] En çok hangi feature ilgi gördü not al
[ ] Issue'lara bak
[ ] Feedback topla
