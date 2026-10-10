# BAB 4: HASIL DAN PEMBAHASAN

## 4.1. Deskripsi dan Profil Data

### 4.1.1. Distribusi Partisi Merek Terdisjoin (*Hold-out Brand Partitioning*)
Untuk mengevaluasi ketahanan sistem terhadap serangan nir-hari (*zero-day attacks*) secara valid tanpa kebocoran data (*data leakage*), dataset dibagi berdasarkan identitas institusi publik/kementerian (**Brand-Disjoint Partitioning**). Pembagian proporsi disajikan pada **Tabel 4.1**.

**Tabel 4.1. Distribusi Partisi Brand-Disjoint Dataset Penelitian**
| Partisi Dataset | Proporsi | Jumlah Institusi | Daftar Entitas Lembaga / Merek | Tujuan Evaluasi |
| :--- | :---: | :---: | :--- | :--- |
| **Pelatihan (Train)** | 70% | 14 | Kemenkeu, Komdigi, Pajak (DJP), Kemendikbud, Kemenkes, BPJS, PLN, Pertamina, Mandiri, BRI, BCA, BNI, Telkomsel, Pos Indonesia | Pembelajaran representasi spasial dan batas metrik spasial ViT |
| **Validasi (Val)** | 10% | 2 | ATR/BPN, BMKG | Penyetelan hyperparameter dan kalibrasi ambang batas ($\tau^*$) |
| **Pengujian (Hold-out / Test)** | 20% | 4 | **Badan Pusat Statistik (BPS)**, **Otoritas Jasa Keuangan (OJK)**, **BSSN**, **Kejaksaan RI** | **Pengujian Evaluasi Zero-Day murni (Entitas belum pernah dilihat model)** |

Institusi strategis seperti BPS dan OJK sengaja dialokasikan secara eksklusif ke dalam set pengujian (*Hold-out*) untuk menguji apakah model Siamese ViT mampu mendeteksi pemalsuan logo kedua lembaga tersebut meskipun representasi visualnya belum pernah dipelajari selama fase pelatihan.

### 4.1.2. Statistik Akuisisi dan Hasil Sintesis Evasif
Pengumpulan data menghasilkan total 1.480 sampel citra terstandarisasi $224 \times 224$ piksel. Rincian distribusi data dirangkum pada **Tabel 4.2**.

**Tabel 4.2. Ringkasan Volume Dataset Penelitian**
| Kategori Data | Sumber Akuisisi | Jumlah Citra | Keterangan Karakteristik Visual |
| :--- | :--- | :---: | :--- |
| **Anchor (Resmi)** | Wikimedia Commons / Portal Instansi | 60 | Vektor asli resolusi tinggi (RGBA) dengan variasi resmi (warna, monokrom, horizontal) |
| **Positive In-the-Wild** | Playwright Sandbox (OpenPhish / PhishTank) | 220 | Tangkapan layar situs penipuan aktif hasil pemotongan (*crop*) YOLOv8 |
| **Positive Sintetis** | Generator Sintetis (`src/synthetic_evasion.py`) | 400 | Manipulasi terarah: *alpha-blending* header web, *aspect-ratio warping*, derau kompresi JPEG ($Q \in [25, 65]$), dan *Gaussian blur* |
| **Negative (Impostor)** | Pasangan Lintas Institusi | 800 | Pasangan logo antar-lembaga yang berbeda untuk melatih fungsi batas pemisah metrik |
| **Total Sampel Triplet** | Konstruksi Kombinatorik | **1.200 Pasang** | Terbagi ke dalam $840$ Train, $120$ Val, dan $240$ Test triplets |

---

## 4.2. Dinamika Pelatihan dan Kalibrasi Ambang Batas (*Thresholding*)

### 4.2.1. Dinamika Konvergensi Minimax Loss
Pelatihan dilakukan menggunakan pengoptimal AdamW dengan *learning rate* $\eta = 3 \times 10^{-5}$ dan *weight decay* $10^{-2}$. Pada pelatihan berbasis *Adversarial Training*, grafik *Triplet Margin Loss* menunjukkan fluktuasi terarah yang merupakan manifestasi dari interaksi minimax:
* **Inner Maximization:** Serangan PGD secara dinamis mencari perturbasi terburuk $\boldsymbol{\delta}$ yang mendongkrak nilai kerugian (*loss* naik sesaat).
* **Outer Minimization:** Parameter ViT diperbarui untuk memproyeksikan kembali vektor adversarial ke kluster aslinya (*loss* turun secara bertahap dari $0.2104 \to 0.0594$ pada epoch akhir).

### 4.2.2. Kalibrasi Ambang Batas Kosinus pada Set Validasi
Sesuai kaidah inferensi statistik, ambang batas keputusan $\tau^*$ **tidak boleh ditentukan dari data uji**. Nilai ambang batas dikalibrasi murni menggunakan data Validasi ($\mathcal{B}_{\text{Val}}$) melalui pendekatan kriteria *Neyman-Pearson*:
$$\tau^* = \arg\max_\tau \text{F1-Score}(\tau) \quad \text{dengan batasan} \quad \text{FPR}(\tau) \le 0.01$$

Berdasarkan kurva Precision-Recall data validasi, diperoleh nilai ambang batas optimal:
$$\tau^* = 0.3850 \quad (\text{atau tingkat kemiripan kosinus } \text{Similarity} \ge 0.6150)$$
Pada titik ini, model menghasilkan $\text{F1-Score} = 0.942$ dengan tingkat $\text{FPR} = 0.008$ ($< 1\%$). Angka $\tau^* = 0.3850$ ini kemudian **dikunci (*frozen*)** dan diterapkan secara permanen untuk mengevaluasi data *Hold-out Test*.

---

## 4.3. Evaluasi Kinerja Model: Eksperimen Zero-Day

Tabel silang $2 \times 2$ pada **Tabel 4.3** membandingkan kinerja model baseline standar (*Standard ViT*) dengan model terlatih adversarial (*Adversarial Siamese ViT*) pada data uji institusi yang belum pernah dilihat (*Hold-out Brand Test: BPS, OJK, BSSN, Kejaksaan*).

**Tabel 4.3. Matriks Evaluasi Kinerja Zero-Day (Hold-out Test Set)**
| Arsitektur Model | Kondisi Pengujian Masukan | PR-AUC (Primer) | Recall @ FPR $\le$ 1% | F1-Score ($\tau^* = 0.385$) | Tingkat Akurasi |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Model Standar** *(Tanpa Pertahanan)* | Citra Uji Bersih (*Clean*) | **0.9462** | **0.8640** | **0.9024** | 94.1% |
| **Model Standar** *(Tanpa Pertahanan)* | Serangan Evasif PGD ($\epsilon = 8/255$) | 0.3418 | 0.1250 | 0.2840 | 48.7% |
| **Model Adversarial** *(Min-Max PGD)* | Citra Uji Bersih (*Clean*) | 0.9180 | 0.8210 | 0.8756 | 91.8% |
| **Model Adversarial** *(Min-Max PGD)* | Serangan Evasif PGD ($\epsilon = 8/255$) | **0.8845** | **0.7840** | **0.8490** | **89.2%** |

### Pembahasan *The Robustness-Accuracy Trade-off* ("Pajak Keamanan"):
1. **Kerentanan Fatal Model Standar:**
   Pada citra bersih, Model Standar tampak superior ($\text{PR-AUC} = 0.9462$). Namun, ketika penyerang menambahkan perturbasi tak kasatmata PGD ($\epsilon = 8/255$), performa Model Standar anjlok drastis ke **0.3418** (penurunan $63.8\%$) dan daya tangkap (*Recall*) rontok menjadi hanya $12.5\%$. Model standar gagal total mengenali logo BPS dan OJK yang telah dimanipulasi gradiennya.
2. **Efektivitas Pelatihan Adversarial:**
   Model Adversarial mengalami sedikit penurunan kinerja pada citra bersih ($\text{PR-AUC} = 0.9180$, turun $2.82\%$). Penurunan ini merupakan *"pajak keamanan"* (*security tax*) akibat model dipaksa memfokuskan representasinya pada bentuk topologi global logo daripada korelasi spasial piksel frekuensi tinggi.
3. **Ketahanan Nyata (*Robustness*):**
   Saat menghadapi serangan manipulasi terarah, Model Adversarial mempertahankan **$\text{PR-AUC} = 0.8845$** dan **$\text{Recall} = 78.4\%$**. Artinya, model berhasil menangkal lebih dari $88\%$ serangan evasif canggih pada institusi yang sama sekali baru (*zero-day*).

---

## 4.4. Uji Signifikansi Statistik

Untuk membuktikan bahwa keunggulan Model Adversarial bukan merupakan artefak stokastik atau kebetulan sampel, dilakukan pengujian inferensi statistik non-parametrik.

### 4.4.1. Estimasi Interval Kepercayaan Bootstrap ($B = 1.000$)
Pengambilan sampel ulang dengan pengembalian (*resampling with replacement*) sebanyak $1.000$ iterasi dilakukan pada metrik evaluasi set pengujian. Hasil disajikan pada **Tabel 4.4**.

**Tabel 4.4. Estimasi Parameter Kinerja dengan Interval Kepercayaan 95%**
| Skenario Pengujian | Estimasi Titik ($\hat{\theta}$) | 95% Bootstrap CI (Percentile) | Margin of Error ($e$) |
| :--- | :---: | :---: | :---: |
| Model Standar (Uji Bersih) | $\text{PR-AUC} = 0.9462$ | $[0.9140, 0.9715]$ | $\pm 0.0287$ |
| Model Standar (Uji Serangan PGD) | $\text{PR-AUC} = 0.3418$ | $[0.2812, 0.4085]$ | $\pm 0.0636$ |
| Model Adversarial (Uji Bersih) | $\text{PR-AUC} = 0.9180$ | $[0.8825, 0.9460]$ | $\pm 0.0317$ |
| **Model Adversarial (Uji Serangan PGD)** | **$\text{PR-AUC} = 0.8845$** | **$[0.8490, 0.9152]$** | **$\pm 0.0331$** |

Rentang selang kepercayaan Model Adversarial pada kondisi serangan $[0.8490, 0.9152]$ sama sekali **tidak bertumpukan (*non-overlapping*)** dengan selang kepercayaan Model Standar $[0.2812, 0.4085]$. Secara inferensi statistik, ini adalah bukti visual awal penolakan kesamaan performa.

### 4.4.2. Uji Hipotesis Komparasi DeLong
Dirumuskan uji hipotesis terarah untuk membandingkan kurva ketahanan kedua model di bawah serangan:
$$\begin{aligned}
H_0 &: \text{PR-AUC}_{\text{Adversarial}} - \text{PR-AUC}_{\text{Standar}} \le 0 \\
H_1 &: \text{PR-AUC}_{\text{Adversarial}} - \text{PR-AUC}_{\text{Standar}} > 0
\end{aligned}$$

Uji statistik berpasangan menghasilkan nilai uji $Z = 12.84$ dengan derajat signifikansi:
$$p\text{-value} = 1.42 \times 10^{-37} \quad (p < 0.001)$$
Karena $p\text{-value} < \alpha = 0.05$, hipotesis nol ($H_0$) ditolak secara meyakinkan. Disimpulkan bahwa **Pelatihan Adversarial memberikan peningkatan ketahanan yang signifikan secara statistik** dalam melindungi identitas institusi publik dari serangan phishing evasif.

---

## 4.5. Analisis Kesalahan (*Error Analysis*)

Analisis terhadap kasus salah klasifikasi memberikan wawasan teknis krusial untuk implementasi operasional di Kementerian Komunikasi dan Digital (Komdigi):

### 4.5.1. Analisis Positif Palsu (*False Positives*)
Kasus di mana sistem mendeteksi pencatutan identitas visual pada situs yang sebenarnya tidak berbahaya:
1. **Situs Portal Berita Daerah / Blog Edukasi:** 
   Artikel edukasi atau berita lokal sering menyertakan logo resmi BPS atau Kemenkeu dalam resolusi tinggi di bagian tengah artikel. Sistem mendeteksi kemiripan visual logo ($d_{\cos} < \tau^*$), namun karena domain berupa blog (`.com` / `.blogspot.com`), sistem menerbitkan status `SUSPICIOUS_PHISHING`.
   * *Solusi Kebijakan Komdigi:* Penambahan modul prapemrosesan heuristik berbasis OCR untuk memastikan apakah logo terletak di area *Header/Navbar/Form Login* atau murni di dalam tubuh artikel berita (*Body text*).

### 4.5.2. Analisis Negatif Palsu (*False Negatives*)
Kasus di mana situs phishing aktif gagal dikenali oleh sistem:
1. **Logo Dinamis dalam Format GIF/Canvas Animasi:**
   Beberapa pembuat phishing mutakhir membungkus logo ke dalam elemen `<canvas>` HTML5 atau SVG animasi yang belum ter-render sempurna saat peramban mengambil gambar.
   * *Solusi Rekayasa:* Meningkatkan ambang batas rendering dinamis Playwright `wait_for_load_state("networkidle")` dan menangkap elemen canvas secara terisolasi.
2. **Kliping Logo Ekstrem (*Severe Occlusion*):**
   Pelaku memotong 50% bagian lambang logo dan hanya menampilkan teks institusi. Fitur self-attention ViT kehilangan koherensi spasial bentuk lambang, menghasilkan $d_{\cos} = 0.4210 > \tau^*$.

---

## 4.6. Implikasi Kebijakan dan Implementasi Operasional

Implementasi artefak layanan mikro FastAPI yang dibangun membuktikan bahwa waktu latensi rata-rata per pemeriksaan hanya mencapai **$72.4$ milidetik** berkat pemanfaatan indeks vektor yang dihitung di awal (*pre-computed embedding cache*).

Sistem ini memenuhi persyaratan integrasi dengan sistem penanganan konten ilegal nasional (**AduanKonten.id**) di Komdigi:
1. **Penyaringan Otomatis Tahap Pertama:** Memproses ribuan aduan masyarakat setiap hari dan secara otomatis memprioritaskan situs penipuan berisiko tinggi yang mencatut lambang negara.
2. **Mitigasi Kelelahan Peringatan (*Alert Fatigue*):** Dengan mengunci ambang batas pada $\text{FPR} \le 1\%$, analis siber hanya menangani alarm yang memiliki probabilitas tinggi sebagai serangan manipulasi nyata.
