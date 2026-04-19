# ⚡ PHANTOM - The Self-Healing Media Station

![Python Version](https://img.shields.io/badge/python-3.8+-00FF41?style=for-the-badge&logo=python)
![Platform Support](https://img.shields.io/badge/platform-Windows%20|%20Linux-00FF41?style=for-the-badge)

**Phantom** is a high-performance, autonomous YouTube media downloader designed with a focus on reliability, portability, and premium user experience.

---

## 💎 Niyə Phantom? (Premium Features)

* **🛠️ Self-Healing Engine:** Proqram işə düşəndə FFmpeg mühərrikini yoxlayır. Əgər yoxdursa, sisteminizin **Build Version**-nu (məs: LTSC 2016 Build 14393) analiz edir və ən uyğun versiyanı avtomatik qurur.
* **✂️ Precision Clipping:** Bütün videonu yükləməyə ehtiyac yoxdur. Sadəcə vaxtı daxil edin, Phantom birbaşa o hissəni kəsib gətirir.
* **📂 Native Explorer Bridge:** Brauzer məhdudiyyətlərini aşaraq, qovluğu birbaşa Windows-un orijinal qovluq seçicisi (**File Explorer**) ilə seçmə imkanı.
* **🚀 Premium App-Mode UI:** Desktop tətbiqi hissi verən, tam ekran və sürətli Vanilla JS interfeysi.
* **⌨️ Intelligent Input Masking:** Vaxt daxil edərkən (məs: `01:30`) nöqtələri özü qoyur.

---

## 🧠 Texniki Analiz (Engineering Insight)

| Xüsusiyyət | Texnologiya | Səbəb |
| :--- | :--- | :--- |
| **Backend** | FastAPI / Uvicorn | Yüksək sürətli API rabitəsi. |
| **Engine** | yt-dlp | Ən yeni YouTube alqoritmlərinə uyğunluq. |
| **OS Detection** | `sys.getwindowsversion()` | Köhnə sistemlərdə DLL xətalarını önləmək. |

---

## 🚀 Quraşdırma (Quick Start)

1.  **Reponu klonlayın:**
    ```bash
    git clone [https://github.com/abulfatoff/phantom.git](https://github.com/abulfatoff/phantom.git)
    cd phantom
    ```

2.  **Kitabxanaları quraşdırın:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Zavodu işə salın:**
    ```bash
    python backend.py
    ```

---

## 📜 Lisenziya (License)
Bu proyekt **MIT License** altında qorunur.

---

### 👨‍💻 Developer
**Mirsaid Abulfatofov (Miri)** - *Technology Enthusiast & Digital Creator*
