# PROJE GEREKSINIMLERI VE KURALLAR SISTEMI (rules.md)

## Proje Özeti
Bu proje, Android platformundaki "Seal" uygulamasina benzer mantikta çalisan, masaüstü (Windows) için hafif, performans odakli ve Python tabanli bir `yt-dlp` Grafik Kullanici Arayüzü (GUI) aracidir.

## 1. Mimari ve Temel Teknolojiler
* **Programlama Dili:** Python 3.x
* **GUI Kütüphanesi:** Tkinter veya CustomTkinter (Sistemi yormamak ve dis bagimliliklari minimumda tutmak için).
* **Core Motor:** Indirme islemleri için `yt_dlp` modülü, video ve ses dosyalarini birlestirmek (muxing) için ise sistem `FFmpeg` araci kullanilacaktir.
* **Asenkron Çalisma (Threading):** UI (Arayüz) donmalarini önlemek kesinlikle zorunludur. Tüm `yt-dlp` indirme süreçleri, Ana Thread'i (Main GUI Thread) mesgul etmemek adina **ayri bir Worker Thread (Isçi Is parçacigi)** üzerinden yürütülmelidir.

## 2. Kullanici Arayüzü (UI) Gereksinimleri
Arayüz karmasadan uzak, "Seal" uygulamasinin sadeliginde olmalidir. Asagidaki bilesenler eksiksiz eklenmelidir:
* **URL Giris Alani (Entry):** Indirilecek içerigin linkinin yapistirilacagi ana TextBox.
* **Hizli Format/Kalite Seçici (Dropdown/Radio):** Standart kullanicilar için hazir ayarlar. (Örn: `En Iyi Video+Ses (1080p)`, `Sadece Ses (MP3 320kbps)`, `Sadece Ses (M4A)`).
* **Gelismis Özel Komut Alani (Text Area):** Kullanicinin dogrudan `yt-dlp` bayraklarini (flags) yazabilecegi genis alan.
  * *Örnek kullanim:* `--download-section "*10:00-15:00" --embed-subs`
* **Kalicilik (Persistence) Modülü (Checkbox):** "Özel komutlari ve mevcut ayarlari hatirla" islevini gören bir onay kutusu.
* **Aksiyon Butonlari:** "Indirmeyi Baslat" ve "Komutu/Ayari Kaydet".
* **Canli Konsol/Log Ekrani:** Indirme hizini, tahmini süreyi, yüzdeyi ve hatalari kullaniciya anlik gösteren salt okunur (read-only) metin kutusu.

## 3. Davranis ve Islem Mantigi (Business Logic)

### 3.1. Komut Önceligi ve Ayristirma (Parsing)
* Kullanici "Özel Komut Alani"na bir girdi yaptiginda, bu girdiler `yt_dlp.YoutubeDL(ydl_opts)` içine dogru sözlük (dictionary) formatinda ayristirilarak (parse edilerek) aktarilmalidir.
* **Çakisma Önleme Kurallari:** Eger kullanici, Özel Komut alanina format belirten bir flag (`-f` veya `--format`) yazmissa, uygulamanin "Hizli Format Seçici" arayüzünden gelen standart format degeri **ezilmeli (override edilmeli)** ve tamamen kullanicinin yazdigi komut baz alinmalidir.

### 3.2. Durum Kaliciligi (State Persistence) ve Yapilandirma Dosyasi
* Uygulama, kullanicinin girdigi özel komutlarin her açilista kaybolmamasi için yerel bir **`config.json`** dosyasi olusturmali ve okumalidir.
* "Ayarlari Hatirla" Checkbox'i aktifken kullanici "Indir" veya "Kaydet" dediginde; girilen özel komut satiri, son seçilen kalite ayari ve kayit dizini bu JSON dosyasina yazilmalidir.
* Uygulama (exe) her baslatildiginda döngü su olmalidir: `config.json` var mi kontrol et -> Varsa oku ve UI elementlerini doldur (Özel komut alani dahil) -> Yoksa varsayilan ayarlarla baslat.

### 3.3. Hata Yönetimi ve Güvenlik (Error Handling)
* **FFmpeg Kontrolü:** Indirme tetiklendiginde sistem PATH degiskenlerinde veya projenin bulundugu dizinde FFmpeg'in var olup olmadigi kontrol edilmelidir. Yoksa islem durdurulup, anlasilir bir hata mesaji verilmelidir.
* Link alani bos birakildiginda uygulama çökmek yerine islemi red edip uyari göstermelidir.
* Ag baglantisi kopmasi veya kisitli bir video durumunda `yt-dlp`'nin firlatacagi exception'lar (hatalar) try-catch/try-except bloklariyla yakalanip GUI üzerindeki konsol alanina yansitilmalidir. Uygulama kesinlikle "Not Responding" (Yanit Vermiyor) durumuna düsmemelidir.