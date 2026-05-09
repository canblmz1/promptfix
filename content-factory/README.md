=== CONTENT FACTORY WEB UI - TEK CUMLE OZET ===
Web arayuzlu icerik fabrikasi. ChatGPT kanal isimlerini belirler. Her gun otomatik video+ses+post uretir. Kullanici sadece "Upload" butonuna basar. YouTube Shorts icin telif korumasi var.

=== PROJE YAPISI ===

content-factory/
├── app.py                  # Flask/FastAPI ana sunucu
├── ui/                     # HTML/JS arayuz
│   ├── index.html          # Ana sayfa (platform sekmeleri)
│   ├── style.css
│   └── app.js
├── engine/
│   ├── namer.py            # ChatGPT ile kanal ismi belirleme
│   ├── trend.py            # Trend haber cekme
│   ├── llm.py              # OpenAI API ile icerik uretimi
│   ├── video.py            # Otomatik video montaj (MoviePy)
│   ├── voice.py            # TTS (Edge-TTS, bedava)
│   ├── thumb.py            # Thumbnail uretimi (Pillow)
│   └── telif.py            # YouTube Shorts telif kontrolu
├── queue/
│   ├── uploads.json        # Yukleme listesi (yapilanlar)
│   └── pending.json        # Bekleyenler
├── output/                 # Uretilen dosyalar
│   ├── videos/
│   ├── thumbs/
│   └── scripts/
└── config.yaml             # API key, kanal isimleri, ayarlar

=== TEKNOLOJI STACK ===

Backend:  Python + Flask (web sunucu)
Frontend: HTML + Vanilla JS (sekme sistemi)
Video:    MoviePy (gorsel+ses birlestirme, altyazi)
Ses:      Edge-TTS (Microsoft, bedava, kaliteli)
Gorsel:   Pillow (thumbnail), Bing Image Creator (bedava)
LLM:      OpenAI API (GPT-4o-mini, ucuz)
DB:       JSON dosyalari (basit, kurulum gerektirmez)

=== MASRAF (AYLIK) ===

OpenAI API (GPT-4o-mini): ~2-5$ (30 gunluk icerik)
Diger her sey:             0$ (Edge-TTS, MoviePy, Bing Image, hepsi bedava)
Toplam:                    ~5$/ay

=== CALISMA AKISI ===

1. KURULUM (Bir kere):
   - Kullanici web arayuze girer.
   - "Kanal Isimlerini Belirle" butonuna basar.
   - ChatGPT, kanal temasina gore isimler uretir:
       Instagram: @ai_breakdown_tr
       TikTok:    @aitoday_clip
       Twitter:   @AIPulseDaily
       YouTube:   AI Explained TR
   - Kullanici onaylar veya degistirir. config.yaml'a kaydeder.

2. GUNLUK URETIM (Otomatik):
   - Saat 08:00'de trend.py calisir, gunun AI konusunu bulur.
   - llm.py, master prompt ile tam icerik paketi uretir.
   - video.py, ses+goruntu+altyaziyi birlestirir.
   - thumb.py, thumbnail uretir.
   - Her platform icin optimize edilmis dosyalar cikar:
       output/videos/youtube_long.mp4
       output/videos/shorts.mp4
       output/scripts/twitter_thread.txt
       output/scripts/ig_caption.txt
   - pending.json'a eklenir.

3. KULLANICI ARAYUZU:
   - Web sayfasinda 4 sekme: YouTube | Shorts | Instagram | TikTok | Twitter
   - Her sekmede: "Bugunun Icerigi" preview + "Upload" butonu.
   - Upload yapinca: pending.json'dan uploads.json'a tasir.
   - "Gecmis" bolumunde: Yapilan uploadlar listesi + "Sil" butonu.
   - YouTube Shorts sekmesinde: "Telif Riski: Dusuk/Orta/Yuksek" gostergesi.

4. YOUTUBE SHORTS TELIF KORUMASI:
   - Ses: Edge-TTS kendi uretir, telif yok.
   - Goruntu: AI uretimi (Bing Image Creator) + basit animasyonlar.
   - Muzik: Telifsiz muzik kutuphanesi (youtube_audio_library).
   - video.py, her Shorts'un meta verisini kaydeder (kaynak gorseller, muzik dosyasi).
   - Eger harici video/clip eklenirse, telif.py uyari verir.

=== MASTER PROMPT (ENGINE/LLM.PY'YE GONDERILIR) ===

[master-prompt.txt dosyasina bak]

=== API KULLANIMI (ORNEK) ===

from engine.llm import ContentEngine
from engine.video import VideoFactory

engine = ContentEngine(api_key="sk-xxx")
topic = engine.find_trend()  # "OpenAI yeni model duyurdu"
pack = engine.generate(topic)  # Tam icerik paketi

factory = VideoFactory()
factory.create_youtube_long(pack['youtube_script'], "output/yt.mp4")
factory.create_shorts(pack['shorts_script'], "output/shorts.mp4")
factory.create_thumb(pack['title'], "output/thumb.jpg")

=== KANAL ISIMLENDIRME PROMPTU ===

Prompt (ChatGPT'ye):
"Ben teknoloji/AI icerigi ureten bir kanal kuruyorum. 
Platformlar: Instagram, TikTok, Twitter/X, YouTube.
Hedef kitle: 18-35 yas, teknolojiye merakli, mobil izleyici.
Dil: Turkce ve Ingilizce karisik (ana dil Turkce).
Her platform icin uygun, akilda kalici, 1-3 kelimelik kullanici adi ve kanal ismi uret.
Instagram: kullanici adi (@...)
TikTok: kullanici adi (@...)
Twitter: kullanici adi (@...)
YouTube: kanal ismi
Hepsi tutarli bir marka kimligi olmali. Ver."

=== KURULUM KOMUTU ===

git clone <repo>
cd content-factory
pip install -r requirements.txt
python app.py
# Tarayici: http://localhost:5000
